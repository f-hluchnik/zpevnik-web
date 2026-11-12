/*
 * Font size of the songs. Loaded from <head> (like theme.js), so that the
 * remembered size is set before the first paint and the text does not jump.
 *
 * The size is --song-font-scale on <html>; songbook.css multiplies the size of
 * the song by it. Without JavaScript the control stays hidden and the songs
 * are set in the size of the book.
 */
(function () {
  "use strict";

  var STORAGE_KEY = "song-font-scale";
  var MIN_SCALE = 0.7;
  var MAX_SCALE = 1.8;
  var STEP = 0.1;
  var root = document.documentElement;

  function clamp(scale) {
    return Math.min(MAX_SCALE, Math.max(MIN_SCALE, scale));
  }

  function readStoredScale() {
    try {
      var value = parseFloat(localStorage.getItem(STORAGE_KEY));
      return isNaN(value) ? 1 : clamp(value);
    } catch (error) {
      return 1; // Private mode, or storage disabled.
    }
  }

  function storeScale(scale) {
    try {
      localStorage.setItem(STORAGE_KEY, String(scale));
    } catch (error) {
      /* Not being able to remember the size is not worth an error. */
    }
  }

  var scale = readStoredScale();
  root.style.setProperty("--song-font-scale", String(scale));

  document.addEventListener("DOMContentLoaded", function () {
    var control = document.querySelector(".font-size-control");
    if (!control) {
      return;
    }
    control.hidden = false;
    control.addEventListener("click", function (event) {
      var button = event.target.closest("[data-font-step]");
      if (!button) {
        return;
      }
      // Rounded, so that ten steps up and down end where they began.
      scale = clamp(Math.round((scale + STEP * Number(button.dataset.fontStep)) * 10) / 10);
      root.style.setProperty("--song-font-scale", String(scale));
      storeScale(scale);
    });
  });
})();
