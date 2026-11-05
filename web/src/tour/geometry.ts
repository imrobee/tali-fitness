// Where the spotlight and the tour's dialog go (UI_SPEC.md section 12). Pure functions
// of rectangles in viewport pixels, so they are unit tested without a browser.

export interface Rect {
  top: number;
  left: number;
  width: number;
  height: number;
}
export interface Size {
  width: number;
  height: number;
}

export const SPOT_PADDING = 8; // room between the card and the spotlight's edge
export const GAP = 12; // between the spotlight and the dialog
export const EDGE = 16; // the page gutter: nothing is placed closer to the screen edge
// Narrower than this (a phone), or shorter (a phone on its side, where a floating
// dialog would not fit top to bottom), the dialog is a bottom sheet instead.
export const SHEET_BELOW = 600;
export const SHEET_BELOW_HEIGHT = 500;

export function isSheet(viewport: Size): boolean {
  return viewport.width < SHEET_BELOW || viewport.height < SHEET_BELOW_HEIGHT;
}

/** The cut-out around a target: padded, and kept on screen. */
export function spotlight(target: Rect, viewport: Size): Rect {
  const top = Math.max(0, target.top - SPOT_PADDING);
  const left = Math.max(0, target.left - SPOT_PADDING);
  const bottom = Math.min(viewport.height, target.top + target.height + SPOT_PADDING);
  const right = Math.min(viewport.width, target.left + target.width + SPOT_PADDING);
  return { top, left, width: Math.max(0, right - left), height: Math.max(0, bottom - top) };
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), Math.max(min, max));
}

/** The dialog's top-left corner. Beside the spotlight when there is room (desktop: the
    page column leaves space either side), else below or above it as the step prefers,
    else wherever it fits best; centred when there is no spotlight. */
export function dialogPosition(
  spot: Rect | null,
  dialog: Size,
  viewport: Size,
  prefer: "top" | "bottom" | "center",
): { top: number; left: number } {
  const centred = {
    top: Math.max(EDGE, (viewport.height - dialog.height) / 2),
    left: Math.max(EDGE, (viewport.width - dialog.width) / 2),
  };
  if (spot === null || prefer === "center") return centred;

  const verticalMiddle = clamp(
    spot.top + spot.height / 2 - dialog.height / 2,
    EDGE,
    viewport.height - dialog.height - EDGE,
  );
  const right = spot.left + spot.width + GAP;
  if (right + dialog.width <= viewport.width - EDGE) return { top: verticalMiddle, left: right };
  const left = spot.left - GAP - dialog.width;
  if (left >= EDGE) return { top: verticalMiddle, left };

  const horizontal = clamp(
    spot.left + spot.width / 2 - dialog.width / 2,
    EDGE,
    viewport.width - dialog.width - EDGE,
  );
  const below = spot.top + spot.height + GAP;
  const above = spot.top - GAP - dialog.height;
  const fitsBelow = below + dialog.height <= viewport.height - EDGE;
  const fitsAbove = above >= EDGE;
  if (prefer === "bottom" ? fitsBelow || !fitsAbove : !fitsAbove && fitsBelow) {
    return { top: clamp(below, EDGE, viewport.height - dialog.height - EDGE), left: horizontal };
  }
  return { top: clamp(above, EDGE, viewport.height - dialog.height - EDGE), left: horizontal };
}

/** Phone: how far down to scroll so the target sits just under the top edge, clear of
    the bottom sheet. targetTop is the target's top in page (document) pixels. */
export function sheetScrollTop(targetTop: number): number {
  return Math.max(0, targetTop - EDGE - SPOT_PADDING);
}
