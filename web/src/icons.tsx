// Every icon in the app, as small SVG components. One set: Tabler (MIT), fetched with the
// better-icons tool and pasted here, so there is no icon library at runtime. Outline icons
// are 24x24 at a 2px stroke; size and colour come from the parent (1em, currentColor).
// Active tabs need filled versions; Tabler has some (apple). For bar chart and user
// circle they are drawn here; the runner gets a heavier stroke.

import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement>;

function Outline({ children, strokeWidth = 2, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="1em"
      height="1em"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      {children}
    </svg>
  );
}

function Solid({ children, ...props }: IconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      width="1em"
      height="1em"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
      {...props}
    >
      {children}
    </svg>
  );
}

const BAR_CHART =
  "M3 13a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1zm12-4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v10a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1zM9 5a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v14a1 1 0 0 1-1 1h-4a1 1 0 0 1-1-1z";

// --- Bottom navigation (UI_SPEC.md section 1) ---------------------------------------------

export function DashboardIcon({ filled, ...props }: IconProps & { filled?: boolean }) {
  // Filling the outline's three touching bars made one solid block, so the active icon is
  // three separate solid bars with a 2px gap between them.
  if (filled) {
    return (
      <Solid {...props}>
        <rect x="3" y="12" width="4.5" height="8" rx="1" />
        <rect x="9.75" y="4" width="4.5" height="16" rx="1" />
        <rect x="16.5" y="8" width="4.5" height="12" rx="1" />
      </Solid>
    );
  }
  return (
    <Outline {...props}>
      <path d={BAR_CHART} />
      <path d="M4 20h14" />
    </Outline>
  );
}

export function RunIcon({ filled, ...props }: IconProps & { filled?: boolean }) {
  return (
    <Outline strokeWidth={filled ? 2.6 : 2} {...props}>
      <path d="M11.007 5a2 2 0 1 0 4 0a2 2 0 1 0-4 0M4 17l5 1l.75-1.5M15 21v-4l-4-3l1-6" />
      <path d="M7 12V9l5-1l3 3l3 1" />
    </Outline>
  );
}

export function AppleIcon({ filled, ...props }: IconProps & { filled?: boolean }) {
  if (filled) {
    return (
      <Solid {...props}>
        <path d="M15 2a1 1 0 0 1 .117 1.993L15 4c-.693 0-1.33.694-1.691 1.552a5.1 5.1 0 0 1 1.982-.544L15.556 5C18.538 5 21 8.053 21 11.32c0 3.547-.606 5.862-2.423 8.578c-1.692 2.251-4.092 2.753-6.41 1.234a.31.31 0 0 0-.317-.01c-2.335 1.528-4.735 1.027-6.46-1.27C3.607 17.184 3 14.868 3 11.32l.004-.222C3.112 7.917 5.53 5 8.444 5c.94 0 1.852.291 2.688.792C11.551 3.842 12.95 2 15 2M7.966 8.154C6.606 9.012 6 10.214 6 12a1 1 0 0 0 2 0c0-1.125.28-1.678 1.034-2.154a1 1 0 1 0-1.068-1.692" />
      </Solid>
    );
  }
  return (
    <Outline {...props}>
      <path d="M4 11.319c0 3.102.444 5.319 2.222 7.978c1.351 1.797 3.156 2.247 5.08.988c.426-.268.97-.268 1.397 0c1.923 1.26 3.728.809 5.079-.988C19.556 16.637 20 14.421 20 11.32C20 8.659 18.01 6 15.556 6c-1.267 0-2.41.693-3.22 1.44a.5.5 0 0 1-.672 0C10.855 6.694 9.711 6 8.444 6C5.99 6 4 8.66 4 11.319" />
      <path d="M7 12c0-1.47.454-2.34 1.5-3M12 7c0-1.2.867-4 3-4" />
    </Outline>
  );
}

