#!/usr/bin/env bash
set -euo pipefail

# Production profile:
# - primary backend: vLLM (OpenAI-compatible endpoint)
# - no deterministic rule fallback; vLLM failures are returned as API errors
#
# Usage:
#   bash scripts/run_prod_stack.sh
#   MODEL_NAME="Qwen/Qwen2.5-3B-Instruct" bash scripts/run_prod_stack.sh
#   MODEL_ALIAS="taskdroid-android-planner-v1" MODEL_NAME="Qwen/Qwen2.5-3B-Instruct" bash scripts/run_prod_stack.sh
#   START_VLLM=0 VLLM_BASE_URL="http://127.0.0.1:8001" MODEL_ALIAS="taskdroid-android-planner-v1" bash scripts/run_prod_stack.sh

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

API_HOST="${API_HOST:-0.0.0.0}"
API_PORT="${API_PORT:-8000}"
VLLM_HOST="${VLLM_HOST:-127.0.0.1}"
VLLM_PORT="${VLLM_PORT:-8001}"
VLLM_BASE_URL="${VLLM_BASE_URL:-http://${VLLM_HOST}:${VLLM_PORT}}"
MODEL_NAME="${MODEL_NAME:-Qwen/Qwen2.5-3B-Instruct}"
MODEL_ALIAS="${MODEL_ALIAS:-taskdroid-android-planner-v1}"
START_VLLM="${START_VLLM:-1}"
VLLM_STARTUP_TIMEOUT_SECONDS="${VLLM_STARTUP_TIMEOUT_SECONDS:-1800}"
VLLM_MAX_MODEL_LEN="${VLLM_MAX_MODEL_LEN:-32768}"
TASKDROID_ALLOW_LOCAL_MACOS_VLLM="${TASKDROID_ALLOW_LOCAL_MACOS_VLLM:-0}"
TASKDROID_ALLOW_FLOAT32_VLLM="${TASKDROID_ALLOW_FLOAT32_VLLM:-0}"
DEFAULT_VLLM_PYTHON_BIN="$HOME/.taskdroid/vllm313/bin/python"
if [[ -x "$DEFAULT_VLLM_PYTHON_BIN" ]]; then
  VLLM_PYTHON_BIN="${VLLM_PYTHON_BIN:-$DEFAULT_VLLM_PYTHON_BIN}"
else
  VLLM_PYTHON_BIN="${VLLM_PYTHON_BIN:-python}"
fi
if [[ -x ".venv313/bin/python" ]]; then
  API_PYTHON_BIN="${API_PYTHON_BIN:-.venv313/bin/python}"
elif [[ -x ".venv/bin/python" ]]; then
  API_PYTHON_BIN="${API_PYTHON_BIN:-.venv/bin/python}"
else
  API_PYTHON_BIN="${API_PYTHON_BIN:-python}"
fi
VLLM_ARGS="${VLLM_ARGS:---gpu-memory-utilization 0.90 --dtype auto}"
if [[ " $VLLM_ARGS " != *" --generation-config "* ]]; then
  VLLM_ARGS="${VLLM_ARGS} --generation-config vllm"
fi
case "$MODEL_NAME" in
  *Qwen2.5-3B-Instruct*)
    if [[ " $VLLM_ARGS " != *" --max-model-len "* && " $VLLM_ARGS " != *" --max_model_len "* ]]; then
      VLLM_ARGS="${VLLM_ARGS} --max-model-len ${VLLM_MAX_MODEL_LEN}"
    fi
    ;;
esac

if [[ -n "${PYTHONPATH:-}" ]]; then
  export PYTHONPATH="${PYTHONPATH}:src"
else
  export PYTHONPATH="src"
fi
export PLANNER_BACKEND="vllm"
export PLANNER_MODEL_PATH="${VLLM_BASE_URL}::${MODEL_ALIAS}"
unset PLANNER_FALLBACK_BACKEND
unset PLANNER_FALLBACK_MODEL_PATH
unset PLANNER_LOW_FALLBACK_BACKEND
unset PLANNER_LOW_FALLBACK_MODEL_PATH
unset PLANNER_MEDIUM_FALLBACK_BACKEND
unset PLANNER_MEDIUM_FALLBACK_MODEL_PATH
unset PLANNER_HIGH_FALLBACK_BACKEND
unset PLANNER_HIGH_FALLBACK_MODEL_PATH
unset PLANNER_XHIGH_FALLBACK_BACKEND
unset PLANNER_XHIGH_FALLBACK_MODEL_PATH
export PLANNER_VLLM_TIMEOUT_SECONDS="${PLANNER_VLLM_TIMEOUT_SECONDS:-120}"
export PLANNER_VLLM_COMPLETION_MAX_TOKENS="${PLANNER_VLLM_COMPLETION_MAX_TOKENS:-1024}"
export PLANNER_VLLM_RESPONSE_FORMAT_JSON="${PLANNER_VLLM_RESPONSE_FORMAT_JSON:-1}"
export PLANNER_HEALTH_GENERATION_PROBE="${PLANNER_HEALTH_GENERATION_PROBE:-1}"
export PLANNER_HEALTH_PROBE_TIMEOUT_SECONDS="${PLANNER_HEALTH_PROBE_TIMEOUT_SECONDS:-5}"
VLLM_STARTUP_GENERATION_PROBE="${VLLM_STARTUP_GENERATION_PROBE:-1}"
VLLM_GENERATION_PROBE_TIMEOUT_SECONDS="${VLLM_GENERATION_PROBE_TIMEOUT_SECONDS:-180}"
VLLM_STARTUP_PROBE_MAX_TOKENS="${VLLM_STARTUP_PROBE_MAX_TOKENS:-32}"
VLLM_VALIDATE_COMPLETIONS="${VLLM_VALIDATE_COMPLETIONS:-1}"
VLLM_VALIDATE_CHAT="${VLLM_VALIDATE_CHAT:-1}"
if [[ -z "${PLANNER_VLLM_API_MODE:-}" ]]; then
  case "$MODEL_NAME" in
    *gpt2*|*GPT2*|*gpt-2*|*GPT-2*)
      export PLANNER_VLLM_API_MODE="completion"
      ;;
    *)
      export PLANNER_VLLM_API_MODE="chat"
      ;;
  esac
