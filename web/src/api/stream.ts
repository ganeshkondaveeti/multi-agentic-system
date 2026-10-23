import { ApiError, apiUrl, requestHeaders, toApiError } from "./client";
import type { SessionView, TraceEvent } from "./types";

// The four turn routes stream server-sent events when asked. EventSource only does
// GET, so the POST response body is read as a stream and parsed here.

export type TurnRequest =
  | { kind: "complaint"; complaint: string }
  | { kind: "refine"; sessionId: string; pushback: string }
  | { kind: "message"; sessionId: string; message: string }
  | { kind: "replace"; sessionId: string; complaint: string };

export interface SseEvent {
  event: string;
  data: unknown;
}

/** Split a buffer into complete events and the unfinished tail. Comments are dropped. */
export function parseSse(buffer: string): { events: SseEvent[]; rest: string } {
  const normalized = buffer.replace(/\r\n/g, "\n");
  const blocks = normalized.split("\n\n");
  const rest = blocks.pop() ?? "";
  const events: SseEvent[] = [];
  for (const block of blocks) {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (!line || line.startsWith(":")) continue;
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
    }
    if (data.length === 0) continue;
    try {
      events.push({ event, data: JSON.parse(data.join("\n")) });
    } catch {
      // A malformed event is ignored; the stream still has to end with result or error.
    }
  }
  return { events, rest };
}

function target(turn: TurnRequest): { path: string; body: Record<string, string> } {
  switch (turn.kind) {
    case "complaint":
      return { path: "/sessions", body: { complaint: turn.complaint } };
    case "refine":
      return { path: `/sessions/${encodeURIComponent(turn.sessionId)}/refine`, body: { pushback: turn.pushback } };
    case "message":
      return { path: `/sessions/${encodeURIComponent(turn.sessionId)}/messages`, body: { message: turn.message } };
    case "replace":
      return { path: `/sessions/${encodeURIComponent(turn.sessionId)}/replace`, body: { complaint: turn.complaint } };
  }
}

/** Run one turn, calling `onTrace` for each node start and return as it happens. */
export async function streamTurn(
  turn: TurnRequest,
  onTrace: (event: TraceEvent) => void,
  signal?: AbortSignal,
): Promise<SessionView> {
  const { path, body } = target(turn);
  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      method: "POST",
      headers: requestHeaders({ "Content-Type": "application/json", Accept: "text/event-stream" }),
      body: JSON.stringify(body),
      signal,
    });
  } catch {
    throw new ApiError(0, "network_error", "The API is unreachable.");
  }
  if (!response.ok) throw await toApiError(response);
  if (!(response.headers.get("content-type") ?? "").includes("text/event-stream") || !response.body) {
    return (await response.json()) as SessionView;
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { done, value } = await reader.read();
    buffer += decoder.decode(value ?? new Uint8Array(), { stream: !done });
    const parsed = parseSse(done ? `${buffer}\n\n` : buffer);
    buffer = parsed.rest;
    for (const { event, data } of parsed.events) {
      if (event === "trace") onTrace(data as TraceEvent);
      else if (event === "result") return data as SessionView;
      else if (event === "error") {
        const failure = data as { error?: string; message?: string };
        throw new ApiError(500, failure.error ?? "turn_failed", failure.message ?? "The turn failed.");
      }
    }
    if (done) throw new ApiError(0, "stream_ended", "The stream ended before a result.");
  }
}
