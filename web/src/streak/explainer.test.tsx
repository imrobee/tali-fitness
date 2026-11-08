// @vitest-environment jsdom
// The streak explainer: the "?" on the streak card opens it in the tour's sheet, and the Me
// page shows the same words from the same file (DECISIONS D129).

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { AUTH_QUERY } from "../api/auth";
import { StreakRulesCard } from "../components/StreakSettings";
import { useTour } from "../tour/context";
import { TourProvider } from "../tour/TourProvider";

beforeEach(() => {
  vi.stubGlobal(
    "ResizeObserver",
    class {
      observe() {}
      disconnect() {}
    },
  );
  window.scrollTo = vi.fn() as unknown as typeof window.scrollTo;
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

/** The dashboard's streak card, reduced to what the explainer needs. */
function StreakCardStub() {
  const { start } = useTour();
  return (
    <section data-tour="streak">
      <button type="button" aria-label="How streaks work" onClick={() => start("streak")}>
        ?
      </button>
    </section>
  );
}

function renderWith(children: React.ReactNode, demo = false) {
  const client = new QueryClient();
  client.setQueryData(AUTH_QUERY, { signedIn: true, demo, story: null });
  localStorage.setItem("tali.tour-seen", "1"); // the demo tour must not start by itself
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <TourProvider>{children}</TourProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** Every step's title and words, walking the sheet with Next. */
async function walkTheSheet(): Promise<string[]> {
  fireEvent.click(screen.getByRole("button", { name: "How streaks work" }));
  const seen: string[] = [];
  for (let step = 0; step < 6; step += 1) {
    const dialog = await screen.findByRole("dialog");
    seen.push(`${within(dialog).getByRole("heading").textContent} ${dialog.querySelector("#tour-text")?.textContent}`);
    if (step < 5) fireEvent.click(within(dialog).getByRole("button", { name: "Next" }));
  }
  return seen;
}

describe("the streak explainer", () => {
  it("says the same as the Me page's card, item for item", async () => {
    renderWith(<StreakCardStub />);
    const sheet = await walkTheSheet();
    cleanup();

    renderWith(<StreakRulesCard />);
    fireEvent.click(screen.getByRole("button", { name: "How your streak works" }));
    const card = screen
      .getAllByRole("listitem")
      .map((item) => `${within(item).getByRole("heading").textContent} ${item.querySelector("p")?.textContent}`);

    expect(sheet).toHaveLength(6);
    expect(card).toEqual(sheet);
  });

  it("opens from the ? only, with Close, no Technical details, and Got it at the end", async () => {
    renderWith(<StreakCardStub />);
    expect(screen.queryByRole("dialog")).toBeNull(); // never opens by itself

    fireEvent.click(screen.getByRole("button", { name: "How streaks work" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("How your streak works · 1 of 6")).toBeTruthy();
    expect(within(dialog).getByRole("button", { name: "Close" })).toBeTruthy();
    expect(within(dialog).queryByRole("switch")).toBeNull();
    expect(screen.getByText("Step 1 of 6: A full day")).toBeTruthy(); // announced

    for (let step = 0; step < 5; step += 1) fireEvent.click(await screen.findByRole("button", { name: "Next" }));
    expect(await screen.findByRole("button", { name: "Got it" })).toBeTruthy();
    expect(screen.getByText(/past days keep the budget they had/)).toBeTruthy();
  });

  it("closes with Got it and gives focus back to the ?", async () => {
    renderWith(<StreakCardStub />);
    const help = screen.getByRole("button", { name: "How streaks work" });
    help.focus();
    fireEvent.click(help);
    for (let step = 0; step < 5; step += 1) fireEvent.click(await screen.findByRole("button", { name: "Next" }));

    fireEvent.click(await screen.findByRole("button", { name: "Got it" }));

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(help);
  });

  it("on Me, starts closed and opens and closes from its header, like an activity row", () => {
    renderWith(<StreakRulesCard />);
    const header = screen.getByRole("button", { name: "How your streak works" });
    expect(header.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);

    fireEvent.click(header);
    expect(header.getAttribute("aria-expanded")).toBe("true");
    expect(document.getElementById(header.getAttribute("aria-controls")!)).not.toBeNull();
    expect(screen.getAllByRole("listitem")).toHaveLength(6);
    expect(screen.getByRole("region", { name: "How your streak works" })).toBeTruthy();

    fireEvent.click(header);
    expect(screen.queryAllByRole("listitem")).toHaveLength(0);
  });

  it("in the demo, says a changed budget applies to every day", async () => {
    renderWith(<StreakRulesCard />, true);
    fireEvent.click(screen.getByRole("button", { name: "How your streak works" }));

    expect(screen.getByText("In this demo, a budget you change applies to every day.")).toBeTruthy();
  });
});
