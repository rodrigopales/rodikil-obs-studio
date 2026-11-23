"""Exporta uma cena existente do OBS para um JSON limpo (formato de scenes/*.json).

Captura, para cada item: nome da fonte, tipo, settings (só as que diferem do padrão do tipo),
filtros, transform (posição, escala, bounds, crop), enabled e locked — na ordem fundo → topo.
Caminhos dentro do repositório viram ${PROJECT_ROOT}; IDs de dispositivo/janela são removidos
(use --keep-device para mantê-los).

Uso:
  python scripts/export_snapshot.py "Live - Dota 2"                       # imprime no terminal
  python scripts/export_snapshot.py "Live - Dota 2" -o scenes/lives/dota.json
  python scripts/export_snapshot.py --list                                # lista cenas
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import obs_common as oc  # noqa: E402


def non_default_settings(cl, kind: str, settings: dict, keep_device: bool) -> dict:
    try:
        defaults = cl.get_input_default_settings(kind).default_input_settings
    except Exception:
        defaults = {}
    out = {}
    for k, v in settings.items():
        if not keep_device and k in oc.DEVICE_SETTING_KEYS:
            continue
        if defaults.get(k) == v:
            continue
        out[k] = v
    return oc.unresolve_value(out)


def export_scene(cl, scene: str, keep_device: bool) -> dict:
    items_out = []
    items = sorted(cl.get_scene_item_list(scene).scene_items, key=lambda i: i["sceneItemIndex"])
    for it in items:
        name = it["sourceName"]
        kind = it.get("inputKind")
        entry: dict = {"source": name}
        if kind:
            settings = cl.get_input_settings(name).input_settings
            try:
                filters = cl.get_source_filter_list(name).filters
            except Exception:
                filters = []
            entry["input"] = {
                "kind": kind,
                "settings": non_default_settings(cl, kind, settings, keep_device),
            }
            if filters:
                entry["input"]["filters"] = [
                    {
                        "name": f["filterName"],
                        "kind": f["filterKind"],
                        "settings": oc.unresolve_value(f.get("filterSettings", {})),
                        **({} if f.get("filterEnabled", True) else {"enabled": False}),
                    }
                    for f in filters
                ]
        else:
            entry["$note"] = "item é uma cena/grupo aninhado — não suportado por apply_scene.py"
        if not it.get("sceneItemEnabled", True):
            entry["enabled"] = False
        if it.get("sceneItemLocked"):
            entry["locked"] = True
        entry["transform"] = oc.clean_transform(it["sceneItemTransform"])
        items_out.append(entry)

    video = cl.get_video_settings()
    return {"scene": scene, "canvas": [video.base_width, video.base_height], "items": items_out}


def main() -> None:
    ap = argparse.ArgumentParser(description="Exporta uma cena do OBS para JSON limpo.")
    ap.add_argument("scene", nargs="?", help="Nome exato da cena no OBS")
    ap.add_argument("-o", "--output", type=Path, help="Arquivo de saída (padrão: stdout)")
    ap.add_argument("--keep-device", action="store_true", help="Mantém IDs de dispositivo/janela")
    ap.add_argument("--list", action="store_true", help="Lista as cenas e sai")
    args = ap.parse_args()

    cl = oc.connect()
    names = [s["sceneName"] for s in reversed(cl.get_scene_list().scenes)]
    if args.list or not args.scene:
        print("\n".join(names))
        return
    if args.scene not in names:
        sys.exit(f"[ERRO] Cena '{args.scene}' não existe. Disponíveis: {', '.join(names)}")

    data = export_scene(cl, args.scene, args.keep_device)
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"[OK] '{args.scene}' exportada para {args.output}")
    else:
        sys.stdout.write(text)


if __name__ == "__main__":
    main()
