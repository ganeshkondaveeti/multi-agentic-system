// The shared access code lives in sessionStorage for this tab only. Nothing else is
// stored in the browser: complaint and pushback text never leave component state.

const KEY = "reply-desk.access-code";

type Listener = () => void;
const listeners = new Set<Listener>();

export function getAccessCode(): string | null {
  try {
    return sessionStorage.getItem(KEY);
  } catch {
    return null;
  }
}

export function setAccessCode(code: string): void {
  try {
    sessionStorage.setItem(KEY, code);
  } catch {
    // Storage blocked: the code lasts until reload, through the request headers only.
  }
  notify();
}

export function clearAccessCode(): void {
  try {
    sessionStorage.removeItem(KEY);
  } catch {
    // Nothing stored.
  }
  notify();
}

/** Called by the client on a 401 so the gate can ask again. */
export function accessRejected(): void {
  clearAccessCode();
}

export function onAccessChange(listener: Listener): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function notify(): void {
  for (const listener of listeners) listener();
}
