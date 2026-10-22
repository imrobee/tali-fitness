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
