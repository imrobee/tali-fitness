import { useState } from "react";
import { MoonIcon, SunIcon } from "../icons";
import {
  applyTheme,
  currentTheme,
  otherTheme,
  saveTheme,
  toggleLabel,
  type Theme,
} from "../lib/theme";
import styles from "./ThemeToggle.module.css";

// How long the colours ease after a switch (index.css .theme-switching); a little longer
// than the 150ms transition so it finishes before the class comes off.
const SWITCH_MS = 200;

/** Sun in dark mode, moon in light: the icon shows the theme a press switches to. */
export function ThemeToggle() {
  // The page already has a theme (theme-init.js ran before React); start from it.
  const [theme, setTheme] = useState<Theme>(() => currentTheme(document.documentElement));

  function onClick() {
    const next = otherTheme(theme);
    const root = document.documentElement;
    // Colours ease only during a switch, so first paint and normal use never animate.
    root.classList.add("theme-switching");
    window.setTimeout(() => root.classList.remove("theme-switching"), SWITCH_MS);
    applyTheme(document, next);
    saveTheme(window.localStorage, next);
    setTheme(next);
  }

  return (
    <button type="button" className={styles.toggle} aria-label={toggleLabel(theme)} onClick={onClick}>
      {theme === "dark" ? <SunIcon /> : <MoonIcon />}
    </button>
  );
}
