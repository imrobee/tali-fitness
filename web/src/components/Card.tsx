import type { ReactNode } from "react";
import { Link } from "react-router";
import styles from "./Card.module.css";

interface CardProps {
  title: string;
  /** When set, the whole card opens this page (stretched link). */
  to?: string;
  /** Small grey text at the right of the title row. */
  aside?: ReactNode;
  label?: string;
  children: ReactNode;
}

export function Card({ title, to, aside, label, children }: CardProps) {
  return (
    <section className={styles.card} aria-label={label}>
      <div className={styles.header}>
        <h2 className={styles.title}>
          {to ? (
            <Link to={to} className={styles.stretched}>
              {title}
            </Link>
          ) : (
            title
          )}
        </h2>
        {aside && <span className={styles.aside}>{aside}</span>}
      </div>
      {children}
    </section>
  );
}

/** A grey placeholder bar at the size of the value it stands in for. */
export function Bar({ width, height }: { width: number | string; height: number }) {
  return <span className={styles.bar} style={{ width, height }} aria-hidden="true" />;
}

/** One sentence and a Retry button, inside the card that failed (UI_SPEC.md 10). */
export function CardError({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className={styles.error} role="alert">
      <span>{message}</span>
      <button type="button" className={`${styles.retry} ${styles.above}`} onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}

