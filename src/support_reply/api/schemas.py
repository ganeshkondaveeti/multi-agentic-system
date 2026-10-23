"""Request and response models. Responses mirror the contracts' `to_dict()` exactly.

They exist for validation and for the OpenAPI schema the frontend generates its
types from. Request text is stripped and bounded; unknown fields are rejected.
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, StringConstraints

from support_reply.contracts import (
    AgentName,
    ComplianceFlag,
    Disposition,
    FactsStatus,
    FiredKind,
    Priority,
    ReviewCheck,
    ReviewStatus,
    Signal,
)

MAX_TEXT_CHARS = 2000

UserText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MAX_TEXT_CHARS)
]
PiiType = Literal["PAN", "AADHAAR", "ACCOUNT", "PHONE", "EMAIL", "OTP"]
Source = Literal["model", "cues"]
TurnKind = Literal["complaint", "message", "refinement", "replace"]


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ComplaintIn(_In):
    complaint: UserText


class PushbackIn(_In):
    pushback: UserText


class MessageIn(_In):
    message: UserText


# --- the contracts --------------------------------------------------------------------


class WindowOut(BaseModel):
    start: str
    end: str


class FactsOut(BaseModel):
    status: FactsStatus
    scheme_id: str | None
    section_title: str | None
    fact: str | None
    citation: str | None
    last_checked: str | None
    searched: list[str]


class PatternOut(BaseModel):
    theme_id: str
    theme_name: str
    signal: Signal
    count: int
    recent_count: int
    window: WindowOut
    recent_window: WindowOut


class ComplianceOut(BaseModel):
    flags: list[ComplianceFlag]
    pii_types: list[PiiType]
    advice_refusal: bool
    redacted_text: str


class RoutingNoteOut(BaseModel):
    team: str
    priority: Priority
    why: str


class DraftOut(BaseModel):
    reply: str
    last_checked: str | None
    citation: str | None
    disposition: Disposition
    disagreement: bool
    routing_note: RoutingNoteOut


class FailureOut(BaseModel):
    check: ReviewCheck
    detail: str


class ReviewOut(BaseModel):
    status: ReviewStatus
    round: int
    failures: list[FailureOut]


class AgentsFiredOut(BaseModel):
    round: int
    kind: FiredKind
    ran: list[AgentName]
    skipped: list[AgentName]


class SessionOut(BaseModel):
    redacted_text: str
    pii_types: list[PiiType]
    facts: FactsOut | None
    pattern: PatternOut | None
    compliance: ComplianceOut | None
    draft: DraftOut | None
    routing_note: RoutingNoteOut | None
    review: ReviewOut | None
    advice_refusal: bool
    refinement_count: int
    agents_fired: list[AgentsFiredOut]


# --- API views --------------------------------------------------------------------------


class TraceEventOut(BaseModel):
    seq: int
    node: str
    kind: Literal["start", "return"]
    elapsed_ms: float


class ProvenanceOut(BaseModel):
    """Where each node's pick came from. A node that has not run yet is null."""

    facts: Source | None = None
    pattern: Source | None = None
    compliance: Source | None = None
    reviewer: Source | None = None


class TurnOut(BaseModel):
    kind: TurnKind
    ran: list[str]
    provenance: ProvenanceOut


class StepOut(BaseModel):
    status: Literal["done", "failed", "off"]
    error: str | None


class DeliveryOut(BaseModel):
    """After approve: the Google Doc append and the Gmail draft, over MCP."""

    doc: StepOut
    email: StepOut


class ApprovedOut(BaseModel):
    approved_at: str
    email_file: str
    delivery: DeliveryOut


class SessionView(BaseModel):
    session_id: str
    session: SessionOut
    trace: list[TraceEventOut]
    provenance: ProvenanceOut
    turn: TurnOut
    approvable: bool
    approved: ApprovedOut | None
    refinements_left: int
    created_at: str
    updated_at: str


class SessionSummary(BaseModel):
    session_id: str
    excerpt: str
    disposition: Disposition | None
    priority: Priority | None
    review_status: ReviewStatus | None
    refinement_count: int
    advice_refusal: bool
    approved: bool
    updated_at: str


class RecordOut(BaseModel):
    session_id: str
    approved_at: str
    redacted_text: str
    pii_types: list[PiiType]
    disposition: Disposition
    reply: str
    citation: str | None
    last_checked: str | None
    routing_note: RoutingNoteOut
    pattern_signal: Signal
    agents_fired: list[AgentsFiredOut]


class ApproveOut(BaseModel):
    session_id: str
    email_file: str
    record: RecordOut
    delivery: DeliveryOut


class EmailOut(BaseModel):
    session_id: str
    text: str


class ModelsOut(BaseModel):
    mode: Literal["auto", "off"]
    agents: Literal["groq", "cues"]
    reviewer: Literal["gemini", "code"]
    agent_model: str | None
    reviewer_model: str | None


class CorpusOut(BaseModel):
    last_checked: str
    schemes: int


class McpOut(BaseModel):
    enabled: bool
    doc_configured: bool


class HealthOut(BaseModel):
    status: Literal["ok"]
    environment: str
    models: ModelsOut
    corpus: CorpusOut
    review_window: WindowOut
    access_code_required: bool
    mcp: McpOut


class ErrorOut(BaseModel):
    error: str
    message: str


# --- acceptance report ------------------------------------------------------------------


class OutcomeOut(BaseModel):
    facts_status: FactsStatus
    scheme_id: str | None
    section_title: str | None
    theme_id: str
    signal: Signal
    count: int
    compliance_flags: list[ComplianceFlag]
    disposition: Disposition
    review_status: ReviewStatus


class RealComplaintOut(OutcomeOut):
    review_id: str
    provenance: ProvenanceOut


class BranchApprovalOut(BaseModel):
    session_id: str
    email_file: str


class BranchOut(OutcomeOut):
    name: str
    redacted_text: str
    routing_note: RoutingNoteOut
    agents_fired_this_turn: list[str]
    agents_fired: list[AgentsFiredOut]
    trace: list[TraceEventOut]
    provenance: ProvenanceOut
    approved: BranchApprovalOut | None


class AdviceTurnOut(BaseModel):
    turn: int
    ask: str
    disposition: Disposition
    flags: list[ComplianceFlag]
    advice_refusal: bool


class BlockedCapOut(BaseModel):
    review_status: ReviewStatus
    review_round: int
    failed_checks: list[ReviewCheck]
    approve_refused: bool
    files_written: int


class RefinementCapOut(BaseModel):
    applied: int
    sixth_refused: bool
    draft_kept: bool


class CapsOut(BaseModel):
    blocked: BlockedCapOut | None = None
    refinement_cap: RefinementCapOut | None = None


class AcceptanceOut(BaseModel):
    status: Literal["pass", "fail"]
    failure: str | None
    mode: str
    ran_at: str
    real_complaints: list[RealComplaintOut]
    branches: list[BranchOut]
    advice_thread: list[AdviceTurnOut]
    caps: CapsOut
