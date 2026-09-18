#!/bin/zsh
# Influenszer Radar indító: venv (ha kell), függőségek, GUI 127.0.0.1:8790-en
set -e
cd "$(dirname "$0")"
PY=${PYTHON:-/opt/homebrew/bin/python3.14}
[ -x "$PY" ] || PY=python3
if [ ! -d .venv ]; then "$PY" -m venv .venv; .venv/bin/pip install -q --upgrade pip; fi
.venv/bin/pip install -q -r requirements.txt
[ -f .env ] && set -a && source .env && set +a
exec .venv/bin/python -m influradar gui "$@"
