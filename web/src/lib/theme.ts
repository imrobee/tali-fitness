// Dark or light theme (UI_SPEC.md section 7). The theme is a data-theme attribute on <html>;
// every colour comes from the tokens in theme/tokens.css, so switching is one attribute.
// public/theme-init.js applies the saved choice before first paint with the same key and
// colours; keep the two in step.

export type Theme = "dark" | "light";

export const THEME_STORAGE_KEY = "fitness-tracker.theme";

/** The browser's top bar (theme-color) follows the page background of each theme. */
export const THEME_COLOR: Record<Theme, string> = { dark: "#000000", light: "#f5f7f6" };

/** Dark unless "light" was saved. A missing or unreadable value means dark. */
export function parseTheme(saved: string | null): Theme {
  return saved === "light" ? "light" : "dark";
}

export function otherTheme(theme: Theme): Theme {
  return theme === "dark" ? "light" : "dark";
}

/** The toggle's accessible name says what pressing it does. */
export function toggleLabel(theme: Theme): string {
  return theme === "dark" ? "Switch to light mode" : "Switch to dark mode";
}

/** The saved theme. Storage can throw (Safari private mode, blocked site data). */
export function loadTheme(storage: Storage): Theme {
  try {
    return parseTheme(storage.getItem(THEME_STORAGE_KEY));
  } catch {
    return "dark";
  }
}

export function saveTheme(storage: Storage, theme: Theme): void {
  try {
    storage.setItem(THEME_STORAGE_KEY, theme);
  } catch {
    // Not saved: the theme still applies until the page is reloaded.
  }
}

/** The theme on the page now, as theme-init.js (or the last toggle) left it. */
export function currentTheme(root: HTMLElement): Theme {
  return parseTheme(root.getAttribute("data-theme"));
}

export function applyTheme(doc: Document, theme: Theme): void {
  doc.documentElement.setAttribute("data-theme", theme);
  doc.querySelector('meta[name="theme-color"]')?.setAttribute("content", THEME_COLOR[theme]);
}
