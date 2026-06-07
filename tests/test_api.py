from fastapi.testclient import TestClient

from android_planner.api import create_app


def test_health_endpoint():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["ready"] is True
    assert payload["fallback_backend"] == "none"
    assert set(payload["intelligence_levels"]) == {"low", "medium", "high", "xhigh"}
    assert all(route["fallback_backend"] == "none" for route in payload["intelligence_levels"].values())
    assert all(route["ready"] is True for route in payload["intelligence_levels"].values())


def test_health_endpoint_reports_degraded_generation_probe(monkeypatch):
    class UnreadyVLLMBackend:
        def check_model_available(self, timeout_seconds=None):  # noqa: ANN001
            return {
                "ok": True,
                "kind": "model_listing",
                "model_alias": "taskdroid-android-planner-v1",
                "observed_models": ["taskdroid-android-planner-v1"],
                "error": None,
            }

        def check_generation_ready(self, timeout_seconds=None):  # noqa: ANN001
            return {
                "ok": False,
                "kind": "generation_probe",
                "error": "vLLM request timed out after 5s.",
            }

        def plan(self, prompt: str):  # pragma: no cover
            raise AssertionError("health must not call plan")

    def fake_build_backend(kind: str, model_path=None):  # noqa: ANN001, ARG001
        if kind == "vllm":
            return UnreadyVLLMBackend()
        raise ValueError(kind)

    monkeypatch.setattr("android_planner.api.build_backend", fake_build_backend)
    monkeypatch.setenv("PLANNER_BACKEND", "vllm")
    monkeypatch.setenv("PLANNER_MODEL_PATH", "http://127.0.0.1:8001::taskdroid-android-planner-v1")
    monkeypatch.setenv("PLANNER_HEALTH_GENERATION_PROBE", "1")

    client = TestClient(create_app())
    response = client.get("/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "degraded"
    assert payload["ready"] is False
    assert payload["fallback_backend"] == "none"
    low_route = payload["intelligence_levels"]["low"]
    assert low_route["ready"] is False
    assert any(check["kind"] == "generation_probe" and check["ok"] is False for check in low_route["readiness_checks"])


def test_plan_endpoint_returns_schema():
    client = TestClient(create_app())
    response = client.post(
        "/plan",
        json={"prompt": "Build Android Jetpack Compose profile screen with ViewModel and tests."},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intelligence_level"] == "low"
    assert body["backend"] == "rule"
    assert body["requested_backend"] == "rule"
    assert body["fallback_used"] is False
    assert body["fallback_reason"] is None
    assert body["attempted_backends"] == ["rule"]
    assert isinstance(body["latency_ms"], int)
    assert body["latency_ms"] >= 0
    metadata = body["planner_metadata"]
    assert metadata == {
        "planner_name": "taskdroid-android-planner",
        "planner_version": "1.0.0",
        "behavior_version": "rule-intent-v25",
        "model_alias": "taskdroid-android-planner-v1",
        "backend_kind": "rule",
        "served_by_fallback": False,
    }
    payload = body["plan"]
    assert payload["is_android_related"] is True
    assert payload["plan_category"] == "implementation"
    assert payload["refusal_category"] == "none"
    assert payload["detected_intents"] == ["ui_compose", "testing_quality"]
    assert payload["requires_user_clarification"] is False
    assert isinstance(payload["plan_quality_score"], float)
    assert payload["plan_quality_score"] > 0
    assert isinstance(payload["confidence_reasons"], list)
    assert payload["confidence_reasons"]
    assert isinstance(payload["implementation_tasks"], list)


def test_plan_endpoint_accepts_intelligence_level():
    client = TestClient(create_app())
    response = client.post(
        "/plan",
        json={
            "prompt": "Build Android Jetpack Compose settings screen with ViewModel and tests.",
            "intelligence_level": "high",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["intelligence_level"] == "high"
    assert body["plan"]["is_android_related"] is True


def test_plan_endpoint_rejects_whitespace_only_prompt():
    client = TestClient(create_app())
    response = client.post("/plan", json={"prompt": "      "})

    assert response.status_code == 422


def test_plan_endpoint_rejects_overlarge_prompt():
    client = TestClient(create_app())
    response = client.post("/plan", json={"prompt": "Android " + ("x" * 4000)})

    assert response.status_code == 422


def test_plan_endpoint_normalizes_prompt_whitespace():
    client = TestClient(create_app())
    response = client.post(
        "/plan",
        json={"prompt": "  Build   Android   Jetpack Compose   settings screen with tests.  "},
    )

    assert response.status_code == 200
    plan = response.json()["plan"]
    assert plan["is_android_related"] is True
    assert plan["plan_category"] == "implementation"


def test_plan_endpoint_routes_intelligence_level_to_rule_backend():
    client = TestClient(create_app())
    prompt = "Create Android onboarding flow with Compose navigation, analytics, accessibility, and tests."

    low_response = client.post("/plan", json={"prompt": prompt, "intelligence_level": "low"})
    xhigh_response = client.post("/plan", json={"prompt": prompt, "intelligence_level": "xhigh"})

    assert low_response.status_code == 200
    assert xhigh_response.status_code == 200
    low_plan = low_response.json()["plan"]
    xhigh_plan = xhigh_response.json()["plan"]
    assert low_response.json()["intelligence_level"] == "low"
    assert xhigh_response.json()["intelligence_level"] == "xhigh"
    assert len(low_plan["implementation_tasks"]) < len(xhigh_plan["implementation_tasks"])
    assert len(low_plan["acceptance_checks"]) < len(xhigh_plan["acceptance_checks"])


def test_plan_endpoint_metadata_uses_configured_model_alias(monkeypatch):
    monkeypatch.setenv("MODEL_ALIAS", "custom-taskdroid-alias")
    client = TestClient(create_app())
    response = client.post(
        "/plan",
        json={"prompt": "Build Android Jetpack Compose profile screen with ViewModel."},
    )

    assert response.status_code == 200
    metadata = response.json()["planner_metadata"]
    assert metadata["model_alias"] == "custom-taskdroid-alias"
    assert metadata["backend_kind"] == "rule"
    assert metadata["served_by_fallback"] is False


def test_plan_endpoint_metadata_uses_model_path_alias(monkeypatch):
    monkeypatch.setenv("PLANNER_LOW_MODEL_PATH", "http://127.0.0.1:8001::taskdroid-low-custom")
    client = TestClient(create_app())
    response = client.post(
        "/plan",
        json={"prompt": "Build Android Jetpack Compose profile screen with ViewModel."},
    )

    assert response.status_code == 200
    assert response.json()["planner_metadata"]["model_alias"] == "taskdroid-low-custom"


def test_plan_endpoint_blocks_unsafe_android_prompt():
    client = TestClient(create_app())
    response = client.post(
        "/plan",
        json={
            "prompt": "Build an Android app feature that secretly records microphone audio and uploads it.",
            "intelligence_level": "xhigh",
        },
    )

    assert response.status_code == 200
    body = response.json()
    plan = body["plan"]
    assert plan["is_android_related"] is True
    assert plan["plan_category"] == "unsafe_refusal"
    assert plan["refusal_category"] == "unsafe_android_request"
    assert plan["detected_intents"] == []
    assert plan["requires_user_clarification"] is True
    assert plan["plan_quality_score"] == 0.0
    assert "Unsafe Android behavior detected." in plan["confidence_reasons"]
    assert plan["implementation_tasks"] == []
    assert plan["acceptance_checks"] == []
    assert "unsafe" in plan["feature_summary"].lower()
    assert body["backend"] == "rule"


def test_plan_endpoint_returns_crash_triage_tasks():
    client = TestClient(create_app())
    response = client.post(
        "/plan",
        json={
            "prompt": "Fix Android crash: NullPointerException in MainActivity when rotating device after login.",
            "intelligence_level": "xhigh",
        },
    )

    assert response.status_code == 200
    body = response.json()
    task_titles = [task["title"] for task in body["plan"]["implementation_tasks"]]
    assert body["plan"]["is_android_related"] is True
    assert "crash" in body["plan"]["feature_summary"].lower()
    assert task_titles[0] == "Capture crash evidence"
    assert "Fix lifecycle/state handling" in task_titles
    assert "Add crash regression tests" in task_titles


def test_plan_endpoint_returns_discovery_and_non_android_categories():
    client = TestClient(create_app())

    discovery_response = client.post(
        "/plan",
        json={"prompt": "Build Android app.", "intelligence_level": "xhigh"},
    )
    non_android_response = client.post(
        "/plan",
        json={"prompt": "Create a PowerPoint deck for quarterly finance report.", "intelligence_level": "xhigh"},
    )

    assert discovery_response.status_code == 200
    assert non_android_response.status_code == 200
    discovery_plan = discovery_response.json()["plan"]
    non_android_plan = non_android_response.json()["plan"]
    assert discovery_plan["is_android_related"] is True
    assert discovery_plan["plan_category"] == "discovery"
    assert discovery_plan["refusal_category"] == "none"
    assert discovery_plan["detected_intents"] == []
    assert discovery_plan["requires_user_clarification"] is True
    assert 0 < discovery_plan["plan_quality_score"] < 0.4
    assert "Discovery tasks are required before coding." in discovery_plan["confidence_reasons"]
    assert non_android_plan["is_android_related"] is False
    assert non_android_plan["plan_category"] == "non_android_refusal"
    assert non_android_plan["refusal_category"] == "non_android_request"
    assert non_android_plan["detected_intents"] == []
    assert non_android_plan["requires_user_clarification"] is True
    assert non_android_plan["plan_quality_score"] == 0.0
    assert "Prompt does not contain enough Android-specific implementation context." in (
        non_android_plan["confidence_reasons"]
    )


def test_plan_endpoint_returns_gradle_dependency_tasks():
    client = TestClient(create_app())
    response = client.post(
        "/plan",
        json={
            "prompt": "Resolve Gradle dependency conflict after adding Firebase Analytics.",
            "intelligence_level": "xhigh",
        },
    )

    assert response.status_code == 200
    body = response.json()
    plan = body["plan"]
    task_titles = [task["title"] for task in plan["implementation_tasks"]]
    assert plan["is_android_related"] is True
    assert "gradle" in plan["feature_summary"].lower()
    assert "Inspect dependency graph" in task_titles
    assert "Align versions and BOMs" in task_titles
    assert any("dependencyInsight" in check for check in plan["acceptance_checks"])


def test_plan_endpoint_returns_accessibility_tasks():
    client = TestClient(create_app())
    response = client.post(
        "/plan",
        json={
            "prompt": "Improve TalkBack accessibility for a custom Compose calendar widget.",
            "intelligence_level": "xhigh",
        },
    )

    assert response.status_code == 200
    body = response.json()
    plan = body["plan"]
    task_titles = [task["title"] for task in plan["implementation_tasks"]]
    assert plan["is_android_related"] is True
    assert "accessibility" in plan["feature_summary"].lower()
    assert "Audit accessibility gaps" in task_titles
    assert "Add semantic labels and roles" in task_titles
    assert any("TalkBack" in check for check in plan["acceptance_checks"])


def test_plan_endpoint_returns_persistence_tasks():
    client = TestClient(create_app())
    response = client.post(
        "/plan",
        json={
            "prompt": "Add Room database offline cache for product list and sync with Retrofit.",
            "intelligence_level": "xhigh",
        },
    )

    assert response.status_code == 200
    body = response.json()
    plan = body["plan"]
    task_titles = [task["title"] for task in plan["implementation_tasks"]]
    assert plan["is_android_related"] is True
    assert plan["detected_intents"] == ["database", "networking"]
    assert "room" in plan["feature_summary"].lower()
    assert "Model Room entities and relations" in task_titles
    assert "Implement offline-first repository sync" in task_titles
    assert any("DaoTest" in check for check in plan["acceptance_checks"])


def test_plan_endpoint_returns_error_if_primary_fails(monkeypatch):
    primary_calls = 0

    class FailingBackend:
        def plan(self, prompt: str):
            nonlocal primary_calls
            primary_calls += 1
            raise RuntimeError("primary failed")

    def fake_build_backend(kind: str, model_path=None):  # noqa: ANN001
        if kind == "vllm":
            return FailingBackend()
        raise ValueError(kind)

    monkeypatch.setattr("android_planner.api.build_backend", fake_build_backend)
    monkeypatch.setenv("PLANNER_BACKEND", "vllm")
    monkeypatch.setenv("PLANNER_FALLBACK_BACKEND", "rule")

    client = TestClient(create_app())
    response = client.post(
        "/plan",
        json={"prompt": "Implement Android login screen with Compose and Retrofit."},
    )

    assert response.status_code == 500
    body = response.json()
    detail = body["detail"]
    assert detail["error"] == "planner_backend_error"
    assert detail["message"] == "primary failed"
    assert detail["backend"] == "vllm"
    assert detail["requested_backend"] == "vllm"
    assert detail["fallback_used"] is False
    assert detail["fallback_backend"] == "none"
    assert detail["attempted_backends"] == ["vllm"]
    assert isinstance(detail["latency_ms"], int)
    assert primary_calls == 1


def test_plan_endpoint_accepts_release_deployment_intent():
    client = TestClient(create_app())
    response = client.post(
        "/plan",
        json={
            "prompt": "Prepare signed Android release AAB with R8, mapping upload, and Play checklist.",
            "intelligence_level": "xhigh",
        },
    )

    assert response.status_code == 200
    plan = response.json()["plan"]
    assert "release_deployment" in plan["detected_intents"]
    assert plan["implementation_tasks"]


def test_plan_endpoint_returns_error_for_malformed_vllm_output(monkeypatch):
    class MalformedOutputBackend:
        supports_intelligence_level = True

        def plan(self, prompt: str, intelligence_level: str = "medium"):
            raise RuntimeError("vLLM returned malformed or non-JSON planner output.")

    def fake_build_backend(kind: str, model_path=None):  # noqa: ANN001, ARG001
        if kind == "vllm":
            return MalformedOutputBackend()
        raise ValueError(kind)

    monkeypatch.setattr("android_planner.api.build_backend", fake_build_backend)
    monkeypatch.setenv("PLANNER_BACKEND", "vllm")
    monkeypatch.delenv("PLANNER_FALLBACK_BACKEND", raising=False)

    client = TestClient(create_app())
    response = client.post(
        "/plan",
        json={"prompt": "Implement Android login screen with Compose and Retrofit."},
    )

    assert response.status_code == 502
    body = response.json()
    assert body["detail"]["message"] == "vLLM returned malformed or non-JSON planner output."
    assert body["detail"]["fallback_used"] is False
