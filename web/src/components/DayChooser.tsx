import { CalendarIcon, ChevronLeftIcon, ChevronRightIcon } from "../icons";
import { addDays, isIsoDate } from "../lib/dates";
import { dayLabel } from "../lib/format";
import { openPicker } from "../lib/picker";
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
      {/* The middle opens the phone's date picker, like the vacation chips: an invisible
          date input lies over the icon and label. */}
      <span className={styles.label}>
        <CalendarIcon className={styles.calendar} />
        <span aria-hidden="true">{dayLabel(selected, today)}</span>
        <input
          type="date"
          className={styles.dateInput}
          aria-label={`Choose a day. Showing ${dayLabel(selected, today)}`}
          value={selected}
          min={earliest}
          max={today}
          onChange={(event) => {
            // A cleared picker ("Reset" on iPhone) gives "": keep the day as it is.
            const value = event.target.value;
            if (isIsoDate(value) && value >= earliest && value <= today) go(value);
          }}
          onClick={openPicker}
        />
      </span>
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
