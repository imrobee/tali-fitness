import type { ReactNode } from "react";
import styles from "./Page.module.css";

/** A page: one <main>, one h1 (UI_SPEC.md section 8). */
export function Page({ title, children }: { title: ReactNode; children: ReactNode }) {
  return (
    <main className={styles.page}>
      <h1 className={styles.title}>{title}</h1>
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
