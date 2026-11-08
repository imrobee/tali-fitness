import { useEffect, useState } from "react";
import { useFirstLoad } from "../api/hooks";
import styles from "./LoadingOverlay.module.css";

/** The page dims and a mint ring fills and empties during a first load (useFirstLoad).
    It waits `delayMs` first, so a quick answer never flashes it. */
export function LoadingOverlay({ delayMs = 300 }: { delayMs?: number }) {
  const loading = useFirstLoad();
  const [waited, setWaited] = useState(false);

  useEffect(() => {
    if (!loading) return;
    const timer = setTimeout(() => setWaited(true), delayMs);
    return () => {
      clearTimeout(timer);
      setWaited(false);
    };
  }, [loading, delayMs]);

  if (!loading || !waited) return null;
  return (
    <div className={styles.overlay} role="status">
      {/* pathLength 100: the dash offsets in the CSS are percentages of the ring. */}
      <svg className={styles.spinner} viewBox="0 0 48 48" aria-hidden="true">
        <circle className={styles.track} cx={24} cy={24} r={20} pathLength={100} />
        <circle className={styles.arc} cx={24} cy={24} r={20} pathLength={100} />
      </svg>
      <span className="visually-hidden">Loading</span>
    </div>
  );
}
