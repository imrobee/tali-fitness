// Activities (UI_SPEC.md 6.1): the last 30 days, grouped by day, newest first. The day in
// ?date= is scrolled to and marked; "Load older" widens the window a month at a time.

import { useEffect, useState } from "react";
import { isOffline } from "../api/client";
import { useActivities, useDashboard } from "../api/hooks";
import type { ActivityDay } from "../api/types";
import { ActivityItem } from "../components/ActivityItem";
import { Bar, Card, CardError } from "../components/Card";
import { OfflineBanner, Page } from "../components/Page";
import { dayChip, dayHeading } from "../lib/activities";
import { addDays } from "../lib/dates";
import { useSelectedDate } from "../lib/selectedDate";
import styles from "./ActivitiesPage.module.css";

const STEP_DAYS = 30;
// The API's per-request limit is 366 days (api/app/activities.py), so the window stops at 360.
const MAX_DAYS = 360;

export function ActivitiesPage() {
  const [selected] = useSelectedDate();
  const today = useDashboard(null);
  const [windowDays, setWindowDays] = useState(STEP_DAYS);
  // Until the server has said what today is, there is no window to ask for.
  const to = today.data?.today ?? null;
  const from = to === null ? null : addDays(to, -(windowDays - 1));
  const list = useActivities(from, to);

  // Scroll to the day named in ?date= once the days are on the screen.
  const loaded = list.data !== undefined;
  useEffect(() => {
    if (!loaded || !selected) return;
    document.getElementById(`day-${selected}`)?.scrollIntoView({ block: "start" });
  }, [loaded, selected]);

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
      {!list.data && <Bar width="100%" height={160} />}
      {list.data && list.data.days.length === 0 && (
        <Card title="Activities">
          <p className={styles.empty}>No activities in the last {windowDays} days.</p>
        </Card>
      )}
      {list.data?.days.map((day) => (
        <DaySection key={day.date} day={day} today={to ?? ""} selected={day.date === selected} />
      ))}
      {list.data && windowDays < MAX_DAYS && (
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

function DaySection({ day, today, selected }: { day: ActivityDay; today: string; selected: boolean }) {
  const chip = dayChip(day.date, today);
  return (
    <section id={`day-${day.date}`} className={selected ? styles.selectedDay : styles.day}>
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