export function PersonCircleIcon({ filled, ...props }: IconProps & { filled?: boolean }) {
  if (filled) {
    // The filled circle with the head and shoulders cut out of it.
    return (
      <svg viewBox="0 0 24 24" width="1em" height="1em" aria-hidden="true" focusable="false" {...props}>
        <mask id="person-cutout">
          <rect width="24" height="24" fill="white" />
          <g fill="none" stroke="black" strokeWidth="2" strokeLinecap="round">
            <circle cx="12" cy="10" r="3" />
            <path d="M6.168 18.849A4 4 0 0 1 10 16h4a4 4 0 0 1 3.834 2.855" />
          </g>
        </mask>
        <circle cx="12" cy="12" r="10" fill="currentColor" mask="url(#person-cutout)" />
      </svg>
    );
  }
  return (
    <Outline {...props}>
      <circle cx="12" cy="12" r="9" />
      <circle cx="12" cy="10" r="3" />
      <path d="M6.168 18.849A4 4 0 0 1 10 16h4a4 4 0 0 1 3.834 2.855" />
    </Outline>
  );
}

// --- Activity types (the streak circles and exercise rows) ---------------------------------

export function WalkIcon(props: IconProps) {
  return (
    <Outline {...props}>
      <path d="M12 4a1 1 0 1 0 2 0a1 1 0 1 0-2 0M7 21l3-4m6 4l-2-4l-3-3l1-6" />
      <path d="m6 12l2-3l4-1l3 3l3 1" />
    </Outline>
  );
}

export function BikeIcon(props: IconProps) {
  return (
    <Outline {...props}>
      <path d="M2 18a3 3 0 1 0 6 0a3 3 0 0 0-6 0m14 0a3 3 0 1 0 6 0a3 3 0 0 0-6 0m-4 1v-4l-3-3l5-4l2 3h3m-5.993-6a2 2 0 1 0 4 0a2 2 0 1 0-4 0" />
    </Outline>
  );
}

export function SwimIcon(props: IconProps) {
  return (
    <Outline {...props}>
      <path d="M15 9a1 1 0 1 0 2 0a1 1 0 1 0-2 0m-9 2l4-2l3.5 3l-1.5 2m-9 2.75A2.4 2.4 0 0 0 4 17a2.4 2.4 0 0 0 2-1a2.4 2.4 0 0 1 2-1a2.4 2.4 0 0 1 2 1a2.4 2.4 0 0 0 2 1a2.4 2.4 0 0 0 2-1a2.4 2.4 0 0 1 2-1a2.4 2.4 0 0 1 2 1a2.4 2.4 0 0 0 2 1a2.4 2.4 0 0 0 1-.25" />
    </Outline>
  );
}

export function BarbellIcon(props: IconProps) {
  return (
    <Outline {...props}>
      <path d="M2 12h1m3-4H4a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2m0-9v10a1 1 0 0 0 1 1h1a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1H7a1 1 0 0 0-1 1m3 5h6m0-5v10a1 1 0 0 0 1 1h1a1 1 0 0 0 1-1V7a1 1 0 0 0-1-1h-1a1 1 0 0 0-1 1m3 1h2a1 1 0 0 1 1 1v6a1 1 0 0 1-1 1h-2m4-4h-1" />
    </Outline>
  );
}

export function YogaIcon(props: IconProps) {
  return (
    <Outline {...props}>
      <path d="M4 20h4l1.5-3m7.5 3l-1-5h-5l1-7" />
      <path d="m4 10l4-1l4-1l4 1.5l4 1.5m-9.993-6a2 2 0 1 0 4 0a2 2 0 1 0-4 0" />
    </Outline>
  );
}

export function BoltIcon(props: IconProps) {
  return (
    <Outline {...props}>
      <path d="M13 3v7h6l-8 11v-7H5z" />
    </Outline>
  );
}

export function PulseIcon(props: IconProps) {
  return (
    <Outline {...props}>
      <path d="M3 12h4l3 8l4-16l3 8h4" />
    </Outline>
  );
}

