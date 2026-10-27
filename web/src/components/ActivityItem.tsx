import { useState } from "react";
import { useActivity, useWeightUnit } from "../api/hooks";
import type { ActivitySummary } from "../api/types";
import { activitySummary, setMeasure, timeRange } from "../lib/activities";
import { ActivityIcon, ChevronDownIcon } from "../icons";
import { Bar } from "./Card";
import styles from "./ActivityItem.module.css";

interface Props {
  activity: ActivitySummary;
}

/**
 * One activity in the day list (UI_SPEC.md 6.1). Lifting sessions and sessions whose text
 * could not be read open to show their sets; other activities are plain rows.
 */
export function ActivityItem({ activity }: Props) {
  const [open, setOpen] = useState(false);
  const unit = useWeightUnit();
  const expandable = activity.set_count > 0 || activity.parse_status === "partial";
  const panelId = `activity-${activity.id}-sets`;
  const head = (
    <>
      <span className={styles.icon}>
        <ActivityIcon kind={activity.type} />
      </span>
      <span className={styles.text}>
        <span className={styles.title}>{activity.title ?? "Activity"}</span>
        <span className={`${styles.meta} num`}>
          {timeRange(activity.started_at, activity.duration_s)}
        </span>
        <span className={`${styles.meta} num`}>{activitySummary(activity, unit)}</span>
      </span>
    </>
  );

  if (!expandable) {
    return (
      <li className={styles.item}>
        <div className={styles.head}>{head}</div>
      </li>
    );
  }

  return (
    <li className={styles.item}>
      <button
        type="button"
        className={`${styles.head} ${styles.toggle}`}
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((value) => !value)}
      >
        {head}
        <ChevronDownIcon className={`${styles.chevron} ${open ? styles.open : ""}`} />
      </button>
      {open && (
        <div id={panelId} className={styles.body}>
          <SetDetail id={activity.id} />
        </div>
      )}
    </li>
  );
}

/** Loads the sets once the row is open; the list itself stays light. */
function SetDetail({ id }: { id: number }) {
  const query = useActivity(id);
  const unit = useWeightUnit();

  if (query.isPending) return <Bar width="100%" height={80} />;
  if (query.isError) {
    return <p className={styles.note}>Couldn't load the sets. Open the row again to retry.</p>;
  }

  const detail = query.data;
  return (
    <>
      {detail.parse_status === "partial" && (
        <p className={styles.tag}>Couldn't read some sets</p>
      )}
      {detail.exercises.map((exercise) => (
        <div key={exercise.order} className={styles.exercise}>
          <p className={styles.exerciseName}>
            {exercise.name}
            {exercise.equipment && <span className={styles.muted}> · {exercise.equipment}</span>}
          </p>
          {exercise.note && <p className={styles.muted}>{exercise.note}</p>}
          <ol className={styles.sets}>
            {exercise.sets.map((set) => (
              <li key={set.number} className={`${styles.set} num`}>
                <span className={styles.muted}>Set {set.number}</span>
                <span>{setMeasure(set, unit)}</span>
              </li>
            ))}
          </ol>
        </div>
      ))}
      {detail.description_raw && (
        <details className={styles.raw}>
          <summary>
            Raw description <ChevronDownIcon className={styles.chevron} />
          </summary>
          <pre>{detail.description_raw}</pre>
        </details>
      )}
    </>
  );
}
