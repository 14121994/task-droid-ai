# Android Gold Dataset Rubric

Use this rubric during human review of seeded training data.

## Scoring (0 to 2)

- `Domain correctness`
  - 0: Not Android specific.
  - 1: Android-related but ambiguous.
  - 2: Clearly Android implementation request.
- `Plan correctness`
  - 0: Wrong tasks for prompt.
  - 1: Partially correct.
  - 2: Correct and relevant tasks.
- `Plan completeness`
  - 0: Major gaps.
  - 1: Missing at least one important layer.
  - 2: Covers needed UI/data/domain/testing/build concerns.
- `Actionability`
  - 0: Generic advice.
  - 1: Some concrete tasks.
  - 2: Engineering-ready implementation tasks.
- `Validation quality`
  - 0: No runnable checks.
  - 1: Incomplete checks.
  - 2: Includes realistic Gradle/lint/test checks.

## Approval Rule

- Approve only if every category scores `2`.
- If any category scores `<2`, mark `approved=no` and add correction notes.

## Typical Corrections

- Missing module/file targets.
- No test strategy.
- No failure-state handling.
- Weak risk and clarification fields.
