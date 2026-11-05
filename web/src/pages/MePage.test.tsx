// @vitest-environment jsdom
// The Me page's kg / lb switch, with the API faked at fetch().

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { MePage } from "./MePage";

const ME = {
  nickname: "Rob",
  timezone: "Asia/Manila",
  targets: { calorie_budget: 1853, protein_goal: 130, effective_from: "2026-10-01" },
  weight_goal_kg: 72.575, // 160 lb as the database stores it
  weight_unit: "kg",
  lenient_weekends: false,
  vacation: null,
  last_vacation: { from: "2026-10-05", to: "2026-10-07" },
  earliest_date: "2026-10-01",
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function fakeApi() {
  const puts: unknown[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      if (url === "/api/v1/vacation" && init?.method === "PUT") {
        const body = JSON.parse(String(init.body));
        puts.push({ vacation: body });
        return new Response(JSON.stringify({ ...ME, vacation: body }), { status: 200 });
      }
      if (url === "/api/v1/me" && init?.method === "PUT") {
        const body = JSON.parse(String(init.body));
        puts.push(body);
        return new Response(JSON.stringify({ ...ME, ...body }), { status: 200 });
      }
      if (url === "/api/v1/me") return new Response(JSON.stringify(ME), { status: 200 });
      return new Promise(() => {}); // pipeline health: still loading
    }),
  );
  return puts;
}

describe("Me page weight unit", () => {
  it("converts the goal on screen and saves the preference when switched to lb", async () => {
    const puts = fakeApi();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <MePage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    const goal = (await screen.findByLabelText(/Weight goal/)) as HTMLInputElement;
    expect(goal.value).toBe("72.6");

    fireEvent.click(screen.getByRole("button", { name: "lb" }));

    expect(goal.value).toBe("160");
    await waitFor(() => expect(puts).toEqual([{ weight_unit: "lb" }]));
  });

  it("does not save an untouched goal again, even though the field is rounded", async () => {
    const puts = fakeApi();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter>
          <MePage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    await screen.findByLabelText(/Weight goal/);
    fireEvent.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(puts).toHaveLength(1));
    expect(puts[0]).toEqual({ nickname: "Rob" });
  });
});

function renderMe() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <MePage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("Me page streak settings", () => {
  it("explains the streak and saves relaxed weekends at once", async () => {
    const puts = fakeApi();
    renderMe();

    // The rule sits in the Weekends card, under the switch, not in the rules list.
    const rule = await screen.findByText("Weekends follow the same rules as weekdays.");
    expect(rule.closest("li")).toBeNull();
    expect(screen.getByRole("heading", { name: "Weekends" })).toBeTruthy();
    fireEvent.click(screen.getByRole("group", { name: "Weekends" }).querySelectorAll("button")[1]);

    await waitFor(() => expect(puts).toEqual([{ lenient_weekends: true }]));
  });

  it("saves a vacation from its From and To dates, and shows the last one", async () => {
    const puts = fakeApi();
    renderMe();

    expect(await screen.findByText("Last break: Oct 5 – Oct 7")).toBeTruthy();
    expect(screen.queryByLabelText("From")).toBeNull(); // closed until "Log break"
    fireEvent.click(screen.getByRole("button", { name: "Log break" }));
    expect(screen.getAllByText("Choose date")).toHaveLength(2);
    fireEvent.change(screen.getByLabelText("From"), { target: { value: "2026-11-02" } });
    fireEvent.change(screen.getByLabelText("To"), { target: { value: "2026-11-06" } });
    fireEvent.click(screen.getByRole("button", { name: "Save break" }));

    expect(screen.getByText("Mon, Nov 2")).toBeTruthy();
    await waitFor(() => expect(puts).toEqual([{ vacation: { from: "2026-11-02", to: "2026-11-06" } }]));
  });

  it("asks for both dates before saving", async () => {
    const puts = fakeApi();
    renderMe();

    fireEvent.click(await screen.findByRole("button", { name: "Log break" }));
    fireEvent.click(screen.getByRole("button", { name: "Save break" }));

    expect(screen.getByText("Pick both dates.")).toBeTruthy();
    expect(puts).toEqual([]);
  });
});
