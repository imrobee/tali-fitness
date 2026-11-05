// @vitest-environment jsdom
// The demo tour: when it starts, how it moves, and how it lets go of the page.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AUTH_QUERY } from "../api/auth";
import { useTour } from "./context";
import { STEPS } from "./steps";
import { TourProvider } from "./TourProvider";

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
});

/** A page per route, holding the cards the steps point at. */
function Pages() {
  const location = useLocation();
  const { start } = useTour();
  const cards = STEPS.filter((step) => step.route === location.pathname && step.target);
  return (
    <>
      <p>Page {location.pathname}</p>
      <button type="button" onClick={start}>
        Take the tour
      </button>
      {cards.map((step) => (
        <section key={step.id} data-tour={step.target ?? undefined}>
          {step.id} card
        </section>
      ))}
    </>
  );
}

function renderTour({ demo = true }: { demo?: boolean } = {}) {
  const client = new QueryClient();
  client.setQueryData(AUTH_QUERY, { signedIn: true, demo });
  client.setQueryData(["dashboard", "today"], { streak: { count: 12 } });
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

describe("the demo tour", () => {
  it("starts by itself on a first demo visit, with a counter and a way out", async () => {
    renderTour();

    const tour = await dialog();
    expect(tour.getAttribute("aria-modal")).toBe("true");
    expect(screen.getByText("1 of 7")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "One app, three sources" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Skip tour" })).toBeTruthy();
  });

  it("does not start by itself a second time", async () => {
    localStorage.setItem("tali.tour-seen", "1");
    renderTour();

    await screen.findByText("Page /");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("never starts on Rob's own app", async () => {
    renderTour({ demo: false });

    await screen.findByText("Page /");
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("moves with the arrow keys and quotes the streak on screen", async () => {
    renderTour();
    fireEvent.keyDown(await dialog(), { key: "ArrowRight" });

    expect(await screen.findByRole("heading", { name: "A 12-day streak" })).toBeTruthy();
    expect(screen.getByText("2 of 7")).toBeTruthy();

    fireEvent.keyDown(await dialog(), { key: "ArrowLeft" });
    expect(await screen.findByText("1 of 7")).toBeTruthy();
  });

  it("opens each step's page and names its sources", async () => {
    renderTour();
    for (let step = 0; step < 3; step += 1) {
      fireEvent.click(await screen.findByRole("button", { name: "Next" }));
    }

    expect(await screen.findByText("Page /activities")).toBeTruthy();
    const sources = await screen.findByRole("list", { name: "Where this comes from" });
    expect(screen.getByText("4 of 7")).toBeTruthy();
    expect(sources.textContent).toContain("strava_sync");
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

  it("ends with Explore freely, which keeps the demo open", async () => {
    renderTour();
    for (let step = 0; step < STEPS.length - 1; step += 1) {
      fireEvent.click(await screen.findByRole("button", { name: "Next" }));
    }
    await act(async () => {
      fireEvent.click(await screen.findByRole("button", { name: "Explore freely" }));
    });

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(await screen.findByText(/^Page \//)).toBeTruthy();
  });

  it("ends with a way to How it works", async () => {
    renderTour();
    for (let step = 0; step < STEPS.length - 1; step += 1) {
      fireEvent.click(await screen.findByRole("button", { name: "Next" }));
    }
    fireEvent.click(await screen.findByRole("button", { name: "How it works" }));

    expect(await screen.findByText("Page /how-it-works")).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("keeps Tab inside the dialog", async () => {
    renderTour();
    const tour = await dialog();
    const next = screen.getByRole("button", { name: "Next" });
    next.focus();

    fireEvent.keyDown(tour, { key: "Tab" });

    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Skip tour" }));
  });
});
