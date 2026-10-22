import { percentOf } from "../lib/chart";
import styles from "./TrendBars.module.css";

export interface TrendBar {
  key: string;
  value: number | null; // null: no bar
  /** Picks the colour: "training", or a calorie status (within, over, not_set). */
  tone: string;
  current: boolean; // the period still running: drawn as "so far"
  /** A dashed reference segment over this bar (the average budget), if any. */
  reference: number | null;
  axis: [string, string];
  label: string; // the spoken sentence for this bar
}

interface Props {
  bars: TrendBar[];
  max: number;
  /** Text at the right end of the last reference segment, e.g. "1,853". */
  referenceLabel?: string;
}

/** Bars per week or month, hand-drawn like the weekly calorie card (no chart library). */
export function TrendBars({ bars, max, referenceLabel }: Props) {
  const lastReference = bars.findLastIndex((bar) => bar.reference !== null);
  return (
    <ol className={styles.chart}>
      {bars.map((bar, index) => (
        <li key={bar.key} className={styles.column}>
          <span className="visually-hidden">{bar.label}</span>
          <span className={styles.track} aria-hidden="true">
            {bar.reference !== null && (
              <span className={styles.reference} style={{ bottom: `${percentOf(bar.reference, max)}%` }}>
                {index === lastReference && referenceLabel && (
                  <span className={`${styles.referenceLabel} num`}>{referenceLabel}</span>
                )}
              </span>
            )}
            {bar.value !== null && bar.value > 0 && (
              <span
                className={`${styles.bar} ${bar.current ? styles.current : ""}`}
                data-tone={bar.tone}
                style={{ height: `${percentOf(bar.value, max)}%` }}
              />
            )}
          </span>
          <span className={styles.axis} aria-hidden="true">
            <span>{bar.axis[0]}</span>
            <span className="num">{bar.axis[1]}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}