else
  export PLANNER_VLLM_API_MODE
fi

VLLM_PID=""
cleanup() {
  if [[ -n "$VLLM_PID" ]]; then
    kill "$VLLM_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

is_qwen_3b_model() {
  case "$MODEL_NAME" in
    *Qwen2.5-3B-Instruct*)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

enforce_runtime_guardrails() {
  if [[ "$START_VLLM" != "1" ]]; then
    return
  fi

  if [[ " $VLLM_ARGS " == *" --dtype float32 "* || " $VLLM_ARGS " == *" --dtype=float32 "* ]]; then
    if [[ "$TASKDROID_ALLOW_FLOAT32_VLLM" != "1" ]]; then
      echo "Refusing to start production vLLM with --dtype float32." >&2
      echo "Use --dtype auto, fp16/bfloat16 where supported, or a quantized/accelerated endpoint." >&2
      echo "Set TASKDROID_ALLOW_FLOAT32_VLLM=1 only for diagnostics, not assistant integration." >&2
      exit 1
    fi
  fi

  if [[ "$(uname -s)" == "Darwin" ]] && is_qwen_3b_model; then
    if [[ "$TASKDROID_ALLOW_LOCAL_MACOS_VLLM" != "1" ]]; then
      echo "Refusing to start local macOS vLLM for ${MODEL_NAME} in production mode." >&2
      echo "The observed local macOS vLLM path serves this model on CPU and stalls during generation." >&2
      echo "Use START_VLLM=0 with a CUDA/Linux vLLM endpoint, or another OpenAI-compatible accelerated endpoint." >&2
      echo "Set TASKDROID_ALLOW_LOCAL_MACOS_VLLM=1 only for diagnostics, not assistant integration." >&2
      exit 1
    fi
  fi
}

ensure_port_available() {
  local label="$1"
  local host="$2"
  local port="$3"
  local output

  if ! output=$("$API_PYTHON_BIN" - "$host" "$port" 2>&1 <<'PY'
import socket
import sys

host = sys.argv[1]
port = int(sys.argv[2])
with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        sock.bind((host, port))
    except OSError as exc:
        sys.exit(str(exc))
PY
  ); then
    echo "${label} port ${host}:${port} is not available: ${output}" >&2
    echo "Stop the existing service or set ${label}_PORT to a free port." >&2
    exit 1
  fi
}

enforce_runtime_guardrails

wait_for_vllm_models() {
  echo "Waiting up to ${VLLM_STARTUP_TIMEOUT_SECONDS}s for vLLM readiness at ${VLLM_BASE_URL}/v1/models"
  for ((elapsed = 0; elapsed < VLLM_STARTUP_TIMEOUT_SECONDS; elapsed += 2)); do
    if curl -fsS "${VLLM_BASE_URL}/v1/models" >/dev/null 2>&1; then
      echo "vLLM is ready"
      return
    fi
    if [[ "$START_VLLM" == "1" ]] && ! kill -0 "$VLLM_PID" >/dev/null 2>&1; then
      wait "$VLLM_PID"
      echo "vLLM exited before becoming ready." >&2
      exit 1
    fi
    sleep 2
  done
  echo "vLLM did not become ready within ${VLLM_STARTUP_TIMEOUT_SECONDS}s." >&2
  echo "Set VLLM_STARTUP_TIMEOUT_SECONDS higher for first-time model downloads, or set START_VLLM=0 for an existing endpoint." >&2
  exit 1
}

run_vllm_generation_probe() {
  local probe_name="$1"
  local endpoint_path="$2"
  local payload="$3"

  echo "Running vLLM ${probe_name} generation probe with ${VLLM_GENERATION_PROBE_TIMEOUT_SECONDS}s timeout"
  if ! curl --max-time "$VLLM_GENERATION_PROBE_TIMEOUT_SECONDS" -fsS \
    -X POST "${VLLM_BASE_URL}${endpoint_path}" \
    -H 'Content-Type: application/json' \
    -d "$payload" >/dev/null; then
    echo "vLLM listed the model but failed the ${probe_name} generation probe." >&2
    echo "The API is not starting because responses must come only from ${MODEL_ALIAS}; no rule fallback will be used." >&2
    echo "Increase PLANNER_VLLM_TIMEOUT_SECONDS only after these probes show the runtime is producing tokens." >&2
    exit 1
  fi
  echo "vLLM ${probe_name} generation probe passed"
}

validate_vllm_generation() {
  if [[ "$VLLM_STARTUP_GENERATION_PROBE" != "1" ]]; then
    echo "WARNING: vLLM startup generation probes are disabled; this is diagnostic-only and not assistant-ready." >&2
    return
  fi

  local completion_payload
  completion_payload="{\"model\":\"${MODEL_ALIAS}\",\"prompt\":\"Return compact JSON only for Android planner readiness with keys is_android_related, confidence, feature_summary, files_or_modules, implementation_tasks, acceptance_checks, risks, questions_for_user. JSON:\",\"temperature\":0,\"max_tokens\":${VLLM_STARTUP_PROBE_MAX_TOKENS}}"
  local chat_payload
  chat_payload="{\"model\":\"${MODEL_ALIAS}\",\"messages\":[{\"role\":\"system\",\"content\":\"Return compact JSON only.\"},{\"role\":\"user\",\"content\":\"Plan Android readiness check for passkey sign-in with recovery fallback. JSON:\"}],\"temperature\":0,\"max_tokens\":${VLLM_STARTUP_PROBE_MAX_TOKENS}"
  case "$PLANNER_VLLM_RESPONSE_FORMAT_JSON" in
    1|true|TRUE|yes|YES|on|ON)
      chat_payload="${chat_payload},\"response_format\":{\"type\":\"json_object\"}"
      ;;
  esac
  chat_payload="${chat_payload}}"

  if [[ "$VLLM_VALIDATE_COMPLETIONS" == "1" ]]; then
    run_vllm_generation_probe "completions" "/v1/completions" "$completion_payload"
  fi
  if [[ "$VLLM_VALIDATE_CHAT" == "1" ]]; then
    run_vllm_generation_probe "chat-completions" "/v1/chat/completions" "$chat_payload"
  fi
}

