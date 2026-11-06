import type { Calendar, CalendarDay, CalendarView } from "../api/types";
import { ChevronLeftIcon, ChevronRightIcon, SnowflakeIcon } from "../icons";
import { calendarDayLabel, periodTitle, WEEKDAY_HEADERS } from "../lib/calendar";
import { dayOfMonth } from "../lib/dates";
import styles from "./CalendarCard.module.css";
import { Card } from "./Card";
import { GRAIN_OPTIONS } from "../lib/trends";
import { Toggle } from "./Toggle";

interface Props {
  calendar: Calendar;
  view: CalendarView;
  onViewChange: (view: CalendarView) => void;
  /** Show another week or month: the server's `previous` or `next` date. */
  onMove: (date: string) => void;
  /** The day the list below is filtered to, if any. */
  selected: string | null;
  /** Tapping a day filters the list; tapping the selected day again clears it. */
  onSelect: (date: string | null) => void;
}

function circleClass(day: CalendarDay, today: string): string {
  if (day.activity_count > 0) return styles.active;
  if (day.recovery) return styles.recovery;
  if (day.future) return styles.future;
  if (day.date === today) return styles.today;
  return styles.rest;
}

// Unlike the streak card, activity days keep their date number: in a month grid the
// numbers are how you find a day. The type is in the spoken label and the list below.
function CircleContent({ day }: { day: CalendarDay }) {
  if (day.activity_count === 0 && day.recovery) return <SnowflakeIcon />;
  return <>{dayOfMonth(day.date)}</>;
}

/** The week or month calendar on Activities: one circle per day, the activity days filled. */
export function CalendarCard({ calendar, view, onViewChange, onMove, selected, onSelect }: Props) {
  const title = periodTitle(view, calendar.period_start, calendar.period_end);
  return (
    <Card
      title="Calendar"
      tour="calendar"
      aside={<Toggle label="Calendar range" options={GRAIN_OPTIONS} value={view} onChange={onViewChange} />}
    >
      <div className={styles.nav}>
        <button
          type="button"
          className={styles.move}
          aria-label={view === "week" ? "Previous week" : "Previous month"}
          disabled={calendar.previous === null}
          onClick={() => calendar.previous && onMove(calendar.previous)}
        >
          <ChevronLeftIcon />
        </button>
        <h3 className={styles.period} aria-live="polite">
          {title}
        </h3>
        <button
          type="button"
          className={styles.move}
          aria-label={view === "week" ? "Next week" : "Next month"}
          disabled={calendar.next === null}
          onClick={() => calendar.next && onMove(calendar.next)}
        >
          <ChevronRightIcon />
        </button>
      </div>

      <div className={styles.grid}>
        {WEEKDAY_HEADERS.map((letter, index) => (
          <span key={index} className={styles.weekday} aria-hidden="true">
            {letter}
          </span>
        ))}
        {calendar.days.map((day) => {
          const isSelected = day.date === selected;
          const outside = day.in_period ? "" : styles.outside;
          return (
            <button
              key={day.date}
              type="button"
              className={`${styles.day} ${outside}`}
              aria-label={calendarDayLabel(day)}
              aria-pressed={day.future ? undefined : isSelected}
              disabled={day.future}
              onClick={() => onSelect(isSelected ? null : day.date)}
            >
              <span
                className={`${styles.circle} ${circleClass(day, calendar.today)} ${
                  isSelected ? styles.selected : ""
                } num`}
              >
                <CircleContent day={day} />
              </span>
            </button>
          );
        })}
      </div>
    </Card>
  );
}
