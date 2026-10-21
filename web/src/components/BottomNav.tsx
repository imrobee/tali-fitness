import type { ComponentType, SVGProps } from "react";
import { NavLink, useSearchParams } from "react-router";
import { AppleIcon, DashboardIcon, PersonCircleIcon, RunIcon } from "../icons";
import styles from "./BottomNav.module.css";

type TabIcon = ComponentType<SVGProps<SVGSVGElement> & { filled?: boolean }>;

const TABS: { to: string; label: string; Icon: TabIcon }[] = [
  { to: "/", label: "Dashboard", Icon: DashboardIcon },
  { to: "/activities", label: "Activities", Icon: RunIcon },
  { to: "/nutrition", label: "Nutrition", Icon: AppleIcon },
  { to: "/me", label: "Me", Icon: PersonCircleIcon },
];

export function BottomNav() {
  // Tab switches keep the selected day (?date=), so every page shows the same day.
  const [params] = useSearchParams();
  const date = params.get("date");
  const search = date ? `?date=${date}` : "";

  return (
    <nav className={styles.nav} aria-label="Primary">
      <ul className={styles.list}>
        {TABS.map(({ to, label, Icon }) => (
          <li key={to}>
            {/* NavLink sets aria-current="page" on the active tab by itself. */}
            <NavLink
              to={{ pathname: to, search }}
              end={to === "/"}
              className={({ isActive }) => `${styles.link} ${isActive ? styles.active : ""}`}
            >
              {({ isActive }) => (
                <>
                  <Icon className={styles.icon} filled={isActive} />
                  {label}
                </>
              )}
            </NavLink>
          </li>
        ))}
      </ul>
    </nav>
  );
}
