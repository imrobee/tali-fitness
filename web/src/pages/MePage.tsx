import { type FormEvent, useState } from "react";
import { UNAUTHORIZED_EVENT, isOffline } from "../api/client";
import { useMe, useSaveMe } from "../api/hooks";
import { getApiKey, maskKey } from "../api/key";
import type { Me, MeUpdate } from "../api/types";
import { Bar, Card, CardError } from "../components/Card";
import { OfflineBanner, Page } from "../components/Page";
import { type ProfileErrors, validateProfile } from "../lib/targets";
import styles from "./MePage.module.css";

// Me (UI_SPEC.md 6.3), minimal for M1: profile and targets, time zone, and the API key.
// The data and sync panel arrives in Slice 6b.
export function MePage() {
  const query = useMe();

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
      {query.data && (
        <Card title="Time zone">
          <div className={styles.row}>
            <span>Days start and end in</span>
            <span className={styles.rowValue}>{query.data.timezone}</span>
          </div>
        </Card>
      )}
      <ConnectionCard />
    </Page>
  );
}

function ProfileForm({ me }: { me: Me }) {
  const save = useSaveMe();
  const [nickname, setNickname] = useState(me.nickname ?? "");
  const [calorieBudget, setCalorieBudget] = useState(
    me.targets ? String(me.targets.calorie_budget) : "",
  );
  const [proteinGoal, setProteinGoal] = useState(me.targets ? String(me.targets.protein_goal) : "");
  const [errors, setErrors] = useState<ProfileErrors>({});

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found = validateProfile({ nickname, calorieBudget, proteinGoal });
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
        <p className={styles.help}>Changes apply from today. Past days keep their old targets.</p>
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
  autoComplete?: string;
}

function Field({ id, label, unit, value, onChange, error, numeric, autoComplete }: FieldProps) {
  return (
    <div className={styles.field}>
      <label className={styles.label} htmlFor={id}>
        {label} {unit && <span className={styles.unit}>({unit})</span>}
      </label>
      <input
        id={id}
        className={`${styles.input} num`}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        inputMode={numeric ? "numeric" : undefined}
        autoComplete={autoComplete ?? "off"}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
      />
      {error && (
        <span id={`${id}-error`} className={styles.fieldError}>
          {error}
        </span>
      )}
    </div>
  );
}

function ConnectionCard() {
  const key = getApiKey();

  return (
    <Card title="Connection">
      <div className={styles.row}>
        <span>
          API key <span className={`${styles.rowValue} num`}>{key ? maskKey(key) : "—"}</span>
        </span>
        <button
          type="button"
          className={styles.change}
          // Asking again is the same as an expired key: the key gate takes over.
          onClick={() => window.dispatchEvent(new Event(UNAUTHORIZED_EVENT))}
        >
          Change
        </button>
      </div>
    </Card>
  );
}
