// Signing in and out (docs/AUTH_SPEC.md section 9). The browser holds only the HttpOnly
// session cookie, which no script can read: nothing about sign-in is kept in storage, in
// JavaScript variables or in URLs.

import { ApiError } from "./client";

// "demo": this server is the public demo (synthetic data, read-only, no sign-in).
export type SignInMethod = "google" | "key" | "demo";

/** How this server signs people in, and where its launch screen's Demo button goes. */
export type SignInInfo = { method: SignInMethod; demoUrl: string | null };

/** Who this browser is: signed in (Rob, or a demo visitor) or not. */
export type Visit =
  | {
      signedIn: true;
      demo: boolean;
      story: Record<string, string | number | null> | null;
      /** The demo only: the real app's launch screen. */
      launchUrl: string | null;
    }
  | { signedIn: false };

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

/** Signed in when the session (or demo) cookie is valid; not on 401. Throws when the
    server can't be reached. */
export async function checkSignedIn(): Promise<Visit> {
  const response = await fetch("/auth/me", { credentials: "same-origin" });
  if (response.status === 401) return { signedIn: false };
  if (!response.ok) {
    throw new ApiError(response.status, "http_error", `The server answered ${response.status}.`);
  }
  const body = await response.json();
  return {
    signedIn: true,
    demo: body.demo === true,
    story: body.story ?? null,
    launchUrl: typeof body.launch_url === "string" ? body.launch_url : null,
  };
}

/** Which sign-in screen this server wants: the Google button, the local dev key form, or
    none at all (the demo). */
export async function fetchSignInMethod(): Promise<SignInInfo> {
  const response = await fetch("/auth/method", { credentials: "same-origin" });
  const body = await response.json();
  const method: SignInMethod = body.method === "key" || body.method === "demo" ? body.method : "google";
  return { method, demoUrl: typeof body.demo_url === "string" ? body.demo_url : null };
}

/** The demo server only: start a visit (a signed cookie). True when it started. */
export async function startDemo(): Promise<boolean> {
  const response = await fetch("/auth/demo", { method: "POST", credentials: "same-origin" });
  return response.ok;
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
