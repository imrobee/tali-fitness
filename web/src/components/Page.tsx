import type { ReactNode } from "react";
import { useIsDemo } from "../api/visit";
import { useTour } from "../tour/context";
import styles from "./Page.module.css";
import { ThemeToggle } from "./ThemeToggle";

/** A page: one <main>, one h1 (UI_SPEC.md section 8), the theme toggle at its right. On
    the public demo, a bar above it on every page: the "Demo version" badge and the tour. */
export function Page({ title, children }: { title: ReactNode; children: ReactNode }) {
  const demo = useIsDemo();
  const tour = useTour();
  return (
    <main className={styles.page}>
      {demo && (
        <div className={styles.demoBar}>
          <span className={styles.demoBadge}>Demo version</span>
          <button type="button" className={styles.tourButton} onClick={() => tour.start()}>
            Take the tour
          </button>
        </div>
      )}
      <div className={styles.header} data-tour="page-title">
        <h1 className={styles.title}>{title}</h1>
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
