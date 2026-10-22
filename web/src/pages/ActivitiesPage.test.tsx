// @vitest-environment jsdom
// The Activities page as a whole, with the API faked at fetch().

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ActivitiesPage } from "./ActivitiesPage";

const SATURDAY = {
  from: "2026-10-17",
  to: "2026-10-17",
  days: [
    {
      date: "2026-10-17",
      activities: [
        {
          id: 1, type: "run", title: "Afternoon Run", started_at: "2026-10-17T13:05:00+08:00",
          duration_s: 1920, moving_s: 1920, distance_m: 5647, parse_status: "not_applicable",
          exercise_count: 0, set_count: 0, volume_kg: 0,
        },
      ],
    },
  ],
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

/** A fake API: `/dashboard` answers only when `releaseDashboard` is called. */
function fakeApi() {
  let releaseDashboard = () => {};
  const dashboard = new Promise<void>((resolve) => (releaseDashboard = resolve));
  const json = (body: unknown) => new Response(JSON.stringify(body), { status: 200 });
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string) => {
      if (url.startsWith("/api/v1/dashboard")) {
        await dashboard;
        return json({ today: "2026-10-17" });
      }
      if (url.startsWith("/api/v1/activities")) return json(SATURDAY);
      return new Promise(() => {}); // calendar and trends: still loading
    }),
  );
  return () => releaseDashboard();
}

describe("Activities page", () => {
  it("waits for the server's today before listing a picked day", async () => {
    const release = fakeApi();
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={["/activities?date=2026-10-17"]}>
          <ActivitiesPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    // The day's activities arrive first; nothing may crash or show a wrong chip.
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(screen.queryByText("Afternoon Run")).toBeNull();

    release();
    expect(await screen.findByText("Afternoon Run")).toBeTruthy();
    expect(screen.getByText("Today")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Show all days" })).toBeTruthy();
  });
});
