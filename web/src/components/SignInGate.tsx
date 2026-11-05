import { useQuery, useQueryClient } from "@tanstack/react-query";
import { type FormEvent, type ReactNode, useEffect, useState } from "react";
import { useLocation } from "react-router";
import { AUTH_QUERY, devSignIn, forgetOldKey, googleSignInUrl, type SignInMethod } from "../api/auth";
import { loadAuth } from "../api/visit";
import { UNAUTHORIZED_EVENT } from "../api/client";
import styles from "./SignInGate.module.css";

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
  return <SignInScreen method={auth.data.method} demoUrl={auth.data.demoUrl} onSignedIn={recheck} />;
}

function SignInScreen({
  method,
  demoUrl,
  onSignedIn,
}: {
  method: SignInMethod;
  demoUrl: string | null;
  onSignedIn: () => void;
}) {
  const location = useLocation();
  return (
    <main className={styles.launch}>
      <div className={styles.column}>
        <img className={styles.icon} src="/favicon.svg" alt="" width={88} height={88} />
        {/* The page's one h1: the app's name, drawn as the wordmark. */}
        <h1 className={styles.brand}>
          <Wordmark />
        </h1>
        <div className={styles.actions}>
          {method === "google" ? (
            // A plain link, not a button: the server runs the Google flow (AUTH_SPEC.md
            // section 9), then sends the browser back to this same page.
            <a className={styles.google} href={googleSignInUrl(location.pathname + location.search)}>
              <GoogleG />
              Sign in with Google
            </a>
          ) : (
            <DevKeyForm onSignedIn={onSignedIn} />
          )}
          <p className={styles.note}>
            This app is limited to invited users only. To learn more about the app, check out the Demo
            version.
          </p>
          {/* The demo is its own service, with its own database (DECISIONS D118): a plain
              link to it. Without one configured, the button stays and does nothing. */}
          {demoUrl ? (
            <a className={styles.demo} href={demoUrl}>
              Demo version
            </a>
          ) : (
            <button type="button" className={styles.demo}>
              Demo version
            </button>
          )}
        </div>
      </div>
      <CornerRing />
    </main>
  );
}

/** "tali": letters in the text colour, the i-dot a mint ring around a core. */
function Wordmark() {
  return (
    <svg className={styles.wordmark} viewBox="0 0 230 140" role="img" aria-label="tali">
      <g fill="none" stroke="currentColor" strokeWidth={14} strokeLinecap="round" strokeLinejoin="round">
        <path d="M8 56 H44" />
        <path d="M24 28 V90 C24 104 32 110 46 110" />
        <circle cx={98} cy={81} r={29} />
        <path d="M127 52 V110" />
        <path d="M166 24 V110" />
        <path d="M206 54 V110" />
      </g>
      <circle className={styles.dotRing} cx={206} cy={24} r={11} strokeWidth={5} />
      <circle className={styles.dotCore} cx={206} cy={24} r={4} />
    </svg>
  );
}

/** Google's multicolour "G". Its four colours are Google's brand, fixed in both themes. */
function GoogleG() {
  return (
    <svg className={styles.g} viewBox="0 0 48 48" aria-hidden="true">
      <path
        fill="#EA4335"
        d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"
      />
      <path
        fill="#4285F4"
        d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"
      />
      <path
        fill="#FBBC05"
        d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"
      />
      <path
        fill="#34A853"
        d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"
      />
    </svg>
  );
}

/** The faint ring cropped by the bottom-right corner: decoration only, hidden from readers. */
function CornerRing() {
  return (
    <svg className={styles.corner} viewBox="0 0 400 400" aria-hidden="true" focusable="false">
      <circle className={styles.cornerRing} cx={200} cy={200} r={160} strokeWidth={44} />
      <circle className={styles.cornerCore} cx={200} cy={200} r={100} />
    </svg>
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
      <button type="submit" className={styles.google} disabled={!value.trim() || busy}>
        Sign in
      </button>
    </form>
  );
}
