import type { Dashboard, StreakDay } from "../api/types";
import { ActivityIcon, FlameIcon, SnowflakeIcon } from "../icons";
import { streakDayLabel, streakSummary } from "../lib/a11y";
import { dayOfMonth } from "../lib/dates";
import { circleLook, RING_RADIUS, RING_SIZE, ringArc, ringTone, trianglePoints } from "../lib/streakRing";
import { Card } from "./Card";
import styles from "./StreakCard.module.css";

interface Props {
  streak: Dashboard["streak"];
  today: string;
}

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

  return (
    <Card title="Your streak" tour="streak" aside={<FlameCount count={streak.count} compact />}>
      <p className="visually-hidden">{streakSummary(streak.count, todayState, streak.at_risk)}</p>
      <div className={styles.body}>
        <FlameCount count={streak.count} />

        <ol className={styles.week} aria-label="This week">
          {streak.week.map((day) => (
            <li key={day.date} className={styles.day}>
              <span className="visually-hidden">{streakDayLabel(day)}</span>
              <span className={styles.ringWrap} aria-hidden="true">
                <CalorieRing day={day} />
                <span className={`${styles.circle} ${styles[circleLook(day, today)]} num`}>
                  <CircleContent day={day} today={today} />
                </span>
              </span>
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
