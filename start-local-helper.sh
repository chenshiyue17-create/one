#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x ".venv/bin/python" ]]; then
    PYTHON_BIN=".venv/bin/python"
  elif [[ -x "$HOME/miniconda/envs/xhs/bin/python" ]]; then
    PYTHON_BIN="$HOME/miniconda/envs/xhs/bin/python"
  else
    PYTHON_BIN="python3"
  fi
fi

exec "$PYTHON_BIN" -m uvicorn backend.app.local_helper:app --host 127.0.0.1 --port 8765 --log-level info
