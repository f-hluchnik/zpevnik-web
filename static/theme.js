/*
 * Light/dark theme switch. Identical in the blog and the songbook repos.
 *
 * Loaded render-blocking from <head>: the first lines must run before the
 * browser paints, or a reader in dark mode gets a light flash.
 *
 * The rule that keeps this honest: `data-theme` is set ONLY when the reader
 * has picked a side. Left unset, the stylesheet follows the OS, so the page
 * keeps tracking the system theme if it changes mid-session. With JS off the
 * OS preference simply wins and the toggle is hidden.
 */
(function () {
  "use strict";

  var STORAGE_KEY = "theme";
  var root = document.documentElement;
  var darkQuery = window.matchMedia("(prefers-color-scheme: dark)");

  function readStoredTheme() {
    try {
      var value = localStorage.getItem(STORAGE_KEY);
      return value === "light" || value === "dark" ? value : null;
    } catch (error) {
      return null; // Private mode, or storage disabled. Fall back to the OS.
    }
  }

  function storeTheme(theme) {
    try {
      localStorage.setItem(STORAGE_KEY, theme);
    } catch (error) {
      /* Not being able to remember the choice is not worth an error. */
    }
  }

  /* What the reader is looking at right now, chosen or inherited. */
  function activeTheme() {
    return readStoredTheme() || (darkQuery.matches ? "dark" : "light");
  }

  /* Before first paint. No stored choice means no attribute, so the OS wins. */
  var stored = readStoredTheme();
  if (stored) {
    root.setAttribute("data-theme", stored);
  }

  /* Lets the stylesheet hide the toggle from readers who have no JS. */
  root.classList.add("has-js");

  document.addEventListener("DOMContentLoaded", function () {
    var button = document.getElementById("theme-toggle");
    if (!button) {
      return;
    }

    function describe() {
      button.setAttribute("aria-pressed", String(activeTheme() === "dark"));
    }

    describe();
    darkQuery.addEventListener("change", describe);

    button.addEventListener("click", function () {
      var next = activeTheme() === "dark" ? "light" : "dark";
      root.setAttribute("data-theme", next);
      storeTheme(next);
      describe();
    });
  });
})();
