import type { ReactNode } from "react";
import { BarbellIcon, RunIcon, SnowflakeIcon } from "../icons";
import styles from "./Tour.module.css";

// A small key for the streak and calendar steps, drawn with the app's own icons and
// colors, so it matches what the card shows. Every mark has a word next to it, so
// nothing relies on color alone.

function Ring({ tone }: { tone: "green" | "orange" | "grey" }) {
  return (
    <svg className={styles.keyRing} viewBox="0 0 20 20" aria-hidden="true">
      <circle
        className={styles[`key_${tone}`]}
        cx={10}
        cy={10}
        r={8}
        strokeDasharray={tone === "orange" ? "43.3 7" : undefined}
        transform={tone === "orange" ? "rotate(115 10 10)" : undefined}
      />
      {tone === "orange" && <polygon className={styles.keyOver} points="10,15.5 7.5,19.5 12.5,19.5" />}
    </svg>
  );
}

function Item({ mark, label }: { mark: ReactNode; label: string }) {
  return (
    <li className={styles.keyItem}>
      <span className={styles.keyMark} aria-hidden="true">
        {mark}
      </span>
      {label}
    </li>
  );
}

export function Legend({ kind }: { kind: "streak" | "calendar" }) {
  if (kind === "streak") {
    return (
      <ul className={styles.legend} aria-label="Key">
        <Item
          mark={
            <>
              <BarbellIcon className={styles.keyIcon} />
              <RunIcon className={styles.keyIcon} />
            </>
          }
          label="Workout"
        />
        <Item mark={<SnowflakeIcon className={styles.keyIcon} />} label="Rest day" />
        <Item mark={<Ring tone="green" />} label="Within budget" />
        <Item mark={<Ring tone="orange" />} label="Over budget" />
        <Item mark={<Ring tone="grey" />} label="No food logged" />
      </ul>
    );
  }
  return (
    <ul className={styles.legend} aria-label="Key">
      <Item mark={<span className={`${styles.keyDay} ${styles.keyDone} num`}>12</span>} label="Workout" />
      <Item
        mark={
          <span className={`${styles.keyDay} ${styles.keyRest}`}>
            <SnowflakeIcon />
          </span>
        }
        label="Rest day"
      />
    </ul>
  );
}