// --- Streak, recovery, day chooser ---------------------------------------------------------

export function FlameIcon(props: IconProps) {
  return (
    <Solid {...props}>
      <path d="M10 2c0-.88 1.056-1.331 1.692-.722c1.958 1.876 3.096 5.995 1.75 9.12l-.08.174l.012.003c.625.133 1.203-.43 2.303-2.173l.14-.224a1 1 0 0 1 1.582-.153C18.733 9.46 20 12.402 20 14.295C20 18.56 16.409 22 12 22s-8-3.44-8-7.706c0-2.252 1.022-4.716 2.632-6.301l.605-.589c.241-.236.434-.43.618-.624C9.285 5.268 10 3.856 10 2" />
    </Solid>
  );
}

export function SnowflakeIcon(props: IconProps) {
  return (
    <Outline {...props}>
      <path d="m10 4l2 1l2-1" />
      <path d="M12 2v6.5l3 1.72m2.928-3.952l.134 2.232l1.866 1.232" />
      <path d="m20.66 7l-5.629 3.25l.01 3.458m4.887.56L18.062 15.5l-.134 2.232" />
      <path d="m20.66 17l-5.629-3.25l-2.99 1.738M14 20l-2-1l-2 1" />
      <path d="M12 22v-6.5l-3-1.72m-2.928 3.952L5.938 15.5l-1.866-1.232" />
      <path d="m3.34 17l5.629-3.25l-.01-3.458m-4.887-.56L5.938 8.5l.134-2.232" />
      <path d="m3.34 7l5.629 3.25l2.99-1.738" />
    </Outline>
  );
}

// --- Theme toggle ---------------------------------------------------------------------------

export function SunIcon(props: IconProps) {
  return (
    <Outline {...props}>
      <path d="M8 12a4 4 0 1 0 8 0a4 4 0 1 0-8 0m-5 0h1m8-9v1m8 8h1m-9 8v1M5.6 5.6l.7.7m12.1-.7l-.7.7m0 11.4l.7.7m-12.1-.7l-.7.7" />
    </Outline>
  );
}

export function MoonIcon(props: IconProps) {
  return (
    <Outline {...props}>
      <path d="M12 3h.393a7.5 7.5 0 0 0 7.92 12.446A9 9 0 1 1 12 2.992z" />
    </Outline>
  );
}

export function CalendarIcon(props: IconProps) {
  return (
    <Outline {...props}>
      <path d="M4 7a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2zm12-4v4M8 3v4m-4 4h16m-9 4h1m0 0v3" />
    </Outline>
  );
}

export function ChevronLeftIcon(props: IconProps) {
  return (
    <Outline {...props}>
      <path d="m15 6l-6 6l6 6" />
    </Outline>
  );
}

export function ChevronRightIcon(props: IconProps) {
  return (
    <Outline {...props}>
      <path d="m9 6l6 6l-6 6" />
    </Outline>
  );
}

export function ChevronDownIcon(props: IconProps) {
  return (
    <Outline {...props}>
      <path d="m6 9l6 6l6-6" />
    </Outline>
  );
}

/** The icon for an activity's app_type; unknown types get the generic pulse. */
// The prop is `kind`, not `type`: SVG elements already have a `type` attribute.
export function ActivityIcon({ kind, ...props }: IconProps & { kind: string | null }) {
  switch (kind) {
    case "run":
      return <RunIcon {...props} />;
    case "walk":
      return <WalkIcon {...props} />;
    case "cycle":
      return <BikeIcon {...props} />;
    case "swim":
      return <SwimIcon {...props} />;
    case "strength":
      return <BarbellIcon {...props} />;
    case "yoga":
      return <YogaIcon {...props} />;
    case "hiit":
      return <BoltIcon {...props} />;
    default:
      return <PulseIcon {...props} />;
  }
}
