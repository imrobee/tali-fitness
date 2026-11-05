// @vitest-environment jsdom
// The dark/light toggle: switches the data-theme attribute, says what it will do next, and
// remembers the choice across a reload.

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import { THEME_STORAGE_KEY, loadTheme } from "../lib/theme";
import { ThemeToggle } from "./ThemeToggle";

beforeEach(() => {
  localStorage.clear();
  document.documentElement.setAttribute("data-theme", "dark");
});

afterEach(cleanup);

describe("ThemeToggle", () => {
  it("switches to light and back, and its name says what a press will do", () => {
    render(<ThemeToggle />);
    const root = document.documentElement;

    fireEvent.click(screen.getByRole("button", { name: "Switch to light mode" }));
    expect(root.getAttribute("data-theme")).toBe("light");

    fireEvent.click(screen.getByRole("button", { name: "Switch to dark mode" }));
    expect(root.getAttribute("data-theme")).toBe("dark");
  });

  it("saves the choice, and a reload starts from it", () => {
    render(<ThemeToggle />);
    fireEvent.click(screen.getByRole("button", { name: "Switch to light mode" }));
    expect(localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(loadTheme(localStorage)).toBe("light");

    // After a reload, theme-init.js has set the attribute; the toggle starts from it.
    cleanup();
    render(<ThemeToggle />);
    expect(screen.getByRole("button", { name: "Switch to dark mode" })).toBeTruthy();
  });

  it("is a native button, so Enter and Space work from the keyboard", () => {
    render(<ThemeToggle />);
    const button = screen.getByRole("button", { name: "Switch to light mode" });
    expect(button.tagName).toBe("BUTTON");
    expect(button.getAttribute("type")).toBe("button");
  });
});
