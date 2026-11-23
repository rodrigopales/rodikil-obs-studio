"""Utilitários compartilhados pelos scripts do rodikil-obs-studio.

- Conexão com o OBS WebSocket v5 (obsws-python ReqClient) usando .env
- Resolução de placeholders nos JSONs de cena:
    ${PROJECT_ROOT}      -> caminho absoluto da raiz do repositório (com barras "/")
    ${QUALQUER_VAR}      -> variável de ambiente / .env
    "@file:caminho"      -> conteúdo do arquivo (relativo à raiz), ex.: CSS customizado
- Normalização de transform (remove campos somente-leitura e valores padrão)
"""

from __future__ import annotations

import copy
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCENES_DIR = PROJECT_ROOT / "scenes"
SOURCES_CATALOG = SCENES_DIR / "sources.json"

_PLACEHOLDER = re.compile(r"\$\{([A-Z0-9_]+)\}")

# Campos de transform que o OBS devolve mas não aceita em SetSceneItemTransform.
READ_ONLY_TRANSFORM_KEYS = {"sourceWidth", "sourceHeight", "width", "height"}
CROP_KEYS = ("cropLeft", "cropRight", "cropTop", "cropBottom")

# Configurações específicas da máquina (IDs de dispositivo/janela). Ficam fora do Git.
DEVICE_SETTING_KEYS = {"video_device_id", "last_video_device_id", "device_id", "audio_device_id", "window", "monitor_id", "monitor"}


def project_root_posix() -> str:
    return PROJECT_ROOT.as_posix()


def load_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover
        sys.exit("python-dotenv não instalado. Rode: pip install -r requirements.txt")
    load_dotenv(PROJECT_ROOT / ".env")


def connect():
    """Abre um ReqClient com as credenciais do .env. Encerra com mensagem clara se falhar."""
    load_env()
    try:
        import obsws_python as obs
    except ImportError:  # pragma: no cover
        sys.exit("obsws-python não instalado. Rode: pip install -r requirements.txt")

    import logging
    logging.getLogger("obsws_python").setLevel(logging.CRITICAL)  # erros 600 são tratados pelos scripts

    host = os.getenv("OBS_HOST", "localhost")
    port = int(os.getenv("OBS_PORT", "4455"))
    password = os.getenv("OBS_PASSWORD", "")
    try:
        return obs.ReqClient(host=host, port=port, password=password, timeout=5)
    except Exception as exc:  # ConnectionRefusedError, auth, timeout...
        sys.exit(
            f"[ERRO] Não foi possível conectar ao OBS em {host}:{port} — {exc}\n"
            "Verifique: OBS aberto, Ferramentas > Configurações do servidor WebSocket habilitado, "
            "porta e senha iguais às do .env."
        )


def request_error_code(exc: Exception) -> int | None:
    """Extrai o código de status de um OBSSDKRequestError (ou None)."""
    return getattr(exc, "code", None)


# ---------------------------------------------------------------------------
# Placeholders
# ---------------------------------------------------------------------------

class MissingVariable(KeyError):
    pass


def resolve_value(value: Any) -> Any:
    """Resolve placeholders recursivamente. Levanta MissingVariable se faltar variável."""
    if isinstance(value, dict):
        return {k: resolve_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_value(v) for v in value]
    if not isinstance(value, str):
        return value

    if value.startswith("@file:"):
        path = PROJECT_ROOT / value[len("@file:"):]
        return path.read_text(encoding="utf-8")

    def repl(m: re.Match) -> str:
        name = m.group(1)
        if name == "PROJECT_ROOT":
            return project_root_posix()
        env = os.getenv(name)
        if env is None or env == "":
            raise MissingVariable(name)
        return env

    return _PLACEHOLDER.sub(repl, value)


def resolve_settings(settings: dict) -> tuple[dict, list[str]]:
    """Resolve cada chave de settings; chaves com variável ausente são OMITIDAS (não sobrescreve o OBS)."""
    out, missing = {}, []
    for key, val in settings.items():
        try:
            out[key] = resolve_value(val)
        except MissingVariable as exc:
            missing.append(f"{key} (precisa de ${{{exc.args[0]}}} no .env)")
    # Arquivo local apontado e inexistente: não envia (evita fonte quebrada) e marca como ausente.
    for key in ("local_file", "file"):
        path = out.get(key)
        if isinstance(path, str) and path and settings.get("is_local_file", True) and not Path(path).exists():
            out.pop(key)
            missing.append(f"{key} (arquivo não encontrado: {path})")
    return out, missing


def unresolve_value(value: Any) -> Any:
    """Inverso parcial: troca o caminho absoluto do projeto por ${PROJECT_ROOT} (para exportar)."""
    if isinstance(value, dict):
        return {k: unresolve_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [unresolve_value(v) for v in value]
    if isinstance(value, str):
        root = project_root_posix()
        norm = value.replace("\\", "/")
        idx = norm.lower().find(root.lower())  # Windows: caminhos não diferenciam maiúsculas
        if idx >= 0:
            return norm[:idx] + "${PROJECT_ROOT}" + norm[idx + len(root):]
    return value


# ---------------------------------------------------------------------------
# Transform
# ---------------------------------------------------------------------------

def clean_transform(t: dict) -> dict:
    """Remove campos somente-leitura e defaults para um JSON limpo e reaplicável."""
    t = {k: v for k, v in t.items() if k not in READ_ONLY_TRANSFORM_KEYS}
    for k in CROP_KEYS:
        if t.get(k) == 0:
            t.pop(k, None)
    if t.get("boundsType", "OBS_BOUNDS_NONE") == "OBS_BOUNDS_NONE":
        for k in ("boundsType", "boundsWidth", "boundsHeight", "boundsAlignment", "cropToBounds"):
            t.pop(k, None)
    if t.get("rotation") == 0:
        t.pop("rotation")
    for k, v in list(t.items()):
        if isinstance(v, float):
            t[k] = round(v, 4)
            if t[k] == int(t[k]):
                t[k] = int(t[k])
    return t


def transform_for_apply(t: dict) -> dict:
    """Prepara transform para SetSceneItemTransform (OBS rejeita bounds < 1)."""
    t = {k: v for k, v in t.items() if k not in READ_ONLY_TRANSFORM_KEYS}
    for k in ("boundsWidth", "boundsHeight"):
        if k in t and t[k] < 1:
            t.pop(k)
    return t


# ---------------------------------------------------------------------------
# Arquivos de cena
# ---------------------------------------------------------------------------

def load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def load_catalog() -> dict:
    if SOURCES_CATALOG.exists():
        return load_json(SOURCES_CATALOG).get("inputs", {})
    return {}


def deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in override.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def input_definition(item: dict, catalog: dict) -> dict:
    """Definição final do input: catálogo (scenes/sources.json) + override inline do item ("input")."""
    name = item["source"]
    base = catalog.get(name, {})
    inline = item.get("input", {})
    definition = deep_merge(base, inline) if inline else copy.deepcopy(base)
    if "kind" not in definition:
        raise ValueError(
            f"Fonte '{name}' sem definição: adicione-a em scenes/sources.json ou inclua \"input\": {{\"kind\": ...}} no item."
        )
    definition.setdefault("settings", {})
    definition.setdefault("filters", [])
    return definition


NAME_PATTERN = re.compile(r"^(Game_Capture(_[A-Z0-9][A-Za-z0-9]*)?|Display_Capture|Webcam_Main|Mic_Main|Desktop_Audio|Overlay_[A-Z][A-Za-z0-9]*)$")


def check_name(name: str) -> bool:
    return bool(NAME_PATTERN.match(name))
