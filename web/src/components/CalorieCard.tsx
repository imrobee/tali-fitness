import { Link } from "react-router";
import type { Dashboard } from "../api/types";
import { calorieLabel } from "../lib/a11y";
import { formatNumber } from "../lib/format";
import { arc, ringContent } from "../lib/ring";
import { Card } from "./Card";
import cardStyles from "./Card.module.css";
import styles from "./CalorieCard.module.css";

const SIZE = 176;
const STROKE = 16;
const RADIUS = (SIZE - STROKE) / 2;

interface Props {
  calories: Dashboard["calories"];
  to?: string;
}

export function CalorieCard({ calories, to }: Props) {
  const ring = ringContent(calories.eaten, calories.budget, calories.status);
  const answerClass =
    ring.tone === "over"
      ? styles.answerOver
      : ring.tone === "within"
        ? styles.answerWithin
        : styles.answerEmpty;

  return (
    <Card title="Calorie budget" to={to} tour="calories">
      <div className={styles.columns}>
        <div className={styles.stat}>
          <span className={styles.caption}>Eaten</span>
          <span className={`${styles.value} num`}>{formatNumber(calories.eaten)}</span>
        </div>

        {/* The ring reads as one sentence; with no budget it holds a link instead. */}
        <div
          className={styles.ring}
          role={ring.figure === null ? undefined : "img"}
          aria-label={
            ring.figure === null
              ? undefined
              : calorieLabel(calories.eaten, calories.budget, calories.status)
          }
        >
          <svg viewBox={`0 0 ${SIZE} ${SIZE}`} aria-hidden="true">
            <circle
              className={styles.track}
              cx={SIZE / 2}
              cy={SIZE / 2}
              r={RADIUS}
              fill="none"
              strokeWidth={STROKE}
            />
            {ring.fill > 0 && (
              <circle
                className={`${styles.arc} ${ring.tone === "over" ? styles.over : styles.within}`}
                cx={SIZE / 2}
                cy={SIZE / 2}
                r={RADIUS}
                fill="none"
                strokeWidth={STROKE}
                strokeDasharray={arc(RADIUS, ring.fill).dashArray}
              />
            )}
          </svg>
          <div className={styles.center}>
            {ring.figure === null ? (
              <Link to="/me" className={`${styles.setBudget} ${cardStyles.above}`}>
                Set your calorie budget
              </Link>
            ) : (
              <>
                <span className={`${styles.answer} ${answerClass} num`}>
                  {formatNumber(ring.figure)}
                </span>
                <span className={styles.caption}>{ring.caption}</span>
              </>
            )}
          </div>
        </div>

        <div className={styles.stat}>
          <span className={styles.caption}>Budget</span>
          {calories.budget === null ? (
            <span className={styles.missing} aria-label="Not set">
              —
            </span>
          ) : (
            <span className={`${styles.value} num`}>{formatNumber(calories.budget)}</span>
          )}
        </div>
      </div>
    </Card>
  );
}
