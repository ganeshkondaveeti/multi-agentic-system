import { useState } from "react";

import type { SessionView, TraceEvent } from "../../api/types";
import { ErrorNote, Label, Spinner } from "../ui";
import { ComplianceCard, FactsCard, PatternCard } from "./AgentCards";
import { MessageInput } from "./Composer";
import { HistoryDrawer } from "./HistoryDrawer";
import { RefinePanel } from "./RefinePanel";
import {
  ApproveBar,
  ComplaintCard,
  DisagreeBanner,
  DraftCard,
  ReviewerPanel,
  RoutingCard,
  TicketHeader,
} from "./TicketCards";
import { TraceTimeline } from "./TraceTimeline";

export interface TicketViewProps {
  view: SessionView;
  /** Trace events of the turn in flight on this session, or null when idle. */
  liveTrace: TraceEvent[] | null;
  running: boolean;
  turnError: string | null;
  onRefine: (pushback: string) => void;
  onMessage: (message: string) => void;
  onReplace: (complaint: string) => void;
  onApprove: () => void;
  approving: boolean;
  approveError: string | null;
}

/**
 * One session: the Stitch workspace's center and right columns. Every state variant
 * (refuse, handoff, blocked, disagree) is this same view with different data.
 */
export function TicketView({
  view,
  liveTrace,
  running,
  turnError,
  onRefine,
  onMessage,
  onReplace,
  onApprove,
  approving,
  approveError,
}: TicketViewProps) {
  const [historyOpen, setHistoryOpen] = useState(false);
  const { session } = view;
  const events = running && liveTrace ? liveTrace : view.trace;
  const inFlight = (agent: string) =>
    running &&
    (liveTrace ?? []).some((event) => event.node === agent && event.kind === "start") &&
    !(liveTrace ?? []).some((event) => event.node === agent && event.kind === "return");

  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]" data-testid="ticket">
      <div className="min-w-0 space-y-4">
        <TicketHeader view={view} onOpenHistory={() => setHistoryOpen(true)} />
        {running && (
          <div data-testid="turn-running" className="flex items-center gap-2 text-body-sm text-primary">
            <Spinner /> Running the turn: watch the trace below.
          </div>
        )}
        {turnError && <ErrorNote message={turnError} testId="turn-error" />}
        <DisagreeBanner view={view} />
        <ComplaintCard view={view} />

        <section>
          <div className="mb-2 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <span className="text-headline-sm uppercase tracking-wide text-ink">Agent analysis</span>
              <span className="flex items-center gap-1 rounded-full border border-primary/30 bg-primary/10 px-2 py-0.5 font-mono text-[10px] text-primary">
                <span className={`h-1.5 w-1.5 rounded-full bg-primary ${running ? "animate-pulse" : ""}`} />
                {running ? "Running in parallel" : "Started in parallel"}
              </span>
            </div>
            <Label>three nodes, started together, no shared inputs</Label>
          </div>
          <div className="grid gap-3 lg:grid-cols-3">
            {session.facts && (
              <FactsCard facts={session.facts} source={view.provenance.facts} running={inFlight("facts")} />
            )}
            {session.pattern && (
              <PatternCard pattern={session.pattern} source={view.provenance.pattern} running={inFlight("pattern")} />
            )}
            {session.compliance && (
              <ComplianceCard
                compliance={session.compliance}
                source={view.provenance.compliance}
                running={inFlight("compliance")}
              />
            )}
          </div>
        </section>

        <DraftCard view={view} />
        <TraceTimeline events={events} running={running} />
        <MessageInput view={view} running={running} onMessage={onMessage} onReplace={onReplace} />
      </div>

      <div className="space-y-4">
        <ReviewerPanel view={view} />
        <RoutingCard view={view} />
        <RefinePanel view={view} running={running} onRefine={onRefine} />
        <ApproveBar view={view} onApprove={onApprove} approving={approving} error={approveError} />
      </div>

      {historyOpen && <HistoryDrawer view={view} onClose={() => setHistoryOpen(false)} />}
    </div>
  );
}
