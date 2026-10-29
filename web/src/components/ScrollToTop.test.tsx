// @vitest-environment jsdom
// A tapped card or tab opens the next page at its top.

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Link, MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ScrollToTop } from "./ScrollToTop";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

describe("ScrollToTop", () => {
  it("scrolls to the top on a new page, but not when only the day changes", () => {
    const scrollTo = vi.spyOn(window, "scrollTo").mockImplementation(() => {});
    render(
      <MemoryRouter initialEntries={["/"]}>
        <ScrollToTop />
        <Link to="/?date=2026-10-20">Another day</Link>
        <Link to="/nutrition">Protein</Link>
        <Routes>
          <Route path="*" element={null} />
        </Routes>
      </MemoryRouter>,
    );
    scrollTo.mockClear(); // the first render

    fireEvent.click(screen.getByText("Another day"));
    expect(scrollTo).not.toHaveBeenCalled();

    fireEvent.click(screen.getByText("Protein"));
    expect(scrollTo).toHaveBeenCalledWith(0, 0);
  });
});
