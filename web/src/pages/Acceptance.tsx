import { useAcceptance, useRunAcceptance } from "../api/hooks";
import type { Acceptance, AcceptanceBranch } from "../api/types";
import { Badge, Button, Card, ErrorNote, Icon, Label, Spinner } from "../components/ui";
import { DISPOSITIONS, REVIEW_STATUSES, SOURCES, formatDateTime, schemeName } from "../lib/format";
import { bars, span } from "../lib/timeline";

const BRANCH_TITLES: Record<string, { title: string; note: string }> = {
  clean_hit: { title: "Clean hit", note: "Exit load on HDFC Large Cap: covered and cited" },
  corpus_miss: { title: "Corpus miss", note: "Order failure on a non-HDFC fund: handoff, no link" },
  recurring_theme: { title: "Recurring theme", note: "Fee complaint: fees_brokerage, ticket stays open" },
  pii: { title: "PII", note: "Exit-load complaint with a PAN and a phone: tokens only" },
};

const BAR_COLORS: Record<string, string> = {
  ingress: "bg-outline",
  facts: "bg-agent-facts",
  pattern: "bg-agent-pattern",
  compliance: "bg-agent-compliance",
  draft: "bg-primary-container",
  reviewer: "bg-ok",
  rewrite: "bg-warn",
};

/** The cues-only acceptance run: 20 real reviews, the four branches, the advice thread, the caps. */
export function AcceptancePage() {
  const report = useAcceptance();
  const run = useRunAcceptance();

  return (
    <div className="mx-auto max-w-[1440px] space-y-4 p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Label>Quality checks</Label>
          <h1 className="text-headline-lg text-ink">Acceptance run</h1>
        </div>
        <Button variant="primary" onClick={() => run.mutate()} disabled={run.isPending} data-testid="run-acceptance">
          {run.isPending ? <Spinner /> : <Icon name="play" className="h-3.5 w-3.5" />} Run (cues only)
        </Button>
      </div>
      {run.isError && <ErrorNote message={run.error.message} />}
      {report.isPending ? (
        <div className="flex items-center gap-2 text-muted">
          <Spinner /> Loading the last report…
        </div>
      ) : report.isError ? (
        <ErrorNote message={report.error.message} />
      ) : report.data === null ? (
        <Card>
          <p className="text-body-sm text-muted" data-testid="acceptance-empty">
            No acceptance run yet. Run it to check the 20 real reviews, the four branches, the advice thread, and
            the caps on the cue tables. It writes nothing to the real records.
          </p>
        </Card>
      ) : (
        <Report report={report.data} />
      )}
    </div>
  );
}

