import styles from "./Wordmark.module.css";

/** "tali": letters in the text colour, the i-dot a mint ring around a core. The launch
    screen's h1 at 120px, and small at the top of every page (Page). Its size comes from
    the className; `decorative` hides it from screen readers where the page already says
    what it is. */
export function Wordmark({ className, decorative = false }: { className?: string; decorative?: boolean }) {
  return (
    <svg
      className={`${styles.wordmark} ${className ?? ""}`}
      viewBox="0 0 230 140"
      role={decorative ? undefined : "img"}
      aria-label={decorative ? undefined : "tali"}
      aria-hidden={decorative ? true : undefined}
    >
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
