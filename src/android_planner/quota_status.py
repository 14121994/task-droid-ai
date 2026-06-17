"""Google Cloud quota status helpers for the local planner API."""

from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime, timezone
from typing import Any

DEFAULT_QUOTA_PROJECT_ID = "taskdroid-planner-training"
DEFAULT_GCLOUD_TIMEOUT_SECONDS = 45
_PROJECT_ID_RE = re.compile(r"^[a-z][a-z0-9-]{4,61}[a-z0-9]$")


class QuotaStatusError(RuntimeError):
    """Raised when quota status cannot be fetched."""


def build_quota_status(project_id: str | None = None) -> dict[str, Any]:
    resolved_project_id = _resolve_project_id(project_id)
    output = _run_gcloud_quota_preferences(resolved_project_id)
    preferences = _parse_gcloud_json(output)
    if not isinstance(preferences, list):
        raise QuotaStatusError("Cloud Quotas response was not a list of quota preferences.")

    return {
        "project_id": resolved_project_id,
        "refreshed_at": datetime.now(timezone.utc).isoformat(),
        "quotas": [_normalize_preference(preference) for preference in preferences],
    }


def quota_dashboard_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>TaskDroid Quotas</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f7f8fa;
      --surface: #ffffff;
      --text: #162033;
      --muted: #5d6678;
      --line: #d9dee8;
      --primary: #0f6cbd;
      --ok-bg: #e7f6ed;
      --ok-text: #0d6b35;
      --wait-bg: #fff5d9;
      --wait-text: #7a4d00;
      --bad-bg: #fde7e9;
      --bad-text: #9f1b2d;
      --neutral-bg: #eef2f7;
      --neutral-text: #405066;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      background: var(--bg);
      color: var(--text);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }
    main {
      width: min(1180px, calc(100vw - 32px));
      margin: 24px auto;
    }
    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 16px;
      margin-bottom: 16px;
    }
    h1 {
      margin: 0;
      font-size: 22px;
      font-weight: 680;
      letter-spacing: 0;
    }
    .meta {
      margin-top: 4px;
      color: var(--muted);
      font-size: 13px;
    }
    button {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      border: 1px solid var(--primary);
      background: var(--primary);
      color: #fff;
      min-height: 38px;
      padding: 0 13px;
      border-radius: 6px;
      font: inherit;
      font-weight: 620;
      cursor: pointer;
    }
    button:disabled {
      opacity: .65;
      cursor: progress;
    }
    .icon {
      font-size: 17px;
      line-height: 1;
    }
    .status {
      min-height: 22px;
      color: var(--muted);
      font-size: 13px;
      margin-bottom: 10px;
    }
    .table-wrap {
      overflow-x: auto;
      border: 1px solid var(--line);
      background: var(--surface);
      border-radius: 8px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      min-width: 960px;
    }
    th, td {
      text-align: left;
      padding: 12px 14px;
      border-bottom: 1px solid var(--line);
      vertical-align: top;
      font-size: 13px;
    }
    th {
      background: #f0f3f8;
      color: #344154;
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .04em;
      white-space: nowrap;
    }
    tr:last-child td { border-bottom: 0; }
    code {
      font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace;
      font-size: 12px;
      color: #26364d;
      word-break: break-word;
    }
    .num {
      font-variant-numeric: tabular-nums;
      white-space: nowrap;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      border-radius: 999px;
      padding: 4px 9px;
      font-size: 12px;
      font-weight: 650;
      white-space: nowrap;
    }
    .approved { background: var(--ok-bg); color: var(--ok-text); }
    .pending { background: var(--wait-bg); color: var(--wait-text); }
    .denied { background: var(--bad-bg); color: var(--bad-text); }
    .neutral { background: var(--neutral-bg); color: var(--neutral-text); }
    @media (max-width: 720px) {
      header { align-items: stretch; flex-direction: column; }
      button { justify-content: center; width: 100%; }
      main { width: min(100vw - 20px, 1180px); margin-top: 14px; }
    }
  </style>
</head>
<body>
  <main>
    <header>
      <div>
        <h1>Quotas and System Limits</h1>
        <div class="meta" id="meta">Project: loading</div>
      </div>
      <button id="refresh" type="button" title="Refresh quota status" aria-label="Refresh quota status">
        <span class="icon" aria-hidden="true">&#8635;</span>
        <span>Refresh</span>
      </button>
    </header>
    <div class="status" id="status">Loading quota status...</div>
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Service</th>
            <th>Quota</th>
            <th>Scope</th>
            <th>Requested</th>
            <th>Granted</th>
            <th>Status</th>
            <th>Trace ID</th>
          </tr>
        </thead>
        <tbody id="rows">
          <tr><td colspan="7">Loading...</td></tr>
        </tbody>
      </table>
    </div>
  </main>
  <script>
    const refreshButton = document.getElementById("refresh");
    const rows = document.getElementById("rows");
    const statusText = document.getElementById("status");
    const meta = document.getElementById("meta");

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
    }

    function statusClass(status) {
      const normalized = String(status || "").toLowerCase();
      if (normalized.includes("approved")) return "approved";
      if (normalized.includes("pending") || normalized.includes("reconciling")) return "pending";
      if (normalized.includes("denied")) return "denied";
      return "neutral";
    }

    function render(payload) {
      meta.textContent = `Project: ${payload.project_id}`;
      const refreshedAt = new Date(payload.refreshed_at);
      statusText.textContent = `Last refreshed ${refreshedAt.toLocaleString()}`;
      if (!payload.quotas.length) {
        rows.innerHTML = '<tr><td colspan="7">No quota preferences found.</td></tr>';
        return;
      }
      rows.innerHTML = payload.quotas.map((quota) => `
        <tr>
          <td><code>${escapeHtml(quota.service)}</code></td>
          <td><code>${escapeHtml(quota.quota_id)}</code></td>
          <td><code>${escapeHtml(quota.scope)}</code></td>
          <td class="num">${escapeHtml(quota.requested)}</td>
          <td class="num">${escapeHtml(quota.granted)}</td>
          <td><span class="badge ${statusClass(quota.status)}">${escapeHtml(quota.status)}</span></td>
          <td><code>${escapeHtml(quota.trace_id)}</code></td>
        </tr>
      `).join("");
    }

    async function refreshQuotas() {
      refreshButton.disabled = true;
      statusText.textContent = "Refreshing quota status...";
      try {
        const response = await fetch("/quota-status", { cache: "no-store" });
        const payload = await response.json();
        if (!response.ok) {
          throw new Error(payload.detail?.message || payload.detail || response.statusText);
        }
        render(payload);
      } catch (error) {
        statusText.textContent = `Unable to refresh quota status: ${error.message}`;
      } finally {
        refreshButton.disabled = false;
      }
    }

    refreshButton.addEventListener("click", refreshQuotas);
    refreshQuotas();
  </script>
