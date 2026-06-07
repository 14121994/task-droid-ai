"""Pydantic schemas for Android implementation task plans."""

from __future__ import annotations

from typing import List, Literal

from pydantic import BaseModel, Field

TaskLayer = Literal["ui", "data", "domain", "testing", "build", "cross-cutting"]
PlanCategory = Literal["implementation", "discovery", "unsafe_refusal", "non_android_refusal"]
RefusalCategory = Literal["none", "unsafe_android_request", "non_android_request"]


class ImplementationTask(BaseModel):
    """Single implementation unit in an Android plan."""

    id: str = Field(description="Stable short id such as T1, T2.")
    title: str = Field(description="Task title.")
    description: str = Field(description="Implementation details.")
    layer: TaskLayer = Field(description="Android architecture layer.")
    estimated_effort: Literal["S", "M", "L"] = Field(description="Relative effort.")
    dependencies: List[str] = Field(default_factory=list, description="Dependent task ids.")


class TaskPlan(BaseModel):
    """Structured output contract for prompt-to-plan generation."""

    is_android_related: bool = Field(description="Whether the prompt is Android-specific.")
    confidence: float = Field(ge=0.0, le=1.0, description="Planner confidence.")
    plan_quality_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Estimated implementation-readiness quality score.",
    )
    confidence_reasons: List[str] = Field(
        default_factory=list,
        description="Human-readable reasons behind confidence and quality scoring.",
    )
    plan_category: PlanCategory = Field(default="implementation", description="High-level response category.")
    refusal_category: RefusalCategory = Field(default="none", description="Structured refusal reason if refused.")
    detected_intents: List[str] = Field(default_factory=list, description="Machine-readable planner intents.")
    requires_user_clarification: bool = Field(
        default=False,
        description="Whether an assistant should ask clarification before implementation.",
    )
    feature_summary: str = Field(description="Short feature or request summary.")
    files_or_modules: List[str] = Field(default_factory=list)
    implementation_tasks: List[ImplementationTask] = Field(default_factory=list)
    acceptance_checks: List[str] = Field(default_factory=list)
    risks: List[str] = Field(default_factory=list)
    questions_for_user: List[str] = Field(default_factory=list)

    def to_pretty_json(self) -> str:
        """Returns pretty-printed JSON."""
        return self.model_dump_json(indent=2)
