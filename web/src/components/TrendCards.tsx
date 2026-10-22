import { useState } from "react";
import { useNutritionTrend, useTrainingTrend, useWeightUnit } from "../api/hooks";
import type { Grain, NutritionTrend, TrainingTrend } from "../api/types";
import { formatNumber } from "../lib/format";
import {
  GRAIN_OPTIONS,
  lastComplete,
  nutritionBarLabel,
  nutritionHeadline,
  periodAxis,
  rollingLine,
  trainingBarLabel,
  trainingDetail,
  trainingHeadline,
  trainingSoFar,
  trendMax,
} from "../lib/trends";
import { Bar, Card, CardError } from "./Card";
import { Toggle } from "./Toggle";
import styles from "./TrendCards.module.css";
import { TrendBars } from "./TrendBars";

/** The training trend with its own Week/Month state, loading bar and error. */
export function TrainingTrendSection() {
  const [grain, setGrain] = useState<Grain>("week");
  const query = useTrainingTrend(grain);
  if (query.isError) {
    return (
      <Card title="Training trend">
        <CardError message={query.error.message} onRetry={() => query.refetch()} />
      </Card>
    );
  }
  if (!query.data) return <Bar width="100%" height={260} />;
  return <TrainingTrendCard trend={query.data} grain={grain} onGrainChange={setGrain} />;
}

export function NutritionTrendSection() {
  const [grain, setGrain] = useState<Grain>("week");
  const query = useNutritionTrend(grain);
  if (query.isError) {
    return (
      <Card title="Calorie trend">
        <CardError message={query.error.message} onRetry={() => query.refetch()} />
      </Card>
    );
  }
  if (!query.data) return <Bar width="100%" height={280} />;
  return <NutritionTrendCard trend={query.data} grain={grain} onGrainChange={setGrain} />;
}

interface Props<T> {
  trend: T;
  grain: Grain;
  onGrainChange: (grain: Grain) => void;
}

/** Activities: active time per week or month, and how the last one compares. */
export function TrainingTrendCard({ trend, grain, onGrainChange }: Props<TrainingTrend>) {
  const unit = useWeightUnit();
  const last = lastComplete(trend.periods);
  const detail = last ? trainingDetail(last, unit) : "";
  return (
    <Card
      title="Training trend"
      aside={<Toggle label="Training trend range" options={GRAIN_OPTIONS} value={grain} onChange={onGrainChange} />}
    >
      <p className={styles.headline}>{trainingHeadline(trend.periods, grain)}</p>
      {detail && <p className={styles.detail}>{detail}</p>}
      <TrendBars
        max={trendMax(trend.periods.map((p) => p.active_s))}
        bars={trend.periods.map((p) => ({
          key: p.start,
          value: p.active_s,
          tone: "training",
          current: p.current,
          reference: null,
          axis: periodAxis(grain, p.start),
          label: trainingBarLabel(p, grain),
        }))}
      />
      <p className={styles.detail}>{trainingSoFar(trend.periods, grain)}</p>
    </Card>
  );
}

/** Nutrition: average calories per logged day, against the average budget. */
export function NutritionTrendCard({ trend, grain, onGrainChange }: Props<NutritionTrend>) {
  const budgets = trend.periods.map((p) => p.avg_budget);
  const lastBudget = budgets.filter((b) => b !== null).at(-1) ?? null;
  return (
    <Card
      title="Calorie trend"
      aside={<Toggle label="Calorie trend range" options={GRAIN_OPTIONS} value={grain} onChange={onGrainChange} />}
    >
      <p className={styles.headline}>{rollingLine(trend.rolling_7d)}</p>
      <p className={styles.detail}>{nutritionHeadline(trend.periods, grain)}</p>
      <TrendBars
        max={trendMax(
          trend.periods.map((p) => p.avg_kcal),
          Math.max(0, ...budgets.map((b) => b ?? 0)),
        )}
        referenceLabel={lastBudget === null ? undefined : formatNumber(lastBudget)}
        bars={trend.periods.map((p) => ({
          key: p.start,
          value: p.avg_kcal,
          tone: p.status,
          current: p.current,
          reference: p.status === "not_set" ? null : p.avg_budget,
          axis: periodAxis(grain, p.start),
          label: nutritionBarLabel(p, grain),
        }))}
      />
      <p className={styles.detail}>Averages count logged days only.</p>
    </Card>
  );
}
