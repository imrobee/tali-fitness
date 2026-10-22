import type { WeekBar } from "../api/types";
import { barLabel, chartMax, chartSummary, hasBar, percentOf, weekdayLetters } from "../lib/chart";
import { dayOfMonth } from "../lib/dates";
import { formatNumber, longDate } from "../lib/format";
import { Card } from "./Card";
import cardStyles from "./Card.module.css";
import styles from "./WeeklyCard.module.css";

interface Props {
  bars: WeekBar[];
  today: string;
  selected: string;
  /** Tapping a day selects it (UI_SPEC.md 5.8). Future days cannot be selected. */
  onSelect: (date: string) => void;
  /** Where the whole card opens (the dashboard links to Nutrition). */
  to?: string;
}

/**
 * The Monday-to-Sunday calorie chart (UI_SPEC.md 5.8): one bar per day, a dashed line at
 * each day's budget, over-budget bars rising above it, and shape-and-text for every state.
 */
export function WeeklyCard({ bars, today, selected, onSelect, to }: Props) {
  const max = chartMax(bars);
  const lastBudget = bars.findLastIndex((bar) => bar.budget !== null && hasBar(bar));

  return (
    <Card title="Weekly calorie budget" to={to}>
      <p className="visually-hidden">{chartSummary(bars)}</p>
      <div className={styles.chart}>
        {bars.map((bar, index) => {
          const isFuture = bar.date > today;
          const isSelected = bar.date === selected;
          const budgetLine = bar.budget !== null && bar.status !== "not_set";
          return (
            <button
              key={bar.date}
              type="button"
              className={`${styles.day} ${cardStyles.above}`}
              aria-label={barLabel(bar, longDate(bar.date))}
              aria-current={isSelected ? "date" : undefined}
              disabled={isFuture}
              onClick={() => onSelect(bar.date)}
            >
              <span className={styles.track}>
                {budgetLine && (
                  <span
                    className={styles.budgetLine}
                    style={{ bottom: `${percentOf(bar.budget ?? 0, max)}%` }}
                  >
                    {index === lastBudget && (
                      <span className={`${styles.budgetLabel} num`}>
                        {formatNumber(bar.budget ?? 0)}
                      </span>
                    )}
                  </span>
                )}
                {hasBar(bar) && (
                  <span
                    className={styles.bar}
                    data-status={bar.status}
                    style={{ height: `${percentOf(bar.kcal ?? 0, max)}%` }}
                  />
                )}
              </span>
              <span className={`${styles.weekday} ${isSelected ? styles.selectedText : ""}`} aria-hidden="true">
                {weekdayLetters(bar.date)}
              </span>
              <span className={`${styles.number} num ${isSelected ? styles.selectedText : ""}`} aria-hidden="true">
                {dayOfMonth(bar.date)}
              </span>
            </button>
          );
        })}
      </div>
    </Card>
  );
}
