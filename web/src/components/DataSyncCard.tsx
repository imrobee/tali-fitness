import { useState } from "react";
import type { PipelineHealth, SourceHealth } from "../api/types";
import { clockTime, reasonLabel, type SourceStatus, sourceName, statusLabel, timeAgo } from "../lib/pipeline";
import { ChevronDownIcon } from "../icons";
import { Card } from "./Card";
import { useIsDemo } from "../api/visit";
import { RunHealthShortcut, SyncNowButton } from "./SyncNow";
import styles from "./DataSyncCard.module.css";

// Shape and text carry the status, never colour alone (UI_SPEC.md 8). No red (section 9).
const GLYPH: Record<SourceStatus, string> = { ok: "✓", delayed: "!", failed: "✕" };

interface Props {
  health: PipelineHealth;
  now: number;
}

/** The Me page's "Data and sync" panel (UI_SPEC.md 6.3): sources, quarantine, data quality. */
export function DataSyncCard({ health, now }: Props) {
  return (
    <Card title="Data and sync">
      <ul className={styles.sources}>
        {health.sources.map((source) => (
          <SourceRow key={source.source} source={source} now={now} />
        ))}
      </ul>
      <Expandable
        label={`Quarantined records: ${health.quarantine.open}`}
        empty={health.quarantine.open === 0 ? "Nothing waiting for a fix." : undefined}
      >
        <ul className={styles.list}>
          {health.quarantine.recent.map((item) => (
            <li key={`${item.source}-${item.entity_id}-${item.line_no}-${item.first_seen_at}`}>
              <span className={styles.meta}>
                {sourceName(item.source)} · {reasonLabel(item.reason_code)}
              </span>
              <code className={styles.snippet}>{item.raw_snippet}</code>
            </li>
          ))}
        </ul>
      </Expandable>
      <Expandable
        label={`Data quality: ${health.dq.passed} passed, ${health.dq.warnings} warnings, ${health.dq.failed} failed`}
        empty={health.dq.checks.length === 0 ? "No checks have run yet." : undefined}
      >
        <ul className={styles.list}>
          {health.dq.checks.map((check) => (
            <li key={check.check_name} className={styles.checkRow}>
              <span>{check.check_name.replaceAll("_", " ")}</span>
              <span className={styles.meta}>
                {statusText(check.status)} · {check.threshold}
              </span>
            </li>
          ))}
        </ul>
      </Expandable>
    </Card>
  );
}

function SourceRow({ source, now }: { source: SourceHealth; now: number }) {
  const status = source.status;
  // The demo never syncs: it has no Strava, no Shortcut and no Airflow (DECISIONS D118).
  const demo = useIsDemo();
  return (
    <li className={styles.source}>
      <div className={styles.sourceHead}>
        <span className={styles.sourceName}>{sourceName(source.source)}</span>
        <span className={`${styles.status} ${styles[status]}`}>
          <span aria-hidden="true">{GLYPH[status]}</span> {statusLabel(status)}
        </span>
      </div>
      <span className={styles.meta}>
        {source.last_success_at
          ? `Last successful sync ${timeAgo(source.last_success_at, now)} (${clockTime(source.last_success_at)})`
          : "No successful sync yet"}
      </span>
      {source.failures_7d > 0 && (
        <span className={styles.meta}>
          {source.failures_7d === 1
            ? "1 failure in the last 7 days"
            : `${source.failures_7d} failures in the last 7 days`}
        </span>
      )}
      {!demo && source.source === "strava" && <SyncNowButton />}
      {!demo && source.source === "health" && <RunHealthShortcut />}
    </li>
  );
}

function statusText(status: "pass" | "warn" | "fail"): string {
  return { pass: "Pass", warn: "Warning", fail: "Failed" }[status];
}

/** A row that opens to show its list. Closed by default; the button says what is inside. */
function Expandable({
  label,
  empty,
  children,
}: {
  label: string;
  empty?: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const id = `${label.replace(/\W+/g, "-").toLowerCase()}-panel`;
  if (empty) {
    return <p className={styles.meta}>{label}. {empty}</p>;
  }
  return (
    <div>
      <button
        type="button"
        className={styles.toggle}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((value) => !value)}
      >
        {label}
        <ChevronDownIcon className={`${styles.chevron} ${open ? styles.open : ""}`} />
      </button>
      {open && (
        <div id={id} className={styles.panel}>
          {children}
        </div>
      )}
    </div>
  );
}
