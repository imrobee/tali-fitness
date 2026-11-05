// @vitest-environment jsdom
// The demo tour: when it starts, how it moves, and how it lets go of the page.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AUTH_QUERY } from "../api/auth";
import { useTour } from "./context";
import { STEPS } from "./steps";
import { TourProvider } from "./TourProvider";

const STORY = {
  streak_days: 10,
  eaten: 1068,
  budget: 1850,
  n_checks: 15,
  n_warnings: 2,
  n_quarantined: 3,
  lift_day: "2026-10-15",
};

beforeEach(() => {
  // jsdom has no layout: these browser features are stand-ins.
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
    },
  );
  Element.prototype.scrollIntoView = vi.fn();
  window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
  sessionStorage.clear();
});

/** A session row like ActivityItem's: closed until clicked. */
function Session() {
  const [open, setOpen] = useState(false);
  return (
    <section data-tour="strength-session">
      <button type="button" aria-expanded={open} onClick={() => setOpen(true)}>
        Lower Body
      </button>
      {open && <div data-tour-part="exercise">Leg Press 125 kg × 10</div>}
    </section>
  );
}

/** A page per route, holding the cards the steps point at. */
function Pages() {
  const location = useLocation();
  const { start } = useTour();
  const names = STEPS.filter((step) => (step.route ?? "").split("?")[0] === location.pathname).flatMap((step) =>
    [...step.targets, step.within ?? ""].flatMap((selector) =>
      [...selector.matchAll(/data-tour='([a-z-]+)'/g)].map((m) => m[1]),
    ),
  );
  const cards = [...new Set(names)];
  return (
    <>
      <p>Page {location.pathname + location.search}</p>
      <button type="button" onClick={() => start()}>
        Take the tour
      </button>
      {cards.map((name) =>
        name === "strength-session" ? (
          <Session key={name} />
        ) : (
          <section key={name} data-tour={name}>
            {name} card
          </section>
        ),
      )}
    </>
  );
}

function renderTour({ demo = true }: { demo?: boolean } = {}) {
  const client = new QueryClient();
  client.setQueryData(AUTH_QUERY, { signedIn: true, demo, story: STORY });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/"]}>
        <TourProvider>
          <Routes>
            <Route path="*" element={<Pages />} />
          </Routes>
        </TourProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

async function dialog() {
  return screen.findByRole("dialog");
}

async function next(times = 1) {
  for (let step = 0; step < times; step += 1) {
    fireEvent.click(await screen.findByRole("button", { name: "Next" }));
  }
}

describe("the demo tour", () => {
  it("starts by itself on a first demo visit, as a welcome with two ways on", async () => {
    renderTour();

    expect((await dialog()).getAttribute("aria-modal")).toBe("true");
    expect(screen.getByText("1 of 7")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Welcome to Tali Fitness!" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Show me around" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Skip" })).toBeTruthy();
  });

  it("does not start by itself a second time, or on Rob's own app", async () => {
    localStorage.setItem("tali.tour-seen", "1");
    renderTour();
    await screen.findByText("Page /");
    expect(screen.queryByRole("dialog")).toBeNull();

    cleanup();
    localStorage.clear();
    renderTour({ demo: false });
    await screen.findByText("Page /");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("quotes the demo's own numbers and announces each step", async () => {
    renderTour();
    fireEvent.click(await screen.findByRole("button", { name: "Show me around" }));

    expect(await screen.findByText(/The demo user is on a 10-day streak right now/)).toBeTruthy();
    expect(screen.getByText("Step 2 of 7: The streak")).toBeTruthy();
    await next();
    expect(await screen.findByText(/So far today, 1,068 of the 1,850 calorie budget/)).toBeTruthy();
  });

  it("moves with the arrow keys", async () => {
    renderTour();
    fireEvent.keyDown(await dialog(), { key: "ArrowRight" });
    expect(await screen.findByText("2 of 7")).toBeTruthy();

    fireEvent.keyDown(await dialog(), { key: "ArrowLeft" });
    expect(await screen.findByText("1 of 7")).toBeTruthy();
  });

  it("opens the gym session before pointing at it", async () => {
    renderTour();
    fireEvent.click(await screen.findByRole("button", { name: "Show me around" }));
    await next(3);

    expect(await screen.findByText("Page /activities?date=2026-10-15")).toBeTruthy();
    expect(await screen.findByText("Leg Press 125 kg × 10")).toBeTruthy();
    expect(await screen.findByText("5 of 7")).toBeTruthy();
  });

  it("shows the engineering only with Technical details on, and remembers the switch", async () => {
    renderTour();
    await dialog();
    expect(screen.queryByRole("switch")).toBeNull(); // not on the welcome
    fireEvent.click(screen.getByRole("button", { name: "Show me around" }));

    expect(await screen.findByText(/The demo user is on/)).toBeTruthy();
    expect(screen.queryByText(/One SQL function labels every day/)).toBeNull();
    expect(screen.queryByRole("button", { name: /Under the hood/ })).toBeNull();
    fireEvent.click(await screen.findByRole("switch", { name: "Technical details" }));
    expect(screen.getByText(/One SQL function labels every day/)).toBeTruthy();

    await next();
    expect(await screen.findByText(/a secret token/)).toBeTruthy();
    expect(sessionStorage.getItem("tali.tour-details")).toBe("1");
  });

  it("starts with Technical details on when it was on earlier in the session", async () => {
    sessionStorage.setItem("tali.tour-details", "1");
    renderTour();
    fireEvent.click(await screen.findByRole("button", { name: "Show me around" }));

    expect(await screen.findByText(/One SQL function labels every day/)).toBeTruthy();
    expect((await screen.findByRole("switch", { name: "Technical details" })).getAttribute("aria-checked")).toBe("true");
  });

  it("has no switch on the last step", async () => {
    renderTour();
    fireEvent.click(await screen.findByRole("button", { name: "Show me around" }));
    await next(STEPS.length - 2);

    expect(await screen.findByText("That's the tour")).toBeTruthy();
    expect(screen.queryByRole("switch")).toBeNull();
  });

  it("closes with Escape and gives focus back to the Tour button", async () => {
    localStorage.setItem("tali.tour-seen", "1");
    renderTour();
    const button = await screen.findByRole("button", { name: "Take the tour" });
    button.focus();
    fireEvent.click(button);

    fireEvent.keyDown(await dialog(), { key: "Escape" });

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(button);
  });

  it("ends with Explore the demo, or How it works", async () => {
    renderTour();
    fireEvent.click(await screen.findByRole("button", { name: "Show me around" }));
    await next(STEPS.length - 2);

    expect(screen.getAllByRole("button").filter((b) => /Explore|How it works/.test(b.textContent ?? ""))).toHaveLength(2);
    await act(async () => {
      fireEvent.click(await screen.findByRole("button", { name: "How it works" }));
    });
    expect(await screen.findByText("Page /how-it-works")).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("keeps Tab inside the dialog", async () => {
    renderTour();
    const tour = await dialog();
    screen.getByRole("button", { name: "Show me around" }).focus();

    fireEvent.keyDown(tour, { key: "Tab" });

    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Skip" }));
  });
});
