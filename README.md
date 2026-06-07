# Android Task Planner Model

This project builds an Android-specialized prompt-to-task planning model.
It converts user prompts into structured Android implementation plans that can drive coding execution.

## What Is Implemented

- Rule-based Android planner baseline (`RuleBasedAndroidPlanner`)
- Android relevance classifier (`TF-IDF + LogisticRegression`)
- PyTorch relevance classifier (small MLP over bag-of-words)
- SFT dataset builder for instruction fine-tuning
- LoRA fine-tuning script for prompt-to-plan generation
- FastAPI serving layer with schema validation and retry guardrails
- Evaluation harness for schema validity and domain accuracy

## Quickstart

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run tests:

```bash
PYTHONPATH=src pytest
```

Run CLI planner:

```bash
PYTHONPATH=src python -m android_planner.cli \
  --prompt "Implement Android login with Compose UI, Retrofit API, and Room cache."
```

Run full local pipeline (data + baselines + evaluation):

```bash
PYTHONPATH=src python scripts/run_full_pipeline.py --skip-lora
```

Run LoRA smoke training:

```bash
PYTHONPATH=src python scripts/train_lora_planner.py \
  --model-name sshleifer/tiny-gpt2 \
  --train-file data/processed/sft_train_smoke.jsonl \
  --val-file data/processed/sft_val_smoke.jsonl \
  --output-dir data/models/lora-smoke \
  --epochs 1 --batch-size 1 --grad-accum 1 --max-seq-length 256
```

Run API:

```bash
bash scripts/run_api.sh
```

Optional API launcher settings:

```bash
API_HOST=127.0.0.1 API_PORT=8080 API_RELOAD=0 bash scripts/run_api.sh
```

Run production profile (`vLLM only; deterministic rule fallback disabled`) with an accelerated endpoint:

```bash
START_VLLM=0 \
VLLM_BASE_URL="http://<accelerated-vllm-host>:8001" \
MODEL_ALIAS="taskdroid-android-planner-v1" \
bash scripts/run_prod_stack.sh
```

If you already have a running vLLM endpoint:

```bash
START_VLLM=0 VLLM_BASE_URL="http://127.0.0.1:8001" MODEL_ALIAS="taskdroid-android-planner-v1" bash scripts/run_prod_stack.sh
```

Use custom vLLM launcher settings on a Linux/CUDA host or another runtime that can actually generate tokens:

```bash
VLLM_PYTHON_BIN="$HOME/.taskdroid/vllm313/bin/python" \
VLLM_ARGS="--gpu-memory-utilization 0.45 --dtype auto --generation-config vllm" \
VLLM_MAX_MODEL_LEN=1024 \
PLANNER_VLLM_TIMEOUT_SECONDS=25 \
PLANNER_VLLM_COMPLETION_MAX_TOKENS=160 \
MODEL_ALIAS="taskdroid-android-planner-v1" \
MODEL_NAME="Qwen/Qwen2.5-3B-Instruct" \
bash scripts/run_prod_stack.sh
```

The production launcher refuses the known-bad local macOS Qwen 3B vLLM path by default because that path was
observed serving on CPU and stalling during generation. For macOS, run an OpenAI-compatible accelerated local
server if available, or point `START_VLLM=0` at a Linux/CUDA vLLM endpoint. Diagnostic overrides exist
(`TASKDROID_ALLOW_LOCAL_MACOS_VLLM=1`, `TASKDROID_ALLOW_FLOAT32_VLLM=1`), but do not use them for AI Assistant
integration readiness.

### vLLM Setup Notes (macOS / paths with spaces)

If your workspace path contains spaces (for example `/Users/.../AI Creations/...`), vLLM kernel compilation can fail with a `clang++` "no such file or directory" error due to path tokenization.
Use a persistent no-space venv path for the vLLM runtime:

```bash
# project env (API/tests/tools)
python3.13 -m venv .venv313
source .venv313/bin/activate
pip install -r requirements.txt

# dedicated vLLM env in a persistent no-space path
bash scripts/setup_vllm_runtime.sh
```

Then launch the stack from `.venv313`. The launcher will automatically use `$HOME/.taskdroid/vllm313/bin/python` when it exists:

