import { useState } from "react";
import { useNavigate, useParams } from "react-router-dom";

import { ApiError } from "../api/client";
import { useApprove, useSessionView, useSessions, useTurn } from "../api/hooks";
import { ComplaintComposer } from "../components/workspace/Composer";
import { QueueList } from "../components/workspace/QueueList";
import { TicketView } from "../components/workspace/TicketView";
import { TraceTimeline } from "../components/workspace/TraceTimeline";
import { ErrorNote, Spinner } from "../components/ui";

const NEW = "new";

export function WorkspacePage() {
  const { sessionId } = useParams();
  const navigate = useNavigate();
  const sessions = useSessions();
  const viewQuery = useSessionView(sessionId);
  const turn = useTurn();
  const approve = useApprove(sessionId ?? "");
  // The session the latest turn belongs to, so its trace and error show in the right place.
  const [turnTarget, setTurnTarget] = useState<string | null>(null);

  const current = sessionId ?? NEW;
  const ownTurn = turnTarget === current;
  const running = turn.running && ownTurn;
  const turnError = ownTurn && turn.error ? turn.error.message : null;

  async function startComplaint(complaint: string) {
    setTurnTarget(NEW);
    const view = await turn.run({ kind: "complaint", complaint });
    if (view) {
      setTurnTarget(view.session_id);
      navigate(`/s/${view.session_id}`);
    }
  }

  function onTurn(kind: "refine" | "message" | "replace", text: string) {
    if (!sessionId) return;
    setTurnTarget(sessionId);
    if (kind === "refine") void turn.run({ kind, sessionId, pushback: text });
    else if (kind === "message") void turn.run({ kind, sessionId, message: text });
    else void turn.run({ kind, sessionId, complaint: text });
  }

  return (
    <div className="grid min-h-[calc(100vh-88px)] xl:grid-cols-[300px_minmax(0,1fr)]">
      <QueueList sessions={sessions.data ?? []} loading={sessions.isPending} selectedId={sessionId} />
      <div className="min-w-0 p-4">
        {!sessionId ? (
          <div className="mx-auto max-w-4xl space-y-4">
            <ComplaintComposer running={running} onSubmit={startComplaint} />
            {turnError && <ErrorNote message={turnError} testId="turn-error" />}
            {(running || (ownTurn && turn.trace.length > 0 && !turnError)) && (
              <TraceTimeline events={turn.trace} running={running} />
            )}
          </div>
        ) : viewQuery.isPending ? (
          <div className="flex items-center gap-2 p-6 text-muted">
            <Spinner /> Loading session…
          </div>
        ) : viewQuery.isError ? (
          <div className="mx-auto max-w-xl space-y-3 p-6">
            <ErrorNote
              testId="session-missing"
              message={
                viewQuery.error instanceof ApiError && viewQuery.error.status === 404
                  ? "This session is no longer on the desk. Sessions expire after two idle hours or when the server restarts; approved records are kept."
                  : viewQuery.error.message
              }
            />
          </div>
        ) : (
          <TicketView
            key={sessionId}
            view={viewQuery.data}
            liveTrace={ownTurn ? turn.trace : null}
            running={running}
            turnError={turnError}
            onRefine={(text) => onTurn("refine", text)}
            onMessage={(text) => onTurn("message", text)}
            onReplace={(text) => onTurn("replace", text)}
            onApprove={() => approve.mutate()}
            approving={approve.isPending}
            approveError={approve.error ? approve.error.message : null}
          />
        )}
      </div>
    </div>
  );
}
