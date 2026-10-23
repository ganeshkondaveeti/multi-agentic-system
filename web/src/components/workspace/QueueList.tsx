import { useState } from "react";
import { Link } from "react-router-dom";

import type { SessionSummary } from "../../api/types";
import { DISPOSITIONS, PRIORITIES, REVIEW_STATUSES, relativeTime, shortId } from "../../lib/format";
import { piiSegments } from "../../lib/text";
import { Badge, Icon, Spinner } from "../ui";

type Filter = "all" | "open" | "approved";

/** Left column: sessions on this desk, newest first. Excerpts are redacted text. */
export function QueueList({
  sessions,
  loading,
  selectedId,
}: {
  sessions: SessionSummary[];
  loading: boolean;
  selectedId: string | undefined;
}) {
  const [filter, setFilter] = useState<Filter>("all");
  const shown = sessions.filter((item) =>
    filter === "all" ? true : filter === "approved" ? item.approved : !item.approved,
  );

  return (
    <aside className="flex min-h-0 flex-col border-line bg-panel xl:border-r" data-testid="queue">
      <div className="border-b border-line p-3">
        <div className="mb-2.5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-headline-sm text-ink">Complaints</span>
            <Badge className="border-line bg-raised text-primary">{sessions.length}</Badge>
          </div>
          <Link
            to="/"
            data-testid="new-complaint"
            className="inline-flex h-7 items-center gap-1 rounded bg-primary-container px-2 text-body-xs font-semibold text-canvas hover:bg-primary"
          >
            <Icon name="plus" className="h-3.5 w-3.5" /> New
          </Link>
        </div>
        <div className="flex gap-1 font-mono text-trace-mono">
          {(["all", "open", "approved"] as const).map((option) => (
            <button
              key={option}
              type="button"
              onClick={() => setFilter(option)}
              className={`rounded px-2 py-1 capitalize ${
                filter === option
                  ? "bg-primary-container font-semibold text-on-primary-container"
                  : "border border-line bg-raised text-on-surface-variant hover:text-ink"
              }`}
            >
              {option}
            </button>
          ))}
        </div>
      </div>
      <div className="flex-1 divide-y divide-line overflow-y-auto scrollbar-thin">
        {loading && (
          <div className="flex items-center gap-2 p-3 text-body-sm text-muted">
            <Spinner /> Loading…
          </div>
        )}
        {!loading && shown.length === 0 && (
          <p className="p-3 text-body-sm text-muted">
            {sessions.length === 0 ? "No complaints yet. Start one on the right." : "Nothing matches this filter."}
          </p>
        )}
        {shown.map((item) => {
          const selected = item.session_id === selectedId;
          return (
            <Link
              key={item.session_id}
              to={`/s/${item.session_id}`}
              data-testid="queue-row"
              data-session={item.session_id}
              className={`block border-l-2 p-3 transition-colors ${
                selected ? "border-primary-container bg-raised" : "border-transparent hover:bg-raised/60"
              }`}
            >
              <div className="mb-1 flex items-center justify-between gap-2 font-mono text-trace-mono">
                <span className={selected ? "font-semibold text-primary" : "text-on-surface-variant"}>
                  {shortId(item.session_id)} · {relativeTime(item.updated_at)}
                </span>
                <span className="flex items-center gap-1">
                  {item.priority && <Badge className={PRIORITIES[item.priority]}>{item.priority}</Badge>}
                  {item.disposition && (
                    <Badge className={DISPOSITIONS[item.disposition].className}>
                      {DISPOSITIONS[item.disposition].label}
                    </Badge>
                  )}
                </span>
              </div>
              <p className="line-clamp-2 text-body-sm text-ink">
                {piiSegments(item.excerpt).map((segment, index) =>
                  segment.kind === "token" ? (
                    <span key={index} className="font-mono text-code-inline text-agent-compliance">
                      [{segment.value}]
                    </span>
                  ) : (
                    <span key={index}>{segment.value}</span>
                  ),
                )}
              </p>
              <div className="mt-1.5 flex flex-wrap gap-1">
                {item.review_status && (
                  <Badge className={REVIEW_STATUSES[item.review_status].className}>
                    {REVIEW_STATUSES[item.review_status].label}
                  </Badge>
                )}
                {item.refinement_count > 0 && <Badge>{item.refinement_count} refine</Badge>}
                {item.advice_refusal && <Badge className="border-warn/40 text-warn">sticky refusal</Badge>}
                {item.approved && (
                  <Badge className="border-ok/40 bg-ok/10 text-ok">
                    <Icon name="check" className="h-3 w-3" /> approved
                  </Badge>
                )}
              </div>
            </Link>
          );
        })}
      </div>
    </aside>
  );
}
