import type { ReactNode } from "react";
import styles from "./Page.module.css";
import { useIsDemo } from "../api/visit";
import { ThemeToggle } from "./ThemeToggle";

/** A page: one <main>, one h1 (UI_SPEC.md section 8), the theme toggle at its right. On
    the public demo, a "Demo data" badge sits beside it on every page. */
export function Page({ title, children }: { title: ReactNode; children: ReactNode }) {
  const demo = useIsDemo();
  return (
    <main className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>{title}</h1>
        {demo && <span className={styles.demoBadge}>Demo data</span>}
        <ThemeToggle />
      </div>
      {children}
    </main>
  );
}

/** Shown when the API cannot be reached at all (UI_SPEC.md section 10). */
export function OfflineBanner({ onRetry }: { onRetry: () => void }) {
  return (
    <div className={styles.banner} role="alert">
      <span>Can't reach the server.</span>
      <button type="button" className={styles.bannerButton} onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}
