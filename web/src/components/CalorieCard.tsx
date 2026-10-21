import { useEffect, useState } from "react";
import { Link } from "react-router";
import type { Dashboard } from "../api/types";
import { calorieLabel } from "../lib/a11y";
import { formatNumber } from "../lib/format";
import { arc, dashedArc, ringContent } from "../lib/ring";
import { Card } from "./Card";
import cardStyles from "./Card.module.css";
import styles from "./CalorieCard.module.css";

const SIZE = 176;
const STROKE = 16;
const RADIUS = (SIZE - STROKE) / 2;
const OVERFLOW_RADIUS = RADIUS - STROKE / 2 - 6; // just inside the main ring

interface Props {
  calories: Dashboard["calories"];
  to?: string;
}

/** Grows from 0 to `target` once after mounting, so the ring fills in (CSS transition). */
function useGrowIn(target: number): number {
  const [value, setValue] = useState(0);
  useEffect(() => {
    const frame = requestAnimationFrame(() => setValue(target));
    return () => cancelAnimationFrame(frame);
  }, [target]);
  return value;
}

export function CalorieCard({ calories, to }: Props) {
  const ring = ringContent(calories.eaten, calories.budget, calories.status);
  const fill = useGrowIn(ring.fill);
  const answerClass =
    ring.tone === "over"
      ? styles.answerOver
      : ring.tone === "within"
        ? styles.answerWithin
        : styles.answerEmpty;

  return (
    <Card title="Calorie budget" to={to}>
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
                strokeDasharray={arc(RADIUS, fill).dashArray}
              />
            )}
            {ring.overflow > 0 && (
              <circle
                className={styles.overflow}
                cx={SIZE / 2}
                cy={SIZE / 2}
                r={OVERFLOW_RADIUS}
                fill="none"
                strokeWidth={3}
                strokeDasharray={dashedArc(OVERFLOW_RADIUS, ring.overflow).dashArray}
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
