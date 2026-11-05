import type { Dashboard } from "../api/types";
import { FlameIcon } from "../icons";
import { streakDayLabel, streakSummary } from "../lib/a11y";
import { useTour } from "../tour/context";
import { Card } from "./Card";
import { DayCircle } from "./DayCircle";
import styles from "./StreakCard.module.css";

interface Props {
  streak: Dashboard["streak"];
  today: string;
}

/** Flame, count and "Days". Large beside the week; small in the header on a phone. */
function FlameCount({ count, compact }: { count: number; compact?: boolean }) {
  const unit = count === 1 ? "Day" : "Days";
  if (compact) {
    return (
      <span className={styles.compact} aria-hidden="true">
        <FlameIcon className={styles.compactFlame} />
        <span className="num">{count}</span> {unit}
      </span>
    );
  }
  return (
    <div className={styles.flameBlock} aria-hidden="true">
      <div className={styles.flame}>
        <FlameIcon />
        <span className={`${styles.count} num`}>{count}</span>
      </div>
      <span className={styles.unit}>{unit}</span>
    </div>
  );
}

// The week is for reading only: the day chooser above picks the dashboard's day.
export function StreakCard({ streak, today }: Props) {
  const todayState = streak.week.find((day) => day.date === today)?.state;
  const tour = useTour();
  // The rules, step by step, in the tour's sheet (D129). Never opens by itself.
  const help = (
    <button type="button" className={styles.help} aria-label="How streaks work" onClick={() => tour.start("streak")}>
      <span className={styles.helpMark} aria-hidden="true">
        ?
      </span>
    </button>
  );

  return (
    <Card
      title="Your streak"
      tour="streak"
      titleAction={help}
      aside={<FlameCount count={streak.count} compact />}
    >
      <p className="visually-hidden">{streakSummary(streak.count, todayState, streak.at_risk)}</p>
      <div className={styles.body}>
        <FlameCount count={streak.count} />

        <ol className={styles.week} aria-label="This week">
          {streak.week.map((day) => (
            <li key={day.date} className={styles.day}>
              <span className="visually-hidden">{streakDayLabel(day)}</span>
              <DayCircle day={day} today={today} />
              <span className={styles.letter} aria-hidden="true">
                {day.weekday}
              </span>
            </li>
          ))}
        </ol>
      </div>

      {streak.message && <p className={styles.message}>{streak.message}</p>}
    </Card>
  );
}
