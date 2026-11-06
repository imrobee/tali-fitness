import type { StreakDay } from "../api/types";
import { ActivityIcon, SnowflakeIcon } from "../icons";
import { dayOfMonth } from "../lib/dates";
import { circleLook, RING_RADIUS, RING_SIZE, ringArc, ringTone, trianglePoints } from "../lib/streakRing";
import styles from "./DayCircle.module.css";

// One day of the streak, as the streak card draws it (UI_SPEC.md 5.3): the circle and its
// calorie ring. The streak explainer's example rows use it too, so they match the card.

function CircleContent({ day, today }: { day: StreakDay; today: string }) {
  const look = circleLook(day, today);
  if (look === "active" && day.primary_activity_type !== null) {
    return <ActivityIcon kind={day.primary_activity_type} />;
  }
  if (look === "recovery") return <SnowflakeIcon />;
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

/** Decoration: whoever shows it says the day in words (a visually hidden label). */
export function DayCircle({ day, today }: { day: StreakDay; today: string }) {
  return (
    <span className={styles.ringWrap} aria-hidden="true">
      <CalorieRing day={day} />
      <span className={`${styles.circle} ${styles[circleLook(day, today)]} num`}>
        <CircleContent day={day} today={today} />
      </span>
    </span>
  );
}
