import { useState, useSyncExternalStore, type FormEvent, type ReactNode } from "react";
import { Link, useLocation } from "react-router-dom";

import { getAccessCode, onAccessChange, setAccessCode } from "../api/access";
import { ApiError, verifyAccessCode } from "../api/client";
import { useHealth } from "../api/hooks";
import type { Health } from "../api/types";
import { windowLabel } from "../lib/format";
import { Badge, Button, ErrorNote, Icon, Spinner } from "./ui";

const NAV = [
  { to: "/", label: "Workspace", match: (path: string) => path === "/" || path.startsWith("/s/") },
  { to: "/records", label: "Records", match: (path: string) => path.startsWith("/records") },
  { to: "/acceptance", label: "Acceptance", match: (path: string) => path.startsWith("/acceptance") },
];

function useAccessCode(): string | null {
  return useSyncExternalStore(onAccessChange, getAccessCode, () => null);
}

export function Shell({ children }: { children: ReactNode }) {
  const health = useHealth();
  const code = useAccessCode();
  const locked = health.data?.access_code_required === true && !code;

  return (
    <div className="flex min-h-screen flex-col bg-canvas text-ink">
      <Header health={health.data} />
      <ContextBar health={health.data} offline={health.isError} />
      <main className="flex-1">
        {health.isPending ? (
          <div className="flex h-64 items-center justify-center gap-2 text-muted">
            <Spinner /> Connecting to the API…
          </div>
        ) : locked ? (
          <AccessGate />
        ) : (
          children
        )}
      </main>
    </div>
  );
}

function Header({ health }: { health: Health | undefined }) {
  const { pathname } = useLocation();
  return (
    <header className="sticky top-0 z-40 border-b border-line bg-surface-container-low">
      <div className="flex h-14 items-center justify-between gap-4 px-4">
        <div className="flex items-center gap-5">
          <div className="flex items-center gap-2">
            <img src="/logo.svg" alt="" className="h-7 w-7" />
            <span className="text-headline-sm uppercase tracking-tight text-ink">Reply Desk</span>
            {health && (
              <Badge className="border-line bg-surface-container-highest text-primary" testId="env-badge">
                {health.environment}
              </Badge>
            )}
          </div>
          <nav className="flex items-center gap-1" aria-label="Main">
            {NAV.map((item) => {
              const active = item.match(pathname);
              return (
                <Link
                  key={item.to}
                  to={item.to}
                  aria-current={active ? "page" : undefined}
                  className={`rounded px-3 py-1.5 text-body-sm transition-colors ${
                    active
                      ? "bg-primary-container font-semibold text-on-primary-container"
                      : "text-on-surface-variant hover:bg-surface-container hover:text-ink"
                  }`}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
        {health && <ModelChip health={health} />}
      </div>
    </header>
  );
}

function ModelChip({ health }: { health: Health }) {
  const live = health.models.agents === "groq";
  return (
    <div
      data-testid="model-mode"
      className="flex items-center gap-2 rounded-full bg-surface-container-lowest px-3 py-1 font-mono text-trace-mono text-on-surface-variant"
      title={
        live
          ? `Agents: ${health.models.agent_model ?? "groq"} · Reviewer: ${health.models.reviewer_model ?? health.models.reviewer}`
          : "Models are off: every node uses its cue table and the code checks"
      }
    >
      <span className={`h-1.5 w-1.5 rounded-full ${live ? "bg-primary" : "bg-muted"}`} />
      {live ? `Groq agents · ${health.models.reviewer === "gemini" ? "Gemini reviewer" : "code reviewer"}` : "Models off · cue tables"}
    </div>
  );
}

function ContextBar({ health, offline }: { health: Health | undefined; offline: boolean }) {
  return (
    <div
      data-testid="context-bar"
      className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-line bg-surface-container-low/60 px-4 py-1.5 font-mono text-trace-mono text-on-surface-variant"
    >
      <div className="flex flex-wrap items-center gap-3">
        <span className={`flex items-center gap-1.5 font-medium ${offline ? "text-danger" : "text-primary"}`}>
          <span className={`h-2 w-2 rounded-full ${offline ? "bg-danger" : "bg-primary"}`} />
          {offline ? "API UNREACHABLE" : health ? "API ONLINE" : "CONNECTING"}
        </span>
        {health && (
          <>
            <span className="text-line">|</span>
            <span data-testid="corpus-date">
              CORPUS LAST CHECKED <span className="text-ink">{health.corpus.last_checked}</span>
            </span>
            <span className="text-line">|</span>
            <span>
              REVIEWS <span className="text-ink">{windowLabel(health.review_window)}</span>
            </span>
          </>
        )}
      </div>
      <span className="flex items-center gap-1.5">
        <Icon name="shield" className="h-3.5 w-3.5" />
        PII REDACTED AT INGRESS · APPROVE WRITES A DRAFT · NOTHING IS SENT
      </span>
    </div>
  );
}

function AccessGate() {
  const [value, setValue] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [checking, setChecking] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    const code = value.trim();
    if (!code) return;
    setChecking(true);
    setError(null);
    try {
      // Store the code only once the API accepts it; storing it unlocks the desk.
      if (await verifyAccessCode(code)) {
        setValue("");
        setAccessCode(code);
        return;
      }
      setValue("");
      setError("That access code was not accepted.");
    } catch (failure) {
      setError(failure instanceof ApiError ? failure.message : "The API could not be reached.");
    }
    setChecking(false);
  }

  return (
    <div className="flex justify-center px-4 py-16">
      <form
        onSubmit={submit}
        className="w-full max-w-sm space-y-4 rounded-lg border border-line bg-panel p-5"
        aria-label="Access code"
      >
        <div className="flex items-center gap-2 text-headline-md">
          <Icon name="lock" className="h-5 w-5 text-primary" /> Access code
        </div>
        <p className="text-body-sm text-muted">
          This desk is shared for a demo. Enter the access code you were given. It is kept for this
          browser tab only.
        </p>
        <input
          type="password"
          autoFocus
          autoComplete="off"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          className="h-9 w-full rounded border border-line bg-canvas px-3 font-mono text-body-sm text-ink focus:border-primary-container focus:outline-none"
          placeholder="Access code"
          aria-label="Access code"
        />
        {error && <ErrorNote message={error} />}
        <Button type="submit" variant="primary" className="w-full" disabled={checking || !value.trim()}>
          {checking ? <Spinner /> : <Icon name="lock" />} Unlock
        </Button>
      </form>
    </div>
  );
}
