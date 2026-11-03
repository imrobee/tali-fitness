import { useState } from "react";
import { useMuscleVolume, useRecords, useWeightUnit } from "../api/hooks";
import type { MuscleVolume, PersonalRecord } from "../api/types";
import { ChevronDownIcon } from "../icons";
import {
  muscleAmount,
  muscleChange,
  recordGain,
  recordLabel,
  recordSet,
  recordValue,
  weekRange,
} from "../lib/progress";
import type { WeightUnit } from "../lib/units";
import { Bar, Card, CardError } from "./Card";
import styles from "./ProgressCards.module.css";

const COLLAPSED_RECORDS = 5;

// --- personal records ----------------------------------------------------------------------

export function RecordsCard({ records, unit }: { records: PersonalRecord[]; unit: WeightUnit }) {
  const [open, setOpen] = useState(false);
  const shown = open ? records : records.slice(0, COLLAPSED_RECORDS);
  const hidden = records.length - COLLAPSED_RECORDS;
  return (
    <Card title="Personal records" aside={records.length > 0 ? String(records.length) : undefined}>
      {records.length === 0 ? (
        <p className={styles.muted}>Records appear once a lifting session with weights is read.</p>
      ) : (
        <ol className={styles.list}>
          {shown.map((record) => {
            const gain = recordGain(record, unit);
            return (
              <li key={record.exercise + (record.equipment ?? "")} className={styles.record} aria-label={recordLabel(record, unit)}>
                <span className={styles.recordHead} aria-hidden="true">
                  <span className={styles.name}>
                    {record.exercise}
                    {record.recent && <span className={styles.chip}>New</span>}
                  </span>
                  <span className={`${styles.value} num`}>{recordValue(record, unit)}</span>
                </span>
                <span className={`${styles.muted} num`} aria-hidden="true">
                  {recordSet(record, unit)}
                  {record.muscle_group && ` · ${record.muscle_group}`}
                </span>
                {gain && (
                  <span className={`${styles.muted} num`} aria-hidden="true">
                    {gain}
                  </span>
                )}
              </li>
            );
          })}
        </ol>
      )}
      {hidden > 0 && (
        <button type="button" className={styles.more} aria-expanded={open} onClick={() => setOpen(!open)}>
          {open ? "Show fewer" : `Show ${hidden} more`}
          <ChevronDownIcon className={`${styles.chevron} ${open ? styles.open : ""}`} />
        </button>
      )}
      <p className={styles.muted}>Estimated one-rep max: weight × (1 + reps ÷ 30), sets of 12 reps or fewer.</p>
    </Card>
  );
}

export function RecordsSection() {
  const query = useRecords();
  const unit = useWeightUnit();
  if (query.isError) return <ErrorCard title="Personal records" retry={() => query.refetch()} message={query.error.message} />;
  if (!query.data) return <Bar width="100%" height={200} />;
  return <RecordsCard records={query.data.records} unit={unit} />;
}

// --- muscle volume -------------------------------------------------------------------------

export function MuscleVolumeCard({ data, unit }: { data: MuscleVolume; unit: WeightUnit }) {
  const most = Math.max(1, ...data.groups.map((g) => Math.max(g.sets, g.prev_sets)));
  return (
    <Card title="Muscle volume" aside={`Last week, ${weekRange(data.week_start, data.week_end)}`}>
      {data.groups.length === 0 ? (
        <p className={styles.muted}>No lifting last week or the week before.</p>
      ) : (
        <ul className={styles.list}>
          {data.groups.map((group) => (
            <li key={group.muscle_group} className={styles.muscle}>
              <span className={styles.recordHead}>
                <span className={styles.name}>{group.muscle_group}</span>
                <span className={`${styles.muted} num`}>{muscleAmount(group, unit)}</span>
              </span>
              <span className={styles.track} aria-hidden="true">
                <span className={styles.fill} style={{ width: `${(100 * group.sets) / most}%` }} />
              </span>
              <span className={`${styles.muted} num`}>{muscleChange(group)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function MuscleVolumeSection() {
  const query = useMuscleVolume();
  const unit = useWeightUnit();
  if (query.isError) return <ErrorCard title="Muscle volume" retry={() => query.refetch()} message={query.error.message} />;
  if (!query.data) return <Bar width="100%" height={160} />;
  return <MuscleVolumeCard data={query.data} unit={unit} />;
}

function ErrorCard({ title, message, retry }: { title: string; message: string; retry: () => void }) {
  return (
    <Card title={title}>
      <CardError message={message} onRetry={retry} />
    </Card>
  );
}
