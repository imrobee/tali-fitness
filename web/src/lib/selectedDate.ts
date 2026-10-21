// The selected day is shared state kept in the URL (?date=YYYY-MM-DD), so it survives
// tab switches, reloads and the back button (UI_SPEC.md section 1). No date means today.

import { useSearchParams } from "react-router";
import { isIsoDate } from "./dates";

export function useSelectedDate(): [string | null, (date: string | null) => void] {
  const [params, setParams] = useSearchParams();
  const raw = params.get("date");
  const selected = isIsoDate(raw) ? raw : null;

  const setSelected = (date: string | null) => {
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        if (date) next.set("date", date);
        else next.delete("date");
        return next;
      },
      { replace: true },
    );
  };

  return [selected, setSelected];
}
