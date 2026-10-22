// Activities (UI_SPEC.md 6.1): the calendar, then the activity list. With a day picked
// (?date=, from the calendar or from the dashboard) the list shows only that day, from any
// month; without one it shows the last 30 days, and "Load older" adds a month at a time.

import { useState } from "react";
import { isOffline } from "../api/client";
import { useActivities, useCalendar, useDashboard } from "../api/hooks";
import type { ActivityDay, CalendarView } from "../api/types";
import { ActivityItem } from "../components/ActivityItem";
import { CalendarCard } from "../components/CalendarCard";
import { Bar, Card, CardError } from "../components/Card";
import { OfflineBanner, Page } from "../components/Page";
import { MuscleVolumeSection, RecordsSection } from "../components/ProgressCards";
import { TrainingTrendSection } from "../components/TrendCards";
import { dayChip, dayHeading } from "../lib/activities";
import { addDays } from "../lib/dates";
import { useSelectedDate } from "../lib/selectedDate";
import styles from "./ActivitiesPage.module.css";

const STEP_DAYS = 30;
// The API's per-request limit is 366 days (api/app/activities.py), so the window stops at 360.
const MAX_DAYS = 360;

export function ActivitiesPage() {
  const [selected, setSelected] = useSelectedDate();
  const today = useDashboard(null);
  const [view, setView] = useState<CalendarView>("month");
  // The calendar opens on the picked day's month; the arrows move it from there.
  const [anchor, setAnchor] = useState<string | null>(selected);
  const calendar = useCalendar(view, anchor);
  const [windowDays, setWindowDays] = useState(STEP_DAYS);

  // Until the server has said what today is, there is no window to ask for.
  const to = today.data?.today ?? null;
  const from = to === null ? null : addDays(to, -(windowDays - 1));
  const list = useActivities(selected ?? from, selected ?? to);

  if (today.isError || list.isError) {
    const error = today.error ?? list.error;
    return (
      <Page title="Activities">
        {error && isOffline(error) ? (
          <OfflineBanner onRetry={() => (today.isError ? today.refetch() : list.refetch())} />
        ) : (
          <Card title="Activities">
            <CardError message={error?.message ?? "Something went wrong."} onRetry={() => list.refetch()} />
          </Card>
        )}
      </Page>
    );
  }

  return (
    <Page title="Activities">
      <TrainingTrendSection />
      <MuscleVolumeSection />
      <RecordsSection />
      {calendar.data ? (
        <CalendarCard
          calendar={calendar.data}
          view={view}
          onViewChange={setView}
          onMove={setAnchor}
          selected={selected}
          onSelect={(day) => {
            setSelected(day);
            if (day) setAnchor(day);
          }}
        />
      ) : calendar.isError ? (
        <Card title="Calendar">
          <CardError message={calendar.error.message} onRetry={() => setAnchor(null)} />
        </Card>
      ) : (
        <Bar width="100%" height={view === "month" ? 320 : 140} />
      )}

      {selected && (
        <div className={styles.filter}>
          <span>Showing one day</span>
          <button type="button" className={styles.showAll} onClick={() => setSelected(null)}>
            Show all days
          </button>
        </div>
      )}

      {/* The day chips need the server's today, so the list waits for it. */}
      {(!list.data || to === null) && <Bar width="100%" height={160} />}
      {list.data && to !== null && list.data.days.length === 0 && (
        <Card title={selected ? dayHeading(selected) : "Activities"}>
          <p className={styles.empty}>
            {selected ? "No activities on this day." : `No activities in the last ${windowDays} days.`}
          </p>
        </Card>
      )}
      {to !== null &&
        list.data?.days.map((day) => <DaySection key={day.date} day={day} today={to} />)}
      {list.data && !selected && windowDays < MAX_DAYS && (
        <button
          type="button"
          className={styles.older}
          onClick={() => setWindowDays((days) => Math.min(days + STEP_DAYS, MAX_DAYS))}
        >
          Load older
        </button>
      )}
    </Page>
  );
}

function DaySection({ day, today }: { day: ActivityDay; today: string }) {
  const chip = dayChip(day.date, today);
  return (
    <section className={styles.day}>
      <h2 className={styles.heading}>
        <span>{dayHeading(day.date)}</span>
        {chip && <span className={styles.chip}>{chip}</span>}
      </h2>
      <ul className={styles.list}>
        {day.activities.map((activity) => (
          <ActivityItem key={activity.id} activity={activity} />
        ))}
      </ul>
    </section>
  );
}
