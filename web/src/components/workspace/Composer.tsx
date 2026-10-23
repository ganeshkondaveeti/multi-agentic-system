import { useState, type FormEvent } from "react";

import type { SessionView } from "../../api/types";
import { Button, Card, Icon, Spinner } from "../ui";

// Demo inputs. The PII one carries a made-up PAN and phone that ingress redacts on
// the server; it shows the pills. These strings live only in this file and the box.
export const EXAMPLES = [
  { label: "Exit load (clean hit)", text: "Why was I charged an exit load on HDFC Large Cap Fund?" },
  { label: "Order failed (not covered)", text: "My order failed on Nippon Small Cap" },
  { label: "Fee complaint (recurring)", text: "Why is there an exit load fee on my HDFC Mid Cap Fund redemption?" },
  {
    label: "With PAN and phone",
    text: "Why was I charged an exit load on HDFC Large Cap Fund? My PAN is ABCDE1234F and my phone is 9876543210.",
  },
  { label: "Advice request", text: "Should I redeem HDFC Large Cap?" },
  { label: "Chart issue (rising)", text: "The chart for HDFC Large Cap Fund shows the wrong NAV" },
];

const INPUT =
  "w-full resize-none rounded border border-line bg-canvas px-3 py-2 text-body-md text-ink placeholder:text-outline focus:border-primary-container focus:outline-none";

/** New complaint. The textarea is cleared the moment the turn starts. */
export function ComplaintComposer({ running, onSubmit }: { running: boolean; onSubmit: (text: string) => void }) {
  const [text, setText] = useState("");

  function submit(event: FormEvent) {
    event.preventDefault();
    const complaint = text.trim();
    if (!complaint || running) return;
    setText("");
    onSubmit(complaint);
  }

  return (
    <Card title="New complaint" icon="inbox" testId="composer">
      <form onSubmit={submit} className="space-y-3">
        <textarea
          data-testid="complaint-input"
          aria-label="Complaint"
          value={text}
          onChange={(event) => setText(event.target.value)}
          rows={5}
          maxLength={2000}
          placeholder="Paste the user's question or complaint. PAN, Aadhaar, phone, email, OTP, and account numbers are redacted before any agent sees it."
          className={INPUT}
        />
        <div className="flex flex-wrap gap-1.5">
          {EXAMPLES.map((example) => (
            <button
              key={example.label}
              type="button"
              onClick={() => setText(example.text)}
              className="rounded border border-line px-2 py-0.5 text-body-xs text-on-surface-variant hover:border-outline hover:text-ink"
            >
              {example.label}
            </button>
          ))}
        </div>
        <div className="flex items-center justify-between gap-3">
          <span className="text-body-xs text-muted">
            Facts, Pattern, and Compliance start together; the reviewer runs after the merge.
          </span>
          <Button type="submit" variant="primary" disabled={running || !text.trim()} data-testid="complaint-submit">
            {running ? <Spinner /> : <Icon name="bolt" className="h-3.5 w-3.5" />} Run agents
          </Button>
        </div>
      </form>
    </Card>
  );
}

/** A later user message in the same thread, or a correction of the complaint text. */
export function MessageInput({
  view,
  running,
  onMessage,
  onReplace,
}: {
  view: SessionView;
  running: boolean;
  onMessage: (text: string) => void;
  onReplace: (text: string) => void;
}) {
  const [mode, setMode] = useState<"message" | "replace">("message");
  const [text, setText] = useState("");
  if (view.approved) return null;
  const replaceBlocked = view.refinements_left <= 0;

  function submit(event: FormEvent) {
    event.preventDefault();
    const value = text.trim();
    if (!value || running) return;
    if (mode === "replace" && replaceBlocked) return;
    setText("");
    if (mode === "message") onMessage(value);
    else onReplace(value);
  }

  return (
    <Card
      title="Continue the thread"
      icon="inbox"
      testId="message-panel"
      right={
        <div className="flex rounded border border-line text-body-xs" role="tablist">
          {(["message", "replace"] as const).map((option) => (
            <button
              key={option}
              type="button"
              role="tab"
              aria-selected={mode === option}
              onClick={() => setMode(option)}
              className={`px-2 py-0.5 ${mode === option ? "bg-raised text-ink" : "text-muted hover:text-ink"}`}
            >
              {option === "message" ? "New customer message" : "Correct complaint text"}
            </button>
          ))}
        </div>
      }
    >
      <form onSubmit={submit} className="space-y-2">
        <textarea
          data-testid="message-input"
          aria-label={mode === "message" ? "Customer message" : "Corrected complaint"}
          value={text}
          onChange={(event) => setText(event.target.value)}
          rows={2}
          maxLength={2000}
          placeholder={
            mode === "message"
              ? "The user's next message in this thread. Every agent runs; an advice refusal stays sticky."
              : "The corrected complaint text. Counts as a refinement; every agent re-runs."
          }
          className={INPUT}
        />
        <div className="flex items-center justify-between">
          <span className="text-body-xs text-muted">
            {mode === "replace" && replaceBlocked ? "Refinement limit reached." : "Redacted before any agent sees it."}
          </span>
          <Button
            type="submit"
            variant="secondary"
            disabled={running || !text.trim() || (mode === "replace" && replaceBlocked)}
            data-testid="message-submit"
          >
            {running ? <Spinner /> : <Icon name="play" className="h-3.5 w-3.5" />}
            {mode === "message" ? "Run on message" : "Re-run with correction"}
          </Button>
        </div>
      </form>
    </Card>
  );
}
