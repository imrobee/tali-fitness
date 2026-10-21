import type { Dashboard, StreakDay } from "../api/types";
import { ActivityIcon, FlameIcon, SnowflakeIcon } from "../icons";
import { streakDayLabel, streakSummary } from "../lib/a11y";
import { addDays, dayOfMonth } from "../lib/dates";
import { Card } from "./Card";
import styles from "./StreakCard.module.css";

interface Props {
  streak: Dashboard["streak"];
  today: string;
  selectedDate: string;
  onSelect: (date: string) => void;
}

/** Days where the marker shows: past days and today, except recovery and future days
    with no calories logged (UI_SPEC.md 5.3). */
function showMarker(day: StreakDay): boolean {
  if (day.state === "future") return false;
  if (day.state === "recovery") return day.calorie_status !== "not_logged";
  return true;
}

function CircleContent({ day }: { day: StreakDay }) {
  if (day.state === "qualifying") return <ActivityIcon kind={day.primary_activity_type} />;
  if (day.state === "recovery") return <SnowflakeIcon />;
  return <>{dayOfMonth(day.date)}</>;
}

export function StreakCard({ streak, today, selectedDate, onSelect }: Props) {
  const todayState = streak.week.find((day) => day.date === today)?.state;
  const yesterday = addDays(today, -1);

  return (
    <Card title="Your streak" quietTitle>
      <p className="visually-hidden">{streakSummary(streak.count, todayState, streak.at_risk)}</p>
      <div className={styles.body}>
        <div className={styles.flameBlock} aria-hidden="true">
          <div className={styles.flame}>
            <FlameIcon />
            <span className={`${styles.count} num`}>{streak.count}</span>
          </div>
          <span className={styles.unit}>{streak.count === 1 ? "Day" : "Days"}</span>
        </div>

        <ol className={styles.week} aria-label="This week">
          {streak.week.map((day) => {
            const isFuture = day.state === "future";
            const isSelected = day.date === selectedDate;
            const marker = showMarker(day)
              ? styles[`marker_${day.calorie_status}`]
              : styles.marker_hidden;
            return (
              <li key={day.date}>
                <button
                  type="button"
                  className={styles.day}
                  disabled={isFuture}
                  aria-pressed={isFuture ? undefined : isSelected}
                  aria-label={streakDayLabel(day)}
                  onClick={() => onSelect(day.date)}
                >
                  <span className={`${styles.circle} ${styles[day.state]} num`}>
                    <CircleContent day={day} />
                  </span>
                  <span className={`${styles.marker} ${marker}`} />
                  <span className={`${styles.letter} ${isSelected ? styles.selected : ""}`}>
                    {day.weekday}
                  </span>
                </button>
              </li>
            );
          })}
        </ol>
      </div>

      {streak.message && (
        <p className={styles.message}>
          {streak.message}
          {streak.at_risk && (
            <button type="button" className={styles.fillIn} onClick={() => onSelect(yesterday)}>
              Fill in
            </button>
          )}
        </p>
      )}
    </Card>
  );
}
