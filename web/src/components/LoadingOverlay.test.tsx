// @vitest-environment jsdom
// The loading overlay: shown while a query has nothing to show yet, after a short wait;
// never for a refetch of data already on screen.

import { QueryClient, QueryClientProvider, useQuery } from "@tanstack/react-query";
import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { LoadingOverlay } from "./LoadingOverlay";

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

function Loader({ queryFn }: { queryFn: () => Promise<string> }) {
  useQuery({ queryKey: ["thing"], queryFn });
  return null;
}

function setup(client: QueryClient, queryFn: () => Promise<string>) {
  render(
    <QueryClientProvider client={client}>
      <Loader queryFn={queryFn} />
      <LoadingOverlay delayMs={300} />
    </QueryClientProvider>,
  );
}

describe("LoadingOverlay", () => {
  it("appears after the wait while the first load is out, and goes when it lands", async () => {
    vi.useFakeTimers();
    let answer: (value: string) => void = () => {};
    setup(new QueryClient(), () => new Promise((resolve) => (answer = resolve)));

    expect(screen.queryByRole("status")).toBeNull(); // not before the wait
    await act(() => vi.advanceTimersByTimeAsync(300));
    expect(screen.getByRole("status").textContent).toBe("Loading");

    answer("done");
    await act(() => vi.advanceTimersByTimeAsync(10)); // React Query passes results on by a timer
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("never shows for a quick answer", async () => {
    vi.useFakeTimers();
    setup(new QueryClient(), () => Promise.resolve("done"));

    await act(() => vi.advanceTimersByTimeAsync(1000));
    expect(screen.queryByRole("status")).toBeNull();
  });

  it("stays away while data already on screen is refetched", async () => {
    vi.useFakeTimers();
    const client = new QueryClient();
    client.setQueryData(["thing"], "cached");
    setup(client, () => new Promise(() => {}));
    void client.refetchQueries({ queryKey: ["thing"] });

    await act(() => vi.advanceTimersByTimeAsync(1000));
    expect(screen.queryByRole("status")).toBeNull();
  });
});
