import { describe, expect, it } from "vitest";
import { dialogPosition, EDGE, GAP, isSheet, sheetScrollTop, spotlight } from "./geometry";

const desktop = { width: 1280, height: 800 };
const phone = { width: 375, height: 667 };
const dialog = { width: 320, height: 240 };
// A card in the centred 520px page column on desktop.
const card = { top: 200, left: 380, width: 520, height: 180 };

describe("spotlight", () => {
  it("pads the card by 8px", () => {
    expect(spotlight(card, desktop)).toEqual({ top: 192, left: 372, width: 536, height: 196 });
  });

  it("stays on screen when the card is partly off it", () => {
    expect(spotlight({ top: -50, left: 0, width: 375, height: 900 }, phone)).toEqual({
      top: 0,
      left: 0,
      width: 375,
      height: 667,
    });
  });
});

describe("dialogPosition", () => {
  it("puts the dialog beside the card on desktop", () => {
    const spot = spotlight(card, desktop);
    const position = dialogPosition(spot, dialog, desktop, "bottom");

    expect(position.left).toBe(spot.left + spot.width + GAP);
    expect(position.top).toBeGreaterThanOrEqual(EDGE);
  });

  it("goes below the card when neither side has room", () => {
    const narrow = { width: 700, height: 800 };
    const spot = spotlight({ top: 100, left: 90, width: 520, height: 150 }, narrow);

    expect(dialogPosition(spot, dialog, narrow, "bottom").top).toBe(spot.top + spot.height + GAP);
  });

  it("goes above when the step prefers it and there is room", () => {
    const narrow = { width: 700, height: 800 };
    const spot = spotlight({ top: 500, left: 90, width: 520, height: 150 }, narrow);

    expect(dialogPosition(spot, dialog, narrow, "top").top).toBe(spot.top - GAP - dialog.height);
  });

  it("is centred without a spotlight", () => {
    expect(dialogPosition(null, dialog, desktop, "center")).toEqual({ top: 280, left: 480 });
  });

  it("never leaves the screen", () => {
    const narrow = { width: 700, height: 400 };
    const spot = spotlight({ top: 50, left: 90, width: 520, height: 300 }, narrow);
    const { top, left } = dialogPosition(spot, dialog, narrow, "bottom");

    expect(top).toBeGreaterThanOrEqual(EDGE);
    expect(left).toBeGreaterThanOrEqual(EDGE);
    expect(left + dialog.width).toBeLessThanOrEqual(narrow.width - EDGE);
  });
});

describe("the phone bottom sheet", () => {
  it("is used below 600px wide, so at 375 and 393", () => {
    expect(isSheet(phone)).toBe(true);
    expect(isSheet({ width: 393, height: 852 })).toBe(true);
    expect(isSheet(desktop)).toBe(false);
  });

  it("is used on a phone turned sideways too, where a floating dialog would not fit", () => {
    expect(isSheet({ width: 667, height: 375 })).toBe(true);
  });

  it("scrolls the card to just under the top edge", () => {
    expect(sheetScrollTop(900)).toBe(876);
    expect(sheetScrollTop(10)).toBe(0);
  });
});
