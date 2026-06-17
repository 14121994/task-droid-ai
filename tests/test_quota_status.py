import json

import pytest

from android_planner.quota_status import (
    QuotaStatusError,
    _parse_gcloud_json,
    build_quota_status,
    quota_dashboard_html,
)


def test_build_quota_status_normalizes_google_cloud_preferences(monkeypatch):
    preferences = [
        {
            "name": "projects/taskdroid-planner-training/locations/global/quotaPreferences/global-gpus",
            "quotaConfig": {
                "grantedValue": "1",
                "preferredValue": "1",
                "stateDetail": "Quota request approved to 1",
                "traceId": "trace-global",
            },
            "quotaId": "GPUS-ALL-REGIONS-per-project",
            "service": "compute.googleapis.com",
        },
        {
            "name": "projects/taskdroid-planner-training/locations/global/quotaPreferences/a100-uscentral1",
            "dimensions": {
                "gpu_family": "NVIDIA_A100_80GB",
                "region": "us-central1",
            },
            "quotaConfig": {
                "grantedValue": "0",
                "preferredValue": "1",
                "traceId": "trace-a100",
            },
            "quotaId": "GPUS-PER-GPU-FAMILY-per-project-region",
            "reconciling": True,
            "service": "compute.googleapis.com",
        },
        {
            "name": "projects/taskdroid-planner-training/locations/global/quotaPreferences/agent-platform",
            "dimensions": {
                "region": "us-central1",
            },
            "quotaConfig": {
                "grantedValue": "0",
                "traceId": "trace-agent-platform",
            },
            "quotaId": "CustomModelServingA10080GBGPUsPerProjectPerRegion",
            "service": "aiplatform.googleapis.com",
        },
    ]
    monkeypatch.setattr(
        "android_planner.quota_status._run_gcloud_quota_preferences",
        lambda project_id: json.dumps(preferences),
    )

    status = build_quota_status("taskdroid-planner-training")

    assert status["project_id"] == "taskdroid-planner-training"
    assert status["quotas"][0] == {
        "preference_id": "global-gpus",
        "service": "compute.googleapis.com",
        "quota_id": "GPUS-ALL-REGIONS-per-project",
        "scope": "Global",
        "requested": "1",
        "granted": "1",
        "status": "Approved",
        "state_detail": "Quota request approved to 1",
        "trace_id": "trace-global",
        "reconciling": False,
    }
    assert status["quotas"][1]["scope"] == "gpu_family=NVIDIA_A100_80GB, region=us-central1"
    assert status["quotas"][1]["status"] == "Pending / reconciling"
    assert status["quotas"][2]["requested"] == "0"
    assert status["quotas"][2]["status"] == "Opted out / reduced to 0"


def test_parse_gcloud_json_ignores_prefix_text():
    assert _parse_gcloud_json("None\n[{\"quotaId\":\"one\"}]") == [{"quotaId": "one"}]


def test_build_quota_status_rejects_invalid_project_id():
    with pytest.raises(QuotaStatusError):
        build_quota_status("bad project")


def test_quota_dashboard_has_refresh_button_and_api_fetch():
    html = quota_dashboard_html()

    assert 'id="refresh"' in html
    assert "fetch(\"/quota-status\"" in html
    assert "Quotas and System Limits" in html
