// The date chips put an invisible <input type="date"> over the chip. Phones open their
// picker on a tap anywhere on it; desktop browsers only from their own small icon, so a
// click asks for the picker. Shared by the day chooser and the vacation dates.

import type { MouseEvent } from "react";

export function openPicker(event: MouseEvent<HTMLInputElement>): void {
  try {
    event.currentTarget.showPicker?.();
  } catch {
    // Not allowed here (or not supported): the input still takes typing.
  }
}
