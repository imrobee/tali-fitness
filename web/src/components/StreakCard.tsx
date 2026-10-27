import type { Dashboard, StreakDay } from "../api/types";
import { ActivityIcon, FlameIcon, SnowflakeIcon } from "../icons";
import { streakDayLabel, streakSummary } from "../lib/a11y";
import { addDays, dayOfMonth } from "../lib/dates";
import { RING_RADIUS, RING_SIZE, ringArc, ringTone, trianglePoints } from "../lib/streakRing";
import { Card } from "./Card";
import styles from "./StreakCard.module.css";

interface Props {
  streak: Dashboard["streak"];
  today: string;
  selectedDate: string;
  onSelect: (date: string) => void;
}

/** The circle's look: a workout is a white circle with its icon, a rest day without a
    workout the snowflake, today an outline, everything else a dark circle with the date. */
function circleClass(day: StreakDay, today: string): string {
  if (day.state === "future") return styles.future;
  if (day.primary_activity_type !== null) return styles.active;
  if (day.kind === "recovery") return styles.recovery;
  if (day.state === "at_risk") return styles.at_risk;
  if (day.date === today) return styles.today;
  return styles.missed;
}

function CircleContent({ day }: { day: StreakDay }) {
  if (day.state !== "future" && day.primary_activity_type !== null) {
    return <ActivityIcon kind={day.primary_activity_type} />;
  }
  if (day.state !== "future" && day.kind === "recovery") return <SnowflakeIcon />;
  return <>{dayOfMonth(day.date)}</>;
}

/** The calorie ring around a circle (UI_SPEC.md 5.3). None on future days. */
function CalorieRing({ day }: { day: StreakDay }) {
  if (day.state === "future") return null;
  const tone = ringTone(day.calorie_status);
  const { dasharray, rotate } = ringArc(tone);
  const centre = RING_SIZE / 2;
  return (
    <svg className={styles.ring} viewBox={`0 0 ${RING_SIZE} ${RING_SIZE}`} aria-hidden="true">
      <circle
        className={styles[`ring_${tone}`]}
        cx={centre}
        cy={centre}
        r={RING_RADIUS}
        strokeDasharray={dasharray ?? undefined}
        transform={rotate ? `rotate(${rotate} ${centre} ${centre})` : undefined}
      />
      {tone === "orange" && <polygon className={styles.overMark} points={trianglePoints(centre)} />}
    </svg>
  );
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
                  <span className={styles.ringWrap}>
                    <CalorieRing day={day} />
                    <span className={`${styles.circle} ${circleClass(day, today)} num`}>
                      <CircleContent day={day} />
                    </span>
                  </span>
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
