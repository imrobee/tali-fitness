import { useQueryClient } from "@tanstack/react-query";
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
import type { Dashboard } from "../api/types";
import { useIsDemo } from "../api/visit";
import { markTourSeen, TourContext, tourSeen } from "./context";
import { dialogPosition, isSheet, type Rect, sheetScrollTop, spotlight } from "./geometry";
import { counter, fill, STEPS, type TourStep } from "./steps";
import styles from "./Tour.module.css";

// How long to wait for a step's card to appear (its page may still be loading).
const FIND_TIMEOUT_MS = 8000;

function reducedMotion(): boolean {
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

function viewportSize() {
  const viewport = window.visualViewport;
  return { width: viewport?.width ?? window.innerWidth, height: viewport?.height ?? window.innerHeight };
}

function targetOf(step: TourStep): HTMLElement | null {
  return step.target ? document.querySelector<HTMLElement>(`[data-tour="${step.target}"]`) : null;
}

/** The demo tour (UI_SPEC.md section 12): the page dims, the step's card is cut out of
    the dimming, and a dialog explains it. Starts by itself on a first demo visit. */
export function TourProvider({ children }: { children: ReactNode }) {
  const demo = useIsDemo();
  // Open from the first render on a first demo visit (the gate has already loaded).
  const [index, setIndex] = useState<number | null>(() => (demo && !tourSeen() ? 0 : null));
  const opener = useRef<HTMLElement | null>(null);

  const start = useCallback(() => {
    opener.current = document.activeElement instanceof HTMLElement ? document.activeElement : null;
    setIndex(0);
  }, []);
  const close = useCallback(() => {
    setIndex(null);
    // Back to whatever had focus before (the Tour button), if it is still on the page.
    if (opener.current?.isConnected) opener.current.focus();
  }, []);

  // Once seen, it never starts by itself again in this browser.
  useEffect(() => {
    if (index !== null) markTourSeen();
  }, [index]);

  const controls = useMemo(() => ({ start, running: index !== null }), [start, index]);
  return (
    <TourContext.Provider value={controls}>
      {children}
      {index !== null && (
        <TourStepView
          key={index} // a fresh view per step: no spotlight left over from the last one
          index={index}
          onBack={() => setIndex(Math.max(0, index - 1))}
          onNext={() => (index + 1 < STEPS.length ? setIndex(index + 1) : close())}
          onClose={close}
        />
      )}
    </TourContext.Provider>
  );
}

function TourStepView({
  index,
  onBack,
  onNext,
  onClose,
}: {
  index: number;
  onBack: () => void;
  onNext: () => void;
  onClose: () => void;
}) {
  const step = STEPS[index];
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();
  const dialog = useRef<HTMLDivElement>(null);
  const [spot, setSpot] = useState<Rect | null>(null);
  const [found, setFound] = useState(step.target === null);
  const [position, setPosition] = useState<{ top: number; left: number } | null>(null);
  const [sheet, setSheet] = useState(() => isSheet(viewportSize()));

  const streak = queryClient.getQueryData<Dashboard>(["dashboard", "today"])?.streak.count;
  const title = fill(step.title, { streak });
  const last = index === STEPS.length - 1;

  // 1. Go to the step's page.
  useEffect(() => {
    if (location.pathname !== step.route) navigate(step.route);
  }, [step.route, location.pathname, navigate]);

  // 2. Wait for its card, then bring it into view.
  useEffect(() => {
    if (step.target === null) return;
    let frame = 0;
    const startedAt = performance.now();
    const look = () => {
      const target = targetOf(step);
      if (target) {
        const behavior = reducedMotion() ? "auto" : "smooth";
        if (isSheet(viewportSize())) {
          const top = target.getBoundingClientRect().top + window.scrollY;
          window.scrollTo({ top: sheetScrollTop(top), behavior });
        } else {
          target.scrollIntoView({ block: "center", behavior });
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
  }, [step]);

  // 3. Measure, and measure again whenever the page scrolls or the screen changes
  //    (rotation, the on-screen keyboard, a card finishing loading and growing).
  const measure = useCallback(() => {
    const viewport = viewportSize();
    const target = targetOf(step);
    const box = target?.getBoundingClientRect();
    const nextSpot = box ? spotlight(box, viewport) : null;
    setSpot(nextSpot);
    setSheet(isSheet(viewport));
    const size = dialog.current?.getBoundingClientRect() ?? { width: 320, height: 240 };
    setPosition(dialogPosition(nextSpot, size, viewport, step.placement));
  }, [step]);

  useLayoutEffect(() => {
    if (!found) return;
    let frame = 0;
    const later = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(measure);
    };
    later();
    window.addEventListener("scroll", later, { passive: true });
    window.addEventListener("resize", later);
    window.visualViewport?.addEventListener("resize", later);
    const growth = new ResizeObserver(later);
    const target = targetOf(step);
    if (target) growth.observe(target);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", later);
      window.removeEventListener("resize", later);
      window.visualViewport?.removeEventListener("resize", later);
      growth.disconnect();
    };
  }, [found, measure, step]);

  // 4. Focus the dialog on each step, so a screen reader reads it from the top.
  useEffect(() => {
    if (found) dialog.current?.focus();
  }, [found, index]);

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
      const lastOne = focusable[focusable.length - 1];
      if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) {
        event.preventDefault();
        lastOne.focus();
      } else if (!event.shiftKey && document.activeElement === lastOne) {
        event.preventDefault();
        first.focus();
      }
    }
  }

  const style = sheet || !position ? undefined : { top: position.top, left: position.left };
  return (
    <div className={styles.layer}>
      {/* The dimming, with the step's card cut out of it. Decoration: the dialog says it all. */}
      <svg className={styles.overlay} aria-hidden="true">
        <defs>
          <mask id="tour-cutout">
            <rect width="100%" height="100%" fill="white" />
            {spot && <rect x={spot.left} y={spot.top} width={spot.width} height={spot.height} rx={24} fill="black" />}
          </mask>
        </defs>
        <rect className={styles.dim} width="100%" height="100%" mask="url(#tour-cutout)" />
        {spot && (
          <rect className={styles.ring} x={spot.left} y={spot.top} width={spot.width} height={spot.height} rx={24} />
        )}
      </svg>

      <div
        ref={dialog}
        className={`${styles.dialog} ${sheet ? styles.sheet : styles.floating}`}
        style={style}
        role="dialog"
        aria-modal="true"
        aria-labelledby="tour-title"
        aria-describedby="tour-text"
        tabIndex={-1}
        onKeyDown={onKeyDown}
        hidden={!found}
      >
        <div className={styles.top}>
          <span className={styles.counter}>{counter(index, STEPS.length)}</span>
          <button type="button" className={styles.skip} onClick={onClose}>
            {last ? "Close" : "Skip tour"}
          </button>
        </div>
        <h2 id="tour-title" className={styles.title}>
          {title}
        </h2>
        <div id="tour-text">
          <p className={styles.text}>{step.text}</p>
          <p className={styles.built}>
            <span className={styles.builtLabel}>How it's built: </span>
            {step.built}
          </p>
        </div>
        {step.lineage.length > 0 && (
          <ul className={styles.lineage} aria-label="Where this comes from">
            {step.lineage.map((item) => (
              <li key={item.name} className={styles.chip}>
                <span className={styles.kind}>{item.kind}</span> <code>{item.name}</code>
              </li>
            ))}
          </ul>
        )}
        <div className={styles.actions}>
          {index > 0 && (
            <button type="button" className={styles.back} onClick={onBack}>
              Back
            </button>
          )}
          <button type="button" className={styles.next} onClick={onNext}>
            {last ? "Explore freely" : "Next"}
          </button>
        </div>
      </div>
    </div>
  );
}
