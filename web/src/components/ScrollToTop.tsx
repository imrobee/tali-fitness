import { useEffect } from "react";
import { useLocation } from "react-router";

/** A new page opens at its top (a tapped card or tab). The browser keeps the old scroll
    position on in-app navigation, so the page would open partway down. Changing only the
    selected day (?date=) keeps the place. */
export function ScrollToTop() {
  const { pathname } = useLocation();
  useEffect(() => {
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}
