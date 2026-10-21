// Activities and Nutrition, minimal for M1 (PROJECT_PLAN Slice 6a): the day chooser and
// the selected day's real cards. The full pages arrive in Slice 6b.

import type { ReactNode } from "react";
import { isOffline } from "../api/client";
import { useDashboard } from "../api/hooks";
import type { Dashboard } from "../api/types";
import { CalorieCard } from "../components/CalorieCard";
import { Bar, Card, CardError } from "../components/Card";
import { DayChooser } from "../components/DayChooser";
import { ExercisesCard } from "../components/ExercisesCard";
import { OfflineBanner, Page } from "../components/Page";
import { ProteinCard } from "../components/ProteinCard";
import { useSelectedDate } from "../lib/selectedDate";

function DayPage({
  title,
  children,
}: {
  title: string;
  children: (dashboard: Dashboard) => ReactNode;
}) {
  const [selected, setSelected] = useSelectedDate();
  const query = useDashboard(selected);

  if (query.isPending) {
    return (
      <Page title={title}>
        <Bar width="100%" height={44} />
        <Bar width="100%" height={160} />
      </Page>
    );
  }
  if (query.isError) {
    return (
      <Page title={title}>
        {isOffline(query.error) ? (
          <OfflineBanner onRetry={() => query.refetch()} />
        ) : (
          <Card title="This day">
            <CardError message={query.error.message} onRetry={() => setSelected(null)} />
          </Card>
        )}
      </Page>
    );
  }

  const dashboard = query.data;
  return (
    <Page title={title}>
      <DayChooser
        selected={dashboard.selected_date}
        today={dashboard.today}
        earliest={dashboard.earliest_date}
        onChange={setSelected}
      />
      {children(dashboard)}
    </Page>
  );
}

export function ActivitiesPage() {
  return (
    <DayPage title="Activities">
      {(dashboard) => <ExercisesCard exercises={dashboard.exercises} startExpanded />}
    </DayPage>
  );
}

export function NutritionPage() {
  return (
    <DayPage title="Nutrition">
      {(dashboard) => (
        <>
          <CalorieCard calories={dashboard.calories} />
          <ProteinCard protein={dashboard.protein} />
        </>
      )}
    </DayPage>
  );
}
