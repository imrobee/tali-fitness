// @vitest-environment jsdom
// Sync now, with the API faked at fetch().

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SyncNowButton } from "./SyncNow";

const RUN = "manual__2026-10-22T12:00:00+00:00";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function fakeApi({ post, state }: { post: () => Response; state: () => string | null }) {
  const calls: string[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push(`${init?.method ?? "GET"} ${url}`);
      if (url === "/api/v1/sync/strava" && init?.method === "POST") return post();
      if (url === "/api/v1/sync/strava") {
        const s = state();
        return new Response(
          JSON.stringify({ requested_at: s ? "2026-10-22T20:00:00+08:00" : null, dag_run_id: s ? RUN : null, state: s }),
          { status: 200 },
        );
      }
      return new Response("{}", { status: 200 });
    }),
  );
  return calls;
}

function renderButton() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <SyncNowButton />
    </QueryClientProvider>,
  );
}

describe("Sync now", () => {
  it("starts a run and says when it is done", async () => {
    let state: string | null = null;
    fakeApi({
      post: () => {
        state = "success";
        return new Response(JSON.stringify({ requested_at: "x", dag_run_id: RUN, state: "queued" }), { status: 202 });
      },
      state: () => state,
    });
    renderButton();

    fireEvent.click(await screen.findByRole("button", { name: "Sync now" }));

    expect(await screen.findByText("Synced. New activities are in.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Sync now" })).toBeTruthy();
  });

  it("shows the server's reason when it is too soon", async () => {
    fakeApi({
      post: () =>
        new Response(
          JSON.stringify({ error: { code: "sync_cooldown", message: "Synced a moment ago. Try again in 90 s." } }),
          { status: 429 },
        ),
      state: () => null,
    });
    renderButton();

    fireEvent.click(await screen.findByRole("button", { name: "Sync now" }));

    expect(await screen.findByText("Synced a moment ago. Try again in 90 s.")).toBeTruthy();
  });

  it("does not claim a run it did not start", async () => {
    fakeApi({ post: () => new Response("{}", { status: 500 }), state: () => "success" });
    renderButton();

    await screen.findByRole("button", { name: "Sync now" });

    expect(screen.queryByText(/Synced\./)).toBeNull();
  });
});
