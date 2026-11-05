import { type FormEvent, useState } from "react";
import { useSaveMe, useVacation } from "../api/hooks";
import { useIsDemo } from "../api/visit";
import type { Me } from "../api/types";
import { CalendarIcon } from "../icons";
import { openPicker } from "../lib/picker";
import { chipText, periodText, streakRules, vacationError, weekendRule } from "../lib/streakRules";
import { Card } from "./Card";
import styles from "./StreakSettings.module.css";
import { Toggle } from "./Toggle";

type Weekends = "strict" | "relaxed";

/** "How your streak works": the rules in plain words (UI_SPEC.md 6.3). */
export function StreakRulesCard() {
  return (
    <Card title="How your streak works">
      <ul className={styles.rules}>
        {streakRules().map((rule) => (
          <li key={rule}>{rule}</li>
        ))}
      </ul>
    </Card>
  );
}

/** The weekend switch in its own card, with the rule it sets under it (UI_SPEC.md 6.3). */
export function WeekendsCard({ me }: { me: Me }) {
  const save = useSaveMe();
  const demo = useIsDemo();
  const weekends: Weekends = me.lenient_weekends ? "relaxed" : "strict";
  return (
    <Card
      title="Weekends"
      aside={
        <Toggle<Weekends>
          label="Weekends"
          options={[
            { value: "strict", text: "Strict" },
            { value: "relaxed", text: "Relaxed" },
          ]}
          value={weekends}
          onChange={(next) => save.mutate({ lenient_weekends: next === "relaxed" })}
        />
      }
    >
      <p className={styles.rule}>{weekendRule(me.lenient_weekends)}</p>
      {/* The demo says it once, at the bottom of the page (DEMO_SAVE_NOTE). */}
      {!demo && <p className={styles.help}>Changes apply from today.</p>}
      {save.isError && (
        <p className={styles.error} role="alert">
          {save.error.message}
        </p>
      )}
    </Card>
  );
}

/** A label and a date chip. The chip shows "Choose date" or the date; the real date input
    lies invisibly over it, so a tap anywhere on the chip opens the phone's picker. */
function DateChip({
  id,
  label,
  value,
  min,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  min?: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className={styles.dateRow}>
      <label htmlFor={id}>{label}</label>
      <span className={`${styles.chip} ${value ? "" : styles.chipEmpty} num`}>
        <CalendarIcon className={styles.chipIcon} />
        <span aria-hidden="true">{chipText(value)}</span>
        <input
          id={id}
          type="date"
          className={styles.dateInput}
          value={value}
          min={min}
          onChange={(event) => onChange(event.target.value)}
          onClick={openPicker}
        />
      </span>
    </div>
  );
}

/** Vacation or injury: during a break only a missed day ends the streak. "Log break" opens
    the From and To dates (UI_SPEC.md 6.3); a break still running or to come shows them open. */
export function VacationCard({ me }: { me: Me }) {
  const { save, end } = useVacation();
  const [open, setOpen] = useState(me.vacation !== null);
  const [from, setFrom] = useState(me.vacation?.from ?? "");
  const [to, setTo] = useState(me.vacation?.to ?? "");
  const [problem, setProblem] = useState<string | null>(null);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found = vacationError(from, to);
    setProblem(found);
    if (found) return;
    save.mutate(
      { from, to },
      {
        // A break that has already ended is history: close the form, it shows as "Last break".
        onSuccess: (saved) => {
          if (saved.vacation === null) {
            setOpen(false);
            setFrom("");
            setTo("");
          }
        },
      },
    );
  };

  const error = problem ?? save.error?.message ?? end.error?.message ?? null;
  return (
    <Card title="Vacation or injury">
      <p className={styles.help}>During a break, only a day with nothing logged ends your streak.</p>
      {!open && (
        <button
          type="button"
          className={styles.secondary}
          aria-expanded={false}
          aria-controls="vacation-form"
          onClick={() => setOpen(true)}
        >
          Log break
        </button>
      )}
      {open && (
        <form id="vacation-form" className={styles.form} onSubmit={submit} noValidate>
          <DateChip id="vacation-from" label="From" value={from} onChange={setFrom} />
          <DateChip id="vacation-to" label="To" value={to} min={from || undefined} onChange={setTo} />
          {error && (
            <p className={styles.error} role="alert">
              {error}
            </p>
          )}
          <div className={styles.actions}>
            <button type="submit" className={styles.primary} disabled={save.isPending}>
              Save break
            </button>
            {me.vacation && (
              <button
                type="button"
                className={styles.secondary}
                disabled={end.isPending}
                onClick={() =>
                  end.mutate(undefined, {
                    onSuccess: () => {
                      setOpen(false);
                      setFrom("");
                      setTo("");
                    },
                  })
                }
              >
                End break
              </button>
            )}
            <span className={styles.help} role="status">
              {save.isSuccess && !save.isPending ? "Saved." : ""}
            </span>
          </div>
        </form>
      )}
      {me.last_vacation && (
        <p className={styles.help}>
          Last break: {periodText(me.last_vacation.from, me.last_vacation.to)}
        </p>
      )}
    </Card>
  );
}
