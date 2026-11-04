// @vitest-environment jsdom
// The sign-in gate (docs/AUTH_SPEC.md section 9), with the server faked at fetch().

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { googleSignInUrl } from "../api/auth";
import { AccountCard } from "./AccountCard";
import { SignInGate } from "./SignInGate";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  localStorage.clear();
});

/** A fake server: signed in or not, which method, and whether the dev key is right. */
function fakeServer({ signedIn, method = "google" }: { signedIn: boolean; method?: string }) {
  const calls: { url: string; init?: RequestInit }[] = [];
  let session = signedIn;
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      calls.push({ url, init });
      if (url === "/auth/me") return new Response("{}", { status: session ? 200 : 401 });
      if (url === "/auth/method") return new Response(JSON.stringify({ method }), { status: 200 });
      if (url === "/auth/logout") {
        session = false;
        return new Response(null, { status: 204 });
      }
      if (url === "/auth/dev-login") {
        const { key } = JSON.parse(String(init?.body));
        session = key === "canary-right-key";
        return new Response(null, { status: session ? 204 : 401 });
      }
      return new Response("{}", { status: 404 });
    }),
  );
  return calls;
}

function renderGate(path = "/") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>
        <SignInGate>
          <p>The app</p>
          <AccountCard />
        </SignInGate>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("SignInGate", () => {
  it("shows the app when the session is valid", async () => {
    fakeServer({ signedIn: true });
    renderGate();

    expect(await screen.findByText("The app")).toBeTruthy();
  });

  it("removes the old API key from this browser on load", async () => {
    localStorage.setItem("fitness-tracker.api-key", "canary-old-key");
    fakeServer({ signedIn: true });
    renderGate();

    await screen.findByText("The app");
    expect(localStorage.getItem("fitness-tracker.api-key")).toBeNull();
  });

  it("offers Google sign-in as a plain link that returns to the same page", async () => {
    fakeServer({ signedIn: false });
    renderGate("/nutrition?date=2026-10-19");

    const link = await screen.findByRole("link", { name: "Sign in with Google" });
    expect(link.getAttribute("href")).toBe("/auth/login?next=%2Fnutrition%3Fdate%3D2026-10-19");
    expect(screen.queryByText("The app")).toBeNull();
  });

  it("in local key mode, signs in with the dev key and keeps it nowhere", async () => {
    const calls = fakeServer({ signedIn: false, method: "key" });
    renderGate();

    const input = await screen.findByLabelText("Dev key");
    fireEvent.change(input, { target: { value: "canary-wrong-key" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByRole("alert")).toBeTruthy();

    fireEvent.change(input, { target: { value: "canary-right-key" } });
    fireEvent.click(screen.getByRole("button", { name: "Sign in" }));
    expect(await screen.findByText("The app")).toBeTruthy();

    const login = calls.find((call) => call.url === "/auth/dev-login");
    expect(login?.init?.method).toBe("POST");
    expect(login?.init?.credentials).toBe("same-origin");
    expect(JSON.stringify(localStorage)).not.toContain("canary");
    expect(JSON.stringify(sessionStorage)).not.toContain("canary");
  });

  it("goes back to sign-in when any request gets a 401", async () => {
    fakeServer({ signedIn: true });
    renderGate();
    await screen.findByText("The app");

    vi.unstubAllGlobals();
    fakeServer({ signedIn: false });
    window.dispatchEvent(new Event("api:unauthorized"));

    expect(await screen.findByRole("link", { name: "Sign in with Google" })).toBeTruthy();
    expect(screen.queryByText("The app")).toBeNull();
  });

  it("signs out from Me: the session ends and the sign-in screen comes back", async () => {
    const calls = fakeServer({ signedIn: true });
    renderGate();

    fireEvent.click(await screen.findByRole("button", { name: "Sign out" }));

    expect(await screen.findByRole("link", { name: "Sign in with Google" })).toBeTruthy();
    expect(screen.queryByText("The app")).toBeNull();
    const logout = calls.find((call) => call.url === "/auth/logout");
    expect(logout?.init?.method).toBe("POST");
  });

  it("says so when the server can't be reached", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => Promise.reject(new TypeError("Failed to fetch"))));
    renderGate();

    expect(await screen.findByText("Can't reach the server")).toBeTruthy();
  });
});

describe("googleSignInUrl", () => {
  it("encodes the page to come back to", () => {
    expect(googleSignInUrl("/")).toBe("/auth/login?next=%2F");
  });
});
