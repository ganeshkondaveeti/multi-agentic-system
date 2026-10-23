import { describe, expect, it } from "vitest";

import { footprint } from "./footprint";
import { sentenceCount, shortUrl, windowLabel } from "./format";
import { piiSegments, replySegments } from "./text";
import { bars } from "./timeline";

describe("footprint mirrors the server's pushback rules", () => {
  it.each([
    ["Shorter", []],
    ["Make it more formal", []],
    ["They're asking about HDFC Gold ETF Fund of Fund", ["facts"]],
    ["wrong fund", ["facts"]],
    ["Check if this is the fee issue from last week", ["pattern"]],
    ["is this a pattern?", ["pattern"]],
    ["It's mid cap and about brokerage", ["facts", "pattern"]],
  ])("%s → %j", (pushback, expected) => {
    expect(footprint(pushback)).toEqual(expected);
  });
});

describe("format", () => {
  it("counts sentences as the reviewer does: a URL never ends one", () => {
    expect(
      sentenceCount(
        "Exit load of 1% if redeemed within 1 year. Last checked 25-Jun-2026. Source: https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
      ),
    ).toBe(3);
  });

  it("labels the review window and shortens URLs", () => {
    expect(windowLabel({ start: "2026-04-12", end: "2026-07-04" })).toBe("12 Apr – 4 Jul 2026");
    expect(shortUrl("https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth")).toBe(
      "groww.in/…/hdfc-large-cap-fund-direct-growth",
    );
  });
});

describe("text segments", () => {
  it("renders PII tokens as their own segments", () => {
    expect(piiSegments("PAN [PAN] and [PHONE].")).toEqual([
      { kind: "text", value: "PAN " },
      { kind: "token", value: "PAN" },
      { kind: "text", value: " and " },
      { kind: "token", value: "PHONE" },
      { kind: "text", value: "." },
    ]);
  });

  it("marks flagged spans and links, dropping trailing punctuation from links", () => {
    const segments = replySegments("You should hold. Source: https://groww.in/x.", ["You should hold"]);
    expect(segments).toEqual([
      { kind: "flagged", value: "You should hold" },
      { kind: "text", value: ". Source: " },
      { kind: "link", value: "https://groww.in/x" },
      { kind: "text", value: "." },
    ]);
  });

  it("ignores reviewer details that are not in the reply", () => {
    expect(replySegments("Fine text.", ["no source_url link in reply"])).toEqual([{ kind: "text", value: "Fine text." }]);
  });
});

describe("timeline bars", () => {
  it("pairs starts and returns per node, including a reviewer that runs twice", () => {
    const list = bars([
      { seq: 0, node: "reviewer", kind: "start", elapsed_ms: 1 },
      { seq: 1, node: "reviewer", kind: "return", elapsed_ms: 2 },
      { seq: 2, node: "rewrite", kind: "start", elapsed_ms: 3 },
      { seq: 3, node: "rewrite", kind: "return", elapsed_ms: 4 },
      { seq: 4, node: "reviewer", kind: "start", elapsed_ms: 5 },
    ]);
    expect(list).toEqual([
      { node: "reviewer", start: 1, end: 2 },
      { node: "rewrite", start: 3, end: 4 },
      { node: "reviewer", start: 5, end: null },
    ]);
  });
});
