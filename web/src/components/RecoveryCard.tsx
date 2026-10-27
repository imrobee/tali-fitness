import { useRecovery } from "../api/hooks";
import type { Dashboard, RecoveryState } from "../api/types";
import cardStyles from "./Card.module.css";
import styles from "./RecoveryCard.module.css";

type Action = "log" | "undo" | null;

// Copy and controls per state (UI_SPEC.md 5.4). A logged recovery day makes the day a rest
// day: it helps on a day that would end the streak, unless the day before was a rest day.
const STATES: Record<RecoveryState, { title: string; body: string; action: Action }> = {
  available: {
    title: "Taking a recovery day?",
    body: "Logging it makes this a rest day, so your streak keeps going.",
    action: "log",
  },
  logged: {
    title: "Recovery day logged",
    body: "This is a rest day. Two rest days in a row end the streak.",
    action: "undo",
  },
  blocked: {
    title: "Rest day yesterday",
    body: "Two rest days in a row end the streak. A workout keeps it going.",
    action: null,
  },
  counted: {
    title: "This day counted",
    body: "Nice work. No recovery needed.",
    action: null,
  },
  locked: {
    title: "Recovery day",
    body: "Recovery days can only be set for today or yesterday.",
    action: null,
  },
};

interface Props {
  recovery: Dashboard["recovery"];
  selectedDate: string;
}

export function RecoveryCard({ recovery, selectedDate }: Props) {
  const { log, undo } = useRecovery();
  const { title, body, action } = STATES[recovery.state];
  const busy = log.isPending || undo.isPending;
  const error = log.error ?? undo.error;

  return (
    // The state's title is the card's heading (UI_SPEC.md 5.4: title and body left,
    // button right), so the card has no separate header.
    <section className={cardStyles.card} aria-labelledby="recovery-title">
      <div className={styles.row}>
        <div className={styles.text}>
          <h2 id="recovery-title" className={styles.title}>
            {title}
          </h2>
          <p className={styles.body}>{body}</p>
          {error && (
            <p className={styles.error} role="alert">
              {error.message}
            </p>
          )}
        </div>

        {action === "log" && (
          <button
            type="button"
            className={styles.primary}
            disabled={busy}
            onClick={() => log.mutate(selectedDate)}
          >
            Log recovery
          </button>
        )}
        {action === "undo" && (
          <button
            type="button"
            className={styles.secondary}
            disabled={busy}
            onClick={() => undo.mutate(selectedDate)}
          >
            Undo
          </button>
        )}
      </div>
    </section>
  );
}
