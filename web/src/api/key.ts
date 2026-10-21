// The API key lives in this browser's localStorage, entered once on the key gate
// (ARCHITECTURE.md section 12). It is never bundled into the JavaScript.
// Storage can throw (private browsing, blocked site data), so every access is guarded.

const STORAGE_KEY = "fitness-tracker.api-key";

export function getApiKey(): string | null {
  try {
    return window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setApiKey(key: string): void {
  try {
    window.localStorage.setItem(STORAGE_KEY, key);
  } catch {
    // Storage blocked: the key works until the page reloads.
  }
}

export function clearApiKey(): void {
  try {
    window.localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Nothing stored.
  }
}

/** "••••••ab12": enough to recognise the key, not enough to use it. */
export function maskKey(key: string): string {
  return `••••••${key.slice(-4)}`;
}
