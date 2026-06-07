# Gold Dataset (Android Planner)

This folder contains curated seed data for Android prompt-to-task-plan training.

## Files

- `android_gold_seed_v1.jsonl`: 200 seeded examples (`prompt -> task_plan`).
- `android_gold_annotation_template_v1.csv`: reviewer template for human quality pass.

## Review Workflow

1. Open `android_gold_annotation_template_v1.csv`.
2. For each row:
   - set `approved=yes` only if prompt and plan are both high-quality.
   - add `review_notes` for required corrections.
3. Update corresponding `task_plan` entries in `android_gold_seed_v1.jsonl`.
4. When finished, copy approved rows into `android_gold_v1_approved.jsonl`.

## Quality Standard

- Prompt is Android-specific and unambiguous.
- Plan contains implementation-ready tasks across appropriate layers.
- Acceptance checks are runnable Android checks (`lint`, tests, assemble).
- Risk and clarification sections are useful and concise.
