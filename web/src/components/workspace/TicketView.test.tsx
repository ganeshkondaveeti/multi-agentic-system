import { fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { SessionView } from "../../api/types";
import { RAW_PAN, RAW_PHONE, api, renderWith } from "../../test/render";
import { TicketView } from "./TicketView";

function show(view: SessionView, overrides: Partial<Parameters<typeof TicketView>[0]> = {}) {
  const handlers = {
    onRefine: vi.fn(),
    onMessage: vi.fn(),
    onReplace: vi.fn(),
    onApprove: vi.fn(),
  };
  const result = renderWith(
    <TicketView
      view={view}
      liveTrace={null}
      running={false}
      turnError={null}
      approving={false}
      approveError={null}
      {...handlers}
      {...overrides}
    />,
  );
  return { ...result, handlers };
}

describe("TicketView states from real API responses", () => {
  it("clean hit: escalate, one citation, the source link, approve offered, ticket stays open", () => {
    show(api.views.clean_hit);
    expect(screen.getByTestId("disposition")).toHaveTextContent("Escalate");
    expect(screen.getByTestId("citation")).toBeInTheDocument();
    expect(screen.getByTestId("draft-link")).toHaveAttribute(
      "href",
      "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth",
    );
    expect(screen.getByTestId("facts-status")).toHaveTextContent("Covered");
    expect(screen.getByTestId("ticket-open")).toBeInTheDocument();
    expect(screen.getByTestId("approve-button")).toBeEnabled();
    expect(screen.queryByTestId("sticky-refusal")).not.toBeInTheDocument();
    expect(screen.getByTestId("provenance-facts")).toHaveTextContent("cues");
  });

  it("refuse: no citation, no link, the sticky badge, and the advice flag lit", () => {
    show(api.views.refuse);
    expect(screen.getByTestId("disposition")).toHaveTextContent("Refuse");
    expect(screen.getByTestId("no-citation")).toBeInTheDocument();
    expect(screen.queryByTestId("citation")).not.toBeInTheDocument();
    expect(screen.queryByTestId("draft-link")).not.toBeInTheDocument();
    expect(screen.getByTestId("sticky-refusal")).toBeInTheDocument();
    expect(screen.getByTestId("flag-advice")).toHaveAttribute("data-active", "true");
  });

  it("handoff: not covered, the searched grid, and no URL anywhere in the draft", () => {
    show(api.views.corpus_miss);
    expect(screen.getByTestId("disposition")).toHaveTextContent("Handoff");
    expect(screen.getByTestId("facts-status")).toHaveTextContent("Not covered");
    expect(screen.getByTestId("searched-grid")).toHaveTextContent("SEARCHED 5 SCHEMES × 7 SECTIONS");
    expect(screen.queryByTestId("draft-link")).not.toBeInTheDocument();
    expect(screen.getByTestId("draft-reply").textContent).not.toMatch(/https?:/);
  });

  it("blocked: no approve, the unavailable panel, flagged spans, and the failed check", () => {
    show(api.views.blocked);
    expect(screen.queryByTestId("approve-button")).not.toBeInTheDocument();
    expect(screen.getByTestId("approval-unavailable")).toHaveTextContent(
      "Approval unavailable: draft failed review twice",
    );
    expect(screen.getByTestId("blocked-banner")).toBeInTheDocument();
    expect(screen.getAllByTestId("flagged-span").length).toBeGreaterThan(0);
    expect(screen.getByTestId("check-advice")).toHaveAttribute("data-failed", "true");
    expect(screen.getByTestId("check-pii")).toHaveAttribute("data-failed", "false");
    expect(screen.getByTestId("refine-input")).toBeEnabled();
  });

  it("disagree: the banner names the rising theme and its recent count", () => {
    show(api.views.disagree);
    const pattern = api.views.disagree.session.pattern!;
    expect(screen.getByTestId("disposition")).toHaveTextContent("Disagree");
    expect(screen.getByTestId("disagree-banner")).toHaveTextContent(String(pattern.recent_count));
    expect(screen.getByTestId("pattern-signal")).toHaveTextContent("rising");
  });

  it("recurring theme: fees_brokerage with 136 reviews", () => {
    show(api.views.recurring_theme);
    expect(screen.getByTestId("pattern-theme")).toHaveTextContent("Fees & brokerage");
    expect(screen.getByTestId("pattern-count")).toHaveTextContent("136");
    expect(screen.getByTestId("routing-team")).toHaveTextContent("Fees and mutual fund ops");
  });

  it("PII: tokens render as pills and no raw value is ever on screen", () => {
    const { container } = show(api.views.pii);
    const pills = screen.getAllByTestId("pii-token").map((pill) => pill.textContent);
    expect(pills).toEqual(["[PAN]", "[PHONE]"]);
    expect(screen.getByTestId("flag-pii")).toHaveAttribute("data-active", "true");
    expect(container.textContent).not.toContain(RAW_PAN);
    expect(container.textContent).not.toContain(RAW_PHONE);
  });

  it("approved: the approved note replaces approve, and refinement is closed", () => {
    show(api.views.approved);
    expect(screen.queryByTestId("approve-button")).not.toBeInTheDocument();
    expect(screen.getByTestId("approved-note")).toHaveTextContent("Nothing was sent.");
    expect(screen.queryByTestId("refine-input")).not.toBeInTheDocument();
  });

  it("five refinements: the counter is full and the input is disabled", () => {
    show(api.views.exhausted);
    expect(screen.getByTestId("refine-counter")).toHaveTextContent("Refinements 5 / 5");
    expect(screen.getByTestId("refine-limit")).toHaveTextContent(
      "Refinement limit reached, last reviewed draft kept.",
    );
    expect(screen.queryByTestId("refine-run")).not.toBeInTheDocument();
  });
});

describe("history drawer", () => {
  it("lists one entry per agents_fired item with ran and skipped chips", async () => {
    show(api.views.refined);
    await userEvent.click(screen.getByTestId("history-button"));

    const entries = within(screen.getByTestId("history-drawer")).getAllByTestId("history-entry");
    expect(entries).toHaveLength(3);
    const ran = entries.map((entry) => within(entry).getAllByTestId("ran-chip").map((chip) => chip.textContent));
    expect(ran).toEqual([["orchestrator"], ["facts", "orchestrator"], ["pattern", "orchestrator"]]);
    const skipped = entries.map((entry) =>
      within(entry).getAllByTestId("skipped-chip").map((chip) => chip.textContent),
    );
    expect(skipped).toEqual([
      ["facts", "pattern", "compliance"],
      ["pattern", "compliance"],
      ["facts", "compliance"],
    ]);
  });

  it("shows a reviewer rework as a dashed round-0 entry", async () => {
    show(api.views.blocked);
    await userEvent.click(screen.getByTestId("history-button"));
    const [entry] = screen.getAllByTestId("history-entry");
    expect(entry).toHaveAttribute("data-kind", "reviewer_rework");
    expect(entry).toHaveAttribute("data-round", "0");
    expect(entry).toHaveTextContent("Reviewer rework: orchestrator only");
  });

  it("closes on Escape", async () => {
    show(api.views.refined);
    await userEvent.click(screen.getByTestId("history-button"));
    fireEvent.keyDown(window, { key: "Escape" });
    expect(screen.queryByTestId("history-drawer")).not.toBeInTheDocument();
  });
});

describe("inputs", () => {
  it("a pushback previews its re-runs, is sent, and the box is cleared", async () => {
    const { handlers } = show(api.views.clean_hit);
    const input = screen.getByTestId("refine-input");

    await userEvent.type(input, "They're asking about HDFC Gold ETF Fund of Fund");
    expect(screen.getByTestId("refine-footprint")).toHaveTextContent("Re-runs: facts → orchestrator");
    await userEvent.click(screen.getByTestId("refine-run"));

    expect(handlers.onRefine).toHaveBeenCalledWith("They're asking about HDFC Gold ETF Fund of Fund");
    expect(input).toHaveValue("");
  });

  it("Shorter re-runs only the orchestrator", async () => {
    show(api.views.clean_hit);
    await userEvent.type(screen.getByTestId("refine-input"), "Shorter");
    expect(screen.getByTestId("refine-footprint")).toHaveTextContent("Re-runs: orchestrator");
  });

  it("a new customer message is sent and cleared", async () => {
    const { handlers } = show(api.views.refuse);
    const input = screen.getByTestId("message-input");
    await userEvent.type(input, "Is it worth it?");
    await userEvent.click(screen.getByTestId("message-submit"));
    expect(handlers.onMessage).toHaveBeenCalledWith("Is it worth it?");
    expect(input).toHaveValue("");
  });

  it("approve calls back once", async () => {
    const { handlers } = show(api.views.clean_hit);
    await userEvent.click(screen.getByTestId("approve-button"));
    expect(handlers.onApprove).toHaveBeenCalledTimes(1);
  });
});

describe("trace timeline", () => {
  it("draws one bar per node run, with three agents starting before any returns", () => {
    show(api.views.clean_hit);
    const bars = screen.getAllByTestId("trace-bar");
    const agent = bars.filter((bar) => ["facts", "pattern", "compliance"].includes(bar.dataset.node ?? ""));
    expect(agent).toHaveLength(3);
    const latestStart = Math.max(...agent.map((bar) => Number(bar.dataset.start)));
    const earliestEnd = Math.min(...agent.map((bar) => Number(bar.dataset.end)));
    expect(latestStart).toBeLessThan(earliestEnd);
  });

  it("a Shorter turn shows no agent bars", () => {
    const shorter: SessionView = {
      ...api.views.clean_hit,
      trace: api.views.clean_hit.trace.filter((event) => !["facts", "pattern", "compliance"].includes(event.node)),
    };
    show(shorter);
    const nodes = screen.getAllByTestId("trace-bar").map((bar) => bar.dataset.node);
    expect(nodes).not.toContain("facts");
    expect(nodes).toContain("reviewer");
  });

  it("while streaming, an agent that started but has not returned shows a spinner", () => {
    const live = api.views.clean_hit.trace.filter((event) => event.seq <= 4); // ingress + three starts
    show(api.views.clean_hit, { running: true, liveTrace: live });
    expect(screen.getByTestId("turn-running")).toBeInTheDocument();
    expect(screen.getByTestId("agent-facts-running")).toBeInTheDocument();
    const open = screen.getAllByTestId("trace-bar").filter((bar) => bar.dataset.end === "");
    expect(open.map((bar) => bar.dataset.node).sort()).toEqual(["compliance", "facts", "pattern"]);
  });
});
