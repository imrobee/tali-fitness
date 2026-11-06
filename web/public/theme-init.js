// Applies the saved theme before the first paint, so a light-mode user never sees a flash
// of dark. A plain, blocking script in <head>: the Content-Security-Policy allows only
// same-origin scripts (script-src 'self'), so this cannot be inline. Same key and colours
// as src/lib/theme.ts.
(function () {
  var theme = "dark";
  try {
    if (window.localStorage.getItem("fitness-tracker.theme") === "light") theme = "light";
  } catch {
    // Storage blocked: stay dark.
  }
  document.documentElement.setAttribute("data-theme", theme);
  var meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute("content", theme === "light" ? "#f5f7f6" : "#000000");
})();
