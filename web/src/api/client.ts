// One way to call the API. The browser sends the session cookie by itself (same origin);
// every failure becomes an ApiError with the server's code and message
// ({"error": {"code", "message"}}). On the demo, a visitor's own settings ride along.

import { demoSettingsHeader } from "../demo/settings";

export class ApiError extends Error {
  status: number;
  code: string;

  constructor(status: number, code: string, message: string) {
    super(message);
    this.status = status;
    this.code = code;
  }
}

/** Fired on any 401 so the sign-in gate can take over (UI_SPEC.md section 1). */
export const UNAUTHORIZED_EVENT = "api:unauthorized";

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(`/api/v1${path}`, {
    ...init,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...demoSettingsHeader(),
      ...init.headers,
    },
  });

  if (response.status === 204) return undefined as T;
  const body = await response.json().catch(() => null);

  if (!response.ok) {
    if (response.status === 401) window.dispatchEvent(new Event(UNAUTHORIZED_EVENT));
    throw new ApiError(
      response.status,
      body?.error?.code ?? "http_error",
      body?.error?.message ?? `The server answered ${response.status}.`,
    );
  }
  return body as T;
}

/** A failed fetch() (server down, Wi-Fi off) rather than an error answer from the API. */
export function isOffline(error: unknown): boolean {
  return !(error instanceof ApiError);
}