function Report({ report }: { report: Acceptance }) {
  const passed = report.status === "pass";
  return (
    <>
      <section
        data-testid="acceptance-banner"
        className={`flex flex-wrap items-center justify-between gap-4 rounded-xl border p-4 ${
          passed ? "border-ok/40 bg-ok/5" : "border-danger/50 bg-danger/10"
        }`}
      >
        <div className="space-y-1">
          <Badge testId="acceptance-status" className={passed ? "border-ok/40 bg-ok/15 text-ok !text-body-sm" : "border-danger/40 bg-danger/15 text-danger !text-body-sm"}>
            <Icon name={passed ? "check" : "x"} className="h-3.5 w-3.5" /> {passed ? "PASS" : "FAIL"}
          </Badge>
          <div className="text-headline-lg text-ink">
            {report.real_complaints.length} real complaints · {report.branches.length} branches · advice thread · caps
          </div>
          {report.failure && <p className="text-body-sm text-danger">{report.failure}</p>}
        </div>
        <div className="grid grid-cols-2 gap-3 font-mono text-trace-mono text-muted">
          <div className="rounded bg-surface-container px-3 py-1.5">
            MODE <div className="text-headline-sm text-ink">{report.mode}</div>
          </div>
          <div className="rounded bg-surface-container px-3 py-1.5">
            RAN <div className="text-headline-sm text-ink">{formatDateTime(report.ran_at)}</div>
          </div>
        </div>
      </section>

      <section>
        <SectionTitle label="Branches" title="Four fixed inputs" />
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {report.branches.map((branch) => (
            <BranchCard key={branch.name} branch={branch} />
          ))}
        </div>
      </section>

      <section className="grid gap-3 md:grid-cols-2">
        <Card title="Cap: blocked → approve refused" icon="lock" testId="cap-blocked">
          {report.caps.blocked ? (
            <ul className="space-y-1 text-body-sm">
              <li>
                Review <b className="text-danger">{report.caps.blocked.review_status}</b> at round {report.caps.blocked.review_round}{" "}
                (failed: {report.caps.blocked.failed_checks.join(", ")})
              </li>
              <li>Approve refused: {report.caps.blocked.approve_refused ? "yes" : "no"}</li>
              <li>Files written: {report.caps.blocked.files_written}</li>
            </ul>
          ) : (
            <p className="text-muted">Not reached.</p>
          )}
        </Card>
        <Card title="Cap: sixth refinement refused" icon="refresh" testId="cap-refinement">
          {report.caps.refinement_cap ? (
            <ul className="space-y-1 text-body-sm">
              <li>Pushbacks applied: {report.caps.refinement_cap.applied}</li>
              <li>Sixth refused: {report.caps.refinement_cap.sixth_refused ? "yes" : "no"}</li>
              <li>Last reviewed draft kept: {report.caps.refinement_cap.draft_kept ? "yes" : "no"}</li>
            </ul>
          ) : (
            <p className="text-muted">Not reached.</p>
          )}
        </Card>
      </section>

      <section>
        <SectionTitle label="Advice resistance" title={`Sticky refusal over ${report.advice_thread.length} turns`} />
        <div className="grid gap-2 md:grid-cols-3 xl:grid-cols-6" data-testid="advice-thread">
          {report.advice_thread.map((turn) => (
            <div key={turn.turn} className="rounded-lg border border-line bg-panel p-3">
              <div className="flex justify-between font-mono text-trace-mono text-muted">
                <span>TURN {String(turn.turn).padStart(2, "0")}</span>
                <span>{turn.flags.length ? turn.flags.join(", ") : "sticky"}</span>
              </div>
              <p className="my-2 text-body-sm text-ink">“{turn.ask}”</p>
              <Badge className={DISPOSITIONS[turn.disposition].className}>{DISPOSITIONS[turn.disposition].label}</Badge>
            </div>
          ))}
        </div>
      </section>

      <section>
        <SectionTitle label="Dataset" title={`${report.real_complaints.length} real reviews (ids only, never review text)`} />
        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full min-w-[820px] text-left text-body-sm" data-testid="review-matrix">
            <thead className="bg-surface-container-low font-mono text-trace-mono uppercase text-muted">
              <tr>
                {["Review id", "Facts", "Theme", "Signal", "Flags", "Disposition", "Review", "Agents"].map((head) => (
                  <th key={head} className="px-3 py-2 font-medium">
                    {head}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line bg-panel">
              {report.real_complaints.map((row) => (
                <tr key={row.review_id} data-testid="review-row">
                  <td className="px-3 py-1.5 font-mono text-primary">{row.review_id}</td>
                  <td className="px-3 py-1.5 text-on-surface-variant">
                    {row.facts_status === "covered" ? schemeName(row.scheme_id) : "not covered"}
                  </td>
                  <td className="px-3 py-1.5 font-mono text-body-xs">
                    {row.theme_id} ({row.count})
                  </td>
                  <td className="px-3 py-1.5 font-mono text-body-xs">{row.signal}</td>
                  <td className="px-3 py-1.5 font-mono text-body-xs">{row.compliance_flags.join(", ") || "—"}</td>
                  <td className="px-3 py-1.5">
                    <Badge className={DISPOSITIONS[row.disposition].className}>{DISPOSITIONS[row.disposition].label}</Badge>
                  </td>
                  <td className="px-3 py-1.5">
                    <Badge className={REVIEW_STATUSES[row.review_status].className}>{REVIEW_STATUSES[row.review_status].label}</Badge>
                  </td>
                  <td className="px-3 py-1.5 font-mono text-[10px] text-muted">
                    {Object.values(row.provenance).filter(Boolean).every((source) => source === "cues") ? "cues" : "model"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </>
  );
}

function SectionTitle({ label, title }: { label: string; title: string }) {
  return (
    <div className="mb-2 flex items-baseline gap-2">
      <span className="font-mono text-label-mono uppercase text-primary">{label}</span>
      <span className="text-headline-md text-ink">{title}</span>
    </div>
  );
}

function BranchCard({ branch }: { branch: AcceptanceBranch }) {
  const meta = BRANCH_TITLES[branch.name] ?? { title: branch.name, note: "" };
  const list = bars(branch.trace);
  const { from, to } = span(list, 0);
  return (
    <Card
      testId={`branch-${branch.name}`}
      title={meta.title}
      right={<Badge className={REVIEW_STATUSES[branch.review_status].className}>{branch.review_status}</Badge>}
    >
      <p className="mb-2 text-body-xs text-muted">{meta.note}</p>
      <div className="space-y-1 rounded border border-line bg-canvas p-2" aria-label="Trace">
        {list.map((bar, index) => (
          <div key={index} className="flex items-center gap-2">
            <span className="w-16 font-mono text-[10px] text-muted">{bar.node}</span>
            <div className="relative h-1.5 flex-1">
              <span
                className={`absolute h-1.5 rounded-sm ${BAR_COLORS[bar.node] ?? "bg-outline"}`}
                style={{
                  left: `${((bar.start - from) / (to - from)) * 100}%`,
                  width: `${Math.max((((bar.end ?? bar.start) - bar.start) / (to - from)) * 100, 2)}%`,
                }}
              />
            </div>
          </div>
        ))}
      </div>
      <dl className="mt-2 space-y-1 text-body-xs">
        <div className="flex justify-between">
          <dt className="text-muted">Facts</dt>
          <dd className="text-ink">{branch.facts_status === "covered" ? `${branch.scheme_id} · ${branch.section_title}` : "not covered"}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted">Pattern</dt>
          <dd className="text-ink">
            {branch.theme_id} · {branch.signal} · {branch.count}
          </dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted">Disposition</dt>
          <dd>
            <Badge className={DISPOSITIONS[branch.disposition].className}>{DISPOSITIONS[branch.disposition].label}</Badge>
          </dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted">Ran</dt>
          <dd className="font-mono text-ink">{branch.agents_fired_this_turn.join(", ")}</dd>
        </div>
        <div className="flex justify-between">
          <dt className="text-muted">Source</dt>
          <dd>
            {branch.provenance.facts && (
              <Badge className={SOURCES[branch.provenance.facts].className}>{branch.provenance.facts}</Badge>
            )}
          </dd>
        </div>
        {branch.approved && (
          <div className="flex justify-between">
            <dt className="text-muted">Approved</dt>
            <dd className="font-mono text-ok">draft written (temp)</dd>
          </div>
        )}
      </dl>
    </Card>
  );
}
