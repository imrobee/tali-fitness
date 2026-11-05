import { type FormEvent, type MouseEvent, type ReactNode, useState } from "react";
import { isOffline } from "../api/client";
import { useMe, usePipelineHealth, useSaveMe } from "../api/hooks";
import { signOut } from "../api/auth";
import { useIsDemo, useLaunchUrl } from "../api/visit";
import { DEMO_SAVE_NOTE } from "../demo/copy";
import { StreakRulesCard, VacationCard, WeekendsCard } from "../components/StreakSettings";
import { Toggle } from "../components/Toggle";
import { toKg, type WeightUnit, weightNumber } from "../lib/units";
import type { Me, MeUpdate } from "../api/types";
import { AccountCard } from "../components/AccountCard";
import { DataSyncCard } from "../components/DataSyncCard";
import { Bar, Card, CardError } from "../components/Card";
import { OfflineBanner, Page } from "../components/Page";
import { type ProfileErrors, validateProfile } from "../lib/targets";
import styles from "./MePage.module.css";

// Me (UI_SPEC.md 6.3): profile and targets, time zone, the data and sync panel, and signing
// out. On the demo there is no account: one note that nothing is saved, and a way back to
// the launch screen.
export function MePage() {
  const query = useMe();
  const health = usePipelineHealth();
  const demo = useIsDemo();

  return (
    <Page title="Me">
      {query.isPending && <Bar width="100%" height={300} />}
      {query.isError &&
        (isOffline(query.error) ? (
          <OfflineBanner onRetry={() => query.refetch()} />
        ) : (
          <Card title="Profile and targets">
            <CardError message={query.error.message} onRetry={() => query.refetch()} />
          </Card>
        ))}
      {query.data && <ProfileForm me={query.data} />}
      {query.data && <StreakRulesCard />}
      {query.data && <WeekendsCard me={query.data} />}
      {query.data && <VacationCard me={query.data} />}
      {query.data && (
        <Card title="Time zone">
          <div className={styles.row}>
            <span>Days start and end in</span>
            <span className={styles.rowValue}>{query.data.timezone}</span>
          </div>
        </Card>
      )}
      {health.isPending && <Bar width="100%" height={200} />}
      {health.isError && (
        <Card title="Data and sync">
          <CardError message={health.error.message} onRetry={() => health.refetch()} />
        </Card>
      )}
      {health.data && <DataSyncCard health={health.data} now={Date.parse(health.data.now)} />}
      {demo ? <DemoFooter /> : <AccountCard />}
    </Page>
  );
}

/** The demo's last words on Me: nothing is saved, and the way back to the launch screen
    (on the real app's address; hidden when the demo doesn't know it). */
function DemoFooter() {
  const launchUrl = useLaunchUrl();
  const leave = async (event: MouseEvent<HTMLAnchorElement>) => {
    if (!launchUrl) return;
    event.preventDefault();
    try {
      await signOut(); // end this visit's cookie; nothing on the server to delete
    } finally {
      window.location.assign(launchUrl);
    }
  };
  return (
    <>
      <p className={styles.demoNote}>{DEMO_SAVE_NOTE}</p>
      {launchUrl && (
        <a className={styles.leave} href={launchUrl} onClick={leave}>
          Return to login screen
        </a>
      )}
    </>
  );
}

