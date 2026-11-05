import { Link } from "react-router";
import { useStory } from "../api/visit";
import { Card } from "../components/Card";
import { Page } from "../components/Page";
import { GitHubIcon, LinkedInIcon } from "../icons";
import { fill, type Story } from "../tour/steps";
import data from "./howItWorks.json";
import styles from "./HowItWorksPage.module.css";

// How it works (UI_SPEC.md section 13): open to anyone, signed in or not, and calls no
// API, so it shows at once even while the demo service is still waking up. The words
// live in howItWorks.json.

type Section = { id: string; title: string; text: string; without?: string };
const SECTIONS = data.sections as Section[];
const ICONS = { github: GitHubIcon, linkedin: LinkedInIcon } as const;

/** A section's words with the demo's numbers filled in, sentence by sentence. A sentence
    whose number isn't known (a signed-out visit: the page asks the server nothing)
    becomes the section's `without` sentence, or is left out. */
function sectionText(section: Section, story: Story): string {
  return section.text
    .split(/(?<=[.!?])\s+/)
    .map((sentence) => fill(sentence, story) || section.without || "")
    .filter(Boolean)
    .join(" ");
}

export function HowItWorksPage() {
  // The tour's numbers, when this browser is on a demo visit; read from the cache only.
  const story = useStory();
  return (
    <Page title="How it works">
      <p className={styles.intro}>{data.intro}</p>

      <figure className={styles.figure}>
        <ol className={styles.stages}>
          {data.diagram.stages.map((stage, index) => (
            <li key={stage.title} className={styles.stage}>
              <span className={styles.number} aria-hidden="true">
                {index + 1}
              </span>
              <span>
                <span className={styles.stageTitle}>{stage.title}</span>
                <span className={styles.stageText}>{stage.text}</span>
              </span>
            </li>
          ))}
        </ol>
        <figcaption className={styles.caption}>{data.diagram.caption}</figcaption>
      </figure>

      {SECTIONS.map((section) => (
        <section key={section.id} className={styles.section} aria-labelledby={`how-${section.id}`}>
          <h2 id={`how-${section.id}`} className={styles.heading}>
            {section.title}
          </h2>
          <p className={styles.text}>{sectionText(section, story)}</p>
        </section>
      ))}

      <Card title={data.profile.title}>
        <div className={styles.profile}>
          {data.profile.links.map((link) => {
            const Icon = ICONS[link.icon as keyof typeof ICONS];
            return (
              <a key={link.href} className={styles.profileLink} href={link.href} target="_blank" rel="noreferrer">
                <Icon className={styles.profileIcon} />
                {link.label}
              </a>
            );
          })}
        </div>
      </Card>

      <Link className={styles.back} to="/">
        Back to the app
      </Link>
    </Page>
  );
}
