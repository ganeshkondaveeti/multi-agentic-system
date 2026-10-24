import { Link } from "react-router-dom";

import type { DeliveryStep, SessionView } from "../../api/types";
import { REVIEW_CHECKS } from "../../api/types";
import { DISPOSITIONS, PRIORITIES, REVIEW_STATUSES, SOURCES, relativeTime, sentenceCount, shortId, shortUrl } from "../../lib/format";
import { piiSegments, replySegments } from "../../lib/text";
import { Badge, Button, Card, Icon, Label, Spinner } from "../ui";

// What a passing check means. Citation and shape differ for a draft with no fact.
const CHECK_LABELS = {
  citation: {
    title: "Citation",
    covered: "One link: the source_url Facts returned",
    uncovered: "No link and no uncited fact",
  },
  advice: { title: "Advice", covered: "No recommendation about a holding", uncovered: "No recommendation about a holding" },
  performance: { title: "Performance", covered: "No return or performance figure", uncovered: "No return or performance figure" },
  pii: {
    title: "PII",
    covered: "Tokens only; no raw value in draft, note, or record",
    uncovered: "Tokens only; no raw value in draft, note, or record",
  },
  shape: {
    title: "Shape",
    covered: "Three sentences or fewer, with a last-checked date",
    uncovered: "Three sentences or fewer",
  },
} as const;

export function TicketHeader({ view, onOpenHistory }: { view: SessionView; onOpenHistory: () => void }) {
  const { session } = view;
  const draft = session.draft;
  const review = session.review;
  return (
    <div className="flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap items-center gap-2">
        <Label>Session</Label>
        <span className="font-mono text-headline-sm text-primary" title={view.session_id} data-testid="session-id">
          {shortId(view.session_id)}
        </span>
        {draft && (
          <Badge testId="disposition" className={DISPOSITIONS[draft.disposition].className}>
            {DISPOSITIONS[draft.disposition].label}
          </Badge>
        )}
        {draft && (
          <Badge testId="priority" className={PRIORITIES[draft.routing_note.priority]}>
            {draft.routing_note.priority}
          </Badge>
        )}
        {review && (
          <Badge testId="review-status" className={REVIEW_STATUSES[review.status].className}>
            Review {REVIEW_STATUSES[review.status].label}
          </Badge>
        )}
        {session.advice_refusal && (
          <Badge testId="sticky-refusal" className="border-warn/50 bg-warn/10 text-warn">
            <Icon name="lock" className="h-3 w-3" /> Advice refusal is sticky for this session
          </Badge>
        )}
        {view.approved && (
          <Badge testId="approved-badge" className="border-ok/40 bg-ok/10 text-ok">
            <Icon name="check" className="h-3 w-3" /> Approved
          </Badge>
        )}
      </div>
      <div className="flex items-center gap-2 font-mono text-trace-mono text-muted">
        <span>updated {relativeTime(view.updated_at)}</span>
        <Button variant="secondary" onClick={onOpenHistory} data-testid="history-button" className="h-7 px-2">
          <Icon name="history" className="h-3.5 w-3.5" /> History ({session.agents_fired.length})
        </Button>
      </div>
    </div>
  );
}

export function DisagreeBanner({ view }: { view: SessionView }) {
  const pattern = view.session.pattern;
  if (!view.session.draft?.disagreement || !pattern) return null;
  return (
    <div
      data-testid="disagree-banner"
      className="flex items-start gap-2 rounded-lg border border-agent-pattern/40 bg-agent-pattern/10 px-3 py-2 text-body-sm text-ink"
    >
      <Icon name="alert" className="mt-0.5 h-4 w-4 shrink-0 text-agent-pattern" />
      <span>
        The agents disagree. Facts has a cited answer, but Pattern shows <b>{pattern.theme_name}</b> rising:{" "}
        {pattern.recent_count} of {pattern.count} reviews came in the last 7 days. The reply is drafted and the
        ticket stays open.
      </span>
    </div>
  );
}

export function ComplaintCard({ view }: { view: SessionView }) {
  const { session } = view;
  return (
    <Card
      title="Customer complaint"
      icon="shield"
      right={
        <span className="flex items-center gap-1 font-mono text-trace-mono text-muted">
          <Icon name="lock" className="h-3 w-3" /> PII redacted at ingress, raw values never stored
        </span>
      }
    >
      <p data-testid="complaint-text" className="whitespace-pre-wrap rounded border border-line bg-canvas p-3 text-body-md leading-7 text-ink">
        {piiSegments(session.redacted_text).map((segment, index) =>
          segment.kind === "token" ? (
            <span
              key={index}
              data-testid="pii-token"
              className="mx-0.5 rounded border border-agent-compliance/40 bg-agent-compliance/10 px-1.5 py-0.5 font-mono text-code-inline text-agent-compliance"
            >
              [{segment.value}]
            </span>
          ) : (
            <span key={index}>{segment.value}</span>
          ),
        )}
      </p>
    </Card>
  );
}

