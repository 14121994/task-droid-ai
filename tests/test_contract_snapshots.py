import json
from pathlib import Path

from fastapi.testclient import TestClient

from android_planner.api import create_app
from android_planner.schemas import TaskPlan


def test_task_plan_schema_contains_public_model_fields():
    schema = json.loads(Path("configs/task_plan_schema.json").read_text(encoding="utf-8"))
    schema_fields = set(schema["properties"])
    model_fields = set(TaskPlan.model_fields)

    assert model_fields.issubset(schema_fields)


def test_detected_intent_schema_enum_covers_expanded_android_capabilities():
    schema = json.loads(Path("configs/task_plan_schema.json").read_text(encoding="utf-8"))
    intent_enum = set(schema["properties"]["detected_intents"]["items"]["enum"])

    assert {
        "crash_triage",
        "gradle_build",
        "security_privacy",
        "permissions_privacy",
        "performance",
        "accessibility",
        "database",
        "dependency_injection",
        "modularization",
        "release_deployment",
        "background_work",
        "notifications",
        "location_maps",
        "media_camera",
        "billing_payments",
        "analytics",
        "localization",
        "deep_links",
        "authentication",
        "networking",
        "ui_compose",
        "testing_quality",
    }.issubset(intent_enum)


def test_plan_endpoint_contract_snapshot_for_android_request():
    client = TestClient(create_app())
    response = client.post(
        "/plan",
        json={
            "prompt": (
                "Build Android login screen in Jetpack Compose with Retrofit API, ViewModel, tests, "
                "analytics, and secure token storage."
            ),
            "intelligence_level": "xhigh",
        },
    )

    assert response.status_code == 200
    body = response.json()
    plan = body["plan"]

    assert sorted(body) == [
        "attempted_backends",
        "backend",
        "fallback_reason",
        "fallback_used",
        "intelligence_level",
        "latency_ms",
        "plan",
        "planner_metadata",
        "requested_backend",
    ]
    assert sorted(plan) == [
        "acceptance_checks",
        "confidence",
        "confidence_reasons",
        "detected_intents",
        "feature_summary",
        "files_or_modules",
        "implementation_tasks",
        "is_android_related",
        "plan_category",
        "plan_quality_score",
        "questions_for_user",
        "refusal_category",
        "requires_user_clarification",
        "risks",
    ]
    assert plan["plan_category"] == "implementation"
    assert plan["refusal_category"] == "none"
    assert plan["detected_intents"][0] == "security_privacy"
    assert "authentication" in plan["detected_intents"]
    assert body["planner_metadata"]["model_alias"] == "taskdroid-android-planner-v1"
