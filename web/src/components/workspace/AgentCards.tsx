import type { Compliance, Facts, Pattern, Source } from "../../api/types";
import { SOURCES, schemeName, windowLabel } from "../../lib/format";
import { Badge, Icon, Spinner, type IconName } from "../ui";

// The three agent cards from the Stitch "Agent Analysis Engine" row. Every value
// comes from the agent's result; the caption says the model only picked an id and
// code wrote the output. The provenance tag shows which one did the picking.

interface AgentCardProps {
  agent: "facts" | "pattern" | "compliance";
  title: string;
  icon: IconName;
  status: React.ReactNode;
  source: Source | null | undefined;
  running: boolean;
  children: React.ReactNode;
}

const ACCENTS = {
  facts: { text: "text-agent-facts", border: "border-agent-facts/40", bg: "bg-agent-facts/5" },
  pattern: { text: "text-agent-pattern", border: "border-agent-pattern/40", bg: "bg-agent-pattern/5" },
  compliance: { text: "text-agent-compliance", border: "border-agent-compliance/40", bg: "bg-agent-compliance/5" },
} as const;

function AgentCard({ agent, title, icon, status, source, running, children }: AgentCardProps) {
  const accent = ACCENTS[agent];
  return (
    <section
      data-testid={`agent-${agent}`}
      className={`flex flex-col rounded-lg border ${accent.border} ${accent.bg} p-3`}
    >
      <header className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <Icon name={icon} className={`h-4 w-4 ${accent.text}`} />
          <h3 className="text-headline-sm text-ink">{title}</h3>
          {running && (
            <span className={accent.text} data-testid={`agent-${agent}-running`}>
              <Spinner />
            </span>
          )}
        </div>
        {status}
      </header>
      <div className="mt-1 flex items-center gap-2 font-mono text-[10px] text-muted">
        <span>model pick → code output</span>
        {source && (
          <Badge className={SOURCES[source].className} testId={`provenance-${agent}`} title="Where this node's pick came from">
            {SOURCES[source].label}
          </Badge>
        )}
      </div>
      <div className="mt-3 flex flex-1 flex-col gap-2 text-body-sm">{children}</div>
    </section>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="text-body-xs text-muted">{label}</div>
      <div className="text-ink">{children}</div>
    </div>
  );
}

export function FactsCard({ facts, source, running }: { facts: Facts; source?: Source | null; running: boolean }) {
  const covered = facts.status === "covered";
  const schemes = facts.searched.filter((item) => /^[a-z0-9_]+$/.test(item));
  const sections = facts.searched.filter((item) => !/^[a-z0-9_]+$/.test(item));
  return (
    <AgentCard
      agent="facts"
      title="Facts Agent"
      icon="facts"
      source={source}
      running={running}
      status={
        <Badge
          testId="facts-status"
          className={covered ? "border-agent-facts/40 bg-agent-facts/10 text-agent-facts" : "border-line bg-raised text-muted"}
        >
          {covered ? "Covered" : "Not covered"}
        </Badge>
      }
    >
      {covered ? (
        <>
          <Field label="Scheme">{schemeName(facts.scheme_id)}</Field>
          <Field label="Section">{facts.section_title}</Field>
          <blockquote
            data-testid="facts-quote"
            className="max-h-40 overflow-auto rounded border border-line bg-canvas p-2 text-body-sm italic text-on-surface-variant scrollbar-thin"
          >
            “{facts.fact}”
          </blockquote>
          <div className="mt-auto flex flex-wrap items-center justify-between gap-2 pt-1 text-body-xs">
            {facts.citation && (
              <a href={facts.citation} target="_blank" rel="noreferrer noopener" className="flex items-center gap-1 text-agent-facts hover:underline">
                <Icon name="link" className="h-3.5 w-3.5" /> Scheme page
              </a>
            )}
            <span className="text-muted">Checked {facts.last_checked}</span>
          </div>
        </>
      ) : (
        <>
          <p className="text-on-surface-variant">
            None of the scheme pages we hold answers this. Nothing was quoted and no link is given.
          </p>
          <div data-testid="searched-grid" className="rounded border border-line bg-canvas p-2">
            <div className="mb-1.5 font-mono text-trace-mono text-muted">
              SEARCHED {schemes.length} SCHEMES × {sections.length} SECTIONS
            </div>
            <div className="grid grid-cols-7 gap-0.5" aria-hidden="true">
              {schemes.flatMap((scheme) =>
                sections.map((section) => (
                  <span key={`${scheme}-${section}`} title={`${scheme} · ${section}`} className="h-2 rounded-sm bg-line" />
                )),
              )}
            </div>
            <div className="mt-2 flex flex-wrap gap-1">
              {schemes.map((scheme) => (
                <Badge key={scheme}>{scheme}</Badge>
              ))}
            </div>
          </div>
        </>
      )}
    </AgentCard>
  );
}

