/**
 * Run a reducer exactly once for an action, then publish the single result to a ref (read
 * synchronously by event handlers) and to React state (read by renders).
 */
export function applyReducerOnce<State, Action>(
  reducer: (state: State, action: Action) => State,
  ref: { current: State },
  publish: (next: State) => void,
  action: Action,
): State {
  const next = reducer(ref.current, action);
  if (next !== ref.current) {
    ref.current = next;
    publish(next);
  }
  return next;
}
