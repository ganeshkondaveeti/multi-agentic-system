import { expect, test, type Page } from "@playwright/test";

// The same inputs as support_reply.fixtures, driven through the browser against the
// real API with models off.
const CLEAN_HIT = "Why was I charged an exit load on HDFC Large Cap Fund?";
const CORPUS_MISS = "My order failed on Nippon Small Cap";
const RECURRING = "Why is there an exit load fee on my HDFC Mid Cap Fund redemption?";
const RAW_PAN = "ABCDE1234F";
const RAW_PHONE = "9876543210";
const PII = `${CLEAN_HIT} My PAN is ${RAW_PAN} and my phone is ${RAW_PHONE}.`;
const ADVICE = [
  "Should I redeem HDFC Large Cap?",
  "Is HDFC Large Cap a good fund?",
  "What returns should I expect from HDFC Large Cap?",
  "Just tell me honestly, is large cap worth holding on to?",
  "Ok, so should I redeem my HDFC Large Cap units or not?",
  "What is the exit load on HDFC Large Cap Fund?",
];
const LARGE_CAP_URL = "https://groww.in/mutual-funds/hdfc-large-cap-fund-direct-growth";
const GOLD_URL = "https://groww.in/mutual-funds/hdfc-gold-etf-fund-of-fund-direct-plan-growth";
const AGENTS = ["facts", "pattern", "compliance"];

async function submitComplaint(page: Page, text: string): Promise<string> {
  await page.goto("/");
  await page.getByTestId("complaint-input").fill(text);
  await page.getByTestId("complaint-submit").click();
  await page.waitForURL(/\/s\/[0-9a-f]{32}$/);
  await expect(page.getByTestId("disposition")).toBeVisible();
  await expect(page.getByTestId("complaint-input")).toHaveCount(0);
  return page.url().split("/s/")[1]!;
}

async function refine(page: Page, pushback: string, expectedCount: number) {
  await page.getByTestId("refine-input").fill(pushback);
  await page.getByTestId("refine-run").click();
  await expect(page.getByTestId("refine-counter")).toHaveText(`Refinements ${expectedCount} / 5`);
}

async function traceNodes(page: Page): Promise<string[]> {
  return page.getByTestId("trace-bar").evaluateAll((bars) => bars.map((bar) => (bar as HTMLElement).dataset.node ?? ""));
}

test("the header reads model mode and corpus date from the API", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("model-mode")).toContainText("Models off");
  await expect(page.getByTestId("corpus-date")).toContainText("25-Jun-2026");
  await expect(page.getByTestId("env-badge")).toHaveText("e2e");
});

test.describe("the four branches", () => {
  test("clean hit: escalate, large-cap citation, ticket stays open", async ({ page }) => {
    await submitComplaint(page, CLEAN_HIT);
    await expect(page.getByTestId("disposition")).toHaveText("Escalate");
    await expect(page.getByTestId("facts-status")).toHaveText("Covered");
    await expect(page.getByTestId("draft-link")).toHaveAttribute("href", LARGE_CAP_URL);
    await expect(page.getByTestId("ticket-open")).toBeVisible();
    await expect(page.getByTestId("draft-reply")).toContainText("Last checked 25-Jun-2026.");
  });

  test("corpus miss: handoff, searched grid, no URL", async ({ page }) => {
    await submitComplaint(page, CORPUS_MISS);
    await expect(page.getByTestId("disposition")).toHaveText("Handoff");
    await expect(page.getByTestId("facts-status")).toHaveText("Not covered");
    await expect(page.getByTestId("searched-grid")).toBeVisible();
    await expect(page.getByTestId("draft-link")).toHaveCount(0);
    await expect(page.getByTestId("draft-reply")).not.toContainText("http");
  });

  test("recurring theme: fees_brokerage, 136 reviews, ticket stays open", async ({ page }) => {
    await submitComplaint(page, RECURRING);
    await expect(page.getByTestId("pattern-theme")).toHaveText("Fees & brokerage");
    await expect(page.getByTestId("pattern-count")).toHaveText("136");
    await expect(page.getByTestId("ticket-open")).toBeVisible();
  });

  test("PII: tokens only, on screen, in storage, in the URL, and in the approved record", async ({ page }) => {
    const responses: Promise<string>[] = [];
    page.on("response", (response) => {
      if (new URL(response.url()).pathname.startsWith("/api/")) responses.push(response.text().catch(() => ""));
    });

    const id = await submitComplaint(page, PII);
    await expect(page.getByTestId("pii-token")).toHaveText(["[PAN]", "[PHONE]"]);
    await expect(page.getByTestId("check-pii")).toHaveAttribute("data-failed", "false");
    const body = await page.locator("body").innerText();
    expect(body).not.toContain(RAW_PAN);
    expect(body).not.toContain(RAW_PHONE);
    expect(page.url()).toMatch(new RegExp(`/s/${id}$`));

    await page.getByTestId("approve-button").click();
    await expect(page.getByTestId("approved-note")).toContainText("Nothing was sent.");

    const stored = await page.evaluate(() => JSON.stringify({ ...localStorage }) + JSON.stringify({ ...sessionStorage }));
    const fromApi = [
      await (await page.request.get(`/api/sessions/${id}`)).text(),
      await (await page.request.get("/api/records")).text(),
      await (await page.request.get(`/api/records/${id}/email`)).text(),
    ];
    const seen = await Promise.all(responses);
    expect(seen.length).toBeGreaterThan(0);
    expect(fromApi[1]).toContain("[PAN]");
    for (const text of [stored, ...fromApi, ...seen]) {
      expect(text).not.toContain(RAW_PAN);
      expect(text).not.toContain(RAW_PHONE);
    }
  });
});

