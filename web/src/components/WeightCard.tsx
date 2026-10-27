import { useWeight, useWeightUnit } from "../api/hooks";
import type { Weight } from "../api/types";
import { parseIsoDate } from "../lib/dates";
import { bodyWeight } from "../lib/units";
import {
  changeLine,
  chartDays,
  chartDomain,
  goalLine,
  weightDayLabel,
  weightHeadline,
  weightSummary,
  xFor,
  yFor,
} from "../lib/weight";
import { Bar, Card, CardError } from "./Card";
import styles from "./WeightCard.module.css";

const WIDTH = 320;
const HEIGHT = 140;

/** Weight and the goal: each weigh-in as a dot, the 7-day average as a line, the goal dashed. */
export function WeightCard({ weight }: { weight: Weight }) {
  const unit = useWeightUnit();
  const days = chartDays(weight.days);
  const domain = chartDomain(
    days.map((day) => day.weight_kg),
    weight.goal_kg,
  );
  const indexed = days.map((day, index) => ({ day, x: xFor(index, days.length, WIDTH) }));
  const averagePoints = indexed
    .filter(({ day }) => day.avg_7d_kg !== null)
    .map(({ day, x }) => `${x.toFixed(1)},${yFor(day.avg_7d_kg ?? 0, domain, HEIGHT).toFixed(1)}`)
    .join(" ");
  const change = changeLine(weight.change_7d_kg, unit);
  const last = days.at(-1);

  return (
    <Card title="Weight">
      <p className="visually-hidden">{weightSummary(weight, unit)}</p>
      <p className={styles.headline} aria-hidden="true">
        {weightHeadline(weight, unit)}
      </p>
      {change && (
        <p className={styles.detail} aria-hidden="true">
          {change}
        </p>
      )}
      <p className={styles.detail} aria-hidden="true">
        {goalLine(weight, unit)}
      </p>

      <svg
        className={styles.chart}
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        role="img"
        aria-label={`Weight since the first weigh-in, over ${days.length} days`}
      >
        {weight.goal_kg !== null && (
          <line
            className={styles.goal}
            x1={0}
            x2={WIDTH}
            y1={yFor(weight.goal_kg, domain, HEIGHT)}
            y2={yFor(weight.goal_kg, domain, HEIGHT)}
          />
        )}
        {averagePoints && <polyline className={styles.average} points={averagePoints} />}
        {indexed.map(({ day, x }) =>
          day.weight_kg === null ? null : (
            <circle
              key={day.date}
              className={styles.point}
              cx={x}
              cy={yFor(day.weight_kg, domain, HEIGHT)}
              r={3}
            >
              <title>{weightDayLabel(day, unit)}</title>
            </circle>
          ),
        )}
      </svg>

      <div className={styles.axis} aria-hidden="true">
        <span>{days[0] && shortDay(days[0].date)}</span>
        <span className="num">
          {weight.goal_kg !== null ? `goal ${bodyWeight(weight.goal_kg, unit)}` : ""}
        </span>
        <span>{last && shortDay(last.date)}</span>
      </div>
    </Card>
  );
}

function shortDay(iso: string): string {
  return parseIsoDate(iso).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
}

/** The weight section on Nutrition: its own loading and error states, like the trend cards. */
export function WeightSection() {
  const query = useWeight();
  if (query.isError) {
    return (
      <Card title="Weight">
        <CardError message={query.error.message} onRetry={() => query.refetch()} />
      </Card>
    );
  }
  if (!query.data) return <Bar width="100%" height={240} />;
  return <WeightCard weight={query.data} />;
}
