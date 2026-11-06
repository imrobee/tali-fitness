import type { ReactNode } from "react";
import { Link } from "react-router";
import styles from "./Card.module.css";

interface CardProps {
  title: string;
  /** When set, the whole card opens this page (stretched link). */
  to?: string;
  /** Small grey text at the right of the title row. */
  aside?: ReactNode;
  /** A small control right after the title (the streak card's "?"). */
  titleAction?: ReactNode;
  label?: string;
  /** The demo tour's name for this card (data-tour), when a tour step points at it. */
  tour?: string;
  children: ReactNode;
}

export function Card({ title, to, aside, titleAction, label, tour, children }: CardProps) {
  return (
    <section className={styles.card} aria-label={label} data-tour={tour}>
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
        {titleAction && <span className={styles.titleAction}>{titleAction}</span>}
        {aside && <span className={styles.aside}>{aside}</span>}
      </div>
      {children}
    </section>
  );
}

/** A grey placeholder bar at the size of the value it stands in for. */
export function Bar({ width, height }: { width: number | string; height: number }) {
  // data-loading: the demo tour waits until a card it points at has none of these left.
  return <span className={styles.bar} style={{ width, height }} aria-hidden="true" data-loading="" />;
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

