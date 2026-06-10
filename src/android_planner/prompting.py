"""Prompt construction shared by training and model-backed inference."""

from __future__ import annotations

from typing import Literal

IntelligenceLevel = Literal["low", "medium", "high", "xhigh"]
INTELLIGENCE_LEVELS: tuple[IntelligenceLevel, ...] = ("low", "medium", "high", "xhigh")

SYSTEM_PROMPT = (
    "You are taskdroid-android-planner-v1. Return exactly one JSON object and no markdown, commentary, "
    "code fences, or trailing prose. The object must include these top-level keys: is_android_related, "
    "confidence, plan_quality_score, confidence_reasons, plan_category, refusal_category, detected_intents, "
    "requires_user_clarification, feature_summary, files_or_modules, implementation_tasks, acceptance_checks, "
    "risks, questions_for_user. Use arrays even when empty. detected_intents must contain only these enum ids: "
    "crash_triage, gradle_build, security_privacy, permissions_privacy, performance, accessibility, database, "
    "dependency_injection, modularization, release_deployment, background_work, notifications, location_maps, "
    "media_camera, billing_payments, analytics, localization, deep_links, authentication, networking, "
    "ui_compose, testing_quality. Never invent human-readable detected_intents such as account recovery; map "
    "passkeys, sign-in, login, account recovery, credentials, sessions, and tokens to authentication. Map unit "
    "tests and regression coverage to testing_quality. plan_category must be one of implementation, discovery, "
    "unsafe_refusal, non_android_refusal. refusal_category must be one of none, unsafe_android_request, "
    "non_android_request. implementation_tasks must contain depth-appropriate objects with id, title, "
    "description, layer, estimated_effort, dependencies. layer must be one of ui, data, domain, testing, build, "
    "cross-cutting. estimated_effort must be S, M, or L."
)

OUTPUT_TEMPLATE = (
    'Required JSON shape: {"is_android_related":true,"confidence":0.0,"plan_quality_score":0.0,'
    '"confidence_reasons":["reason"],"plan_category":"implementation","refusal_category":"none",'
    '"detected_intents":["authentication"],"requires_user_clarification":false,'
    '"feature_summary":"short summary","files_or_modules":["FileOrModule.kt"],'
    '"implementation_tasks":[{"id":"T1","title":"Task title","description":"Task detail","layer":"ui",'
    '"estimated_effort":"M","dependencies":[]}],"acceptance_checks":["check"],"risks":["risk"],'
    '"questions_for_user":[]}.'
)

DEPTH_GUIDANCE: dict[IntelligenceLevel, str] = {
    "low": (
        "Produce a concise plan: 1-3 implementation tasks, the minimum useful files/modules, core risks, and "
        "2-4 acceptance checks. Prefer direct implementation steps over exploratory detail."
    ),
    "medium": (
        "Produce a standard implementation plan: 3-5 tasks that cover presentation, domain/data ownership, and "
        "normal unit-test verification."
    ),
    "high": (
        "Produce a deeper engineering plan: 5-8 tasks, explicit ViewModel/repository boundaries where relevant, "
        "integration risks, edge cases, and unit plus device or instrumentation checks."
    ),
    "xhigh": (
        "Produce the deepest practical plan: 8-12 tasks when justified, explicit ownership boundaries, edge-case "
        "mapping, verification matrix coverage, rollout or migration notes when relevant, and clear non-blocking "
        "questions."
    ),
}


def normalize_intelligence_level(intelligence_level: str) -> IntelligenceLevel:
    """Normalize the public planner depth value."""

    if intelligence_level in INTELLIGENCE_LEVELS:
        return intelligence_level  # type: ignore[return-value]
    return "medium"


def gpt_oss_reasoning_level(intelligence_level: str) -> str:
    """Map planner depth to gpt-oss reasoning labels."""

    level = normalize_intelligence_level(intelligence_level)
    if level == "xhigh":
        return "high"
    return level


def build_system_prompt(intelligence_level: str) -> str:
    """Build the full model system prompt for a planner request."""

    level = normalize_intelligence_level(intelligence_level)
    return (
        f"Reasoning: {gpt_oss_reasoning_level(level)}\n"
        f"Planner intelligence_level: {level}\n"
        f"{SYSTEM_PROMPT}\n"
        f"{OUTPUT_TEMPLATE}\n"
        f"Depth guidance: {DEPTH_GUIDANCE[level]}"
    )


def build_planner_messages(prompt: str, intelligence_level: str) -> list[dict[str, str]]:
    """Build chat messages used for both SFT rows and inference."""

    return [
        {"role": "system", "content": build_system_prompt(intelligence_level)},
        {"role": "user", "content": prompt},
    ]


def build_completion_prompt(prompt: str, intelligence_level: str) -> str:
    """Build a text-completion prompt for non-chat compatible runtimes."""

    return (
        f"{build_system_prompt(intelligence_level)}\n"
        "Return valid JSON only.\n"
        f"User request: {prompt}\n"
        "JSON:"
    )
