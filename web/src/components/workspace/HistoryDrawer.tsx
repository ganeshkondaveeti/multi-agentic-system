import { useEffect } from "react";

import type { AgentsFired, SessionView } from "../../api/types";
import { shortId } from "../../lib/format";
import { Badge, Button, Icon } from "../ui";

const RAN: Record<string, string> = {
  facts: "border-agent-facts/40 bg-agent-facts/10 text-agent-facts",
  pattern: "border-agent-pattern/40 bg-agent-pattern/10 text-agent-pattern",
  compliance: "border-agent-compliance/40 bg-agent-compliance/10 text-agent-compliance",
  orchestrator: "border-primary/40 bg-primary/10 text-primary",
};

/** The Stitch "Refinement history" slide-over: one entry per `agents_fired` item. */
export function HistoryDrawer({ view, onClose }: { view: SessionView; onClose: () => void }) {
  const entries = view.session.agents_fired;
  const used = 5 - view.refinements_left;

  useEffect(() => {
    const close = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", close);
    return () => window.removeEventListener("keydown", close);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label="Refinement history">
      <button type="button" aria-label="Close history" className="absolute inset-0 bg-canvas/70" onClick={onClose} />
      <aside
        data-testid="history-drawer"
        className="relative flex h-full w-full max-w-xl flex-col border-l border-line bg-surface-container-low shadow-[0_4px_12px_rgba(0,0,0,0.45)]"
      >
        <header className="border-b border-line p-4">
          <div className="flex items-center justify-between">
            <h2 className="flex items-center gap-2 text-headline-lg text-ink">
              <Icon name="history" className="h-5 w-5 text-primary" /> Refinement history
            </h2>
            <Button variant="ghost" onClick={onClose} aria-label="Close" className="h-8 w-8 px-0">
              <Icon name="close" />
            </Button>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-body-sm">
            <Badge className="border-primary/40 text-primary">{shortId(view.session_id)}</Badge>
            <Badge testId="history-count" className={used >= 5 ? "border-danger/40 bg-danger/10 text-danger" : undefined}>
              {used} / 5 refinements{used >= 5 ? " (max reached)" : ""}
            </Badge>
          </div>
          <p className="mt-2 text-body-sm text-muted">
            Which agents ran on each human pushback and each reviewer rework. Skipped agents kept their earlier
            result.
          </p>
        </header>

        <ol className="flex-1 space-y-3 overflow-y-auto p-4 scrollbar-thin">
          <li className="rounded-lg border border-line bg-panel p-3">
            <div className="flex items-center gap-2 text-headline-sm text-ink">
              <span className="flex h-6 w-6 items-center justify-center rounded-full border border-primary font-mono text-[10px] text-primary">
                R0
              </span>
              Initial complaint
            </div>
            <div className="mt-2 flex flex-wrap gap-1">
              {["facts", "pattern", "compliance", "orchestrator"].map((agent) => (
                <Badge key={agent} className={RAN[agent]}>
                  {agent}
                </Badge>
              ))}
            </div>
          </li>
          {entries.length === 0 && (
            <li className="text-body-sm text-muted" data-testid="history-empty">
              No pushbacks or reworks yet.
            </li>
          )}
          {entries.map((entry, index) => (
            <HistoryEntry key={index} entry={entry} />
          ))}
        </ol>

        {view.refinements_left <= 0 && (
          <footer className="border-t border-line p-4">
            <div className="flex items-center gap-2 text-body-sm text-ink">
              <Icon name="lock" className="h-4 w-4 text-muted" /> Refinement limit reached, last reviewed draft kept
            </div>
            <input
              disabled
              aria-label="Further refinement disabled"
              placeholder="Further refinement disabled (5/5 used)"
              className="mt-2 h-8 w-full cursor-not-allowed rounded border border-line bg-canvas px-2 text-body-sm"
            />
          </footer>
        )}
      </aside>
    </div>
  );
}

function HistoryEntry({ entry }: { entry: AgentsFired }) {
  const rework = entry.kind === "reviewer_rework";
  return (
    <li
      data-testid="history-entry"
      data-kind={entry.kind}
      data-round={entry.round}
      className={`rounded-lg p-3 ${
        rework ? "border border-dashed border-warn/60 bg-warn/5" : "border border-line bg-panel"
      }`}
    >
      <div className="flex items-center gap-2 text-headline-sm">
        <span
          className={`flex h-6 w-6 items-center justify-center rounded-full border font-mono text-[10px] ${
            rework ? "border-warn text-warn" : "border-secondary text-secondary"
          }`}
        >
          R{entry.round}
        </span>
        <span className={rework ? "text-warn" : "text-ink"}>
          {rework ? "Reviewer rework: orchestrator only" : `Refinement ${entry.round}`}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1">
        <span className="mr-1 font-mono text-[10px] uppercase text-muted">Ran</span>
        {entry.ran.map((agent) => (
          <Badge key={agent} testId="ran-chip" className={RAN[agent]}>
            <span data-agent={agent}>{agent}</span>
          </Badge>
        ))}
      </div>
      <div className="mt-1 flex flex-wrap items-center gap-1">
        <span className="mr-1 font-mono text-[10px] uppercase text-muted">Skipped</span>
        {entry.skipped.length === 0 ? (
          <span className="text-body-xs text-muted">none</span>
        ) : (
          entry.skipped.map((agent) => (
            <Badge key={agent} testId="skipped-chip" className="border-line bg-transparent text-outline line-through">
              <span data-agent={agent}>{agent}</span>
            </Badge>
          ))
        )}
      </div>
    </li>
  );
}
