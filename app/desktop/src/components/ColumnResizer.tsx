import { useEffect, useRef, type KeyboardEvent, type PointerEvent } from "react";

export interface DragStartMetrics {
  startPx: number;
  containerPx: number;
}

export type ResizerKeyboardAction = "decrease" | "increase" | "min" | "max";

export interface ColumnResizerProps {
  className?: string;
  label: string;
  valueNow: number;
  valueMin: number;
  valueMax: number;
  inert?: boolean;
  onDragStart: () => DragStartMetrics | null;
  onDragMove: (start: DragStartMetrics, deltaX: number) => void;
  onDragEnd: (start: DragStartMetrics, deltaX: number, cancelled: boolean) => void;
  onKeyboardStep: (action: ResizerKeyboardAction) => void;
  onReset: () => void;
}

const RESIZING_BODY_CLASS = "is-resizing-columns";

export function keyboardActionForResizerKey(key: string): ResizerKeyboardAction | null {
  switch (key) {
    case "ArrowLeft":
      return "decrease";
    case "ArrowRight":
      return "increase";
    case "Home":
      return "min";
    case "End":
      return "max";
    default:
      return null;
  }
}

/** Accessible vertical column splitter supporting pointer drag, arrow keys and double-click reset. */
export function ColumnResizer({
  className,
  label,
  valueNow,
  valueMin,
  valueMax,
  inert = false,
  onDragStart,
  onDragMove,
  onDragEnd,
  onKeyboardStep,
  onReset,
}: ColumnResizerProps) {
  const dragRef = useRef<{
    pointerId: number;
    startX: number;
    lastDeltaX: number;
    start: DragStartMetrics;
    element: HTMLDivElement;
  } | null>(null);

  useEffect(() => {
    return () => {
      if (dragRef.current) {
        dragRef.current.element.classList.remove("is-dragging");
        dragRef.current = null;
        document.body.classList.remove(RESIZING_BODY_CLASS);
      }
    };
  }, []);

  const finishDrag = (deltaX: number, cancelled: boolean) => {
    const active = dragRef.current;
    if (!active) return;
    dragRef.current = null;
    active.element.classList.remove("is-dragging");
    document.body.classList.remove(RESIZING_BODY_CLASS);
    try {
      if (active.element.hasPointerCapture?.(active.pointerId)) {
        active.element.releasePointerCapture(active.pointerId);
      }
    } catch {
      // Capture may already have ended.
    }
    onDragEnd(active.start, deltaX, cancelled);
  };

  const handlePointerDown = (event: PointerEvent<HTMLDivElement>) => {
    if (inert || event.button !== 0) return;
    const start = onDragStart();
    if (!start) return;
    event.preventDefault();
    const element = event.currentTarget;
    dragRef.current = {
      pointerId: event.pointerId,
      startX: event.clientX,
      lastDeltaX: 0,
      start,
      element,
    };
    element.classList.add("is-dragging");
    document.body.classList.add(RESIZING_BODY_CLASS);
    try {
      element.setPointerCapture?.(event.pointerId);
    } catch {
      // Synthetic events or unsupported environments may not support capture.
    }
  };

  const handlePointerMove = (event: PointerEvent<HTMLDivElement>) => {
    const active = dragRef.current;
    if (!active || event.pointerId !== active.pointerId) return;
    const deltaX = event.clientX - active.startX;
    active.lastDeltaX = deltaX;
    onDragMove(active.start, deltaX);
  };

  const handlePointerUp = (event: PointerEvent<HTMLDivElement>) => {
    const active = dragRef.current;
    if (!active || event.pointerId !== active.pointerId) return;
    const deltaX = event.clientX - active.startX;
    finishDrag(deltaX, false);
  };

  const handlePointerCancel = (event: PointerEvent<HTMLDivElement>) => {
    const active = dragRef.current;
    if (!active || event.pointerId !== active.pointerId) return;
    finishDrag(active.lastDeltaX, true);
  };

  const handleLostPointerCapture = (event: PointerEvent<HTMLDivElement>) => {
    const active = dragRef.current;
    if (!active || event.pointerId !== active.pointerId) return;
    finishDrag(active.lastDeltaX, true);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (inert || event.nativeEvent?.isComposing || event.ctrlKey || event.metaKey || event.altKey) return;
    const action = keyboardActionForResizerKey(event.key);
    if (!action) return;
    event.preventDefault();
    onKeyboardStep(action);
  };

  const handleDoubleClick = () => {
    if (inert) return;
    onReset();
  };

  const classes = className ? `column-resizer ${className}` : "column-resizer";

  return (
    <div
      role="separator"
      aria-orientation="vertical"
      aria-label={label}
      aria-valuenow={Math.round(valueNow)}
      aria-valuemin={Math.round(valueMin)}
      aria-valuemax={Math.round(valueMax)}
      tabIndex={inert ? -1 : 0}
      inert={inert}
      className={classes}
      title={`${label} (drag, arrow keys, or double-click to reset)`}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
      onPointerCancel={handlePointerCancel}
      onLostPointerCapture={handleLostPointerCapture}
      onDoubleClick={handleDoubleClick}
      onKeyDown={handleKeyDown}
    />
  );
}