test("the live timeline shows three agent bars starting before any ends", async ({ page }) => {
  await submitComplaint(page, CLEAN_HIT);
  const bars = await page.getByTestId("trace-bar").evaluateAll((elements) =>
    elements.map((element) => {
      const data = (element as HTMLElement).dataset;
      return { node: data.node, start: Number(data.start), end: Number(data.end) };
    }),
  );
  const agents = bars.filter((bar) => AGENTS.includes(bar.node ?? ""));
  expect(agents).toHaveLength(3);
  expect(Math.max(...agents.map((bar) => bar.start))).toBeLessThan(Math.min(...agents.map((bar) => bar.end)));
});

test("refinements re-run only the named agents, the history shows it, and the sixth is refused", async ({ page }) => {
  const id = await submitComplaint(page, CLEAN_HIT);

  await refine(page, "Shorter", 1);
  expect(await traceNodes(page)).not.toEqual(expect.arrayContaining(["facts"]));
  expect((await traceNodes(page)).filter((node) => AGENTS.includes(node))).toEqual([]);

  await refine(page, "They're asking about HDFC Gold ETF Fund of Fund", 2);
  await expect(page.getByTestId("draft-link")).toHaveAttribute("href", GOLD_URL);
  expect((await traceNodes(page)).filter((node) => AGENTS.includes(node))).toEqual(["facts"]);

  await refine(page, "Check if this is the fee issue from last week", 3);
  expect((await traceNodes(page)).filter((node) => AGENTS.includes(node))).toEqual(["pattern"]);

  await page.getByTestId("history-button").click();
  const entries = page.getByTestId("history-drawer").getByTestId("history-entry");
  await expect(entries).toHaveCount(3);
  await expect(entries.nth(0).getByTestId("ran-chip")).toHaveText(["orchestrator"]);
  await expect(entries.nth(1).getByTestId("ran-chip")).toHaveText(["facts", "orchestrator"]);
  await expect(entries.nth(1).getByTestId("skipped-chip")).toHaveText(["pattern", "compliance"]);
  await expect(entries.nth(2).getByTestId("ran-chip")).toHaveText(["pattern", "orchestrator"]);
  await page.keyboard.press("Escape");

  await refine(page, "Shorter", 4);
  await refine(page, "Shorter", 5);
  await expect(page.getByTestId("refine-limit")).toContainText("Refinement limit reached, last reviewed draft kept.");
  await expect(page.getByTestId("refine-input")).toHaveCount(0);

  const sixth = await page.request.post(`/api/sessions/${id}/refine`, { data: { pushback: "Shorter" } });
  expect(sixth.status()).toBe(409);
  expect((await sixth.json()).error).toBe("refinement_refused");
});

test("the six-turn advice thread stays refused", async ({ page }) => {
  await submitComplaint(page, ADVICE[0]!);
  await expect(page.getByTestId("disposition")).toHaveText("Refuse");
  await expect(page.getByTestId("sticky-refusal")).toBeVisible();

  for (const ask of ADVICE.slice(1)) {
    const before = await page.getByTestId("draft-reply").innerText();
    await page.getByTestId("message-input").fill(ask);
    await page.getByTestId("message-submit").click();
    await expect(page.getByTestId("message-input")).toHaveValue("");
    await expect(page.getByTestId("turn-running")).toHaveCount(0);
    await expect(page.getByTestId("disposition")).toHaveText("Refuse");
    await expect(page.getByTestId("citation")).toHaveCount(0);
    await expect(page.getByTestId("draft-reply")).toHaveText(before);
  }
  await expect(page.getByTestId("sticky-refusal")).toBeVisible();
});

test("approve writes a record the Records page lists, with its email draft", async ({ page }) => {
  const id = await submitComplaint(page, CLEAN_HIT);
  await page.getByTestId("approve-button").click();
  await expect(page.getByTestId("approved-note")).toContainText("Nothing was sent.");
  await expect(page.getByTestId("approve-button")).toHaveCount(0);

  await page.getByRole("link", { name: "Records", exact: true }).click();
  const row = page.locator(`[data-testid="record-row"][data-session="${id}"]`);
  await expect(row).toBeVisible();
  await row.click();
  await expect(page.getByTestId("draft-only-banner")).toHaveText(/Draft only — not sent/);
  await expect(page.getByTestId("email-text")).toContainText("Exit load of 1% if redeemed within 1 year.");
  await expect(page.getByTestId("email-text")).toContainText(LARGE_CAP_URL);
});

test("the acceptance page runs to PASS and leaves the real records unchanged", async ({ page }) => {
  const before = (await (await page.request.get("/api/records")).json()).length;

  await page.goto("/acceptance");
  await page.getByTestId("run-acceptance").click();
  await expect(page.getByTestId("acceptance-status")).toHaveText(/PASS/, { timeout: 20_000 });
  await expect(page.getByTestId("review-row")).toHaveCount(20);
  await expect(page.getByTestId("branch-pii")).toBeVisible();

  const after = (await (await page.request.get("/api/records")).json()).length;
  expect(after).toBe(before);
});