const SIGNALS = {
  rising: "border-danger/40 bg-danger/10 text-danger",
  recurring: "border-agent-pattern/40 bg-agent-pattern/10 text-agent-pattern",
  "one-off": "border-line bg-raised text-muted",
} as const;

export function PatternCard({ pattern, source, running }: { pattern: Pattern; source?: Source | null; running: boolean }) {
  const share = pattern.count > 0 ? Math.round((pattern.recent_count / pattern.count) * 100) : 0;
  return (
    <AgentCard
      agent="pattern"
      title="Pattern Agent"
      icon="pattern"
      source={source}
      running={running}
      status={
        <Badge testId="pattern-signal" className={SIGNALS[pattern.signal]}>
          {pattern.signal}
        </Badge>
      }
    >
      <Field label="Theme">
        <span data-testid="pattern-theme">{pattern.theme_name}</span>{" "}
        <span className="font-mono text-body-xs text-muted">{pattern.theme_id}</span>
      </Field>
      <div className="grid grid-cols-2 gap-2 rounded border border-line bg-canvas p-2 text-center">
        <div>
          <div data-testid="pattern-count" className="font-mono text-headline-md text-ink tabular">
            {pattern.count}
          </div>
          <div className="font-mono text-[10px] uppercase text-muted">reviews in window</div>
        </div>
        <div>
          <div data-testid="pattern-recent" className="font-mono text-headline-md text-agent-pattern tabular">
            {pattern.recent_count}
          </div>
          <div className="font-mono text-[10px] uppercase text-muted">last 7 days</div>
        </div>
      </div>
      <div>
        <div className="h-1.5 overflow-hidden rounded-full bg-line" aria-hidden="true">
          <div className="h-full bg-agent-pattern" style={{ width: `${Math.max(share, 2)}%` }} />
        </div>
        <div className="mt-1 flex justify-between font-mono text-[10px] text-muted">
          <span>{share}% in the last week</span>
          <span>{windowLabel(pattern.window)}</span>
        </div>
      </div>
    </AgentCard>
  );
}

export function ComplianceCard({
  compliance,
  source,
  running,
}: {
  compliance: Compliance;
  source?: Source | null;
  running: boolean;
}) {
  const advice = compliance.flags.includes("advice");
  const performance = compliance.flags.includes("performance_claim");
  const flagged = advice || performance;
  return (
    <AgentCard
      agent="compliance"
      title="Compliance Agent"
      icon="shield"
      source={source}
      running={running}
      status={
        <Badge
          testId="compliance-status"
          className={flagged ? "border-danger/40 bg-danger/10 text-danger" : "border-agent-compliance/40 bg-agent-compliance/10 text-agent-compliance"}
        >
          {flagged ? "Refusal required" : "Evaluated"}
        </Badge>
      }
    >
      <FlagRow testId="flag-advice" label="Advice" active={advice} />
      <FlagRow testId="flag-performance" label="Performance claim" active={performance} />
      <div
        data-testid="flag-pii"
        data-active={compliance.pii_types.length > 0}
        className="flex items-center justify-between rounded border border-line bg-canvas px-2 py-1.5"
      >
        <span className="flex items-center gap-1.5 text-body-xs text-muted">
          <Icon name="lock" className="h-3.5 w-3.5 text-agent-compliance" /> PII guard
        </span>
        <span className="font-mono text-body-xs text-agent-compliance">
          {compliance.pii_types.length ? compliance.pii_types.join(", ") : "none found"}
        </span>
      </div>
      <p className="mt-auto text-body-xs text-muted">
        Scans the incoming message. The reviewer applies the same policy to the draft.
      </p>
    </AgentCard>
  );
}

function FlagRow({ label, active, testId }: { label: string; active: boolean; testId: string }) {
  return (
    <div
      data-testid={testId}
      data-active={active}
      className={`flex items-center justify-between rounded border px-2 py-1.5 ${
        active ? "border-warn/50 bg-warn/10 text-warn" : "border-line bg-canvas text-muted"
      }`}
    >
      <span className="flex items-center gap-1.5 text-body-xs">
        <Icon name={active ? "alert" : "check"} className="h-3.5 w-3.5" />
        {label}
      </span>
      <span className="font-mono text-body-xs">{active ? "Detected" : "Clear"}</span>
    </div>
  );
}
