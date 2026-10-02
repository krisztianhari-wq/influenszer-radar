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


def load_env() -> list[str]:
    """.env betöltése (KEY=VALUE sorok) a felhasználói adatmappából és a repo gyökeréből; a már beállított változót nem írja felül."""
    loaded = []
    for f in (data_dir() / ".env", resources() / ".env", Path.cwd() / ".env"):
        if not f.is_file():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
                loaded.append(k)
    return loaded
