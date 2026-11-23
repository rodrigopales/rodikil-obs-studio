"""Descobre o perfil e a coleção de cenas ATIVOS no OBS (para os scripts de setup não dependerem de nomes fixos).

O OBS grava em %APPDATA%/obs-studio/user.ini (OBS 31+) ou global.ini, seção [Basic]:
  ProfileDir=<pasta do perfil>        SceneCollectionFile=<arquivo da coleção, sem .json>
"""

from __future__ import annotations

import configparser
import os
from pathlib import Path

OBS_DIR = Path(os.environ.get("APPDATA", "")) / "obs-studio"


def _basic(key: str) -> str | None:
    for name in ("user.ini", "global.ini"):
        ini = OBS_DIR / name
        if not ini.exists():
            continue
        cp = configparser.ConfigParser(interpolation=None, strict=False)
        cp.optionxform = str
        try:
            cp.read_string(ini.read_text(encoding="utf-8-sig"))
        except (configparser.Error, UnicodeDecodeError):
            continue
        value = cp.get("Basic", key, fallback="").strip()
        if value:
            return value
    return None


def active_profile_dir() -> str:
    return _basic("ProfileDir") or _basic("Profile") or "Sem nome"


def active_collection_file() -> str:
    name = _basic("SceneCollectionFile") or _basic("SceneCollection") or "Sem nome"
    return name[:-5] if name.endswith(".json") else name
