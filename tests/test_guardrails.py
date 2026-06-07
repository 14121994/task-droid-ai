from android_planner.guardrails import PlanValidator, plan_with_retry
from android_planner.rule_planner import RuleBasedAndroidPlanner


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
