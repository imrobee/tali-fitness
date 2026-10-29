import { isOffline } from "../api/client";
import { useDashboard } from "../api/hooks";
import { CalorieCard } from "../components/CalorieCard";
import { Bar, Card, CardError } from "../components/Card";
import { DayChooser } from "../components/DayChooser";
import { ExercisesCard } from "../components/ExercisesCard";
import { OfflineBanner, Page } from "../components/Page";
import { ProteinCard } from "../components/ProteinCard";
import { RecoveryCard } from "../components/RecoveryCard";
import { StreakCard } from "../components/StreakCard";
import { WeeklyCard } from "../components/WeeklyCard";
import { greetingLine } from "../lib/format";
import { useSelectedDate } from "../lib/selectedDate";
import { showRecoveryCard } from "../lib/streakRules";

// Order is fixed by UI_SPEC.md section 2: greeting, day chooser, streak, recovery,
// activities, calories, protein, calories by day.
export function DashboardPage() {
  const [selected, setSelected] = useSelectedDate();
  const query = useDashboard(selected);

  if (query.isPending) return <DashboardSkeleton />;

  if (query.isError) {
    const error = query.error;
    return (
      <Page title="Dashboard">
        {isOffline(error) && <OfflineBanner onRetry={() => query.refetch()} />}
        {!isOffline(error) && (
          <Card title="This day">
            <CardError message={error.message} onRetry={() => setSelected(null)} />
          </Card>
        )}
      </Page>
    );
  }

  const dashboard = query.data;
  const date = dashboard.selected_date;
  return (
    <Page title={greetingLine(dashboard.greeting, dashboard.nickname)}>
      <DayChooser
        selected={date}
        today={dashboard.today}
        earliest={dashboard.earliest_date}
        onChange={setSelected}
      />
      <StreakCard streak={dashboard.streak} today={dashboard.today} />
      {showRecoveryCard(dashboard.exercises.length, dashboard.recovery.state) && (
        <RecoveryCard recovery={dashboard.recovery} selectedDate={date} />
      )}
      <ExercisesCard exercises={dashboard.exercises} to={`/activities?date=${date}`} />
      <CalorieCard calories={dashboard.calories} to={`/nutrition?date=${date}`} />
      <ProteinCard protein={dashboard.protein} to={`/nutrition?date=${date}`} />
      <WeeklyCard
        bars={dashboard.week_chart.bars}
        today={dashboard.today}
        selected={dashboard.selected_date}
        onSelect={(day) => setSelected(day === dashboard.today ? null : day)}
        to={`/nutrition?date=${date}`}
      />
    </Page>
  );
}

/** The final layout with grey bars where values will land, so nothing jumps. */
function DashboardSkeleton() {
  return (
    <Page title={<Bar width="70%" height={32} />}>
      <Bar width="100%" height={44} />
      <Card title="Your streak">
        <Bar width="100%" height={84} />
      </Card>
      <Card title="Recovery day">
        <Bar width="100%" height={92} />
      </Card>
      <Card title="Activities">
        <Bar width="100%" height={60} />
      </Card>
      <Card title="Calorie budget">
        <Bar width="100%" height={176} />
      </Card>
      <Card title="Protein">
        <Bar width="100%" height={36} />
      </Card>
      <Card title="Calories by day">
        <Bar width="100%" height={180} />
      </Card>
    </Page>
  );
}
