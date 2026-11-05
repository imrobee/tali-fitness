import { Link } from "react-router";
import { Card } from "../components/Card";
import { Page } from "../components/Page";
import data from "../tour/flow.json";
import styles from "./HowItWorksPage.module.css";

// How it works (UI_SPEC.md section 13): open to anyone, signed in or not, and calls no
// API, so it shows at once even while the demo service is still waking up.

const REPO = "https://github.com/imrobee/fitness-tracker";
const LINKS = [
  { label: "Code on GitHub", href: REPO },
  { label: "README", href: `${REPO}#readme` },
  { label: "Rob Feliciano on LinkedIn", href: "https://www.linkedin.com/in/robeefeliciano" },
];

const STACK = [
  ["Warehouse", "PostgreSQL 16: raw, core (star schema), mart (SQL functions), ops, app"],
  ["Orchestration", "Apache Airflow 3.3.2, two DAGs (Strava sync, data quality)"],
  ["API", "Python 3.13, FastAPI, SQLAlchemy Core with SQL in .sql files, Alembic"],
  ["Web", "React 19, TypeScript, Vite, TanStack Query; installable on an iPhone"],
  ["Quality", "pytest against a real Postgres, Vitest, Playwright screenshots, gitleaks, CI on every push"],
] as const;

type Name = { kind: string; name: string };
type Flow = { id: string; title: string; steps: { text: string; names: Name[] }[] };
const FLOWS = data.flows as Flow[];

export function HowItWorksPage() {
  return (
    <Page title="How it works">
      <p className={styles.lede}>
        My training, running and nutrition data lives in separate apps that don't talk to each other, so I
        built a pipeline that joins them.
      </p>

      <Card title="Architecture">
        <figure className={styles.figure}>
          <figcaption className="visually-hidden">
            Three sources feed one PostgreSQL warehouse: Strava through an hourly Airflow sync, Apple Health
            through an iPhone Shortcut posting to the API, and settings typed into the app. The API reads the
            warehouse's business rules and serves this web app.
          </figcaption>
          <div className={styles.diagram} aria-hidden="true">
            <div className={styles.row}>
              <Box title="Strava API" note="runs, walks, Hevy lifting" />
              <Box title="iOS Shortcut" note="Apple Health: food, weight" />
              <Box title="This app" note="targets, recovery days" />
            </div>
            <div className={styles.row}>
              <Arrow label="hourly pull" />
              <Arrow label="POST, bearer token" />
              <Arrow label="JSON" />
            </div>
            <div className={styles.row}>
              <Box title="Airflow" note="sync, parse, 15 checks" />
              <Box title="FastAPI" note="ingest and pages" wide />
            </div>
            <div className={styles.single}>
              <Arrow label="idempotent loads" />
            </div>
            <div className={styles.warehouse}>
              <span className={styles.boxTitle}>PostgreSQL</span>
              <span className={styles.layers}>
                <code>raw</code> → <code>core</code> → <code>mart</code>
                <span className={styles.aside}>
                  {" "}
                  + <code>ops</code> (runs, quarantine, checks) + <code>app</code> (settings)
                </span>
              </span>
            </div>
            <div className={styles.single}>
              <Arrow label="business rules, read time" />
            </div>
            <div className={styles.single}>
              <Box title="This web app" note="React, on an iPhone home screen" />
            </div>
          </div>
        </figure>
      </Card>

      <Card title="How the data flows">
        <div className={styles.flows}>
          {FLOWS.map((flow) => (
            <section key={flow.id} className={styles.flow} aria-labelledby={`flow-${flow.id}`}>
              <h3 id={`flow-${flow.id}`} className={styles.flowTitle}>
                {flow.title}
              </h3>
              <ol className={styles.steps}>
                {flow.steps.map((step) => (
                  <li key={step.text} className={styles.step}>
                    <p>{step.text}</p>
                    <ul className={styles.names} aria-label="Names in the code">
                      {step.names.map((item) => (
                        <li key={item.name} className={styles.chip}>
                          <span className={styles.kind}>{item.kind}</span> <code>{item.name}</code>
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ol>
            </section>
          ))}
        </div>
      </Card>

      <Card title="The stack">
        <dl className={styles.stack}>
          {STACK.map(([term, detail]) => (
            <div key={term} className={styles.stackRow}>
              <dt>{term}</dt>
              <dd>{detail}</dd>
            </div>
          ))}
        </dl>
      </Card>

      <Card title="The demo">
        <p className={styles.text}>
          The demo is its own service on its own database. It holds a read-only database login and no real
          credentials, so it can't reach my data or change anything. Its data is synthetic Strava and Shortcut
          payloads, run through the same pipeline code every day.
        </p>
      </Card>

      <Card title="Links">
        <ul className={styles.links}>
          {LINKS.map((link) => (
            <li key={link.href}>
              <a className={styles.link} href={link.href} target="_blank" rel="noreferrer">
                {link.label}
              </a>
            </li>
          ))}
          <li>
            <Link className={styles.link} to="/">
              Back to the app
            </Link>
          </li>
        </ul>
      </Card>
    </Page>
  );
}

function Box({ title, note, wide = false }: { title: string; note: string; wide?: boolean }) {
  return (
    <div className={`${styles.box} ${wide ? styles.wide : ""}`}>
      <span className={styles.boxTitle}>{title}</span>
      <span className={styles.boxNote}>{note}</span>
    </div>
  );
}

function Arrow({ label }: { label: string }) {
  return (
    <div className={styles.arrow}>
      <span className={styles.arrowLine}>↓</span>
      <span className={styles.arrowLabel}>{label}</span>
    </div>
  );
}
