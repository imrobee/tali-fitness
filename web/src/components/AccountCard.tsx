import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { AUTH_QUERY, signOut } from "../api/auth";
import { useResetDemo } from "../api/hooks";
import { Card } from "./Card";
import { useIsDemo } from "../api/visit";
import styles from "../pages/MePage.module.css";

/** Me: "Signed in" and Sign out (UI_SPEC.md 6.3). No email or name: the app keeps nothing
    from Google. */
export function AccountCard() {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);
  const demo = useIsDemo();
  const resetDemo = useResetDemo();

  const signOutNow = async () => {
    setBusy(true);
    try {
      await signOut();
    } finally {
      // Drop every page's data from memory, then ask the server again: the session is
      // gone, so the sign-in gate takes over.
      queryClient.removeQueries({ predicate: (query) => query.queryKey[0] !== AUTH_QUERY[0] });
      await queryClient.invalidateQueries({ queryKey: AUTH_QUERY });
    }
  };

  // The demo has no account to sign out of: opening it again would start a new visit.
  // Reset puts back the demo's own settings after a visitor changed theirs.
  if (demo) {
    return (
      <Card title="Account">
        <div className={styles.row}>
          <span>A demo visit: synthetic data. Nothing you change is saved.</span>
          <button type="button" className={styles.change} onClick={resetDemo}>
            Reset demo
          </button>
        </div>
      </Card>
    );
  }

  return (
    <Card title="Account">
      <div className={styles.row}>
        <span>Signed in</span>
        <button type="button" className={styles.change} disabled={busy} onClick={signOutNow}>
          Sign out
        </button>
      </div>
    </Card>
  );
}