export function DraftCard({ view }: { view: SessionView }) {
  const draft = view.session.draft;
  const review = view.session.review;
  if (!draft) return null;
  const blocked = review?.status === "blocked";
  const flagged = blocked ? (review?.failures ?? []).map((failure) => failure.detail) : [];
  const count = sentenceCount(draft.reply);
  return (
    <Card
      title="Generated reply draft"
      icon="doc"
      testId="draft-card"
      accent={blocked ? "!border-danger/60" : undefined}
      right={
        <div className="flex items-center gap-2">
          {draft.citation ? (
            <Badge testId="citation" className="border-agent-facts/40 bg-agent-facts/10 text-agent-facts">
              <Icon name="link" className="h-3 w-3" /> 1 citation
            </Badge>
          ) : (
            <Badge testId="no-citation">no citation</Badge>
          )}
          <Badge testId="sentence-count" className={count > 3 ? "border-danger/40 bg-danger/10 text-danger" : undefined}>
            {count} / 3 sentences
          </Badge>
        </div>
      }
    >
      {blocked && (
        <div
          data-testid="blocked-banner"
          className="mb-3 flex items-start gap-2 rounded border border-danger/50 bg-danger/10 px-3 py-2 text-body-sm text-danger"
        >
          <Icon name="alert" className="mt-0.5 h-4 w-4 shrink-0" />
          <span>
            Blocked after the one rework: the draft failed review twice. Highlighted spans are what the reviewer
            flagged. Push back to redraft; approve is not available.
          </span>
        </div>
      )}
      <p data-testid="draft-reply" className="rounded border border-line bg-canvas p-3 text-body-md leading-7 text-ink">
        {replySegments(draft.reply, flagged).map((segment, index) => {
          if (segment.kind === "link") {
            return (
              <a
                key={index}
                href={segment.value}
                target="_blank"
                rel="noreferrer noopener"
                data-testid="draft-link"
                className="rounded border border-agent-facts/30 bg-agent-facts/10 px-1 font-mono text-code-inline text-agent-facts hover:underline"
                title={segment.value}
              >
                {shortUrl(segment.value)}
              </a>
            );
          }
          if (segment.kind === "flagged") {
            return (
              <mark key={index} data-testid="flagged-span" className="rounded bg-danger/25 px-0.5 text-ink ring-1 ring-danger/60">
                {segment.value}
              </mark>
            );
          }
          return <span key={index}>{segment.value}</span>;
        })}
      </p>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 font-mono text-trace-mono text-muted">
        <span>{draft.last_checked ? `Last checked ${draft.last_checked}` : "No fact quoted, so no last-checked date"}</span>
        <span>Facts-only template · no advice · no figures beyond the cited page</span>
      </div>
    </Card>
  );
}