```bash
source .venv313/bin/activate
MODEL_ALIAS=taskdroid-android-planner-v1 \
MODEL_NAME=sshleifer/tiny-gpt2 \
VLLM_VALIDATE_CHAT=0 \
bash scripts/run_prod_stack.sh
```

Sanity checks:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8001/v1/models
curl -X POST http://127.0.0.1:8001/v1/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"taskdroid-android-planner-v1","prompt":"Return JSON readiness check:","temperature":0,"max_tokens":32}'
curl -X POST http://127.0.0.1:8001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"taskdroid-android-planner-v1","messages":[{"role":"user","content":"Return JSON readiness check."}],"temperature":0,"max_tokens":32}'
curl -X POST http://127.0.0.1:8000/plan \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Build Android login screen with Jetpack Compose and validation.","intelligence_level":"high"}'
```

Stable integration model name:
- Public model ID for assistant integrations: `taskdroid-android-planner-v1`
- Underlying runtime/base model can change (`MODEL_NAME`) without changing this public ID.
- Planner intelligence levels accepted by `/plan`: `low`, `medium`, `high`, `xhigh`

Notes:
- `sshleifer/tiny-gpt2` is useful for startup smoke checks but is not ideal for production planning quality.
- Prefer an instruct/chat model for better JSON planning output quality.
- The launcher sets `Qwen/Qwen2.5-3B-Instruct` to `VLLM_MAX_MODEL_LEN=1024` by default. This keeps the local vLLM KV cache requirement within the observed available memory; increase it only when the runtime has enough free KV cache.
- API fallback is disabled in the production launcher. If vLLM fails, times out, or returns invalid planner JSON, `/plan` returns an error instead of serving a deterministic rule-based plan.
- The production launcher runs both `/v1/completions` and `/v1/chat/completions` generation probes before starting the API. A model-listing-only `/v1/models` success is not considered enough for assistant readiness.
- Higher levels only become materially smarter after you configure stronger underlying models for those levels.

## Output Contract

The planner always returns JSON with:

- `plan`
- `intelligence_level`
- `backend`: backend that actually produced the response
- `requested_backend`: primary backend selected for the request
- `fallback_used`: always `false` for successful production vLLM responses
- `fallback_reason`: `null` for successful production vLLM responses
- `attempted_backends`: ordered list of backend attempts
- `latency_ms`: end-to-end planner latency in milliseconds
- `planner_metadata`: planner name, planner version, behavior version, model alias, backend kind, and fallback-serving flag

The nested `plan` object contains:

- `is_android_related`
- `confidence`
- `plan_quality_score`: implementation-readiness score from `0.0` to `1.0`
- `confidence_reasons`: human-readable reasons behind confidence and quality scoring
- `plan_category`: one of `implementation`, `discovery`, `unsafe_refusal`, or `non_android_refusal`
- `refusal_category`: one of `none`, `unsafe_android_request`, or `non_android_request`
- `detected_intents`: priority-ordered intent ids such as `crash_triage`, `authentication`, or `networking`
- `requires_user_clarification`: whether an assistant should ask follow-up questions before implementation
- `feature_summary`
- `files_or_modules`
- `implementation_tasks`
- `acceptance_checks`
- `risks`
- `questions_for_user`

Schema is defined at `configs/task_plan_schema.json`.

Example response metadata:

```json
{
  "intelligence_level": "xhigh",
  "backend": "vllm",
  "requested_backend": "vllm",
  "fallback_used": false,
  "fallback_reason": null,
  "attempted_backends": ["vllm"],
  "latency_ms": 4210,
  "planner_metadata": {
    "planner_name": "taskdroid-android-planner",
    "planner_version": "1.0.0",
    "behavior_version": "rule-intent-v25",
    "model_alias": "taskdroid-android-planner-v1",
    "backend_kind": "vllm",
    "served_by_fallback": false
  }
}
```

Unsafe Android requests are treated separately from non-Android prompts. If a prompt asks for destructive,
privacy-invasive, permission-bypassing, or abusive Android/device behavior, the planner returns
`is_android_related=true`, `plan_category=unsafe_refusal`, `refusal_category=unsafe_android_request`, no
`implementation_tasks`, and a safety-oriented risk/question list. Non-Android prompts return
`plan_category=non_android_refusal` and `refusal_category=non_android_request`. Vague Android prompts return
`plan_category=discovery` with `refusal_category=none`.

Crash, exception, ANR, Logcat, and rotation/lifecycle prompts route to a dedicated crash-triage plan that
starts with evidence capture, app-owned stack-frame analysis, lifecycle/state repair, and regression tests.

Gradle sync/build, dependency conflict, Firebase/Compose BOM, plugin, and version-catalog prompts route to
a dedicated build plan with dependency graph inspection, `dependencyInsight`, version alignment, and
build verification checks.

Accessibility, TalkBack, screen-reader, semantics, focus-order, content-description, touch-target, and
contrast prompts route to a dedicated accessibility plan with assistive-technology verification.

Room, SQLite, offline cache, offline-first sync, DAO, migration, transactional write, and Retrofit-sync
prompts route to a dedicated persistence plan with entities, DAOs, migrations, cache invalidation,
conflict handling, and database/repository tests.

Acceptance checks are intent-specific. For example, auth prompts include auth ViewModel/repository checks,
networking prompts include API/repository failure-state checks, crash prompts include reproduction and Logcat
verification, Compose prompts include UI/navigation state checks, and quality prompts include lint/test-report
review.

The planner also routes common Android capability prompts for permissions/privacy, WorkManager/background work,
notifications/FCM, CameraX/media picker, location/maps, performance, security/privacy, Hilt/Dagger dependency
injection, modularization, release/Play deployment, analytics, localization, Play Billing, and deep links.

Risks are also intent-specific. Auth prompts call out token/session risks, networking prompts call out HTTP,
timeout, offline, and DTO-mapping risks, crash prompts call out lifecycle/root-cause regression risks, Compose
prompts call out state/navigation risks, and testing-quality prompts call out coverage, flaky-test, and CI-gate
risks.

Follow-up questions are intent-specific as well. Auth prompts ask about required auth flows and token/session
handling, networking prompts ask about endpoint contracts and failure states, Compose prompts ask about UI
states and navigation behavior, and testing-quality prompts ask about CI gates, flaky tests, and release-blocking
journeys.

Multi-intent prompts are prioritized explicitly. Blockers are planned first in this order: crash triage, Gradle/build
failure, security/privacy, permissions/privacy, performance, accessibility, persistence, dependency injection,
modularization, background work, notifications, location/maps, media/camera, billing/payments, analytics,
localization, deep links, authentication, networking, Compose UI, and testing-quality work.

Keyword matching is boundary-aware. Short terms such as `test`, `rest`, `api`, `ui`, and `intent` must appear as
standalone terms or phrases, so unrelated words like `latest`, `restore`, or `unintentional` do not trigger the
wrong planning intent.

Confidence is calibrated by specificity. Vague prompts such as `Build Android app` remain Android-related but
low-confidence, while prompts with concrete technologies, layers, intents, and implementation actions receive
higher confidence.

Vague Android prompts use a discovery fallback. If the planner cannot detect a concrete Android intent, it returns
product-brief, MVP scope, technical-direction, and acceptance-criteria tasks instead of inventing UI/data/build
implementation work.

Feature summaries are intent-aware and priority-aware. Instead of concatenating internal labels, the planner now
summarizes the actual workflow, such as crash-fix first, Gradle/build repair first, Room plus Retrofit integration,
or discovery before implementation for vague prompts.

File/module suggestions are prompt-aware. Combined prompts get feature-specific paths such as profile/product
API services, repositories, Room entities, UI tests, crash reproduction docs, and verification docs instead of
generic `Feature*` placeholders where the prompt gives a clear domain.

Task effort estimates are intent-aware. Short investigation or verification tasks use `S`, normal design/build/test
tasks use `M`, and complex lifecycle fixes, auth API integration, Room migrations, offline sync, persistence
regression tests, and instrumentation-heavy work use `L`.

Task dependencies are semantic. Follow-up feature work can start independently after a blocker plan, while dependent
tasks point to their real prerequisites, such as Gradle inspection after failure capture, auth UI after auth state/API
work, and Room sync after DAO/database setup.

API responses include planner metadata for observability. Assistants can log `planner_name`, `planner_version`,
`behavior_version`, `model_alias`, `backend_kind`, and `served_by_fallback` to compare quality, debug regressions,
and confirm that the response was served by vLLM.

Plan category fields make assistant routing explicit. Integrations can branch on `plan_category` and
`refusal_category` instead of inferring unsafe requests, non-Android prompts, vague discovery plans, or normal
implementation plans from empty task lists or summary text.

Detected intents make assistant orchestration explicit. Integrations can inspect `detected_intents` to route crash,
Gradle, security, permissions, performance, accessibility, persistence, DI, modularization, background work,
notifications, location/maps, media/camera, billing, analytics, localization, deep-link, auth, networking, Compose UI,
or testing work without parsing summaries or task titles.

Clarification routing is explicit. `requires_user_clarification=true` is returned for unsafe refusals, non-Android
refusals, vague discovery plans, and low-confidence implementation plans so assistants can ask before coding.

Plan quality scoring is explicit. `plan_quality_score` estimates implementation readiness, while
`confidence_reasons` explains why the planner considers the response high-confidence, low-confidence, discovery-only,
unsafe, or out of Android scope.

Prompt input is normalized before planning. Whitespace-only prompts are rejected and `/plan` currently limits prompts
to 4000 characters to protect local runtimes from accidental oversized requests.

## Project Layout

```text
src/android_planner/
  api.py
  cli.py
  data_io.py
  guardrails.py
  inference.py
  rule_planner.py
  schemas.py
  vllm_backend.py
  ml/baseline_classifier.py
