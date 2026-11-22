import { memo, useState, type RefObject } from "react";

import type { TranscriptTurnDto } from "../protocol.ts";
import type { LiveTurn, PendingConversationTurn, VisibleConversationTurn } from "../conversations.ts";
import type { AnnotationControls } from "./Annotation.tsx";
import { MessageBody, MessageCard, ReferenceCards, SafeContent } from "./messageParts.tsx";

/**
 * A turn reaches the transcript in one of three ways, each with its own data and lifecycle:
 * `RestoredTurn` (saved history, any terminal state, lazy tool details), `CompletedTurn` (finished in
 * this session, plain answer or local command) and `PendingTurn` (still running: spinner and
 * activity list). They share `MessageCard`, `MessageBody` and `ReferenceCards` and stay separate
 * entries because their data and states do not overlap (U22).
 */

interface MessageSource { projectId: string; sessionId: string; turnId: string }
type Role = "user" | "assistant";

function chatSource(source: MessageSource | undefined, role: Role) {
  return source === undefined ? undefined : { ...source, role };
}

function ToolActivity({ activity }: {
  activity: TranscriptTurnDto["toolActivities"][number];
}) {
  const [expanded, setExpanded] = useState(false);
  return (
    <details
      className="tool-activity"
      aria-label={`Tool activity ${activity.name}`}
      onToggle={(event) => setExpanded(event.currentTarget.open)}
    >
      <summary className="message-label">
        Tool activity · {activity.name} · {activity.status}
        {activity.promptEligible ? " · restored context" : " · display only"}
      </summary>
      {expanded && <div className="tool-activity-content">
        <MessageCard kind="tool" label={`Tool arguments · ${activity.name}`}>
          <SafeContent content={activity.arguments} />
        </MessageCard>
        <MessageCard kind="tool-result" label={`Tool result · ${activity.name}`}>
          <SafeContent content={activity.result} />
        </MessageCard>
      </div>}
    </details>
  );
}

export const RestoredTurn = memo(function RestoredTurn({ turn, projectId, sessionId, annotationControls }: { turn: TranscriptTurnDto; projectId?: string; sessionId?: string; annotationControls?: AnnotationControls }) {
  const source = projectId === undefined || sessionId === undefined ? undefined : { projectId, sessionId, turnId: turn.turnId };
  const displayOnly = turn.kind === "display-only";
  return (
    <article className="turn-group">
      <MessageCard kind="user" label={`You · restored turn ${turn.turnNumber}${displayOnly ? " · display-only" : ""}`}>
        <MessageBody text={turn.userText} source={chatSource(source, "user")} annotationControls={annotationControls} />
        <ReferenceCards references={turn.submittedContext?.references ?? []} />
      </MessageCard>
      {turn.toolActivities.map((activity, index) => (
        <ToolActivity
          activity={activity}
          key={`${activity.callId ?? "legacy"}-${activity.name}-${index}`}
        />
      ))}
      {turn.state === "completed" && turn.assistantText !== null ? (
        <MessageCard kind={displayOnly ? "system" : "assistant"}
          label={displayOnly ? "Local command output · restored · display-only" : "Assistant · restored"}>
          <MessageBody text={turn.assistantText} source={displayOnly ? undefined : chatSource(source, "assistant")} annotationControls={annotationControls} />
        </MessageCard>
      ) : turn.state === "pending" ? (
        <MessageCard kind="system" label="Pending · saved locally">
          <p>This turn has not reached a terminal state and will not replay automatically.</p>
        </MessageCard>
      ) : (
        <MessageCard kind="system" label={`${turn.state === "failed" ? "Failed" : "Interrupted"} · saved locally`}>
          <SafeContent content={turn.failureMessage ?? "This turn did not complete."} />
        </MessageCard>
      )}
    </article>
  );
});

function CompletedTurn({ turn, source, annotationControls }: { turn: LiveTurn; source: MessageSource | undefined; annotationControls?: AnnotationControls }) {
  const command = turn.responseKind === "command";
  return <article className="turn-group">
    <MessageCard kind="user" label="You">
      <MessageBody text={turn.userText} source={chatSource(source, "user")} annotationControls={annotationControls} />
      <ReferenceCards references={turn.submittedContext?.references ?? []} />
    </MessageCard>
    <MessageCard kind={command ? "system" : "assistant"} label={`${command ? "Local command output" : "Assistant"} · complete`}>
      <MessageBody text={turn.assistantText} source={command ? undefined : chatSource(source, "assistant")} annotationControls={annotationControls} />
    </MessageCard>
  </article>;
}

function PendingTurn({ turn, retrying, source }: { turn: PendingConversationTurn; retrying: boolean; source: MessageSource | undefined }) {
  return <article className="turn-group pending-turn">
    <MessageCard kind="user" label={`You · ${retrying ? "retrying" : "pending"}`}>
      <MessageBody text={turn.userText} source={chatSource(source, "user")} />
      <ReferenceCards references={turn.submittedContext?.references ?? []} />
    </MessageCard>
    <MessageCard kind="assistant" label="Assistant · working"><div className="inline-spinner" aria-label="Waiting for answer" /></MessageCard>
    {turn.activity.length > 0 && <ul className="activity-list">{turn.activity.map((activity, index) => <li key={`${activity.kind}-${index}`}>
      <strong>{activity.kind === "stage" ? "Stage" : "Tool"}:</strong> {activity.label}{activity.status === null ? "" : ` · ${activity.status}`}
    </li>)}</ul>}
  </article>;
}

export const ConversationTurns = memo(function ConversationTurns({ turns, projectId, annotationControls }: { turns: readonly VisibleConversationTurn[]; projectId?: string; annotationControls?: AnnotationControls }) {
  return turns.map((item) => {
    const source = projectId === undefined ? undefined : { projectId, sessionId: item.sessionId, turnId: item.turnId };
    if (item.source === "restored") {
      return <RestoredTurn turn={item.turn} projectId={projectId} sessionId={item.sessionId} annotationControls={annotationControls} key={item.key} />;
    }
    if (item.source === "live") return <CompletedTurn turn={item.turn} source={source} annotationControls={annotationControls} key={item.key} />;
    return <PendingTurn turn={item.turn} retrying={item.retrying} source={source} key={item.key} />;
  });
});

export function Transcript({ turns, projectId, annotationControls, transcriptRef, endRef, hasOlder = false, issue = null, empty = false, loadOlderDisabled = false, onLoadOlder }: {
  turns: readonly VisibleConversationTurn[]; projectId?: string; annotationControls?: AnnotationControls;
  transcriptRef: RefObject<HTMLDivElement | null>; endRef: RefObject<HTMLDivElement | null>;
  hasOlder?: boolean; issue?: string | null;
  /** Show the empty-conversation prompt when there are no turns. */
  empty?: boolean;
  loadOlderDisabled?: boolean; onLoadOlder?: () => void;
}) {
  return <div className="transcript" ref={transcriptRef} aria-label="Conversation transcript" aria-live="polite">
    {hasOlder && <button className="load-older" type="button" onClick={onLoadOlder} disabled={loadOlderDisabled}>Load older turns</button>}
    {issue !== null && <p className="transcript-issue">{issue}</p>}
    {empty && turns.length === 0 && <div className="conversation-empty"><div className="hero-mark" aria-hidden="true">R</div><h3>What would you like to research?</h3><p>Enter sends. Shift+Enter adds a new line.</p></div>}
    <ConversationTurns turns={turns} projectId={projectId} annotationControls={annotationControls} />
    <div ref={endRef} />
  </div>;
}
