import { type FormEvent, type ReactNode, useEffect, useState } from "react";
import { UNAUTHORIZED_EVENT } from "../api/client";
import { clearApiKey, getApiKey, setApiKey } from "../api/key";
import { FlameIcon } from "../icons";
import styles from "./KeyGate.module.css";

/** Asks for the API key once; any 401 later brings this screen back (UI_SPEC.md 1). */
export function KeyGate({ children }: { children: ReactNode }) {
  const [hasKey, setHasKey] = useState(() => getApiKey() !== null);
  const [rejected, setRejected] = useState(false);

  useEffect(() => {
    const onUnauthorized = () => {
      clearApiKey();
      setRejected(true);
      setHasKey(false);
    };
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, []);

  if (hasKey) return <>{children}</>;
  return (
    <KeyForm
      rejected={rejected}
      onSave={(key) => {
        setApiKey(key);
        setRejected(false);
        setHasKey(true);
      }}
    />
  );
}

function KeyForm({ rejected, onSave }: { rejected: boolean; onSave: (key: string) => void }) {
  const [value, setValue] = useState("");

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (value.trim()) onSave(value.trim());
  };

  return (
    <main className={styles.screen}>
      <FlameIcon className={styles.mark} aria-hidden="true" />
      <div>
        <h1 className={styles.title}>Connect to your tracker</h1>
        <p className={styles.lede}>
          Enter the API key from the server's .env file. This browser remembers it.
        </p>
      </div>
      <form className={styles.form} onSubmit={submit}>
        <label className={styles.label} htmlFor="api-key">
          API key
        </label>
        <input
          id="api-key"
          className={styles.input}
          type="password"
          autoComplete="off"
          autoCapitalize="none"
          spellCheck={false}
          value={value}
          onChange={(event) => setValue(event.target.value)}
        />
        {rejected && (
          <p className={styles.error} role="alert">
            That key was not accepted. Check it against API_KEY in .env.
          </p>
        )}
        <button type="submit" className={styles.submit} disabled={!value.trim()}>
          Connect
        </button>
      </form>
    </main>
  );
}