</body>
</html>
"""


def _resolve_project_id(project_id: str | None) -> str:
    resolved = (
        project_id
        or os.getenv("CLOUD_QUOTAS_PROJECT_ID")
        or os.getenv("GOOGLE_CLOUD_PROJECT")
        or os.getenv("GCLOUD_PROJECT")
        or DEFAULT_QUOTA_PROJECT_ID
    ).strip()
    if not _PROJECT_ID_RE.fullmatch(resolved):
        raise QuotaStatusError(f"Invalid Google Cloud project ID: {resolved!r}")
    return resolved


def _run_gcloud_quota_preferences(project_id: str) -> str:
    command = [
        "gcloud",
        "beta",
        "quotas",
        "preferences",
        "list",
        f"--project={project_id}",
        f"--billing-project={project_id}",
        "--format=json",
    ]
    env = {
        **os.environ,
        "CLOUDSDK_CORE_DISABLE_PROMPTS": "1",
    }
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            check=False,
            encoding="utf-8",
            env=env,
            timeout=DEFAULT_GCLOUD_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise QuotaStatusError("gcloud CLI was not found on PATH.") from exc
    except subprocess.TimeoutExpired as exc:
        raise QuotaStatusError("Timed out while fetching quota preferences from gcloud.") from exc

    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "gcloud quota preference lookup failed.").strip()
        raise QuotaStatusError(message)
    return completed.stdout


def _parse_gcloud_json(output: str) -> Any:
    stripped = output.strip()
    if not stripped:
        return []
    json_start_candidates = [index for index in (stripped.find("["), stripped.find("{")) if index >= 0]
    if not json_start_candidates:
        raise QuotaStatusError("gcloud did not return JSON output.")
    return json.loads(stripped[min(json_start_candidates):])


def _normalize_preference(preference: dict[str, Any]) -> dict[str, Any]:
    quota_config = preference.get("quotaConfig") or {}
    dimensions = preference.get("dimensions") or {}
    granted = _display_value(quota_config.get("grantedValue"))
    preferred = quota_config.get("preferredValue")
    requested = _display_value(preferred if preferred is not None else _inferred_requested_value(preference))
    status = _quota_status(preference)

    return {
        "preference_id": str(preference.get("name", "")).rsplit("/", maxsplit=1)[-1],
        "service": preference.get("service", ""),
        "quota_id": preference.get("quotaId", ""),
        "scope": _format_scope(dimensions),
        "requested": requested,
        "granted": granted,
        "status": status,
        "state_detail": quota_config.get("stateDetail", ""),
        "trace_id": quota_config.get("traceId", ""),
        "reconciling": bool(preference.get("reconciling", False)),
    }


def _inferred_requested_value(preference: dict[str, Any]) -> str:
    quota_config = preference.get("quotaConfig") or {}
    granted = quota_config.get("grantedValue")
    if str(granted) == "0":
        return "0"
    return ""


def _display_value(value: Any) -> str:
    if value is None or value == "":
        return "-"
    return str(value)


def _format_scope(dimensions: dict[str, Any]) -> str:
    if not dimensions:
        return "Global"
    return ", ".join(f"{key}={dimensions[key]}" for key in sorted(dimensions))


def _quota_status(preference: dict[str, Any]) -> str:
    quota_config = preference.get("quotaConfig") or {}
    state_detail = str(quota_config.get("stateDetail", ""))
    state_lower = state_detail.lower()
    granted = quota_config.get("grantedValue")
    preferred = quota_config.get("preferredValue")

    if "denied" in state_lower:
        return "Denied"
    if bool(preference.get("reconciling", False)):
        return "Pending / reconciling"
    if _is_zero(granted) and (preferred is None or _is_zero(preferred)):
        return "Opted out / reduced to 0"
    if preferred is not None and str(granted) == str(preferred):
        return "Approved"
    if "approved" in state_lower:
        return "Approved"
    if _is_zero(granted) and preferred is not None and not _is_zero(preferred):
        return "Not granted"
    return "Current"


def _is_zero(value: Any) -> bool:
    try:
        return float(str(value)) == 0
    except (TypeError, ValueError):
        return False
