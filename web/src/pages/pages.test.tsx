import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { clearAccessCode } from "../api/access";
import { keys } from "../api/hooks";
import { Shell } from "../components/Shell";
import { RAW_PAN, api, renderWith } from "../test/render";
import { AcceptancePage } from "./Acceptance";
import { RecordsPage } from "./Records";

afterEach(() => {
  vi.unstubAllGlobals();
  clearAccessCode();
});

describe("Records page", () => {
  it("lists records, counts them, and opens the email draft marked not sent", async () => {
    const [first] = api.records;
    const { container } = renderWith(<RecordsPage />, {
      seed: [
        [keys.records({}), api.records],
        [keys.email(api.email.session_id), api.email],
      ],
    });

    expect(screen.getByTestId("records-total")).toHaveTextContent(`${api.records.length} records`);
    const rows = screen.getAllByTestId("record-row");
    expect(rows).toHaveLength(api.records.length);
    expect(first).toBeDefined();

    await userEvent.click(rows.find((row) => row.dataset.session === api.email.session_id)!);

    const drawer = screen.getByTestId("record-drawer");
    expect(within(drawer).getByTestId("draft-only-banner")).toHaveTextContent("Draft only — not sent");
    expect(within(drawer).getByTestId("email-text")).toHaveTextContent(api.email.text.trim());
    expect(container.textContent).not.toContain(RAW_PAN);
    expect(container.textContent).not.toMatch(/dispatched|hsm|investor relations/i);
  });
});

describe("Acceptance page", () => {
  it("shows PASS, the four branches, both caps, six advice turns, and twenty review ids", () => {
    renderWith(<AcceptancePage />, { seed: [[keys.acceptance, api.acceptance]] });

    expect(screen.getByTestId("acceptance-status")).toHaveTextContent("PASS");
    for (const name of ["clean_hit", "corpus_miss", "recurring_theme", "pii"]) {
      expect(screen.getByTestId(`branch-${name}`)).toBeInTheDocument();
    }
    expect(screen.getByTestId("cap-blocked")).toHaveTextContent("blocked");
    expect(screen.getByTestId("cap-refinement")).toHaveTextContent("Sixth refused: yes");
    expect(within(screen.getByTestId("advice-thread")).getAllByText("Refuse")).toHaveLength(6);
    const rows = screen.getAllByTestId("review-row");
    expect(rows).toHaveLength(20);
    expect(rows[0]).toHaveTextContent(api.acceptance.real_complaints[0]!.review_id);
  });

  it("offers a first run when there is no report", () => {
    renderWith(<AcceptancePage />, { seed: [[keys.acceptance, null]] });
    expect(screen.getByTestId("acceptance-empty")).toBeInTheDocument();
    expect(screen.getByTestId("run-acceptance")).toBeEnabled();
  });
});

describe("Shell and access gate", () => {
  function stubApi(sessionsStatus: () => number) {
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string) => {
        if (url.endsWith("/api/health")) {
          return new Response(JSON.stringify({ ...api.health, access_code_required: true }), { status: 200 });
        }
        const status = sessionsStatus();
        return new Response(
          status === 200 ? "[]" : JSON.stringify({ error: "access_code_required", message: "no" }),
          { status },
        );
      }),
    );
  }

  it("shows the context bar from /api/health and asks for the access code", async () => {
    let status = 401;
    stubApi(() => status);
    renderWith(
      <Shell>
        <div data-testid="inside">desk</div>
      </Shell>,
    );

    expect(await screen.findByLabelText("Access code", { selector: "form" })).toBeInTheDocument();
    expect(screen.getByTestId("corpus-date")).toHaveTextContent("25-Jun-2026");
    expect(screen.getByTestId("model-mode")).toHaveTextContent("Models off");
    expect(screen.queryByTestId("inside")).not.toBeInTheDocument();

    await userEvent.type(screen.getByPlaceholderText("Access code"), "wrong");
    await userEvent.click(screen.getByRole("button", { name: /unlock/i }));
    expect(await screen.findByText("That access code was not accepted.")).toBeInTheDocument();

    status = 200;
    await userEvent.type(screen.getByPlaceholderText("Access code"), "right");
    await userEvent.click(screen.getByRole("button", { name: /unlock/i }));
    await waitFor(() => expect(screen.getByTestId("inside")).toBeInTheDocument());
    expect(sessionStorage.getItem("reply-desk.access-code")).toBe("right");
  });
});
