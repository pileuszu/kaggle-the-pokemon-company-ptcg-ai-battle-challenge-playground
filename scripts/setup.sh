#!/bin/sh
set -eu

ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
PYTHON=${PYTHON:-python3.11}
VENV="$ROOT/.venv-kaggle"

if [ ! -x "$VENV/bin/python" ]; then
  "$PYTHON" -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11 이상이 필요합니다."'
  "$PYTHON" -m venv "$VENV"
fi
"$VENV/bin/python" -c 'import sys; assert sys.version_info >= (3, 11), "Python 3.11 이상이 필요합니다."'
"$VENV/bin/python" -m pip install -r "$ROOT/requirements.txt"
"$VENV/bin/python" "$ROOT/scripts/download_data.py"
