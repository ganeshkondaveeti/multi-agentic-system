import type { TraceEvent } from "../api/types";

export const TIMELINE_NODES = [
  "ingress",
  "facts",
  "pattern",
  "compliance",
  "draft",
  "reviewer",
  "rewrite",
] as const;

export interface Bar {
  node: string;
  start: number;
  /** null while the node is still running. */
  end: number | null;
}

/**
 * One bar per node run, from its start event to its matching return. The reviewer
 * runs twice after a rework, so a node can have more than one bar.
 */
export function bars(events: readonly TraceEvent[]): Bar[] {
  const open = new Map<string, Bar[]>();
  const out: Bar[] = [];
  for (const event of [...events].sort((a, b) => a.seq - b.seq)) {
    if (event.kind === "start") {
      const bar: Bar = { node: event.node, start: event.elapsed_ms, end: null };
      out.push(bar);
      open.set(event.node, [...(open.get(event.node) ?? []), bar]);
    } else {
      const pending = open.get(event.node) ?? [];
      const bar = pending.shift();
      if (bar) bar.end = event.elapsed_ms;
    }
  }
  return out;
}

export function span(list: readonly Bar[], now: number): { from: number; to: number } {
  if (list.length === 0) return { from: 0, to: 1 };
  const from = Math.min(...list.map((bar) => bar.start));
  const to = Math.max(now, ...list.map((bar) => bar.end ?? bar.start));
  return { from, to: Math.max(to, from + 1) };
}