scripts/
  create_gold_dataset.py
  build_gold_approved_dataset.py
  generate_seed_dataset.py
  train_baseline_classifier.py
  train_torch_classifier.py
  build_sft_dataset.py
  train_lora_planner.py
  evaluate_baseline_classifier.py
  evaluate_planner_outputs.py
  run_full_pipeline.py
  run_prod_stack.sh
tests/
configs/
data/
```

## Serving Modes

- `PLANNER_BACKEND=rule`: fast baseline planner.
- `PLANNER_BACKEND=hf` and `PLANNER_MODEL_PATH=<local-model-dir>`: local HF model.
- `PLANNER_BACKEND=vllm` and `PLANNER_MODEL_PATH=http://host:port::model_alias`: vLLM OpenAI-compatible backend.
- `PLANNER_VLLM_TIMEOUT_SECONDS=25`: per-request timeout for vLLM HTTP calls before the API returns a structured vLLM-only error.
- `VLLM_MAX_MODEL_LEN=1024`: default vLLM context length appended for `Qwen/Qwen2.5-3B-Instruct` unless `VLLM_ARGS` already includes a max-model-len option.
- `VLLM_ARGS="--gpu-memory-utilization 0.45 --dtype auto --generation-config vllm"`: default local vLLM args. The production launcher refuses `--dtype float32` unless `TASKDROID_ALLOW_FLOAT32_VLLM=1` is set for diagnostics.
- `TASKDROID_ALLOW_LOCAL_MACOS_VLLM=0`: default guard that refuses local macOS Qwen 3B vLLM startup for assistant readiness. Use `START_VLLM=0` with an accelerated OpenAI-compatible endpoint instead.
- `PLANNER_VLLM_COMPLETION_MAX_TOKENS=160`: max tokens for vLLM chat/completion generation; this keeps planner responses compact and leaves prompt headroom inside the default 1024-token context.
- `PLANNER_VLLM_RESPONSE_FORMAT_JSON=0`: keeps OpenAI `response_format` disabled by default. Enable only after verifying the target vLLM runtime handles structured outputs reliably.
- `PLANNER_HEALTH_GENERATION_PROBE=1`: production launcher default; `/health` marks readiness degraded if a bounded one-token generation probe fails.
- `VLLM_STARTUP_GENERATION_PROBE=1`: production launcher default; stack startup fails before starting the API if vLLM cannot complete direct generation from `taskdroid-android-planner-v1`.
- `VLLM_VALIDATE_COMPLETIONS=1` and `VLLM_VALIDATE_CHAT=1`: production launcher defaults; both `/v1/completions` and `/v1/chat/completions` must generate before the API starts.
- `VLLM_STARTUP_PROBE_MAX_TOKENS=<tokens>`: defaults to `PLANNER_VLLM_COMPLETION_MAX_TOKENS` for the startup readiness probe.
- The launcher appends `--generation-config vllm` to `VLLM_ARGS` when it is missing, so request-level deterministic sampling settings are not overridden by a model `generation_config.json`.
- `PLANNER_PRIMARY_RETRIES=0`: extra primary-backend retries after the first failed attempt.

