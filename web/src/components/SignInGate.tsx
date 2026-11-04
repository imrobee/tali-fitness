import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, type ReactNode, useEffect, useState } from "react";
import { useLocation } from "react-router";
import {
  AUTH_QUERY,
  checkSignedIn,
  devSignIn,
  fetchSignInMethod,
  forgetOldKey,
  googleSignInUrl,
  type SignInMethod,
} from "../api/auth";
import { UNAUTHORIZED_EVENT } from "../api/client";
import { FlameIcon } from "../icons";
import styles from "./SignInGate.module.css";

type Auth = { signedIn: true } | { signedIn: false; method: SignInMethod };

async function loadAuth(): Promise<Auth> {
  if (await checkSignedIn()) return { signedIn: true };
  return { signedIn: false, method: await fetchSignInMethod() };
}

/** Shows the app only to a signed-in browser (UI_SPEC.md section 1); any 401 later brings
    the sign-in screen back. The server decides: this asks /auth/me, never storage. */
export function SignInGate({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const auth = useQuery({ queryKey: AUTH_QUERY, queryFn: loadAuth });
  const recheck = () => void queryClient.invalidateQueries({ queryKey: AUTH_QUERY });

  useEffect(() => {
    forgetOldKey();
    const onUnauthorized = () => void queryClient.invalidateQueries({ queryKey: AUTH_QUERY });
    window.addEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
    return () => window.removeEventListener(UNAUTHORIZED_EVENT, onUnauthorized);
  }, [queryClient]);

  if (auth.isPending) return <main className={styles.screen} aria-busy="true" />;
  if (auth.isError) {
    return (
      <main className={styles.screen}>
        <h1 className={styles.title}>Can't reach the server</h1>
        <button type="button" className={styles.submit} onClick={() => void auth.refetch()}>
          Retry
        </button>
      </main>
    );
  }
  if (auth.data.signedIn) return <>{children}</>;
  return <SignInScreen method={auth.data.method} onSignedIn={recheck} />;
}

function SignInScreen({ method, onSignedIn }: { method: SignInMethod; onSignedIn: () => void }) {
  const location = useLocation();
  return (
    <main className={styles.screen}>
      <FlameIcon className={styles.mark} aria-hidden="true" />
      <div>
        <h1 className={styles.title}>Sign in to your tracker</h1>
        <p className={styles.lede}>
          {method === "google"
            ? "Only the owner's Google account can open it."
            : "Local development: enter DEV_LOGIN_KEY from the server's .env file."}
        </p>
      </div>
      {method === "google" ? (
        // Back to the same page after Google (the server accepts only a path on this site).
        <a className={styles.submit} href={googleSignInUrl(location.pathname + location.search)}>
          Sign in with Google
        </a>
      ) : (
        <DevKeyForm onSignedIn={onSignedIn} />
      )}
    </main>
  );
}

function DevKeyForm({ onSignedIn }: { onSignedIn: () => void }) {
  const [value, setValue] = useState("");
  const [rejected, setRejected] = useState(false);
  const [busy, setBusy] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    const accepted = await devSignIn(value.trim()).catch(() => false);
    setBusy(false);
    setValue(""); // the key is not kept anywhere once sent
    if (accepted) onSignedIn();
    else setRejected(true);
  };

  return (
    <form className={styles.form} onSubmit={submit}>
      <label className={styles.label} htmlFor="dev-key">
        Dev key
      </label>
      <input
        id="dev-key"
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
          That key was not accepted. Check it against DEV_LOGIN_KEY in .env.
        </p>
      )}
      <button type="submit" className={styles.submit} disabled={!value.trim() || busy}>
        Sign in
      </button>
    </form>
  );
}
