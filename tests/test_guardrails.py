from android_planner.guardrails import PlanValidator, plan_with_retry
from android_planner.rule_planner import RuleBasedAndroidPlanner
from android_planner.schemas import TaskPlan


def test_validator_accepts_rule_plan():
    planner = RuleBasedAndroidPlanner()
    plan = planner.plan("Create Android Compose login flow with Retrofit API.")
    validator = PlanValidator(schema_path="configs/task_plan_schema.json")
    validator.validate_plan(plan)


def test_plan_with_retry_returns_plan():
    planner = RuleBasedAndroidPlanner()
    validator = PlanValidator(schema_path="configs/task_plan_schema.json")
    plan = plan_with_retry(planner.plan, "Improve Android Room database query.", validator, retries=1)
    assert plan.is_android_related is True


def test_plan_with_retry_reprompts_on_schema_validation_error():
    validator = PlanValidator(schema_path="configs/task_plan_schema.json")
    prompts = []

    def planner(prompt: str) -> TaskPlan:
        prompts.append(prompt)
        detected_intents = ["authentication", "account recovery"] if len(prompts) == 1 else ["authentication"]
        return TaskPlan(
            is_android_related=True,
            confidence=0.9,
            plan_quality_score=0.85,
            confidence_reasons=["Android authentication request"],
            detected_intents=detected_intents,
            requires_user_clarification=False,
            feature_summary="Plan passkey sign-in with account recovery fallback.",
            files_or_modules=["AuthViewModel.kt", "AuthRepository.kt"],
            implementation_tasks=[
                {
                    "id": "T1",
                    "title": "Model auth state",
                    "description": "Represent passkey success and account recovery fallback.",
                    "layer": "domain",
                    "estimated_effort": "M",
                    "dependencies": [],
                }
            ],
            acceptance_checks=["Unit tests cover recovery fallback."],
            risks=["Credential provider behavior may vary."],
            questions_for_user=[],
        )

    plan = plan_with_retry(
        planner,
        "Plan Android passkey sign-in with account recovery fallback.",
        validator,
        retries=1,
    )

    assert plan.detected_intents == ["authentication"]
    assert len(prompts) == 2
    assert "account recovery" in prompts[1]
    assert "use only these enum ids" in prompts[1]
