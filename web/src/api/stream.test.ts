import { afterEach, describe, expect, it, vi } from "vitest";

import { clearAccessCode, setAccessCode } from "./access";
import { ApiError } from "./client";
import { parseSse, streamTurn } from "./stream";
import type { TraceEvent } from "./types";

function sseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { "Content-Type": "text/event-stream" } });
}

const trace = (seq: number, node: string, kind: "start" | "return") =>
  `event: trace\ndata: ${JSON.stringify({ seq, node, kind, elapsed_ms: seq })}\n\n`;

afterEach(() => {
  vi.unstubAllGlobals();
  clearAccessCode();
});

describe("parseSse", () => {
  it("returns whole events, skips heartbeats, and keeps the unfinished tail", () => {
    const { events, rest } = parseSse(
      `: heartbeat\n\n${trace(0, "ingress", "start")}event: result\ndata: {"ok": tr`,
    );
    expect(events).toEqual([
      { event: "trace", data: { seq: 0, node: "ingress", kind: "start", elapsed_ms: 0 } },
    ]);
    expect(rest).toBe('event: result\ndata: {"ok": tr');
  });

  it("handles CRLF line endings", () => {
    const { events } = parseSse('event: error\r\ndata: {"error": "x"}\r\n\r\n');
    expect(events).toEqual([{ event: "error", data: { error: "x" } }]);
  });
});

describe("streamTurn", () => {
  it("reports trace events in order across chunk boundaries, then resolves the result", async () => {
    const body = [trace(0, "ingress", "start"), trace(1, "ingress", "return"), 'event: result\ndata: {"session_id": "abc"}\n\n'].join("");
    const fetchMock = vi.fn().mockResolvedValue(sseResponse([body.slice(0, 30), body.slice(30, 90), body.slice(90)]));
    vi.stubGlobal("fetch", fetchMock);
    const seen: TraceEvent[] = [];

    const view = await streamTurn({ kind: "complaint", complaint: "hello" }, (event) => seen.push(event));

    expect(view).toEqual({ session_id: "abc" });
    expect(seen.map((event) => `${event.kind}:${event.node}`)).toEqual(["start:ingress", "return:ingress"]);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/api/sessions");
    expect(init.method).toBe("POST");
    expect(init.headers.Accept).toBe("text/event-stream");
    expect(JSON.parse(init.body)).toEqual({ complaint: "hello" });
  });

  it("an error event becomes an ApiError with its code", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(sseResponse(['event: error\ndata: {"error": "internal_error", "message": "The turn failed."}\n\n'])),
    );
    await expect(streamTurn({ kind: "refine", sessionId: "s1", pushback: "Shorter" }, () => {})).rejects.toMatchObject({
      code: "internal_error",
      message: "The turn failed.",
    });
  });

  it("a 409 before the stream is an ApiError with the server's code", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: "refinement_refused", message: "Refinement limit reached." }), {
          status: 409,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
    const failure = await streamTurn({ kind: "refine", sessionId: "s1", pushback: "Shorter" }, () => {}).catch(
      (error: unknown) => error,
    );
    expect(failure).toBeInstanceOf(ApiError);
    expect(failure).toMatchObject({ status: 409, code: "refinement_refused" });
  });

  it("sends the access code and routes each kind to its path", async () => {
    setAccessCode("s3cret");
    const fetchMock = vi.fn().mockImplementation(async () => sseResponse(['event: result\ndata: {"session_id": "s1"}\n\n']));
    vi.stubGlobal("fetch", fetchMock);

    await streamTurn({ kind: "message", sessionId: "s1", message: "hi" }, () => {});
    await streamTurn({ kind: "replace", sessionId: "s1", complaint: "new" }, () => {});

    expect(fetchMock.mock.calls.map(([url]) => url)).toEqual(["/api/sessions/s1/messages", "/api/sessions/s1/replace"]);
    expect(fetchMock.mock.calls[0]![1].headers["X-Access-Code"]).toBe("s3cret");
  });

  it("a stream that ends without a result is an error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(sseResponse([trace(0, "ingress", "start")])));
    await expect(streamTurn({ kind: "complaint", complaint: "x" }, () => {})).rejects.toMatchObject({ code: "stream_ended" });
  });

  it("a 401 clears the stored access code", async () => {
    setAccessCode("old");
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: "access_code_required", message: "no" }), { status: 401 })),
    );
    await expect(streamTurn({ kind: "complaint", complaint: "x" }, () => {})).rejects.toMatchObject({ status: 401 });
    expect(sessionStorage.getItem("reply-desk.access-code")).toBeNull();
  });
});