## Intelligence Levels

Every `/plan` request can include an `intelligence_level`:

```json
{
  "prompt": "Create Android onboarding with Compose navigation and tests.",
  "intelligence_level": "xhigh"
}
```

Supported values:

- `low`: concise plan with the smallest useful task and check set.
- `medium`: standard implementation plan with core Android layers and normal verification.
- `high`: deeper planner route with integration-boundary review, extra files, risks, and device checks.
- `xhigh`: deepest planner route with edge-case mapping, verification matrix, rollout notes, and expanded checks.

For model-backed routes, configure stronger models per level with environment variables:

```bash
PLANNER_LOW_BACKEND=vllm
PLANNER_LOW_MODEL_PATH="http://127.0.0.1:8001::taskdroid-android-planner-v1"
PLANNER_MEDIUM_BACKEND=vllm
PLANNER_MEDIUM_MODEL_PATH="http://127.0.0.1:8011::taskdroid-android-planner-v1-medium"
PLANNER_HIGH_BACKEND=vllm
PLANNER_HIGH_MODEL_PATH="http://127.0.0.1:8021::taskdroid-android-planner-v1-high"
PLANNER_XHIGH_BACKEND=vllm
PLANNER_XHIGH_MODEL_PATH="http://127.0.0.1:8031::taskdroid-android-planner-v1-xhigh"
```

