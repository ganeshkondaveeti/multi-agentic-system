// Friendly names for the generated OpenAPI schema types (src/api/types.gen.ts).
// Regenerate with `npm run gen:api` while the API runs locally.
import type { components } from "./types.gen";

type Schemas = components["schemas"];

export type SessionView = Schemas["SessionView"];
export type SessionSummary = Schemas["SessionSummary"];
export type SessionData = Schemas["SessionOut"];
export type Facts = Schemas["FactsOut"];
export type Pattern = Schemas["PatternOut"];
export type Compliance = Schemas["ComplianceOut"];
export type Draft = Schemas["DraftOut"];
export type RoutingNote = Schemas["RoutingNoteOut"];
export type Review = Schemas["ReviewOut"];
export type ReviewFailure = Schemas["FailureOut"];
export type AgentsFired = Schemas["AgentsFiredOut"];
export type TraceEvent = Schemas["TraceEventOut"];
export type Provenance = Schemas["ProvenanceOut"];
export type Turn = Schemas["TurnOut"];
export type Health = Schemas["HealthOut"];
export type RecordOut = Schemas["RecordOut"];
export type ApproveResult = Schemas["ApproveOut"];
export type EmailDraft = Schemas["EmailOut"];
export type Acceptance = Schemas["AcceptanceOut"];
export type AcceptanceBranch = Schemas["BranchOut"];
export type AcceptanceOutcome = Schemas["RealComplaintOut"];
export type AdviceTurn = Schemas["AdviceTurnOut"];
export type ErrorBody = Schemas["ErrorOut"];

export type Disposition = Draft["disposition"];
export type Priority = RoutingNote["priority"];
export type ReviewStatus = Review["status"];
export type ReviewCheck = ReviewFailure["check"];
export type Source = NonNullable<Provenance["facts"]>;

export const AGENTS = ["facts", "pattern", "compliance"] as const;
export type AgentNode = (typeof AGENTS)[number];

export const REVIEW_CHECKS: readonly ReviewCheck[] = [
  "citation",
  "advice",
  "performance",
  "pii",
  "shape",
];
