import type { ReactNode } from "react";
import { useIsDemo } from "../api/visit";
import { useTour } from "../tour/context";
import styles from "./Page.module.css";
import { ThemeToggle } from "./ThemeToggle";
import { Wordmark } from "./Wordmark";

/** A page: one <main>, one h1 (UI_SPEC.md section 8), the theme toggle at its right. Above
    it on every page, a top bar with the "tali" wordmark in the middle; on the public demo
    the bar also holds the "Demo version" badge (left) and the tour (right). */
export function Page({ title, children }: { title: ReactNode; children: ReactNode }) {
  const demo = useIsDemo();
  const tour = useTour();
  return (
    <main className={styles.page}>
      <div className={styles.topBar}>
        <span className={styles.barStart}>{demo && <span className={styles.demoBadge}>Demo version</span>}</span>
        {/* Decoration: the page's h1 and the browser tab already name the app. */}
        <Wordmark className={styles.wordmark} decorative />
        <span className={styles.barEnd}>
          {demo && (
            <button type="button" className={styles.tourButton} onClick={() => tour.start()}>
              Take the tour
            </button>
          )}
        </span>
      </div>
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
