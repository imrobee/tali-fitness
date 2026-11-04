// Signing in and out (docs/AUTH_SPEC.md section 9). The browser holds only the HttpOnly
// session cookie, which no script can read: nothing about sign-in is kept in storage, in
// JavaScript variables or in URLs.

import { ApiError } from "./client";

export type SignInMethod = "google" | "key";

/** The React Query key of "is this browser signed in?" (SignInGate). */
export const AUTH_QUERY = ["auth"];

// Where the shared API key of earlier versions was kept. It is removed on every load, so a
// leaked old key does not linger on Rob's devices.
const OLD_KEY_STORAGE = "fitness-tracker.api-key";

export function forgetOldKey(): void {
  try {
    window.localStorage.removeItem(OLD_KEY_STORAGE);
  } catch {
    // Storage blocked: nothing could have been stored either.
  }
}

/** True when the session cookie is valid; false on 401. Throws when the server can't be reached. */
export async function checkSignedIn(): Promise<boolean> {
  const response = await fetch("/auth/me", { credentials: "same-origin" });
  if (response.status === 401) return false;
  if (!response.ok) {
    throw new ApiError(response.status, "http_error", `The server answered ${response.status}.`);
  }
  return true;
}

/** Which sign-in screen this server wants: the Google button or the local dev key form. */
export async function fetchSignInMethod(): Promise<SignInMethod> {
  const response = await fetch("/auth/method", { credentials: "same-origin" });
  const body = await response.json();
  return body.method === "key" ? "key" : "google";
}

/** A full-page link: Google's page opens in this tab, and no Google script runs in ours. */
export function googleSignInUrl(returnTo: string): string {
  return `/auth/login?next=${encodeURIComponent(returnTo)}`;
}

/** The dev key form (local key mode only). True when the key was accepted. */
export async function devSignIn(key: string): Promise<boolean> {
  const response = await fetch("/auth/dev-login", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ key }),
  });
  return response.ok;
}

export async function signOut(): Promise<void> {
  await fetch("/auth/logout", {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/json" },
  });
}
