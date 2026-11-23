"""Desativa o Áudio Global (desktop e microfones) na coleção de cenas do OBS — IDEMPOTENTE.

Neste projeto o som do PC (Desktop_Audio) e o microfone (Mic_Main) são FONTES DE CENA, só onde devem tocar
(lives, Resenha, gravações). Áudio Global tocaria em TODAS as cenas (vazando no Iniciando/Intervalo/Encerrando)
e o OBS não deixa colocar uma fonte global dentro de cena (CreateSceneItem retorna 700).
Equivale a: Configurações › Áudio › Áudio do desktop / Microfone = Desativado.

O OBS precisa estar FECHADO. Backup único: "<coleção>.json.antes-audio-global".
Depois abra o OBS e rode: python scripts/apply_scene.py --all

Uso:
  python scripts/setup_obs_global_audio.py --dry-run
  python scripts/setup_obs_global_audio.py
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

SCENES_DIR = Path(os.environ.get("APPDATA", "")) / "obs-studio" / "basic" / "scenes"
GLOBAL_KEYS = ("DesktopAudioDevice1", "DesktopAudioDevice2",
               "AuxAudioDevice1", "AuxAudioDevice2", "AuxAudioDevice3", "AuxAudioDevice4")


def obs_running() -> bool:
    out = subprocess.run(["tasklist", "/FI", "IMAGENAME eq obs64.exe"], capture_output=True, text=True).stdout
    return "obs64.exe" in out


def main() -> None:
    ap = argparse.ArgumentParser(description="Desativa o Áudio Global na coleção do OBS (idempotente).")
    ap.add_argument("--collection", default=None, help="Coleção de cenas (padrão: a ativa no OBS)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    args.collection = args.collection or obs_paths.active_collection_file()
    target = SCENES_DIR / f"{args.collection}.json"
    print(f"Coleção: {args.collection}")
    if not target.exists():
        sys.exit(f"[ERRO] Coleção '{args.collection}' não existe em {SCENES_DIR}.")
    if obs_running() and not args.dry_run:
        sys.exit("[ERRO] Feche o OBS antes (ele regrava a coleção ao sair).")

    raw = target.read_bytes()
    bom = raw.startswith(b"\xef\xbb\xbf")
    data = json.loads(raw.decode("utf-8-sig"))
    found = [k for k in GLOBAL_KEYS if k in data]
    for k in found:
        print(f"  - Áudio Global {k}: '{data[k].get('name')}' ({data[k].get('id')}) será desativado")
    if found and not args.dry_run:
        bak = target.with_name(target.name + ".antes-audio-global")
        if not bak.exists():
            shutil.copy2(target, bak)
        for k in found:
            del data[k]
        target.write_bytes((b"\xef\xbb\xbf" if bom else b"") + json.dumps(data, ensure_ascii=False, indent=4).encode("utf-8"))
    prefix = "[dry-run] " if args.dry_run else ""
    print(f"\n{prefix}{'Nenhum Áudio Global ativo — nada a mudar.' if not found else f'{len(found)} desativado(s).'}")


if __name__ == "__main__":
    main()
