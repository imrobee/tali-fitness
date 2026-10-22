import styles from "./Toggle.module.css";

interface Props<T extends string> {
  /** Spoken name of the group, e.g. "Calendar range". */
  label: string;
  options: { value: T; text: string }[];
  value: T;
  onChange: (value: T) => void;
}

/** A small Week / Month switch: one pressed button out of a few. */
export function Toggle<T extends string>({ label, options, value, onChange }: Props<T>) {
  return (
    <div className={styles.group} role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={styles.option}
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
        >
          {option.text}
        </button>
      ))}
    </div>
  );
}
