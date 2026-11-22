import { useEffect, useRef } from "react";

import type { DraftAnnotation } from "../conversations.ts";
import type { Reference } from "../protocol.ts";
import { handleAnnotationKey } from "../lib/composer.ts";

export interface AnnotationControls {
  annotations: readonly DraftAnnotation[];
  references: readonly Reference[];
  disabled: boolean;
  onChange: (referenceId: string, comment: string) => void;
  onToggle: (referenceId: string, expanded: boolean) => void;
  onRemove: (referenceId: string) => void;
}

export function AnnotationComment({ annotation, controls }: { annotation: DraftAnnotation; controls: AnnotationControls }) {
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const composingRef = useRef(false);
  useEffect(() => { if (annotation.expanded) inputRef.current?.focus(); }, [annotation.expanded]);
  return <div className="annotation-comment" data-reference-exclude onMouseDown={(event) => event.stopPropagation()}>
    <button className="annotation-number" type="button" aria-label={`Comment ${annotation.number}`}
      aria-expanded={annotation.expanded} disabled={controls.disabled}
      title={annotation.comment || "Add a request for this selection"}
      onClick={() => controls.onToggle(annotation.referenceId, !annotation.expanded)}>{annotation.number}</button>
    {annotation.expanded && <div className="annotation-popup">
      <label>Comment {annotation.number}<textarea ref={inputRef} rows={3} value={annotation.comment} disabled={controls.disabled}
        aria-label={`Comment ${annotation.number}`} placeholder="What should the agent do with this passage?"
        onChange={(event) => controls.onChange(annotation.referenceId, event.target.value)}
        onCompositionStart={() => { composingRef.current = true; }} onCompositionEnd={() => { composingRef.current = false; }}
        onKeyDown={(event) => handleAnnotationKey({ key: event.key, shiftKey: event.shiftKey,
          isComposing: composingRef.current || event.nativeEvent.isComposing || event.nativeEvent.keyCode === 229,
          preventDefault: () => event.preventDefault(), stopPropagation: () => event.stopPropagation(),
        }, () => controls.onToggle(annotation.referenceId, false))} /></label>
      <div className="annotation-actions">
        <button type="button" disabled={controls.disabled} onClick={() => controls.onToggle(annotation.referenceId, false)}>Done</button>
        <button type="button" disabled={controls.disabled} onClick={() => controls.onRemove(annotation.referenceId)}>Remove</button>
      </div>
      <p>Enter to confirm · Shift+Enter for a new line</p>
    </div>}
  </div>;
}
