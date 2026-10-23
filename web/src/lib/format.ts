import type { Disposition, Priority, ReviewStatus, Source } from "../api/types";

export const SCHEME_NAMES: Record<string, string> = {
  large_cap: "HDFC Large Cap Fund Direct Growth",
  mid_cap: "HDFC Mid Cap Fund Direct Growth",
  small_cap: "HDFC Small Cap Fund Direct Growth",
  gold_fof: "HDFC Gold ETF Fund of Fund Direct Plan Growth",
  silver_fof: "HDFC Silver ETF FoF Direct Growth",
};

export function schemeName(id: string | null | undefined): string {
  if (!id) return "—";
  return SCHEME_NAMES[id] ?? id;
}

interface Tone {
  label: string;
  className: string;
}

export const DISPOSITIONS: Record<Disposition, Tone> = {
  reply: { label: "Reply", className: "bg-primary/10 text-primary border-primary/30" },
  escalate: { label: "Escalate", className: "bg-warn/15 text-warn border-warn/40" },
  disagree: { label: "Disagree", className: "bg-agent-pattern/15 text-agent-pattern border-agent-pattern/40" },
  handoff: { label: "Handoff", className: "bg-info/15 text-info border-info/40" },
  refuse: { label: "Refuse", className: "bg-danger/15 text-danger border-danger/40" },
};

export const PRIORITIES: Record<Priority, string> = {
  P1: "bg-danger/15 text-danger border-danger/40",
  P2: "bg-warn/15 text-warn border-warn/40",
  P3: "bg-raised text-muted border-line",
};

export const REVIEW_STATUSES: Record<ReviewStatus, Tone> = {
  pass: { label: "Pass", className: "bg-ok/15 text-ok border-ok/40" },
  fail: { label: "Fail", className: "bg-warn/15 text-warn border-warn/40" },
  blocked: { label: "Blocked", className: "bg-danger/15 text-danger border-danger/40" },
};

export const SOURCES: Record<Source, Tone> = {
  model: { label: "model", className: "bg-primary/10 text-primary border-primary/30" },
  cues: { label: "cues", className: "bg-raised text-muted border-line" },
};

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2026-04-12" → "12 Apr 2026" without time-zone drift. */
export function formatDay(iso: string, withYear = true): string {
  const [year, month, day] = iso.split("-").map(Number);
  if (!year || !month || !day) return iso;
  return `${day} ${MONTHS[month - 1]}${withYear ? ` ${year}` : ""}`;
}

export function windowLabel(window: { start: string; end: string }): string {
  const sameYear = window.start.slice(0, 4) === window.end.slice(0, 4);
  return `${formatDay(window.start, !sameYear)} – ${formatDay(window.end)}`;
}

export function formatDateTime(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return iso;
  return date.toLocaleString(undefined, {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function relativeTime(iso: string, now: number = Date.now()): string {
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const seconds = Math.max(0, Math.round((now - then) / 1000));
  if (seconds < 45) return "just now";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.round(hours / 24)}d ago`;
}

/** "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth" → "groww.in/…/hdfc-large-cap-fund-direct-growth" */
export function shortUrl(url: string): string {
  try {
    const parsed = new URL(url);
    const tail = parsed.pathname.split("/").filter(Boolean).pop();
    return tail ? `${parsed.host}/…/${tail}` : parsed.host;
  } catch {
    return url;
  }
}

export function domain(url: string | null | undefined): string {
  if (!url) return "—";
  try {
    return new URL(url).host;
  } catch {
    return url;
  }
}

const URL_PATTERN = /https?:\/\/\S+/g;
const BOUNDARY = /(?<=[.!?])\s+(?=[A-Z0-9₹(["'])/;

/** Sentences as the reviewer counts them: a link never ends a sentence. */
export function sentenceCount(text: string): number {
  const masked = text.replace(URL_PATTERN, (match) => "x".repeat(match.length));
  return masked.split(BOUNDARY).filter((part) => part.trim()).length;
}

export function shortId(id: string): string {
  return id.length > 10 ? `${id.slice(0, 6)}…${id.slice(-4)}` : id;
}
