# GitHub Deployment Setup

This repository is configured for three GitHub workflows:

- `CI`: lint, unit tests, and offline release gates.
- `Live Runtime Smoke Test`: manually tests the API against a real vLLM/OpenAI-compatible endpoint.
- `Publish API Container`: builds and publishes the FastAPI API image to GitHub Container Registry.

## Required Runtime Shape

`taskdroid-android-planner-v1` is the public served model alias. The API expects a vLLM/OpenAI-compatible endpoint
that lists this alias from `/v1/models` and can generate from `/v1/chat/completions`.

The production API configuration is:

```bash
PLANNER_BACKEND=vllm
PLANNER_MODEL_PATH="${VLLM_BASE_URL}::taskdroid-android-planner-v1"
PLANNER_VLLM_RESPONSE_FORMAT_JSON=1
PLANNER_PRIMARY_RETRIES=1
```

## Repository Secrets

Add this secret before running `Live Runtime Smoke Test`:

```text
VLLM_BASE_URL=http://your-vllm-host:8001
```

## Container

The published GHCR image contains the FastAPI API only. It does not bundle model weights or start vLLM.
Run it with a remote or separately hosted vLLM endpoint:

```bash
docker run --rm -p 8000:8000 \
  -e PLANNER_BACKEND=vllm \
  -e PLANNER_MODEL_PATH="http://your-vllm-host:8001::taskdroid-android-planner-v1" \
  -e PLANNER_VLLM_TIMEOUT_SECONDS=120 \
  -e PLANNER_VLLM_COMPLETION_MAX_TOKENS=2048 \
  -e PLANNER_VLLM_RESPONSE_FORMAT_JSON=1 \
  -e PLANNER_PRIMARY_RETRIES=1 \
  ghcr.io/14121994/task-droid-ai:main
```

Then verify:

```bash
curl http://127.0.0.1:8000/health
curl -X POST http://127.0.0.1:8000/plan \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Build Android login with Compose, ViewModel, Retrofit, and tests.","intelligence_level":"high"}'
```

## Full Production Compose Stack

For a Linux CPU host that should run both vLLM and the API container:

```bash
cp deploy/taskdroid.prod.env.example deploy/taskdroid.prod.env
docker compose --env-file deploy/taskdroid.prod.env \
  -f deploy/docker-compose.taskdroid.yml up -d
```

Then verify the full chain:

```bash
python scripts/verify_taskdroid_deployment.py \
  --vllm-base-url http://YOUR_VLLM_HOST:8001 \
  --api-base-url http://YOUR_API_HOST:8000 \
  --expected-model-alias taskdroid-android-planner-v1
```

See `docs/taskdroid_production_release.md` for the end-to-end release and Ask The Assistant setup runbook.
