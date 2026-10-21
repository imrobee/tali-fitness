import { CalendarIcon, ChevronLeftIcon, ChevronRightIcon } from "../icons";
import { addDays } from "../lib/dates";
import { dayLabel } from "../lib/format";
import styles from "./DayChooser.module.css";

interface Props {
  selected: string;
  today: string;
  earliest: string;
  onChange: (date: string | null) => void; // null = back to today
}

export function DayChooser({ selected, today, earliest, onChange }: Props) {
  const isToday = selected === today;
  const atEarliest = selected <= earliest; // ISO dates compare as strings

  const go = (date: string) => onChange(date === today ? null : date);

  return (
    <div className={styles.pill}>
      <button
        type="button"
        className={styles.arrow}
        aria-label="Previous day"
        disabled={atEarliest}
        onClick={() => go(addDays(selected, -1))}
      >
        <ChevronLeftIcon />
      </button>
      <button
        type="button"
        className={styles.label}
        aria-label={isToday ? "Today" : `${dayLabel(selected, today)}. Jump to today`}
        disabled={isToday}
        onClick={() => onChange(null)}
      >
        <CalendarIcon className={styles.calendar} />
        {dayLabel(selected, today)}
      </button>
      <button
        type="button"
        className={styles.arrow}
        aria-label="Next day"
        disabled={isToday}
        onClick={() => go(addDays(selected, 1))}
      >
        <ChevronRightIcon />
      </button>
    </div>
  );
}
