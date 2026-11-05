// What the sign-in gate knows about this browser, and the hook pages use to tell the public
// demo from Rob's own app. Kept apart from SignInGate.tsx, which exports components only.

import { useQueryClient } from "@tanstack/react-query";
import { AUTH_QUERY, checkSignedIn, fetchSignInMethod, type SignInMethod, startDemo } from "./auth";

export type Auth =
  | { signedIn: true; demo: boolean }
  | { signedIn: false; method: SignInMethod; demoUrl: string | null };

export async function loadAuth(): Promise<Auth> {
  const visit = await checkSignedIn();
  if (visit.signedIn) return visit;
  const { method, demoUrl } = await fetchSignInMethod();
  // The demo server has no sign-in: opening it is pressing Demo, so start the visit.
  if (method === "demo" && (await startDemo())) return { signedIn: true, demo: true };
  return { signedIn: false, method, demoUrl };
}

/** True on the public demo: the header shows "Demo data" (UI_SPEC.md section 1). Reads the
    gate's own answer from the cache; no extra request. */
export function useIsDemo(): boolean {
  const auth = useQueryClient().getQueryData<Auth>(AUTH_QUERY);
  return auth?.signedIn === true && auth.demo;
}
