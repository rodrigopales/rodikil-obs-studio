"""Aplica a configuração de referência (obs-config/profile/) num perfil do OBS — de forma IDEMPOTENTE.

O WebSocket não altera o encoder da Saída Avançada, então isto mexe direto nos arquivos do perfil:
  * basic.ini          -> MESCLA só as chaves de obs-config/profile/basic.ini (o resto do arquivo fica intacto)
  * streamEncoder.json -> copiado
  * recordEncoder.json -> copiado
Nunca toca em service.json (chave de transmissão). Faz backup (*.antes-setup) só quando algo muda.
O OBS precisa estar FECHADO (senão ele sobrescreve tudo ao sair).

Uso:
  python scripts/setup_obs_profile.py --dry-run
  python scripts/setup_obs_profile.py                      # perfil ativo no OBS
  python scripts/setup_obs_profile.py --profile "Meu perfil"
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import obs_paths  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "obs-config" / "profile"
PROFILES = Path(os.environ.get("APPDATA", "")) / "obs-studio" / "basic" / "profiles"
COPY_FILES = ("streamEncoder.json", "recordEncoder.json")


def obs_running() -> bool:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq obs64.exe"], capture_output=True, text=True).stdout
    return "obs64.exe" in out


def parse_reference(path: Path) -> dict[str, dict[str, str]]:
    data: dict[str, dict[str, str]] = {}
    section = None
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("[") and line.endswith("]"):
            section = line[1:-1]
            data.setdefault(section, {})
        elif "=" in line and section:
            k, v = line.split("=", 1)
            data[section][k] = v
    return data


def merge_ini(text: str, ref: dict[str, dict[str, str]]) -> tuple[str, list[str]]:
    """Troca/insere chaves preservando ordem, comentários e chaves não citadas. Devolve (texto, mudanças)."""
    lines = text.splitlines()
    changes: list[str] = []
    for section, keys in ref.items():
        header = f"[{section}]"
        try:
            start = next(i for i, l in enumerate(lines) if l.strip() == header)
        except StopIteration:
            if lines and lines[-1].strip():
                lines.append("")
            lines.append(header)
            lines.extend(f"{k}={v}" for k, v in keys.items())
            changes.extend(f"+ [{section}] {k}={v}" for k, v in keys.items())
            continue
        end = next((i for i in range(start + 1, len(lines)) if lines[i].strip().startswith("[")), len(lines))
        for k, v in keys.items():
            idx = next((i for i in range(start + 1, end) if lines[i].split("=", 1)[0].strip() == k), None)
            if idx is None:
                # insere após a última linha não vazia da seção
                pos = end
                while pos - 1 > start and not lines[pos - 1].strip():
                    pos -= 1
                lines.insert(pos, f"{k}={v}")
                end += 1
                changes.append(f"+ [{section}] {k}={v}")
            elif lines[idx].split("=", 1)[1] != v:
                changes.append(f"~ [{section}] {k}: {lines[idx].split('=', 1)[1]} -> {v}")
                lines[idx] = f"{k}={v}"
    return "\n".join(lines) + "\n", changes


def backup(path: Path) -> None:
    bak = path.with_name(path.name + ".antes-setup")
    if path.exists() and not bak.exists():
        shutil.copy2(path, bak)


def main() -> None:
    ap = argparse.ArgumentParser(description="Aplica obs-config/profile/ num perfil do OBS (idempotente).")
    ap.add_argument("--profile", default=None, help="Pasta do perfil (padrão: o perfil ativo no OBS)")
    ap.add_argument("--dry-run", action="store_true", help="Só mostra o que mudaria")
    args = ap.parse_args()

    args.profile = args.profile or obs_paths.active_profile_dir()
    target = PROFILES / args.profile
    print(f"Perfil: {args.profile}")
    if not target.is_dir():
        found = ", ".join(p.name for p in PROFILES.glob("*") if p.is_dir()) or "nenhum"
        sys.exit(f"[ERRO] Perfil '{args.profile}' não existe em {PROFILES}. Encontrados: {found}.\n"
                 "Abra o OBS uma vez (ele cria o perfil) e rode de novo, ou use --profile.")
    if obs_running() and not args.dry_run:
        sys.exit("[ERRO] Feche o OBS antes (ele regrava o perfil ao sair e desfaria as mudanças).")

    total = 0
    ini = target / "basic.ini"
    raw = ini.read_bytes() if ini.exists() else b""
    has_bom = raw.startswith(b"\xef\xbb\xbf")
    merged, changes = merge_ini(raw.decode("utf-8-sig"), parse_reference(SRC / "basic.ini"))
    for c in changes:
        print(f"  basic.ini {c}")
    if changes and not args.dry_run:
        backup(ini)
        ini.write_bytes((b"\xef\xbb\xbf" if has_bom or not raw else b"") + merged.encode("utf-8"))
    total += len(changes)

    for name in COPY_FILES:
        src, dst = SRC / name, target / name
        new = src.read_text(encoding="utf-8").strip()
        old = dst.read_text(encoding="utf-8").strip() if dst.exists() else None
        if new != old:
            print(f"  {name}: {'atualizado' if old is not None else 'criado'}")
            total += 1
            if not args.dry_run:
                backup(dst)
                dst.write_text(new, encoding="utf-8")

    prefix = "[dry-run] " if args.dry_run else ""
    print(f"\n{prefix}{'Nada a mudar — perfil já está no padrão.' if total == 0 else f'{total} mudança(s).'}")


if __name__ == "__main__":
    main()
