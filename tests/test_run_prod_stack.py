import os
import subprocess
import textwrap
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_prod_stack.sh"


def _write_executable(path: Path, body: str) -> Path:
    path.write_text(textwrap.dedent(body).lstrip(), encoding="utf-8")
    path.chmod(0o755)
    return path


def _stubbed_env(tmp_path: Path, uname_value: str = "Linux") -> dict:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_dir = tmp_path / "logs"
    log_dir.mkdir()

    python_stub = _write_executable(
        bin_dir / "python-stub",
        """
        #!/usr/bin/env bash
        printf '%s\\n' "$*" >> "$PYTHON_STUB_LOG"
        if [[ "${1:-}" == "-m" && "${2:-}" == "vllm.entrypoints.openai.api_server" ]]; then
          trap 'exit 0' TERM INT
          while true; do read -r -t 1 _ || true; done
        fi
        exit 0
        """,
    )
    _write_executable(
        bin_dir / "curl",
        """
        #!/usr/bin/env bash
        printf '%s\\n' "$*" >> "$CURL_STUB_LOG"
        exit 0
        """,
    )
    _write_executable(
        bin_dir / "uname",
        f"""
        #!/usr/bin/env bash
        echo {uname_value}
        """,
    )

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "HOME": str(tmp_path / "home"),
            "API_HOST": "127.0.0.1",
            "API_PORT": "19000",
            "VLLM_PORT": "19001",
            "API_PYTHON_BIN": str(python_stub),
            "VLLM_PYTHON_BIN": str(python_stub),
            "PYTHON_STUB_LOG": str(log_dir / "python.log"),
            "CURL_STUB_LOG": str(log_dir / "curl.log"),
            "MODEL_NAME": "Qwen/Qwen2.5-3B-Instruct",
            "MODEL_ALIAS": "taskdroid-android-planner-v1",
            "VLLM_STARTUP_TIMEOUT_SECONDS": "2",
            "VLLM_GENERATION_PROBE_TIMEOUT_SECONDS": "2",
            "PLANNER_VLLM_TIMEOUT_SECONDS": "25",
            "PLANNER_VLLM_COMPLETION_MAX_TOKENS": "16",
        }
    )
    return env


def _run_stack(env: dict) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def test_run_prod_stack_rejects_float32_vllm_args(tmp_path):
    env = _stubbed_env(tmp_path, uname_value="Linux")
    env["VLLM_ARGS"] = "--gpu-memory-utilization 0.45 --dtype float32 --generation-config vllm"

    result = _run_stack(env)

    assert result.returncode == 1
    assert "Refusing to start production vLLM with --dtype float32" in result.stderr


def test_run_prod_stack_rejects_local_macos_qwen_vllm(tmp_path):
    env = _stubbed_env(tmp_path, uname_value="Darwin")

    result = _run_stack(env)

    assert result.returncode == 1
    assert "Refusing to start local macOS vLLM" in result.stderr
    assert "START_VLLM=0" in result.stderr


def test_run_prod_stack_validates_completions_and_chat_before_api(tmp_path):
    env = _stubbed_env(tmp_path, uname_value="Linux")

    result = _run_stack(env)

    curl_log = Path(env["CURL_STUB_LOG"]).read_text(encoding="utf-8")
    python_log = Path(env["PYTHON_STUB_LOG"]).read_text(encoding="utf-8")
    assert result.returncode == 0
    assert "/v1/models" in curl_log
    assert "/v1/completions" in curl_log
    assert "/v1/chat/completions" in curl_log
    assert "uvicorn android_planner.api:app" in python_log
    assert "fallback disabled" in result.stdout
