import { useRecovery } from "../api/hooks";
import type { Dashboard, RecoveryState } from "../api/types";
import { SnowflakeIcon } from "../icons";
import { addDays } from "../lib/dates";
import cardStyles from "./Card.module.css";
import styles from "./RecoveryCard.module.css";

type Action = "log" | "undo" | "yesterday" | null;

// Copy and controls per state, word for word from UI_SPEC.md 5.4.
const STATES: Record<RecoveryState, { title: string; body: string; action: Action }> = {
  available: {
    title: "Taking a recovery day?",
    body: "Rest counts. Your freeze keeps the streak on hold.",
    action: "log",
  },
  logged: {
    title: "Recovery day logged",
    body: "Your streak is on hold. A workout and logged calories reset your freeze.",
    action: "undo",
  },
  no_freeze: {
    title: "No freezes left",
    body: "Log a workout and calories to reset your freeze.",
    action: null,
  },
  blocked: {
    title: "Fill in yesterday first",
    body: "A freeze needs yesterday to be counted.",
    action: "yesterday",
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

function pillText(state: RecoveryState, freezesLeft: number): string | null {
  if (state === "locked") return null;
  if (state === "logged") return "Freeze used";
  if (state === "available" || state === "counted") {
    return freezesLeft === 1 ? "1 freeze available" : `${freezesLeft} freezes available`;
  }
  return "0 freezes";
}

interface Props {
  recovery: Dashboard["recovery"];
  selectedDate: string;
  onSelect: (date: string) => void;
}

export function RecoveryCard({ recovery, selectedDate, onSelect }: Props) {
  const { log, undo } = useRecovery();
  const { title, body, action } = STATES[recovery.state];
  const pill = pillText(recovery.state, recovery.freezes_left);
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
          {pill && (
            <span className={styles.pill}>
              <SnowflakeIcon className={styles.pillIcon} />
              {pill}
            </span>
          )}
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
        {action === "yesterday" && (
          <button
            type="button"
            className={styles.secondary}
            onClick={() => onSelect(addDays(selectedDate, -1))}
          >
            Go to yesterday
          </button>
        )}
      </div>
    </section>
  );
}
