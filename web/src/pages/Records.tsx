import { useMemo, useState } from "react";

import type { RecordFilters } from "../api/client";
import { useEmail, useRecords } from "../api/hooks";
import type { Disposition, Priority, RecordOut } from "../api/types";
import { Badge, Button, Card, ErrorNote, Icon, Label, Spinner } from "../components/ui";
import { DISPOSITIONS, PRIORITIES, domain, formatDateTime, shortId } from "../lib/format";
import { piiSegments } from "../lib/text";

const DISPOSITION_KEYS = Object.keys(DISPOSITIONS) as Disposition[];
const PRIORITY_KEYS: Priority[] = ["P1", "P2", "P3"];

/** Approved records: the redacted lines in records.jsonl and their email drafts. */
export function RecordsPage() {
  const [filters, setFilters] = useState<RecordFilters>({});
  const [selected, setSelected] = useState<string | null>(null);
  const all = useRecords({});
  const filtered = useRecords(filters);
  const rows = filtered.data ?? [];
  const teams = useMemo(
    () => [...new Set((all.data ?? []).map((record) => record.routing_note.team))].sort(),
    [all.data],
  );
  const counts = useMemo(() => {
    const out: Record<string, number> = {};
    for (const record of all.data ?? []) out[record.disposition] = (out[record.disposition] ?? 0) + 1;
    return out;
  }, [all.data]);
  const record = rows.find((item) => item.session_id === selected) ?? null;

  return (
    <div className="flex min-h-[calc(100vh-88px)]">
      <div className="min-w-0 flex-1 space-y-4 p-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <h1 className="text-headline-lg text-ink">Approved records</h1>
            <Badge testId="records-total" className="border-primary/30 bg-primary/10 text-primary">
              {all.data?.length ?? 0} records
            </Badge>
          </div>
          <Button onClick={() => exportCsv(rows)} disabled={rows.length === 0} data-testid="export-csv">
            <Icon name="download" className="h-3.5 w-3.5" /> Export CSV
          </Button>
        </div>

        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6" data-testid="record-tiles">
          <Tile label="Total" value={all.data?.length ?? 0} />
          {DISPOSITION_KEYS.map((key) => (
            <Tile key={key} label={DISPOSITIONS[key].label} value={counts[key] ?? 0} />
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Select
            label="Disposition"
            value={filters.disposition ?? ""}
            options={DISPOSITION_KEYS.map((key) => [key, DISPOSITIONS[key].label])}
            onChange={(value) => setFilters((f) => ({ ...f, disposition: (value || undefined) as Disposition | undefined }))}
          />
          <Select
            label="Priority"
            value={filters.priority ?? ""}
            options={PRIORITY_KEYS.map((key) => [key, key])}
            onChange={(value) => setFilters((f) => ({ ...f, priority: (value || undefined) as Priority | undefined }))}
          />
          <Select
            label="Team"
            value={filters.team ?? ""}
            options={teams.map((team) => [team, team])}
            onChange={(value) => setFilters((f) => ({ ...f, team: value || undefined }))}
          />
          {(filters.disposition || filters.priority || filters.team) && (
            <Button variant="ghost" onClick={() => setFilters({})}>
              <Icon name="x" className="h-3.5 w-3.5" /> Reset
            </Button>
          )}
        </div>

        {filtered.isError && <ErrorNote message={filtered.error.message} />}
        <div className="overflow-x-auto rounded-lg border border-line">
          <table className="w-full min-w-[860px] text-left text-body-sm" data-testid="records-table">
            <thead className="bg-surface-container-low font-mono text-trace-mono uppercase text-muted">
              <tr>
                {["Session", "Approved", "Disposition", "Priority", "Team", "Signal", "Citation"].map((head) => (
                  <th key={head} className="px-3 py-2 font-medium">
                    {head}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line bg-panel">
              {filtered.isPending && (
                <tr>
                  <td colSpan={7} className="px-3 py-4 text-muted">
                    <Spinner /> Loading…
                  </td>
                </tr>
              )}
              {!filtered.isPending && rows.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-3 py-6 text-center text-muted">
                    No approved records{filters.disposition || filters.priority || filters.team ? " match these filters" : " yet"}.
                  </td>
                </tr>
              )}
              {rows.map((row) => (
                <tr
                  key={row.session_id}
                  data-testid="record-row"
                  data-session={row.session_id}
                  onClick={() => setSelected(row.session_id)}
                  className={`cursor-pointer hover:bg-raised ${selected === row.session_id ? "bg-raised" : ""}`}
                >
                  <td className="px-3 py-2 font-mono text-primary" title={row.session_id}>
                    {shortId(row.session_id)}
                  </td>
                  <td className="px-3 py-2 font-mono text-body-xs text-on-surface-variant">{formatDateTime(row.approved_at)}</td>
                  <td className="px-3 py-2">
                    <Badge className={DISPOSITIONS[row.disposition].className}>{DISPOSITIONS[row.disposition].label}</Badge>
                  </td>
                  <td className="px-3 py-2">
                    <Badge className={PRIORITIES[row.routing_note.priority]}>{row.routing_note.priority}</Badge>
                  </td>
                  <td className="px-3 py-2 text-ink">{row.routing_note.team}</td>
                  <td className="px-3 py-2 font-mono text-body-xs text-on-surface-variant">{row.pattern_signal}</td>
                  <td className="px-3 py-2 font-mono text-body-xs text-agent-facts">{domain(row.citation)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      {record && <RecordDrawer record={record} onClose={() => setSelected(null)} />}
    </div>
  );
}

function Tile({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-lg border border-line bg-panel px-3 py-2">
      <Label>{label}</Label>
      <div className="font-mono text-headline-lg text-ink tabular">{value}</div>
    </div>
  );
}

function Select({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: string;
  options: Array<[string, string]>;
  onChange: (value: string) => void;
}) {
  return (
    <label className="flex items-center gap-2 rounded border border-line bg-panel px-2 py-1 text-body-xs text-muted">
      {label}
      <select
        aria-label={label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="bg-transparent text-body-sm text-ink focus:outline-none"
      >
        <option value="">All</option>
        {options.map(([key, text]) => (
          <option key={key} value={key} className="bg-panel">
            {text}
          </option>
        ))}
      </select>
    </label>
  );
}

function RecordDrawer({ record, onClose }: { record: RecordOut; onClose: () => void }) {
  const email = useEmail(record.session_id);
  return (
    <aside
      data-testid="record-drawer"
      className="w-full max-w-md shrink-0 space-y-4 overflow-y-auto border-l border-line bg-surface-container-low p-4 scrollbar-thin"
    >
      <div className="flex items-center justify-between">
        <h2 className="text-headline-md text-ink">Approved email draft</h2>
        <Button variant="ghost" onClick={onClose} aria-label="Close" className="h-8 w-8 px-0">
          <Icon name="close" />
        </Button>
      </div>
      <div className="font-mono text-trace-mono text-muted">
        <div>
          SESSION <span className="text-primary">{record.session_id}</span>
        </div>
        <div>APPROVED {formatDateTime(record.approved_at)}</div>
      </div>
      <div data-testid="draft-only-banner" className="flex items-center gap-2 rounded bg-danger/80 px-3 py-2 font-mono text-trace-mono font-semibold uppercase text-ink">
        <Icon name="alert" className="h-4 w-4" /> Draft only — not sent
      </div>
      <Card title="Email draft" icon="doc">
        {email.isPending ? (
          <Spinner />
        ) : email.isError ? (
          <ErrorNote message={email.error.message} />
        ) : (
          <pre data-testid="email-text" className="whitespace-pre-wrap break-words font-sans text-body-md leading-7 text-ink">
            {email.data.text}
          </pre>
        )}
      </Card>
      <Card title="Record" icon="layers">
        <dl className="space-y-2 text-body-sm">
          <div>
            <dt className="text-body-xs text-muted">Redacted complaint</dt>
            <dd className="text-ink">
              {piiSegments(record.redacted_text).map((segment, index) =>
                segment.kind === "token" ? (
                  <span key={index} className="font-mono text-code-inline text-agent-compliance">
                    [{segment.value}]
                  </span>
                ) : (
                  <span key={index}>{segment.value}</span>
                ),
              )}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted">Routing</dt>
            <dd className="text-right text-ink">
              {record.routing_note.team} · {record.routing_note.priority}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted">Citation</dt>
            <dd>
              {record.citation ? (
                <a href={record.citation} target="_blank" rel="noreferrer noopener" className="text-agent-facts hover:underline">
                  {domain(record.citation)}
                </a>
              ) : (
                <span className="text-muted">none</span>
              )}
            </dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted">Last checked</dt>
            <dd className="text-ink">{record.last_checked ?? "—"}</dd>
          </div>
          <div className="flex justify-between">
            <dt className="text-muted">Agents fired</dt>
            <dd className="text-ink">{record.agents_fired.length} entries</dd>
          </div>
        </dl>
      </Card>
    </aside>
  );
}

function exportCsv(rows: RecordOut[]) {
  const header = ["session_id", "approved_at", "disposition", "priority", "team", "pattern_signal", "citation"];
  const escape = (value: string) => `"${value.replace(/"/g, '""')}"`;
  const lines = rows.map((row) =>
    [row.session_id, row.approved_at, row.disposition, row.routing_note.priority, row.routing_note.team, row.pattern_signal, row.citation ?? ""]
      .map((value) => escape(String(value)))
      .join(","),
  );
  const blob = new Blob([[header.join(","), ...lines].join("\n")], { type: "text/csv" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = "reply-desk-records.csv";
  link.click();
  URL.revokeObjectURL(url);
}
