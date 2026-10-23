import { useEffect, useState } from "react";

import type { TraceEvent } from "../../api/types";
import { TIMELINE_NODES, bars, span } from "../../lib/timeline";
import { Card, Label } from "../ui";

const COLORS: Record<string, string> = {
  ingress: "bg-outline",
  facts: "bg-agent-facts",
  pattern: "bg-agent-pattern",
  compliance: "bg-agent-compliance",
  draft: "bg-primary-container",
  reviewer: "bg-ok",
  rewrite: "bg-warn",
};

const TEXT: Record<string, string> = {
  facts: "text-agent-facts",
  pattern: "text-agent-pattern",
  compliance: "text-agent-compliance",
  draft: "text-primary",
  reviewer: "text-ok",
  rewrite: "text-warn",
};

/**
 * The Stitch "Execution Trace Timeline". Bars come from the trace's start and return
 * events; while a turn streams, open bars grow until their return arrives.
 */
export function TraceTimeline({ events, running }: { events: readonly TraceEvent[]; running: boolean }) {
  // Milliseconds since the latest event arrived, ticking while the turn streams.
  const [sinceLatest, setSinceLatest] = useState(0);

  useEffect(() => {
    if (!running) return;
    const arrivedAt = performance.now();
    const timer = window.setInterval(() => setSinceLatest(performance.now() - arrivedAt), 60);
    return () => window.clearInterval(timer);
  }, [running, events.length]);

  const list = bars(events);
  const latest = events.reduce((max, event) => Math.max(max, event.elapsed_ms), 0);
  const now = running ? latest + sinceLatest : latest;
  const { from, to } = span(list, now);
  const scale = (value: number) => ((value - from) / (to - from)) * 100;
  const rows = TIMELINE_NODES.filter((node) => node !== "rewrite" || list.some((bar) => bar.node === node));
  const agentStarts = list.filter((bar) => ["facts", "pattern", "compliance"].includes(bar.node));

  return (
    <Card
      title="Execution trace"
      icon="timeline"
      testId="trace-timeline"
      right={
        <span className="font-mono text-trace-mono text-primary" data-testid="trace-total">
          {running ? "streaming…" : `${(to - from).toFixed(1)} ms total`}
        </span>
      }
    >
      {events.length === 0 ? (
        <p className="text-body-sm text-muted">No trace yet.</p>
      ) : (
        <div className="space-y-1.5">
          {rows.map((node) => {
            const nodeBars = list.filter((bar) => bar.node === node);
            return (
              <div key={node} className="grid grid-cols-[96px_1fr] items-center gap-3">
                <span className={`font-mono text-trace-mono ${TEXT[node] ?? "text-muted"}`}>
                  {node}
                  {nodeBars.length === 0 && <span className="ml-1 text-outline">skipped</span>}
                </span>
                <div className="relative h-3 rounded-sm bg-canvas">
                  {nodeBars.map((bar, index) => {
                    const end = bar.end ?? now;
                    return (
                      <span
                        key={index}
                        data-testid="trace-bar"
                        data-node={bar.node}
                        data-start={bar.start}
                        data-end={bar.end ?? ""}
                        title={`${bar.node}: ${bar.start.toFixed(1)}–${end.toFixed(1)} ms`}
                        className={`absolute top-0 h-3 rounded-sm ${COLORS[node] ?? "bg-outline"} ${bar.end === null ? "animate-pulse" : ""}`}
                        style={{ left: `${scale(bar.start)}%`, width: `${Math.max(scale(end) - scale(bar.start), 1.2)}%` }}
                      />
                    );
                  })}
                </div>
              </div>
            );
          })}
          <div className="flex justify-between pt-1 font-mono text-[10px] text-muted">
            <Label className="!text-[10px]">T+0 ingress</Label>
            {agentStarts.length > 0 && (
              <span>
                {agentStarts.length} agent{agentStarts.length > 1 ? "s" : ""} started by T+
                {Math.max(...agentStarts.map((bar) => bar.start)).toFixed(1)} ms
              </span>
            )}
          </div>
        </div>
      )}
    </Card>
  );
}
