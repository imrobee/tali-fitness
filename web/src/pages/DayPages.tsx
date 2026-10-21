// Nutrition (UI_SPEC.md 6.2): the day chooser and the selected day's calorie, protein and
// weekly cards. Activities has its own page (ActivitiesPage.tsx).

import type { ReactNode } from "react";
import { isOffline } from "../api/client";
import { useDashboard } from "../api/hooks";
import type { Dashboard } from "../api/types";
import { CalorieCard } from "../components/CalorieCard";
import { Bar, Card, CardError } from "../components/Card";
import { DayChooser } from "../components/DayChooser";
import { OfflineBanner, Page } from "../components/Page";
import { ProteinCard } from "../components/ProteinCard";
import { WeeklyCard } from "../components/WeeklyCard";
import { useSelectedDate } from "../lib/selectedDate";

function DayPage({
  title,
  children,
}: {
  title: string;
  children: (dashboard: Dashboard, select: (date: string | null) => void) => ReactNode;
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
      {children(dashboard, setSelected)}
    </Page>
  );
}

export function NutritionPage() {
  return (
    <DayPage title="Nutrition">
      {(dashboard, select) => (
        <>
          <CalorieCard calories={dashboard.calories} />
          <ProteinCard protein={dashboard.protein} />
          <WeeklyCard
            bars={dashboard.week_chart.bars}
            today={dashboard.today}
            selected={dashboard.selected_date}
            onSelect={(day) => select(day === dashboard.today ? null : day)}
          />
        </>
      )}
    </DayPage>
  );
}