## Recommended Next Training Step

1. Review and approve examples in `data/gold/android_gold_annotation_template_v1.csv`.
2. Export approved rows: `PYTHONPATH=src python scripts/build_gold_approved_dataset.py`.
3. Train on approved gold rows plus targeted synthetic augmentation.
4. Expand SFT examples to include bug-fix/refactor/build-release scenarios.
5. Fine-tune a stronger base model (e.g. 3B to 8B instruct) with LoRA/QLoRA.
6. Enforce strict JSON schema decoding in production inference.

## Gold Dataset

- Seeded 200-example set: `data/gold/android_gold_seed_v1.jsonl`
- Review template: `data/gold/android_gold_annotation_template_v1.csv`
- Review rubric: `docs/gold_dataset_rubric.md`
- Approved export target: `data/gold/android_gold_v1_approved.jsonl`

Generate or rebuild the 200-row seed set:

```bash
PYTHONPATH=src python scripts/create_gold_dataset.py --count 200
```

Export approved reviewed rows later:

```bash
PYTHONPATH=src python scripts/build_gold_approved_dataset.py
```

Validate gold review/export readiness:

```bash
python scripts/check_gold_readiness.py --min-approved 50
```

## Production Readiness Gates

Run offline release gates (quality metrics + approved-gold minimum + tests):

```bash
python scripts/release_gates.py --min-approved 50 --run-tests
```

Run full release gates including live runtime checks:

```bash
python scripts/release_gates.py \
  --min-approved 50 \
  --run-tests \
  --check-runtime \
  --expected-model-alias taskdroid-android-planner-v1
```

Makefile shortcuts:

```bash
make gold-ready
make release-gates
```

## Reference Resources

- Android architecture guide: https://developer.android.com/topic/architecture
- Android fundamentals: https://developer.android.com/guide/components/fundamentals
- Android build from command line: https://developer.android.com/build/building-cmdline
- Android lint: https://developer.android.com/studio/write/lint
- Compose testing: https://developer.android.com/develop/ui/compose/testing
- Hugging Face PEFT docs: https://huggingface.co/docs/peft
- TRL SFTTrainer docs: https://huggingface.co/docs/trl/main/sft_trainer
- vLLM docs: https://docs.vllm.ai
