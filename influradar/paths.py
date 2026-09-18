"""Útvonalak: csomagolt erőforrások (PyInstaller _MEIPASS vagy repo) és írható felhasználói adatmappa."""
from __future__ import annotations

import os
import sys
from pathlib import Path

APP = "InfluenszerRadar"


def resources() -> Path:
    base = getattr(sys, "_MEIPASS", None)
    return Path(base) if base else Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    env = os.environ.get("INFLURADAR_DATA")
    if env:
        p = Path(env).expanduser()
    elif getattr(sys, "frozen", False) or os.environ.get("INFLURADAR_USERDIR"):
        if sys.platform == "darwin":
            p = Path.home() / "Library" / "Application Support" / APP
        elif os.name == "nt":
            p = Path(os.environ.get("APPDATA", Path.home())) / APP
        else:
            p = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / APP
    else:
        p = resources() / "data"
    p.mkdir(parents=True, exist_ok=True)
    return p