function ProfileForm({ me }: { me: Me }) {
  const save = useSaveMe();
  const demo = useIsDemo();
  const [nickname, setNickname] = useState(me.nickname ?? "");
  const [calorieBudget, setCalorieBudget] = useState(
    me.targets ? String(me.targets.calorie_budget) : "",
  );
  const [proteinGoal, setProteinGoal] = useState(me.targets ? String(me.targets.protein_goal) : "");
  const saveUnit = useSaveMe();
  const [unit, setUnit] = useState<WeightUnit>(me.weight_unit);
  const [weightGoal, setWeightGoal] = useState(
    me.weight_goal_kg === null ? "" : weightNumber(me.weight_goal_kg, me.weight_unit),
  );

  // The goal in kg as the field means it. While the field still shows the stored goal, use
  // the stored value: the field is rounded to a tenth, and converting the rounded number
  // would turn 160 lb into 160.1 lb, or save 72.6 kg over 72.575 kg.
  const goalInKg = (text: string, inUnit: WeightUnit): number | null => {
    if (text.trim() === "" || !Number.isFinite(Number(text.trim()))) return null;
    if (me.weight_goal_kg !== null && text.trim() === weightNumber(me.weight_goal_kg, inUnit)) {
      return me.weight_goal_kg;
    }
    return toKg(Number(text.trim()), inUnit);
  };

  // The unit is a preference, saved at once; a goal already typed is converted, not lost.
  const changeUnit = (next: WeightUnit) => {
    const kg = goalInKg(weightGoal, unit);
    if (kg !== null) setWeightGoal(weightNumber(kg, next));
    setUnit(next);
    saveUnit.mutate({ weight_unit: next });
  };
  const [errors, setErrors] = useState<ProfileErrors>({});

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found = validateProfile({ nickname, calorieBudget, proteinGoal, weightGoal, weightUnit: unit });
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    const update: MeUpdate = { nickname: nickname.trim() || null };
    const targets = { calorie_budget: Number(calorieBudget), protein_goal: Number(proteinGoal) };
    // Send targets only when they changed: saving them adds a row to the target history.
    const changed =
      calorieBudget.trim() !== "" &&
      (targets.calorie_budget !== me.targets?.calorie_budget ||
        targets.protein_goal !== me.targets?.protein_goal);
    if (changed) update.targets = targets;
    // The weight goal is its own history (weight_goal_history), saved only when it changed.
    // Goals are stored in kg; an unchanged goal is not saved again.
    const goal = goalInKg(weightGoal, unit);
    if (goal !== null && goal !== me.weight_goal_kg) update.weight_goal_kg = goal;
    save.mutate(update);
  };

  return (
    <Card title="Profile and targets">
      <form className={styles.form} onSubmit={submit} noValidate>
        <Field
          id="nickname"
          label="Nickname"
          value={nickname}
          onChange={setNickname}
          error={errors.nickname}
          autoComplete="nickname"
        />
        <Field
          id="calorie-budget"
          label="Calorie budget"
          unit="kcal per day"
          value={calorieBudget}
          onChange={setCalorieBudget}
          error={errors.calorieBudget}
          numeric
        />
        <Field
          id="protein-goal"
          label="Protein goal"
          unit="grams per day"
          value={proteinGoal}
          onChange={setProteinGoal}
          error={errors.proteinGoal}
          numeric
        />
        <Field
          id="weight-goal"
          label="Weight goal"
          unit={unit}
          value={weightGoal}
          onChange={setWeightGoal}
          error={errors.weightGoal}
          decimal
          trailing={
            <Toggle
              label="Weight unit"
              options={[
                { value: "kg", text: "kg" },
                { value: "lb", text: "lb" },
              ]}
              value={unit}
              onChange={changeUnit}
            />
          }
        />
        {/* The demo says it once, at the bottom of the page (DEMO_SAVE_NOTE). */}
        {!demo && <p className={styles.help}>Changes apply from today. Past days keep their old targets.</p>}
        <div className={styles.actions}>
          <button type="submit" className={styles.save} disabled={save.isPending}>
            Save changes
          </button>
          <span className={styles.saved} role="status">
            {save.isSuccess && !save.isPending ? "Saved." : ""}
          </span>
        </div>
        {save.isError && (
          <p className={styles.fieldError} role="alert">
            {save.error.message}
          </p>
        )}
      </form>
    </Card>
  );
}

interface FieldProps {
  id: string;
  label: string;
  unit?: string;
  value: string;
  onChange: (value: string) => void;
  error?: string;
  numeric?: boolean;
  decimal?: boolean;
  /** A control beside the input, e.g. the kg / lb switch. */
  trailing?: ReactNode;
  autoComplete?: string;
}

function Field({ id, label, unit, value, onChange, error, numeric, decimal, trailing, autoComplete }: FieldProps) {
  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={id}>
        {label} {unit && <span className={styles.unit}>({unit})</span>}
      </label>
      <div className={styles.inputRow}>
        <input
          id={id}
          className={`${styles.input} num`}
          value={value}
          onChange={(event) => onChange(event.target.value)}
          inputMode={numeric ? "numeric" : decimal ? "decimal" : undefined}
          autoComplete={autoComplete ?? "off"}
          aria-invalid={error ? true : undefined}
          aria-describedby={error ? `${id}-error` : undefined}
        />
        {trailing}
      </div>
      {error && (
        <span id={`${id}-error`} className={styles.fieldError}>
          {error}
        </span>
      )}
    </div>
  );
}
