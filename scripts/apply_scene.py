"""Aplica cenas declaradas em scenes/*.json no OBS — de forma ESTRITAMENTE IDEMPOTENTE.

Regras:
  * Cena inexistente -> cria. Existente -> reaproveita.
  * Input (fonte) inexistente -> CreateInput. Existente -> SetInputSettings (overlay=True, só as chaves do JSON).
    Nunca cria um segundo input com o mesmo nome; se o tipo (kind) divergir, aborta com erro.
  * Item de cena inexistente na cena -> CreateSceneItem. Existente -> reaproveita o mesmo sceneItemId.
  * Transform / enabled / locked / ordem (index) sempre reaplicados a partir do JSON.
  * Filtros: inexistente -> CreateSourceFilter; existente -> SetSourceFilterSettings + Enabled.
  * Itens que estão no OBS mas não no JSON são mantidos, a menos que se use --prune.
  Rodar N vezes produz exatamente o mesmo estado que rodar 1 vez.

Uso:
  python scripts/apply_scene.py scenes/lives/dota.json
  python scripts/apply_scene.py --all                 # todas as cenas em scenes/**
  python scripts/apply_scene.py scenes/lives/*.json --prune --switch
  python scripts/apply_scene.py scenes/lives/dota.json --dry-run
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import obs_common as oc  # noqa: E402

try:
    from obsws_python.error import OBSSDKRequestError
except ImportError:  # pragma: no cover
    OBSSDKRequestError = Exception  # type: ignore

RESOURCE_NOT_FOUND = 600


class Applier:
    def __init__(self, client, dry_run: bool = False):
        self.cl = client
        self.dry = dry_run
        self.inputs: dict[str, str] = {}  # nome -> kind (cache)
        self.done_inputs: set[str] = set()
        self.missing: dict[str, bool] = {}
        self._refresh_inputs()

    # ------------------------------------------------------------------ helpers
    def log(self, msg: str) -> None:
        print(("[dry-run] " if self.dry else "") + msg)

    def _refresh_inputs(self) -> None:
        resp = self.cl.get_input_list()
        self.inputs = {i["inputName"]: i["inputKind"] for i in resp.inputs}

    def scene_names(self) -> set[str]:
        return {s["sceneName"] for s in self.cl.get_scene_list().scenes}

    def scene_item_id(self, scene: str, source: str) -> int | None:
        try:
            return self.cl.get_scene_item_id(scene, source).scene_item_id
        except OBSSDKRequestError as exc:
            if oc.request_error_code(exc) == RESOURCE_NOT_FOUND:
                return None
            raise

    # ------------------------------------------------------------------ steps
    def ensure_scene(self, scene: str) -> None:
        if scene in self.scene_names():
            self.log(f"= cena '{scene}' já existe")
            return
        self.log(f"+ criando cena '{scene}'")
        if not self.dry:
            self.cl.create_scene(scene)

    def ensure_input_and_item(self, scene: str, item: dict, definition: dict) -> int | None:
        name = item["source"]
        kind = definition["kind"]
        settings, missing = oc.resolve_settings(definition["settings"])
        for m in missing:
            print(f"  ! '{name}': {m} — item ficará DESATIVADO até isso ser resolvido")
        self.missing[name] = bool(missing)

        existing_kind = self.inputs.get(name)
        if existing_kind is None:
            # Input novo: CreateInput já cria o item na cena.
            self.log(f"  + criando input '{name}' ({kind}) na cena")
            if self.dry:
                return None
            resp = self.cl.create_input(scene, name, kind, settings, bool(item.get("enabled", True)) and not missing)
            self.inputs[name] = kind
            self.done_inputs.add(name)
            return resp.scene_item_id

        if existing_kind != kind:
            raise SystemExit(
                f"[ERRO] Já existe uma fonte '{name}' do tipo '{existing_kind}', mas o JSON pede '{kind}'. "
                "Renomeie/remova a fonte no OBS ou corrija o JSON (nada foi duplicado)."
            )

        if name not in self.done_inputs:  # settings/filtros são globais: aplica 1x por execução
            if settings:
                self.log(f"  ~ atualizando settings de '{name}'")
                if not self.dry:
                    self.cl.set_input_settings(name, settings, True)
            self.done_inputs.add(name)

        item_id = self.scene_item_id(scene, name)
        if item_id is None:
            self.log(f"  + adicionando '{name}' (existente) à cena")
            if self.dry:
                return None
            item_id = self.cl.create_scene_item(scene, name, bool(item.get("enabled", True))).scene_item_id
        else:
            self.log(f"  = '{name}' já está na cena (id {item_id})")
        return item_id

    def ensure_filters(self, source: str, filters: list[dict]) -> None:
        if not filters:
            return
        try:
            current = {f["filterName"]: f for f in self.cl.get_source_filter_list(source).filters}
        except OBSSDKRequestError:
            current = {}
        for f in filters:
            fname, fkind = f["name"], f["kind"]
            settings, _ = oc.resolve_settings(f.get("settings", {}))
            enabled = bool(f.get("enabled", True))
            if fname in current:
                if current[fname]["filterKind"] != fkind:
                    raise SystemExit(f"[ERRO] Filtro '{fname}' em '{source}' tem tipo diferente no OBS.")
                self.log(f"    ~ filtro '{fname}'")
                if not self.dry:
                    if settings:
                        self.cl.set_source_filter_settings(source, fname, settings, True)
                    self.cl.set_source_filter_enabled(source, fname, enabled)
            else:
                self.log(f"    + filtro '{fname}' ({fkind})")
                if not self.dry:
                    self.cl.create_source_filter(source, fname, fkind, settings)
                    if not enabled:
                        self.cl.set_source_filter_enabled(source, fname, False)

    def apply(self, data: dict, catalog: dict, prune: bool) -> None:
        scene = data["scene"]
        print(f"\n=== {scene} ===")
        self.ensure_scene(scene)

        ids: list[tuple[str, int | None]] = []
        filtered_this_run: set[str] = getattr(self, "_filtered", set())
        for item in data["items"]:
            name = item["source"]
            if not oc.check_name(name):
                print(f"  ! '{name}' fora do padrão de nomenclatura (ver CLAUDE.md)")
            definition = oc.input_definition(item, catalog)
            item_id = self.ensure_input_and_item(scene, item, definition)
            if name not in filtered_this_run:
                self.ensure_filters(name, definition["filters"])
                filtered_this_run.add(name)
            ids.append((name, item_id))

            if item_id is None or self.dry:
                continue
            transform = item.get("transform")
            if transform:
                self.cl.set_scene_item_transform(scene, item_id, oc.transform_for_apply(transform))
            enabled = bool(item.get("enabled", True)) and not self.missing.get(name, False)
            self.cl.set_scene_item_enabled(scene, item_id, enabled)
            self.cl.set_scene_item_locked(scene, item_id, bool(item.get("locked", False)))
        self._filtered = filtered_this_run

        # Ordem: primeiro item do JSON = fundo (index 0).
        if not self.dry:
            for index, (_, item_id) in enumerate(ids):
                if item_id is not None:
                    self.cl.set_scene_item_index(scene, item_id, index)

        if prune and not self.dry:
            wanted = {n for n, _ in ids}
            for it in self.cl.get_scene_item_list(scene).scene_items:
                if it["sourceName"] not in wanted:
                    self.log(f"  - removendo item '{it['sourceName']}' (--prune; o input continua existindo)")
                    self.cl.remove_scene_item(scene, it["sceneItemId"])


def check_consistency(files: list[Path], catalog: dict) -> None:
    """Inputs são globais no OBS: a mesma fonte não pode ter definições diferentes entre cenas."""
    seen: dict[str, tuple[Path, str]] = {}
    for path in files:
        for item in oc.load_json(path)["items"]:
            d = json.dumps(oc.input_definition(item, catalog), sort_keys=True)
            prev = seen.get(item["source"])
            if prev and prev[1] != d:
                raise SystemExit(
                    f"[ERRO] '{item['source']}' definida de forma diferente em {prev[0].name} e {path.name}. "
                    "Inputs são globais no OBS — mova a definição para scenes/sources.json."
                )
            seen[item["source"]] = (path, d)


def warn_global_audio(cl, files: list[Path], catalog: dict) -> None:
    """Avisa se uma cena inclui uma fonte que também é Áudio Global do OBS (o som sairia duplicado)."""
    try:
        special = cl.get_special_inputs()
    except Exception:
        return
    slots = ("desktop1", "desktop2", "mic1", "mic2", "mic3", "mic4")
    globals_ = {n for n in (getattr(special, k, None) for k in slots) if n}
    clash = {item["source"] for path in files for item in oc.load_json(path)["items"]} & globals_
    if clash:
        print(f"  ! {', '.join(sorted(clash))} é Áudio Global e também está em cena: o som pode duplicar. "
              "Desative-o em Configurações > Áudio > Áudio global.")


def main() -> None:
    ap = argparse.ArgumentParser(description="Aplica cenas JSON no OBS de forma idempotente.")
    ap.add_argument("files", nargs="*", type=Path, help="Arquivos de cena (scenes/**/*.json)")
    ap.add_argument("--all", action="store_true", help="Aplica todas as cenas de scenes/")
    ap.add_argument("--prune", action="store_true", help="Remove da cena itens que não estão no JSON")
    ap.add_argument("--switch", action="store_true", help="Coloca a (última) cena aplicada no Programa")
    ap.add_argument("--dry-run", action="store_true", help="Só mostra o que seria feito")
    args = ap.parse_args()

    files = list(args.files)
    if args.all:
        files = sorted(p for p in oc.SCENES_DIR.rglob("*.json") if p.name != "sources.json")
    if not files:
        ap.error("informe arquivos de cena ou --all")

    catalog = oc.load_catalog()
    check_consistency(files, catalog)

    cl = oc.connect()
    warn_global_audio(cl, files, catalog)
    applier = Applier(cl, dry_run=args.dry_run)
    last = None
    for path in files:
        data = oc.load_json(path)
        applier.apply(data, catalog, prune=args.prune)
        last = data["scene"]

    # Inputs do catálogo que não estão em nenhuma cena mas existem no OBS (ex.: Áudio Global
    # renomeado para Mic_Main/Desktop_Audio): aplica settings e filtros declarados.
    applier._refresh_inputs()
    done = getattr(applier, "_filtered", set())
    for name, definition in catalog.items():
        if name in done or name not in applier.inputs:
            continue
        if applier.inputs[name] != definition.get("kind"):
            print(f"  ! '{name}' existe com tipo diferente do catálogo — ignorado")
            continue
        print(f"\n=== input global '{name}' ===")
        settings, _ = oc.resolve_settings(definition.get("settings", {}))
        if settings and not args.dry_run:
            cl.set_input_settings(name, settings, True)
        applier.ensure_filters(name, definition.get("filters", []))

    if args.switch and last and not args.dry_run:
        cl.set_current_program_scene(last)
        print(f"\n>> Programa: '{last}'")
    print("\nOK — estado aplicado.")


if __name__ == "__main__":
    main()
