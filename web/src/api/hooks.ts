import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useRef, useState } from "react";

import { ApiError, api, type RecordFilters } from "./client";
import { streamTurn, type TurnRequest } from "./stream";
import type { SessionView, TraceEvent } from "./types";

export const keys = {
  health: ["health"] as const,
  sessions: ["sessions"] as const,
  session: (id: string) => ["session", id] as const,
  records: (filters: RecordFilters) => ["records", filters] as const,
  email: (id: string) => ["email", id] as const,
  acceptance: ["acceptance"] as const,
};

const notFound = (error: unknown) => error instanceof ApiError && (error.status === 404 || error.status === 401);

export function useHealth() {
  return useQuery({ queryKey: keys.health, queryFn: api.health, refetchInterval: 30_000, retry: 1 });
}

export function useSessions(enabled = true) {
  return useQuery({ queryKey: keys.sessions, queryFn: api.sessions, refetchInterval: 20_000, enabled });
}

export function useSessionView(id: string | undefined) {
  return useQuery({
    queryKey: keys.session(id ?? ""),
    queryFn: () => api.session(id ?? ""),
    enabled: Boolean(id),
    retry: (count, error) => !notFound(error) && count < 2,
  });
}

export function useRecords(filters: RecordFilters) {
  return useQuery({ queryKey: keys.records(filters), queryFn: () => api.records(filters) });
}

export function useEmail(id: string | null) {
  return useQuery({ queryKey: keys.email(id ?? ""), queryFn: () => api.email(id ?? ""), enabled: Boolean(id) });
}

export function useAcceptance() {
  return useQuery({ queryKey: keys.acceptance, queryFn: api.acceptance, retry: 1 });
}

export function useRunAcceptance() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: api.runAcceptance,
    onSuccess: (report) => client.setQueryData(keys.acceptance, report),
  });
}

export function useApprove(sessionId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.approve(sessionId),
    onSettled: () => {
      void client.invalidateQueries({ queryKey: keys.session(sessionId) });
      void client.invalidateQueries({ queryKey: keys.sessions });
      void client.invalidateQueries({ queryKey: ["records"] });
    },
  });
}

export interface TurnState {
  running: boolean;
  kind: TurnRequest["kind"] | null;
  /** Trace events of the turn in flight, in arrival order. */
  trace: TraceEvent[];
  error: ApiError | null;
}

const IDLE: TurnState = { running: false, kind: null, trace: [], error: null };

/** One streamed turn at a time. The result lands in the session's query cache. */
export function useTurn() {
  const client = useQueryClient();
  const [state, setState] = useState<TurnState>(IDLE);
  const busy = useRef(false);

  const run = useCallback(
    async (turn: TurnRequest): Promise<SessionView | null> => {
      if (busy.current) return null;
      busy.current = true;
      setState({ running: true, kind: turn.kind, trace: [], error: null });
      try {
        const view = await streamTurn(turn, (event) =>
          setState((current) => ({ ...current, trace: [...current.trace, event] })),
        );
        client.setQueryData(keys.session(view.session_id), view);
        void client.invalidateQueries({ queryKey: keys.sessions });
        setState((current) => ({ ...current, running: false }));
        return view;
      } catch (error) {
        const failure =
          error instanceof ApiError ? error : new ApiError(0, "turn_failed", "The turn failed.");
        setState((current) => ({ ...current, running: false, error: failure }));
        if ("sessionId" in turn) void client.invalidateQueries({ queryKey: keys.session(turn.sessionId) });
        return null;
      } finally {
        busy.current = false;
      }
    },
    [client],
  );

  const reset = useCallback(() => setState(IDLE), []);
  return { ...state, run, reset };
}
