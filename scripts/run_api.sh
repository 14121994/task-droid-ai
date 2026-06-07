#!/usr/bin/env bash
set -euo pipefail

API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8000}"
API_RELOAD="${API_RELOAD:-1}"
if [[ -x ".venv313/bin/python" ]]; then
  API_PYTHON_BIN="${API_PYTHON_BIN:-.venv313/bin/python}"
elif [[ -x ".venv/bin/python" ]]; then
  API_PYTHON_BIN="${API_PYTHON_BIN:-.venv/bin/python}"
else
  API_PYTHON_BIN="${API_PYTHON_BIN:-python}"
fi

if [[ -n "${PYTHONPATH:-}" ]]; then
  export PYTHONPATH="${PYTHONPATH}:src"
else
  export PYTHONPATH="src"
fi

RELOAD_ARGS=()
if [[ "$API_RELOAD" == "1" ]]; then
  RELOAD_ARGS=(--reload)
fi

"$API_PYTHON_BIN" -m uvicorn android_planner.api:app --host "$API_HOST" --port "$API_PORT" "${RELOAD_ARGS[@]}"
