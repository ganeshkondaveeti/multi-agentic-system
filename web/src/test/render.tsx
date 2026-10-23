import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";

import fixtures from "./fixtures/api.json";
import type {
  Acceptance,
  EmailDraft,
  Health,
  RecordOut,
  SessionSummary,
  SessionView,
} from "../api/types";

// Responses captured from the real API by scripts/capture_web_fixtures.py.
export const api = fixtures as unknown as {
  views: Record<
    | "clean_hit"
    | "corpus_miss"
    | "recurring_theme"
    | "pii"
    | "refuse"
    | "blocked"
    | "disagree"
    | "refined"
    | "exhausted"
    | "approved",
    SessionView
  >;
  sessions: SessionSummary[];
  records: RecordOut[];
  email: EmailDraft;
  acceptance: Acceptance;
  health: Health;
};

export const RAW_PAN = "ABCDE1234F";
export const RAW_PHONE = "9876543210";

/** Render inside a router and a query client whose cache is pre-seeded, so nothing fetches. */
export function renderWith(
  ui: ReactElement,
  { route = "/", seed = [] }: { route?: string; seed?: Array<[readonly unknown[], unknown]> } = {},
) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: Infinity, gcTime: Infinity } },
  });
  for (const [key, value] of seed) client.setQueryData(key, value);
  const result = render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[route]}>{ui}</MemoryRouter>
    </QueryClientProvider>,
  );
  return { ...result, client };
}
