"""Valida a conexão com o OBS WebSocket v5 e lista as cenas atuais.

Uso:
  python scripts/test_connection.py            # versão, cenas e fontes
  python scripts/test_connection.py --devices  # também lista microfones/webcams disponíveis (IDs p/ o .env)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import obs_common as oc  # noqa: E402


DEVICE_PROPS = {"wasapi_input_capture": "device_id", "wasapi_output_capture": "device_id", "dshow_input": "video_device_id"}


def list_devices(cl, inputs: list[dict]) -> None:
    """Lista dispositivos usando a primeira fonte existente de cada tipo."""
    seen = set()
    for i in inputs:
        kind = i["inputKind"]
        if kind not in DEVICE_PROPS or kind in seen:
            continue
        seen.add(kind)
        print(f"\nDispositivos [{kind}] (via '{i['inputName']}'):")
        for it in cl.get_input_properties_list_property_items(i["inputName"], DEVICE_PROPS[kind]).property_items:
            print(f"  - {it['itemName']}\n      {it['itemValue']}")


def main() -> None:
    cl = oc.connect()
    v = cl.get_version()
    print(f"[OK] Conectado — OBS {v.obs_version} | WebSocket {v.obs_web_socket_version} | {v.platform_description}")

    scenes = cl.get_scene_list()
    print(f"\nCenas ({len(scenes.scenes)}) — programa atual: '{scenes.current_program_scene_name}'")
    # A API devolve de baixo para cima; invertemos para bater com a lista do OBS.
    for s in reversed(scenes.scenes):
        mark = "▶" if s["sceneName"] == scenes.current_program_scene_name else " "
        print(f"  {mark} {s['sceneName']}")

    inputs = cl.get_input_list().inputs
    print(f"\nFontes/inputs ({len(inputs)}):")
    for i in sorted(inputs, key=lambda x: x["inputName"].lower()):
        flag = "" if oc.check_name(i["inputName"]) else "   (fora do padrão de nomes)"
        print(f"  - {i['inputName']}  [{i['inputKind']}]{flag}")

    if "--devices" in sys.argv:
        list_devices(cl, inputs)


if __name__ == "__main__":
    main()
