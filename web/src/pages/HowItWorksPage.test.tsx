// @vitest-environment jsdom
// How it works: open to anyone, and it never waits for (or calls) the API.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../App";
import { AUTH_QUERY } from "../api/auth";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function renderAt(path: string, client = new QueryClient()) {
  // The server is unreachable: the page must not need it.
  const fetch = vi.fn(async () => Promise.reject(new TypeError("Failed to fetch")));
  vi.stubGlobal("fetch", fetch);
  render(
    <QueryClientProvider client={client}>
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
    expect(screen.getByText(/three apps collect the data/)).toBeTruthy();
    expect(fetch).not.toHaveBeenCalled();
  });

  it("draws the three stages in order, with a caption", () => {
    renderAt("/how-it-works");

    const stages = screen.getAllByRole("listitem").slice(0, 3).map((item) => item.textContent);
    expect(stages[0]).toMatch(/^1My apps/);
    expect(stages[1]).toMatch(/^2The pipeline/);
    expect(stages[2]).toMatch(/^3Tali Fitness/);
    expect(screen.getByText(/Data moves one way/)).toBeTruthy();
  });

  it("has the six sections, in plain prose", () => {
    renderAt("/how-it-works");

    const headings = screen.getAllByRole("heading", { level: 2 }).map((heading) => heading.textContent);
    expect(headings).toEqual([
      "Where the data comes from",
      "What happens to the data",
      "How the rules work",
      "Keeping an eye on it",
      "What it's built with",
      "The demo",
      "Check out my profile",
    ]);
    expect(document.querySelector("code")).toBeNull(); // no code badges
  });

  it("without the demo's numbers, describes the checks without a count", () => {
    renderAt("/how-it-works");

    expect(screen.getByText(/Every hour, a set of automatic checks looks for problems/)).toBeTruthy();
    expect(screen.queryByText(/\{n_checks\}/)).toBeNull();
  });

  it("on a demo visit, quotes the number of checks from the demo's last rebuild", () => {
    const client = new QueryClient();
    client.setQueryData(AUTH_QUERY, { signedIn: true, demo: true, story: { n_checks: 15 } });
    renderAt("/how-it-works", client);

    expect(screen.getByText(/Every hour, 15 checks look for problems/)).toBeTruthy();
  });

  it("links to GitHub and LinkedIn, and back to the app", () => {
    renderAt("/how-it-works");

    const href = (name: string) => screen.getByRole("link", { name }).getAttribute("href");
    expect(href("GitHub")).toBe("https://github.com/imrobee/fitness-tracker");
    expect(href("LinkedIn")).toBe("https://www.linkedin.com/in/robeefeliciano");
    expect(href("Back to the app")).toBe("/");
    expect(screen.queryByRole("link", { name: "README" })).toBeNull();
  });
});
