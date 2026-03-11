"""Pydantic models for Dev Engine MCP domain objects.

Backend-agnostic: works with both Trello and Plane backends.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


# --- Workflow States ---

WorkflowState = Literal["user_stories", "backlog", "in_progress", "review", "done"]

WORKFLOW_LIST_NAMES: dict[WorkflowState, str] = {
    "user_stories": "User Stories",
    "backlog": "Backlog",
    "in_progress": "In Progress",
    "review": "Review",
    "done": "Done",
}

LIST_NAME_TO_STATE: dict[str, WorkflowState] = {v: k for k, v in WORKFLOW_LIST_NAMES.items()}


# --- Actor ---

ActorType = Literal["Todos", "Profesional", "Empresa", "Centro", "Admin", "Dev"]

ACTOR_OPTIONS: list[str] = ["Todos", "Profesional", "Empresa", "Centro", "Admin", "Dev"]


# --- Card Types ---

CardType = Literal["US", "UC"]

CARD_TYPE_OPTIONS: list[str] = ["US", "UC"]


# --- Custom Field Names ---

CUSTOM_FIELD_NAMES = ["tipo", "us_id", "uc_id", "horas", "pantallas", "actor"]


# --- Evidence Types ---

EvidenceType = Literal["prd", "plan", "ag09", "delivery", "feedback"]

TargetType = Literal["us", "uc"]


# --- Import Spec Models ---

class AcceptanceCriterionSpec(BaseModel):
    text: str


class UseCaseSpec(BaseModel):
    uc_id: str
    name: str
    actor: str = "Todos"
    hours: float = 0
    screens: str = ""
    acceptance_criteria: list[str] = Field(default_factory=list)
    context: str = ""


class UserStorySpec(BaseModel):
    us_id: str
    name: str
    hours: float = 0
    screens: str = ""
    description: str = ""
    use_cases: list[UseCaseSpec] = Field(default_factory=list)


class ImportSpec(BaseModel):
    user_stories: list[UserStorySpec]


# --- Response Models ---

class AcceptanceCriterion(BaseModel):
    id: str
    text: str
    done: bool = False


class UseCaseSummary(BaseModel):
    uc_id: str
    us_id: str = ""
    name: str = ""
    actor: str = ""
    hours: float = 0
    status: str = ""
    screens: str = ""
    ac_total: int = 0
    ac_done: int = 0


class UseCaseDetail(BaseModel):
    uc_id: str
    name: str = ""
    us_id: str = ""
    us_name: str = ""
    actor: str = ""
    hours: float = 0
    screens: list[str] = Field(default_factory=list)
    status: str = ""
    acceptance_criteria: list[AcceptanceCriterion] = Field(default_factory=list)
    context: str = ""
    description_raw: str = ""
    attachments: list[dict[str, Any]] = Field(default_factory=list)
    backend_item_id: str = ""
    backend_item_url: str = ""
    backend_type: str = ""  # "trello" or "plane"


class UserStorySummary(BaseModel):
    us_id: str
    name: str = ""
    hours: float = 0
    status: str = ""
    screens: str = ""
    uc_total: int = 0
    uc_done: int = 0
    ac_total: int = 0
    ac_done: int = 0


class UserStoryDetail(BaseModel):
    us_id: str
    name: str = ""
    hours: float = 0
    status: str = ""
    screens: str = ""
    description: str = ""
    use_cases: list[UseCaseSummary] = Field(default_factory=list)
    attachments: list[dict[str, Any]] = Field(default_factory=list)


class BoardSetupResult(BaseModel):
    board_id: str
    board_url: str
    lists: dict[str, str]
    custom_fields: dict[str, str]
    labels: dict[str, str]


class BoardStatus(BaseModel):
    lists: list[dict[str, Any]]
    progress: dict[str, Any]
    us_summary: list[dict[str, Any]]


class SprintStatus(BaseModel):
    board_name: str = ""
    total_us: int = 0
    total_uc: int = 0
    total_ac: int = 0
    by_status: dict[str, dict[str, int]] = Field(default_factory=dict)
    hours: dict[str, Any] = Field(default_factory=dict)
    acs: dict[str, Any] = Field(default_factory=dict)
    blocked: list[dict[str, Any]] = Field(default_factory=list)


class DeliveryReport(BaseModel):
    project: str = ""
    generated_at: str = ""
    summary: dict[str, Any] = Field(default_factory=dict)
    user_stories: list[dict[str, Any]] = Field(default_factory=list)
