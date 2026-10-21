import { Link } from "react-router";
import type { Dashboard } from "../api/types";
import { proteinLabel } from "../lib/a11y";
import { proteinFill } from "../lib/ring";
import cardStyles from "./Card.module.css";
import styles from "./ProteinCard.module.css";

interface Props {
  protein: Dashboard["protein"];
  to?: string;
}

export function ProteinCard({ protein, to }: Props) {
  const { grams, goal, percent } = protein;
  const left = goal === null ? null : Math.max(goal - grams, 0);

  return (
    // Its own card layout (no separate header): "Protein" is the title (UI_SPEC.md 5.7).
    <section className={cardStyles.card} aria-label={proteinLabel(grams, goal, percent)}>
      <div className={styles.top}>
        <div className={styles.label}>
          <h2 className={styles.title}>
            {to ? (
              <Link to={to} className={cardStyles.stretched}>
                Protein
              </Link>
            ) : (
              "Protein"
            )}
          </h2>
          {goal === null ? (
            <Link to="/me" className={`${styles.setGoal} ${cardStyles.above}`}>
              Set a protein goal
            </Link>
          ) : (
            <span className={`${styles.grams} num`}>
              {grams}g, {left}g left
            </span>
          )}
        </div>
        {percent !== null && <span className={`${styles.percent} num`}>{percent}%</span>}
      </div>
      <div className={styles.track} aria-hidden="true">
        <div className={styles.fill} style={{ width: `${proteinFill(grams, goal) * 100}%` }} />
      </div>
    </section>
  );
}
