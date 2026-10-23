import { useState, type FormEvent } from "react";

import type { SessionView } from "../../api/types";
import { footprint } from "../../lib/footprint";
import { Badge, Button, Card, Icon, Spinner } from "../ui";

const CHIPS = [
  { label: "Shorter", text: "Shorter" },
  { label: "Different scheme", text: "They're asking about HDFC Gold ETF Fund of Fund" },
  { label: "Check fee issue from last week", text: "Check if this is the fee issue from last week" },
];

const DOT: Record<string, string> = {
  facts: "bg-agent-facts",
  pattern: "bg-agent-pattern",
  orchestrator: "bg-primary-container",
};

/**
 * The Stitch "Refine Draft" panel. The text stays in this component until it is
 * sent, then the box is cleared; it is never stored. The footprint line previews
 * which agents the server will re-run.
 */
export function RefinePanel({
  view,
  running,
  onRefine,
}: {
  view: SessionView;
  running: boolean;
  onRefine: (pushback: string) => void;
}) {
  const [text, setText] = useState("");
  const left = view.refinements_left;
  const used = 5 - left;
  const closed = view.approved !== null;
  const exhausted = left <= 0;
  const reruns = [...footprint(text), "orchestrator"];

  function submit(event: FormEvent) {
    event.preventDefault();
    const pushback = text.trim();
    if (!pushback || running || exhausted || closed) return;
    setText("");
    onRefine(pushback);
  }

  return (
    <Card
      title="Refine draft"
      icon="refresh"
      testId="refine-panel"
      right={
        <Badge testId="refine-counter" className={exhausted ? "border-danger/40 bg-danger/10 text-danger" : undefined}>
          Refinements {used} / 5
        </Badge>
      }
    >
      {exhausted ? (
        <div data-testid="refine-limit" className="space-y-2">
          <div className="flex items-start gap-2 rounded border border-line bg-canvas p-2 text-body-sm text-on-surface-variant">
            <Icon name="lock" className="mt-0.5 h-4 w-4 shrink-0 text-muted" />
            Refinement limit reached, last reviewed draft kept.
          </div>
          <input
            disabled
            aria-label="Pushback"
            className="h-8 w-full cursor-not-allowed rounded border border-line bg-canvas px-2 text-body-sm text-outline"
            placeholder="Further refinement disabled (5/5 used)"
          />
        </div>
      ) : closed ? (
        <p className="text-body-sm text-muted">This session is approved. Start a new complaint to continue.</p>
      ) : (
        <form onSubmit={submit} className="space-y-2">
          <textarea
            data-testid="refine-input"
            aria-label="Pushback"
            value={text}
            onChange={(event) => setText(event.target.value)}
            rows={2}
            maxLength={2000}
            placeholder="Tell the orchestrator what to change…"
            className="w-full resize-none rounded border border-line bg-canvas px-2 py-1.5 text-body-sm text-ink placeholder:text-outline focus:border-primary-container focus:outline-none"
          />
          <div className="flex flex-wrap gap-1">
            {CHIPS.map((chip) => (
              <button
                key={chip.label}
                type="button"
                onClick={() => setText(chip.text)}
                className="rounded border border-line px-2 py-0.5 text-body-xs text-on-surface-variant hover:border-outline hover:text-ink"
              >
                + {chip.label}
              </button>
            ))}
          </div>
          <div className="flex items-center justify-between gap-2">
            <span data-testid="refine-footprint" className="flex items-center gap-1.5 text-body-xs text-muted">
              <span className="flex gap-0.5">
                {reruns.map((node) => (
                  <span key={node} className={`h-2 w-2 rounded-full ${DOT[node]}`} />
                ))}
              </span>
              Re-runs: {reruns.join(" → ")}
            </span>
            <Button type="submit" variant="primary" disabled={running || !text.trim()} data-testid="refine-run">
              {running ? <Spinner /> : <Icon name="play" className="h-3.5 w-3.5" />} Run
            </Button>
          </div>
        </form>
      )}
    </Card>
  );
}
