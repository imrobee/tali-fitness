import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { AUTH_QUERY, signOut } from "../api/auth";
import { Card } from "./Card";
import styles from "../pages/MePage.module.css";

/** Me: "Signed in" and Sign out (UI_SPEC.md 6.3). No email or name: the app keeps nothing
    from Google. Not on the demo, which has no account (MePage's DemoFooter instead). */
export function AccountCard() {
  const queryClient = useQueryClient();
  const [busy, setBusy] = useState(false);

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
