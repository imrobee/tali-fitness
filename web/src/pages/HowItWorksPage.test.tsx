// @vitest-environment jsdom
// How it works: open to anyone, and it never waits for (or calls) the API.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderAt(path: string) {
  // The server is unreachable: the page must not need it.
  const fetch = vi.fn(async () => Promise.reject(new TypeError("Failed to fetch")));
  vi.stubGlobal("fetch", fetch);
  render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter initialEntries={[path]}>
        <App />
      </MemoryRouter>
    </QueryClientProvider>,
  );
  return fetch;
}

describe("How it works", () => {
  it("shows at once, signed out and with the server down, and asks it nothing", async () => {
    const fetch = renderAt("/how-it-works");

    expect(await screen.findByRole("heading", { level: 1, name: "How it works" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "How the data flows" })).toBeTruthy();
    expect(screen.getByText("strava_sync")).toBeTruthy();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("describes its diagram in words for screen readers", () => {
    renderAt("/how-it-works");

    expect(screen.getByText(/Three sources feed one PostgreSQL warehouse/)).toBeTruthy();
  });

  it("links to the code, the README and LinkedIn", () => {
    renderAt("/how-it-works");

    const href = (name: string) => screen.getByRole("link", { name }).getAttribute("href");
    expect(href("Code on GitHub")).toBe("https://github.com/imrobee/fitness-tracker");
    expect(href("README")).toBe("https://github.com/imrobee/fitness-tracker#readme");
    expect(href("Rob Feliciano on LinkedIn")).toBe("https://www.linkedin.com/in/robeefeliciano");
  });
});
