"""Grava os atalhos de obs-config/hotkeys.json no script Rodikil dentro da coleção de cenas do OBS — IDEMPOTENTE.

Os atalhos ficam nas configurações do script obs-config/scripts/rodikil-intro.lua (módulo "scripts-tool" da
coleção de cenas). Se o script ainda não estiver adicionado no OBS, ele é adicionado aqui.
O OBS precisa estar FECHADO (ele regrava a coleção ao sair). Backup único: "<coleção>.json.antes-atalhos".

Uso:
  python scripts/setup_obs_hotkeys.py --dry-run
  python scripts/setup_obs_hotkeys.py
  python scripts/setup_obs_hotkeys.py --collection "Sem nome"
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import obs_paths  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
MAP_FILE = ROOT / "obs-config" / "hotkeys.json"
SCRIPT = (ROOT / "obs-config" / "scripts" / "rodikil-intro.lua").as_posix()
SCENES_DIR = Path(os.environ.get("APPDATA", "")) / "obs-studio" / "basic" / "scenes"
MODIFIERS = {"ctrl": "control", "control": "control", "alt": "alt", "shift": "shift", "win": "command"}


def obs_running() -> bool:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq obs64.exe"], capture_output=True, text=True).stdout
    return "obs64.exe" in out


def parse_combo(text: str) -> dict:
    """'Ctrl+Alt+1' -> {"control": true, "alt": true, "key": "OBS_KEY_1"}"""
    parts = [p.strip() for p in text.split("+") if p.strip()]
    binding: dict = {}
    for p in parts[:-1]:
        mod = MODIFIERS.get(p.lower())
        if not mod:
            raise SystemExit(f"[ERRO] Modificador desconhecido '{p}' em '{text}' (use Ctrl, Alt, Shift, Win).")
        binding[mod] = True
    key = parts[-1].upper()
    binding["key"] = key if key.startswith("OBS_KEY_") else f"OBS_KEY_{key}"
    return binding


def main() -> None:
    ap = argparse.ArgumentParser(description="Aplica obs-config/hotkeys.json no OBS (idempotente).")
    ap.add_argument("--collection", default=None, help="Coleção de cenas (padrão: a ativa no OBS)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    args.collection = args.collection or obs_paths.active_collection_file()
    target = SCENES_DIR / f"{args.collection}.json"
    print(f"Coleção: {args.collection}")
    if not target.exists():
        found = ", ".join(p.stem for p in SCENES_DIR.glob("*.json")) or "nenhuma"
        sys.exit(f"[ERRO] Coleção '{args.collection}' não existe em {SCENES_DIR}. Encontradas: {found}.")
    if obs_running() and not args.dry_run:
        sys.exit("[ERRO] Feche o OBS antes (ele regrava a coleção ao sair e desfaria os atalhos).")

    wanted = {
        k: [parse_combo(c) for c in (v if isinstance(v, list) else [v])]
        for k, v in json.loads(MAP_FILE.read_text(encoding="utf-8")).items() if not k.startswith("$")
    }

    raw = target.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    data = json.loads(raw.decode("utf-8-sig"))
    scripts = data.setdefault("modules", {}).setdefault("scripts-tool", [])
    entry = next((s for s in scripts if Path(s.get("path", "")).name == "rodikil-intro.lua"), None)
    changes: list[str] = []
    if entry is None:
        entry = {"path": SCRIPT, "settings": {}}
        scripts.append(entry)
        changes.append(f"+ script adicionado: {SCRIPT}")
    elif entry["path"] != SCRIPT:
        changes.append(f"~ caminho do script: {entry['path']} -> {SCRIPT}")
        entry["path"] = SCRIPT
    settings = entry.setdefault("settings", {})
    for hk_id, binding in wanted.items():
        if settings.get(hk_id) != binding:
            changes.append(f"~ {hk_id}: {json.dumps(binding)}")
            settings[hk_id] = binding

    for c in changes:
        print("  " + c)
    if changes and not args.dry_run:
        bak = target.with_name(target.name + ".antes-atalhos")
        if not bak.exists():
            shutil.copy2(target, bak)
        text = json.dumps(data, ensure_ascii=False, indent=4)
        target.write_bytes((b"\xef\xbb\xbf" if bom else b"") + text.encode("utf-8"))
    prefix = "[dry-run] " if args.dry_run else ""
    print(f"\n{prefix}{'Nada a mudar — atalhos já estão no padrão.' if not changes else f'{len(changes)} mudança(s).'}")


if __name__ == "__main__":
    main()
