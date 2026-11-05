import {
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { useLocation, useNavigate } from "react-router";
import { useIsDemo, useStory } from "../api/visit";
import { DayCircle } from "../components/DayCircle";
import { EXPLAINER, type ExplainerExample, exampleDays } from "../lib/streakExplainer";
import { markTourSeen, TourContext, type TourName, tourSeen } from "./context";
import {
  dialogPosition,
  isSheet,
  type Rect,
  sheetRoom,
  sheetScrollTop,
  spotlight,
  technicalLines,
  union,
} from "./geometry";
import { Legend } from "./Legend";
import {
  counter,
  fill,
  fillRoute,
  footer,
  hasSwitch,
  paragraphs,
  STEPS,
  type Story,
  type TourButton,
  type TourStep,
} from "./steps";
import { streakSteps } from "./streakTour";
import styles from "./Tour.module.css";

// How long to wait for a step's card to load (its page may still be fetching).
const FIND_TIMEOUT_MS = 8000;
// "Technical details" on or off, for this browser tab.
const DETAILS_KEY = "tali.tour-details";

function reducedMotion(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

function viewportSize() {
  const viewport = window.visualViewport;
  return { width: viewport?.width ?? window.innerWidth, height: viewport?.height ?? window.innerHeight };
}

/** Where the step's selectors look: the page, or the first element matching `within`. */
function scopeOf(step: TourStep): ParentNode | null {
  return step.within ? document.querySelector(step.within) : document;
}

/** Every element the step points at (two cards, or a session's first exercises). */
function targetsOf(step: TourStep): HTMLElement[] {
  const scope = scopeOf(step);
  if (!scope) return [];
  return step.targets.flatMap((selector) => [...scope.querySelectorAll<HTMLElement>(selector)]);
}

/** The step's closed session, to open (null when there is none, or it is open). */
function toOpenOf(step: TourStep): HTMLElement | null {
  return step.open ? (scopeOf(step)?.querySelector<HTMLElement>(step.open) ?? null) : null;
}

/** One box around all of them, in viewport pixels; null when none is on the page. */
function targetBox(step: TourStep): Rect | null {
  return union(targetsOf(step).map((element) => element.getBoundingClientRect()));
}

function detailsOnAtStart(): boolean {
  try {
    return window.sessionStorage.getItem(DETAILS_KEY) === "1";
  } catch {
    return false;
  }
}

/** The demo tour (UI_SPEC.md section 12): the page dims, the step's card is cut out of the
    dimming, and a dialog (a bottom sheet on a phone) explains it in plain words; the
    Technical details switch adds the engineering. Starts by itself on a first demo visit.
    The same engine runs the streak explainer (the "?" on the streak card, D129). */
export function TourProvider({ children }: { children: ReactNode }) {
  const demo = useIsDemo();
  const story = useStory();
  // Open from the first render on a first demo visit (the gate has already loaded).
  const [tour, setTour] = useState<TourName>("demo");
  const [index, setIndex] = useState<number | null>(() => (demo && !tourSeen() ? 0 : null));
  const [details, setDetails] = useState(detailsOnAtStart);
  const opener = useRef<HTMLElement | null>(null);
  const steps = tour === "streak" ? streakSteps(demo) : STEPS;

  const start = useCallback((name: TourName = "demo") => {
    opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setTour(name);
    setIndex(0);
  }, []);
  const close = useCallback(() => {
    setIndex(null);
    // Back to whatever had focus before (the Tour button), if it is still on the page.
    if (opener.current?.isConnected) opener.current.focus();
  }, []);
  const toggleDetails = useCallback(() => {
    setDetails((on) => {
      try {
        window.sessionStorage.setItem(DETAILS_KEY, on ? "0" : "1");
      } catch {
        // Storage blocked: the switch still works for this page.
      }
      return !on;
    });
  }, []);

  // Once seen, it never starts by itself again in this browser. While it runs, the page
  // gets room at the bottom, so even its last card can scroll clear of the sheet.
  useEffect(() => {
    if (index !== null && tour === "demo") markTourSeen();
    document.body.classList.toggle("tour-open", index !== null);
  }, [index, tour]);

  const controls = useMemo(() => ({ start, running: index !== null }), [start, index]);
  const step = index === null ? null : steps[index];
  return (
    <TourContext.Provider value={controls}>
      {children}
      {/* Announces each step; always on the page, so screen readers notice the change. */}
      <p className="visually-hidden" aria-live="polite">
        {index !== null && step ? `Step ${counter(index, steps.length)}: ${fill(step.title, story)}` : ""}
      </p>
      {index !== null && (
        <TourStepView
          key={`${tour}-${index}`} // a fresh view per step: no spotlight left over from the last one
          steps={steps}
          heading={tour === "streak" ? EXPLAINER.title : null}
          index={index}
          story={story}
          details={details}
          onToggleDetails={toggleDetails}
          onBack={() => setIndex(Math.max(0, index - 1))}
          onNext={() => (index + 1 < steps.length ? setIndex(index + 1) : close())}
          onClose={close}
        />
      )}
    </TourContext.Provider>
  );
}

interface ViewProps {
  steps: TourStep[];
  /** The explainer's name above its counter ("How your streak works"); null for the tour. */
  heading: string | null;
  index: number;
  story: Story;
  details: boolean;
  onToggleDetails: () => void;
  onBack: () => void;
  onNext: () => void;
  onClose: () => void;
}

function lineHeightOf(element: HTMLElement): number {
  const style = window.getComputedStyle(element);
  const height = Number.parseFloat(style.lineHeight);
  return Number.isFinite(height) ? height : Number.parseFloat(style.fontSize) * 1.45;
}

function TourStepView({
  steps,
  heading,
  index,
  story,
  details,
  onToggleDetails,
  onBack,
  onNext,
  onClose,
}: ViewProps) {
  const step = steps[index];
  const modal = step.placement === "modal";
  // No route: the step is about something on the page already open (the streak card).
  const route = step.route ? fillRoute(step.route, story) : null;
  const navigate = useNavigate();
  const location = useLocation();
  const dialog = useRef<HTMLDivElement>(null);
  const technical = useRef<HTMLParagraphElement>(null);
  const [found, setFound] = useState(modal);
  const [spot, setSpot] = useState<Rect | null>(null);
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);
  const [phone, setPhone] = useState(() => isSheet(viewportSize()));
  // Phone, Technical details on: the lines of technical words that fit (null: all), and
  // whether "Show more" has swapped them in for the body.
  const [clamp, setClamp] = useState<{ lines: number; lineHeight: number } | null>(null);
  const [swappedChoice, setSwapped] = useState(false);
  const showTechnical = details && hasSwitch(step);
  const swapped = swappedChoice && showTechnical; // switching details off goes back to the body

  // 1. Go to the step's page.
  useEffect(() => {
    if (route !== null && location.pathname + location.search !== route) navigate(route);
  }, [route, location.pathname, location.search, navigate]);

  // 2. Wait for its cards to finish loading (and open the gym session), then bring them
  //    into view: on a phone at the top of the screen, clear of the sheet.
  useEffect(() => {
    if (modal) return;
    let frame = 0;
    const startedAt = performance.now();
    const look = () => {
      const toOpen = toOpenOf(step);
      if (toOpen) toOpen.click();
      const targets = targetsOf(step);
      // Loaded: no placeholder in the targets, nor in the session they belong to (its sets
      // arrive after it opens, and the targets' own box isn't final until they do).
      const scope = step.within ? document.querySelector(step.within) : null;
      const ready =
        targets.length > 0 &&
        !toOpen &&
        !scope?.querySelector("[data-loading]") &&
        targets.every((target) => !target.querySelector("[data-loading]"));
      if (ready) {
        const box = targetBox(step);
        const behavior = reducedMotion() ? "auto" : "smooth";
        if (box && isSheet(viewportSize())) {
          window.scrollTo({ top: sheetScrollTop(box.top + window.scrollY), behavior });
        } else if (box) {
          const middle = box.top + window.scrollY + box.height / 2;
          window.scrollTo({ top: Math.max(0, middle - viewportSize().height / 2), behavior });
        }
        setFound(true);
      } else if (performance.now() - startedAt < FIND_TIMEOUT_MS) {
        frame = requestAnimationFrame(look);
      } else {
        setFound(true); // not there: show the words without a spotlight
      }
    };
    frame = requestAnimationFrame(look);
    return () => cancelAnimationFrame(frame);
  }, [step, modal]);

  // 3. Measure, and measure again whenever the page scrolls or the screen changes
  //    (rotation, the on-screen keyboard, a card growing).
  const measure = useCallback(() => {
    const viewport = viewportSize();
    // The page may re-render under the tour (a list refreshing closes an opened session):
    // open it again.
    const reopen = toOpenOf(step);
    if (reopen) reopen.click();
    const box = modal ? null : targetBox(step);
    const sheet = isSheet(viewport);
    // Phone: a card above may finish loading after the scroll and shrink, pushing the
    // target up off the screen. Put it back at the top (at once: this is a correction).
    if (sheet && box && box.top < 0) {
      window.scrollTo({ top: sheetScrollTop(box.top + window.scrollY), behavior: "auto" });
    }
    setPhone(sheet);
    setSpot(box ? spotlight(box, viewport) : null);
    // Phone: clamp the technical words so the sheet never grows over the target.
    const words = technical.current;
    const sheetBox = dialog.current;
    if (sheet && box && words && sheetBox && !swapped) {
      const more = sheetBox.querySelector<HTMLElement>("[data-more]")?.offsetHeight ?? 0;
      const others = sheetBox.offsetHeight - words.offsetHeight - more;
      const lineHeight = lineHeightOf(words);
      const lines = technicalLines(sheetRoom(box.height, viewport.height), others, words.scrollHeight, lineHeight);
      setClamp(lines === null ? null : { lines, lineHeight });
    } else if (!sheet) {
      setClamp(null);
    }
    const size = sheetBox?.getBoundingClientRect() ?? { width: 320, height: 240 };
    setPosition(dialogPosition(box ? spotlight(box, viewport) : null, size, viewport, "bottom"));
  }, [step, modal, swapped]);

  useLayoutEffect(() => {
    if (!found) return;
    let frame = 0;
    const later = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(measure);
    };
    later();
    // Also every half second: a card can be replaced, not just resized, by a re-render.
    const poll = window.setInterval(later, 500);
    window.addEventListener("scroll", later, { passive: true });
    window.addEventListener("resize", later);
    window.visualViewport?.addEventListener("resize", later);
    const growth = new ResizeObserver(later);
    for (const target of targetsOf(step)) growth.observe(target);
    if (dialog.current) growth.observe(dialog.current);
    return () => {
      cancelAnimationFrame(frame);
      window.clearInterval(poll);
      window.removeEventListener("scroll", later);
      window.removeEventListener("resize", later);
      window.visualViewport?.removeEventListener("resize", later);
      growth.disconnect();
    };
  }, [found, measure, step, showTechnical]);

  // 4. Focus the dialog on each step, so a screen reader reads it from the top.
  useEffect(() => {
    if (found) dialog.current?.focus();
  }, [found, index]);

  function press(button: TourButton) {
    if (button.does === "next") onNext();
    else if (button.does === "back") onBack();
    else {
      onClose();
      if (button.does === "link" && button.to) navigate(button.to);
    }
  }

  function onKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      onClose();
    } else if (event.key === "ArrowRight") {
      onNext();
    } else if (event.key === "ArrowLeft" && index > 0) {
      onBack();
    } else if (event.key === "Tab") {
      // Keep Tab inside the dialog while it is open (aria-modal).
      const focusable = dialog.current?.querySelectorAll<HTMLElement>("button, a[href]");
      if (!focusable?.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  }

  const sheet = phone && !modal;
  const layout = modal ? styles.modal : sheet ? styles.sheet : styles.floating;
  const style = !modal && !sheet && position ? { top: position.top, left: position.left } : undefined;
  const buttons = footer(step, index);
  // Skip sits at the top of the tour's middle steps (its first and last have their own
  // footer); the streak explainer has Close on every step.
  const explainer = heading !== null;
  const skipAtTop = explainer || !step.buttons;
  const clamped = sheet && showTechnical && !swapped && clamp !== null;
  const technicalStyle = clamped
    ? { WebkitLineClamp: Math.max(clamp.lines, 1), maxHeight: clamp.lines * clamp.lineHeight }
    : undefined;

  return (
    <div className={styles.layer}>
      {/* The dimming, with the step's cards cut out of it (none for the modal steps).
          Decoration: the dialog says it all. */}
      <svg className={styles.overlay} aria-hidden="true">
        <defs>
          <mask id="tour-cutout">
            <rect width="100%" height="100%" fill="white" />
            {spot && <rect x={spot.left} y={spot.top} width={spot.width} height={spot.height} rx={20} fill="black" />}
          </mask>
        </defs>
        <rect className={styles.dim} width="100%" height="100%" mask="url(#tour-cutout)" />
      </svg>

      <div
        ref={dialog}
        className={`${styles.dialog} ${layout}`}
        style={style}
        role="dialog"
        aria-modal="true"
        aria-labelledby="tour-title"
        aria-describedby={swapped ? "tour-technical" : "tour-text"}
        tabIndex={-1}
        onKeyDown={onKeyDown}
        hidden={!found}
        data-tour-dialog=""
      >
        <div className={styles.content}>
          <div className={styles.top}>
            <span className={styles.counter}>
              {explainer && `${heading} · `}
              {counter(index, steps.length)}
            </span>
            {skipAtTop && (
              <button type="button" className={styles.skip} onClick={onClose}>
                {explainer ? "Close" : "Skip tour"}
              </button>
            )}
          </div>
          <h2 id="tour-title" className={styles.title}>
            {fill(step.title, story)}
          </h2>
          {!swapped && (
            <>
              <div id="tour-text" className={styles.body}>
                <RichText text={fill(step.body, story)} />
              </div>
              {step.legend && <Legend kind={step.legend} />}
              {step.example && <Example example={step.example} />}
              {step.note && <p className={styles.note}>{step.note}</p>}
            </>
          )}
          {showTechnical && step.technical && (
            <div className={styles.technical} id="tour-technical">
              <p ref={technical} className={clamped ? styles.clamp : undefined} style={technicalStyle}>
                {fill(step.technical, story)}
              </p>
              {(clamped || swapped) && (
                <button
                  type="button"
                  className={styles.more}
                  data-more=""
                  aria-expanded={swapped}
                  aria-controls="tour-technical"
                  onClick={() => setSwapped(!swapped)}
                >
                  {swapped ? "Show less" : clamp?.lines === 0 ? "Show technical details" : "Show more"}
                </button>
              )}
            </div>
          )}
        </div>
        <div className={styles.footer}>
          {hasSwitch(step) ? (
            <button
              type="button"
              role="switch"
              aria-checked={details}
              className={styles.switch}
              onClick={onToggleDetails}
            >
              <span className={styles.switchTrack} aria-hidden="true" />
              Technical details
            </button>
          ) : (
            <span />
          )}
          <div className={styles.buttons}>
            {buttons.map((button, position) => (
              <button
                key={button.label}
                type="button"
                className={position === buttons.length - 1 ? styles.primary : styles.secondary}
                onClick={() => press(button)}
              >
                {button.label}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

/** The streak explainer's row of example days, drawn by the streak card's own circle, with
    its caption. The caption says it in words; the circles are decoration. */
function Example({ example }: { example: ExplainerExample }) {
  const { days, today } = exampleDays(example);
  return (
    <figure className={styles.example}>
      <span className={styles.exampleDays}>
        {days.map((day) => (
          <DayCircle key={day.date} day={day} today={today} />
        ))}
      </span>
      <figcaption className={styles.exampleCaption}>{example.caption}</figcaption>
    </figure>
  );
}

/** A step's words: one <p> per paragraph, *words* in italics (steps.ts paragraphs()). */
function RichText({ text }: { text: string }) {
  return paragraphs(text).map((parts, index) => (
    // Paragraphs never move or change order within a step, so their place is their key.
    <p key={index} className={styles.text}>
      {parts.map((part, at) => (part.italic ? <em key={at}>{part.text}</em> : part.text))}
    </p>
  ));
}
