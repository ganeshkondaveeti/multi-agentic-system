import { accessRejected, getAccessCode } from "./access";
import type {
  Acceptance,
  ApproveResult,
  Disposition,
  EmailDraft,
  Health,
  Priority,
  RecordOut,
  SessionSummary,
  SessionView,
} from "./types";

// Empty in development: Vite proxies /api to the local FastAPI service.
const BASE = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");

export function apiUrl(path: string): string {
  return `${BASE}/api${path}`;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

export function requestHeaders(extra: Record<string, string> = {}): Record<string, string> {
  const headers: Record<string, string> = { ...extra };
  const code = getAccessCode();
  if (code) headers["X-Access-Code"] = code;
  return headers;
}

/** Turn a failed response into an `ApiError`. The body never echoes what was sent. */
export async function toApiError(response: Response): Promise<ApiError> {
  if (response.status === 401) accessRejected();
  let code = "http_error";
  let message = `The request failed (${response.status}).`;
  try {
    const body = (await response.json()) as { error?: string; message?: string };
    if (body.error) code = body.error;
    if (body.message) message = body.message;
  } catch {
    // Not JSON: keep the generic message.
  }
  return new ApiError(response.status, code, message);
}

async function request<T>(path: string, init: { method?: string; body?: unknown } = {}): Promise<T> {
  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      method: init.method ?? "GET",
      headers: requestHeaders(init.body === undefined ? {} : { "Content-Type": "application/json" }),
      body: init.body === undefined ? undefined : JSON.stringify(init.body),
    });
  } catch {
    throw new ApiError(0, "network_error", "The API is unreachable.");
  }
  if (!response.ok) throw await toApiError(response);
  return (await response.json()) as T;
}

/** Check a candidate access code without storing it. False when the API rejects it. */
export async function verifyAccessCode(code: string): Promise<boolean> {
  let response: Response;
  try {
    response = await fetch(apiUrl("/sessions"), { headers: { "X-Access-Code": code } });
  } catch {
    throw new ApiError(0, "network_error", "The API is unreachable.");
  }
  if (response.status === 401) return false;
  if (!response.ok) throw await toApiError(response);
  return true;
}

export interface RecordFilters {
  disposition?: Disposition;
  priority?: Priority;
  team?: string;
}

export const api = {
  health: () => request<Health>("/health"),
  sessions: () => request<SessionSummary[]>("/sessions"),
  session: (id: string) => request<SessionView>(`/sessions/${encodeURIComponent(id)}`),
  approve: (id: string) =>
    request<ApproveResult>(`/sessions/${encodeURIComponent(id)}/approve`, { method: "POST" }),
  records: (filters: RecordFilters = {}) => {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(filters)) if (value) params.set(key, value);
    const query = params.toString();
    return request<RecordOut[]>(`/records${query ? `?${query}` : ""}`);
  },
  email: (id: string) => request<EmailDraft>(`/records/${encodeURIComponent(id)}/email`),
  acceptance: async (): Promise<Acceptance | null> => {
    try {
      return await request<Acceptance>("/acceptance");
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    }
  },
  runAcceptance: () => request<Acceptance>("/acceptance/run", { method: "POST" }),
};
