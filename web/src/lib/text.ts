// Splitting text for display. Nothing here un-redacts anything: the API only ever
// returns typed tokens such as [PAN], and these helpers render them as pills.

export type Segment =
  | { kind: "text"; value: string }
  | { kind: "token"; value: string }
  | { kind: "link"; value: string }
  | { kind: "flagged"; value: string };

const TOKEN = /\[(PAN|AADHAAR|ACCOUNT|PHONE|EMAIL|OTP)\]/g;
const LINK = /https?:\/\/[^\s<>"')\]]+/g;

/** Split redacted text into plain runs and `[PAN]`-style token pills. */
export function piiSegments(text: string): Segment[] {
  return splitBy(text, TOKEN, (match) => ({ kind: "token", value: match[1] ?? match[0] }));
}

/** Split a reply into text, links, and the reviewer's flagged spans. */
export function replySegments(text: string, flagged: readonly string[] = []): Segment[] {
  const spans = [...new Set(flagged.map((span) => span.trim()).filter((span) => span.length >= 3))];
  const ranges: Array<{ start: number; end: number; kind: "flagged" | "link" }> = [];
  const lower = text.toLowerCase();
  for (const span of spans) {
    let from = 0;
    const needle = span.toLowerCase();
    for (;;) {
      const at = lower.indexOf(needle, from);
      if (at < 0) break;
      ranges.push({ start: at, end: at + needle.length, kind: "flagged" });
      from = at + needle.length;
    }
  }
  for (const match of text.matchAll(LINK)) {
    const value = match[0].replace(/[.,;:!?]+$/, "");
    ranges.push({ start: match.index ?? 0, end: (match.index ?? 0) + value.length, kind: "link" });
  }
  ranges.sort((a, b) => a.start - b.start || b.end - a.end);

  const segments: Segment[] = [];
  let cursor = 0;
  for (const range of ranges) {
    if (range.start < cursor) continue; // overlapping span: the earlier one wins
    if (range.start > cursor) segments.push({ kind: "text", value: text.slice(cursor, range.start) });
    segments.push({ kind: range.kind, value: text.slice(range.start, range.end) });
    cursor = range.end;
  }
  if (cursor < text.length) segments.push({ kind: "text", value: text.slice(cursor) });
  return segments;
}

function splitBy(
  text: string,
  pattern: RegExp,
  make: (match: RegExpMatchArray) => Segment,
): Segment[] {
  const segments: Segment[] = [];
  let cursor = 0;
  for (const match of text.matchAll(pattern)) {
    const at = match.index ?? 0;
    if (at > cursor) segments.push({ kind: "text", value: text.slice(cursor, at) });
    segments.push(make(match));
    cursor = at + match[0].length;
  }
  if (cursor < text.length) segments.push({ kind: "text", value: text.slice(cursor) });
  return segments;
}
