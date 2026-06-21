# TaskDroid Production Release Runbook

This runbook deploys the released TaskDroid API image and a CPU-backed vLLM runtime so
`Ask The Assistant` can call `taskdroid-android-planner-v1`.

## Runtime Shape

- vLLM serves the public model alias `taskdroid-android-planner-v1` from `/v1/models` and `/v1/chat/completions`.
- The TaskDroid API container calls vLLM through `PLANNER_MODEL_PATH=http://vllm:8001::taskdroid-android-planner-v1`.
- The macOS assistant calls only the TaskDroid API base URL, not vLLM directly.

The GitHub Actions publish run `27874689507` completed successfully for commit
`f797cab8f8fb1c709023ea5e6d8c254a3243e3c6`. Start with:

```text
ghcr.io/14121994/task-droid-ai:main
```

Pin the SHA tag after the deployment is validated.

## Deploy On The CPU Host

On the Linux CPU host:

```bash
cp deploy/taskdroid.prod.env.example deploy/taskdroid.prod.env
```

Edit `deploy/taskdroid.prod.env` if the host ports, model name, or Hugging Face token need to change.
Then start the full runtime:

```bash
docker compose --env-file deploy/taskdroid.prod.env \
  -f deploy/docker-compose.taskdroid.yml up -d
```

Equivalent Make target:

```bash
make deploy-up
```

Stop the stack with:

```bash
make deploy-down
```

## Verify The Release

Check the deployed vLLM and TaskDroid API chain:

```bash
python scripts/verify_taskdroid_deployment.py \
  --vllm-base-url http://YOUR_VLLM_HOST:8001 \
  --api-base-url http://YOUR_API_HOST:8000 \
  --expected-model-alias taskdroid-android-planner-v1
```

Then run the release gates against the live runtime:

```bash
python scripts/release_gates.py \
  --min-approved 50 \
  --run-tests \
  --check-runtime \
  --api-base-url http://YOUR_API_HOST:8000 \
  --vllm-base-url http://YOUR_VLLM_HOST:8001 \
  --expected-model-alias taskdroid-android-planner-v1
```

For public production use, put HTTPS in front of the TaskDroid API and keep vLLM private.

## Connect Ask The Assistant

In `C:\Users\Akshay Kamat\OneDrive\AI creations\android-app-developer-ai-assistant`:

1. Build and test the assistant:

   ```bash
   swift test
   swift run AndroidDevAgentSmokeTests
   ```

2. Open `Ask The Assistant`, expand `Model Setup`, enable `Use TaskDroid`, and set the TaskDroid base URL to the API URL, for example:

   ```text
   https://planner.example.com
   ```

3. Enable provider-sharing consent in the Ask panel. Without this consent, Ask intentionally uses the private local route.
4. Select `Fast`, `Auto`, or `Deep`; `Private` never calls TaskDroid.
5. Ask an Android implementation prompt and confirm the response status names `TaskDroid Android Planner` and `taskdroid-android-planner-v1`.

For automation builds, launch the app with:

```bash
TASKDROID_API_BASE_URL=https://planner.example.com \
TASKDROID_API_TIMEOUT_SECONDS=360 \
open "dist/Android Dev Agent.app"
```

## Acceptance Criteria

- `GET /v1/models` lists `taskdroid-android-planner-v1`.
- `POST /v1/chat/completions` can generate from `taskdroid-android-planner-v1`.
- `GET /health` returns `ready=true`.
- `POST /plan` returns `backend=vllm`, `fallback_used=false`, and planner metadata with `model_alias=taskdroid-android-planner-v1`.
- Ask The Assistant renders a TaskDroid-attributed response and does not substitute OpenAI/local output when the configured TaskDroid route fails.
