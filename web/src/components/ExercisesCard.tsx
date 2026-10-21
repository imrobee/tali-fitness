import { useState } from "react";
import type { Exercise } from "../api/types";
import { ActivityIcon, ChevronDownIcon } from "../icons";
import { formatDuration } from "../lib/format";
import { Card } from "./Card";
import cardStyles from "./Card.module.css";
import styles from "./ExercisesCard.module.css";

/** Rows shown before the card is expanded (UI_SPEC.md 5.5). */
export const COLLAPSED_EXERCISE_COUNT = 1;

interface Props {
  exercises: Exercise[];
  /** Where the whole card links; omit for a plain list (the Activities page). */
  to?: string;
  startExpanded?: boolean;
}

export function ExercisesCard({ exercises, to, startExpanded = false }: Props) {
  // Session-only state: every launch starts collapsed.
  const [expanded, setExpanded] = useState(startExpanded);
  const hidden = exercises.length - COLLAPSED_EXERCISE_COUNT;
  const canExpand = hidden > 0;
  const visible = expanded ? exercises : exercises.slice(0, COLLAPSED_EXERCISE_COUNT);

  return (
    <Card title="Logged exercises" to={to} aside={<span className="num">{exercises.length}</span>}>
      {exercises.length === 0 ? (
        <p className={styles.empty}>No exercises logged for this day.</p>
      ) : (
        <ul className={styles.list} id="exercise-rows">
          {visible.map((exercise) => (
            <li key={exercise.id} className={styles.row}>
              <span className={styles.icon}>
                <ActivityIcon kind={exercise.type} />
              </span>
              <span className={styles.text}>
                <span className={styles.name}>{exercise.title ?? "Activity"}</span>
                <span className={`${styles.duration} num`}>
                  {formatDuration(exercise.duration_s)}
                </span>
              </span>
            </li>
          ))}
        </ul>
      )}

      {canExpand && !startExpanded && (
        <button
          type="button"
          className={`${styles.toggle} ${cardStyles.above}`}
          aria-expanded={expanded}
          aria-controls="exercise-rows"
          aria-label={
            expanded
              ? "Show fewer exercises"
              : `Show ${hidden} more ${hidden === 1 ? "exercise" : "exercises"}`
          }
          onClick={() => setExpanded(!expanded)}
        >
          <ChevronDownIcon className={`${styles.toggleIcon} ${expanded ? styles.open : ""}`} />
        </button>
      )}
    </Card>
  );
}