ensure_port_available "API" "$API_HOST" "$API_PORT"
if [[ "$START_VLLM" == "1" ]]; then
  ensure_port_available "VLLM" "$VLLM_HOST" "$VLLM_PORT"
fi

if [[ "$START_VLLM" == "1" ]]; then
  if [[ "$VLLM_PYTHON_BIN" != "python" && ! -x "$VLLM_PYTHON_BIN" ]]; then
    echo "Configured vLLM Python does not exist or is not executable: $VLLM_PYTHON_BIN" >&2
    echo "Run: bash scripts/setup_vllm_runtime.sh" >&2
    exit 1
  fi

  "$VLLM_PYTHON_BIN" - <<'PY'
import importlib.util, sys
if importlib.util.find_spec("vllm") is None:
    sys.exit("vLLM is not installed. Run scripts/setup_vllm_runtime.sh or set START_VLLM=0 for an existing endpoint.")
PY

  echo "Starting vLLM server on ${VLLM_HOST}:${VLLM_PORT}"
  echo "Base model: ${MODEL_NAME}"
  echo "Served model alias: ${MODEL_ALIAS}"
  echo "Using vLLM python: ${VLLM_PYTHON_BIN}"
  echo "vLLM args: ${VLLM_ARGS}"
  # shellcheck disable=SC2086
  env -u VLLM_ARGS -u VLLM_STARTUP_TIMEOUT_SECONDS "$VLLM_PYTHON_BIN" -m vllm.entrypoints.openai.api_server \
    --model "$MODEL_NAME" \
    --served-model-name "$MODEL_ALIAS" \
    --host "$VLLM_HOST" \
    --port "$VLLM_PORT" \
    $VLLM_ARGS &
  VLLM_PID=$!
else
  echo "Using existing vLLM endpoint: ${VLLM_BASE_URL}"
  echo "Planner will call model alias: ${MODEL_ALIAS}"
fi
wait_for_vllm_models
validate_vllm_generation

echo "Starting planner API on ${API_HOST}:${API_PORT} with vLLM only; fallback disabled"
echo "Planner vLLM API mode: ${PLANNER_VLLM_API_MODE}"
echo "Planner vLLM timeout: ${PLANNER_VLLM_TIMEOUT_SECONDS}s"
echo "Planner vLLM max tokens: ${PLANNER_VLLM_COMPLETION_MAX_TOKENS}"
echo "Planner vLLM response_format JSON: ${PLANNER_VLLM_RESPONSE_FORMAT_JSON}"
echo "Planner health generation probe: ${PLANNER_HEALTH_GENERATION_PROBE}"
echo "vLLM startup completions probe: ${VLLM_VALIDATE_COMPLETIONS}"
echo "vLLM startup chat probe: ${VLLM_VALIDATE_CHAT}"
"$API_PYTHON_BIN" -m uvicorn android_planner.api:app --host "$API_HOST" --port "$API_PORT"
