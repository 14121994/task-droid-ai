#!/usr/bin/env bash
set -euo pipefail

# Keep this path free of spaces. vLLM CPU kernel setup can fail when the Python
# environment path contains spaces.
VLLM_RUNTIME_DIR="${VLLM_RUNTIME_DIR:-$HOME/.taskdroid/vllm313}"
PYTHON_BIN="${PYTHON_BIN:-/usr/local/bin/python3}"
VLLM_PACKAGE_URL="${VLLM_PACKAGE_URL:-https://files.pythonhosted.org/packages/97/bb/8dbba4136f6851470f4324ac665affe55c0b618341ccc42f35a53c5e708e/vllm-0.21.0.tar.gz}"

case "$VLLM_RUNTIME_DIR" in
  *" "*)
    echo "VLLM_RUNTIME_DIR must not contain spaces: $VLLM_RUNTIME_DIR" >&2
    exit 1
    ;;
esac

if [[ ! -x "$VLLM_RUNTIME_DIR/bin/python" ]]; then
  "$PYTHON_BIN" -m venv "$VLLM_RUNTIME_DIR"
fi

"$VLLM_RUNTIME_DIR/bin/python" -m pip install --upgrade pip
"$VLLM_RUNTIME_DIR/bin/pip" install "$VLLM_PACKAGE_URL"

echo "vLLM runtime ready: $VLLM_RUNTIME_DIR/bin/python"