export function ReviewerPanel({ view }: { view: SessionView }) {
  const review = view.session.review;
  if (!review) return null;
  const tone = REVIEW_STATUSES[review.status];
  const source = view.provenance.reviewer;
  const covered = Boolean(view.session.draft?.citation);
  return (
    <Card
      title="Automated reviewer"
      icon="shield"
      testId="reviewer-panel"
      right={
        <Badge testId="reviewer-status" className={`${tone.className} !text-body-sm`}>
          {tone.label.toUpperCase()}
        </Badge>
      }
    >
      <div className="mb-2 flex items-center justify-between font-mono text-trace-mono text-muted">
        <span>Round {review.round} of 2</span>
        {source && (
          <span>
            second opinion: <Badge className={SOURCES[source].className}>{source === "model" ? "Gemini" : "code only"}</Badge>
          </span>
        )}
      </div>
      <ul className="space-y-2">
        {REVIEW_CHECKS.map((check, index) => {
          const failures = review.failures.filter((failure) => failure.check === check);
          const failed = failures.length > 0;
          return (
            <li key={check} data-testid={`check-${check}`} data-failed={failed} className="flex gap-2">
              <Icon
                name={failed ? "x" : "check"}
                className={`mt-0.5 h-4 w-4 shrink-0 ${failed ? "text-danger" : "text-ok"}`}
              />
              <div className="min-w-0">
                <div className={`text-body-sm ${failed ? "text-danger" : "text-ink"}`}>
                  {index + 1}. {CHECK_LABELS[check].title}
                </div>
                {failed ? (
                  failures.map((failure, n) => (
                    <div key={n} className="break-words font-mono text-[11px] text-on-surface-variant">
                      “{failure.detail}”
                    </div>
                  ))
                ) : (
                  <div className="text-body-xs text-muted">
                    {covered ? CHECK_LABELS[check].covered : CHECK_LABELS[check].uncovered}
                  </div>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </Card>
  );
}

export function RoutingCard({ view }: { view: SessionView }) {
  const draft = view.session.draft;
  if (!draft) return null;
  const note = draft.routing_note;
  const open = draft.disposition === "escalate" || draft.disposition === "disagree";
  return (
    <Card
      title="Routing note"
      icon="route"
      testId="routing-card"
      right={
        open ? (
          <Badge testId="ticket-open" className="border-warn/40 bg-warn/10 text-warn">
            Ticket stays open
          </Badge>
        ) : (
          <Label>internal</Label>
        )
      }
    >
      <dl className="space-y-1.5 text-body-sm">
        <div className="flex justify-between gap-3">
          <dt className="text-muted">Team</dt>
          <dd data-testid="routing-team" className="text-right text-ink">
            {note.team}
          </dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-muted">Priority</dt>
          <dd>
            <Badge className={PRIORITIES[note.priority]}>{note.priority}</Badge>
          </dd>
        </div>
      </dl>
      <p data-testid="routing-why" className="mt-2 text-body-xs leading-5 text-on-surface-variant">
        {note.why}
      </p>
    </Card>
  );
}

export function ApproveBar({
  view,
  onApprove,
  approving,
  error,
}: {
  view: SessionView;
  onApprove: () => void;
  approving: boolean;
  error: string | null;
}) {
  if (view.approved) {
    return (
      <div data-testid="approved-note" className="rounded-lg border border-ok/40 bg-ok/10 p-3 text-body-sm text-ink">
        <div className="flex items-center gap-2 font-semibold text-ok">
          <Icon name="check" /> Approved
        </div>
        <p className="mt-1 text-on-surface-variant">
          A redacted record was appended and the email draft <span className="font-mono">{view.approved.email_file}</span>{" "}
          was saved. Nothing was sent.
        </p>
        {view.approved.delivery.doc.status !== "off" && (
          <ul data-testid="delivery" className="mt-2 space-y-1 text-body-xs">
            <DeliveryLine testId="delivery-doc" label="Google Doc" step={view.approved.delivery.doc} done="record appended" />
            <DeliveryLine
              testId="delivery-email"
              label="Gmail"
              step={view.approved.delivery.email}
              done="draft created; review it in Gmail and send it from there"
            />
          </ul>
        )}
        <Link to="/records" className="mt-2 inline-flex items-center gap-1 text-primary hover:underline">
          Open records <Icon name="chevron" className="h-3.5 w-3.5" />
        </Link>
      </div>
    );
  }
  if (view.session.review?.status === "blocked") {
    return (
      <div data-testid="approval-unavailable" className="rounded-lg border border-danger/50 bg-danger/10 p-3 text-body-sm">
        <div className="flex items-center gap-2 font-semibold text-danger">
          <Icon name="lock" /> Approval unavailable: draft failed review twice
        </div>
        <p className="mt-1 text-on-surface-variant">Push back to redraft. A new draft is reviewed afresh.</p>
      </div>
    );
  }
  if (!view.approvable) return null;
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-1.5 text-body-xs text-warn">
        <Icon name="alert" className="h-3.5 w-3.5" /> Human approval required before anything is saved.
      </div>
      <Button
        variant="primary"
        className="h-10 w-full text-body-md"
        onClick={onApprove}
        disabled={approving}
        data-testid="approve-button"
      >
        {approving ? <Spinner /> : <Icon name="check" />} Approve &amp; create email draft
      </Button>
      <p className="text-center text-body-xs text-muted">
        Appends a redacted record and saves an email draft. Nothing is sent.
      </p>
      {error && <p className="text-body-xs text-danger">{error}</p>}
    </div>
  );
}

// One line per MCP step after approve. A failure shows the server's error code only.
function DeliveryLine({ testId, label, step, done }: { testId: string; label: string; step: DeliveryStep; done: string }) {
  const ok = step.status === "done";
  return (
    <li data-testid={testId} data-status={step.status} className={`flex items-start gap-1.5 ${ok ? "text-ok" : "text-warn"}`}>
      <Icon name={ok ? "check" : "alert"} className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <span>
        <span className="font-semibold">{label}:</span> {ok ? done : `not done (${step.error ?? "unknown"})`}
      </span>
    </li>
  );
}
