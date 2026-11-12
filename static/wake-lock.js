/*
 * The "keep the screen on" toggle of a song (templates/song.html), by the
 * Screen Wake Lock API. The button is hidden in the page and shown here only
 * where the browser has the API (it needs a secure context, so https).
 *
 * The browser drops the lock whenever the page is hidden, so the lock is asked
 * for again when the page is shown. The choice is remembered for the tab (not
 * for good, so that the screen is not kept on a day later) and carried to the
 * next song: a singer goes from song to song. A browser may refuse a request,
 * for instance on a low battery, or one that does not come from a tap (Safari
 * has done so); the button then goes back to "off", so it never claims what is
 * not true.
 */
(function () {
  "use strict";

  var STORAGE_KEY = "song-wake-lock";
  var STORED_ON = "on";

  var button = document.querySelector(".wake-lock-toggle");
  if (!button || !("wakeLock" in navigator)) {
    return;
  }

  var wanted = false; // what the reader chose
  var sentinel = null; // the lock held by the browser, if any

  function remember(on) {
    try {
      if (on) {
        sessionStorage.setItem(STORAGE_KEY, STORED_ON);
      } else {
        sessionStorage.removeItem(STORAGE_KEY);
      }
    } catch (error) {
      /* Not being able to remember the choice is not worth an error. */
    }
  }

  function wasRemembered() {
    try {
      return sessionStorage.getItem(STORAGE_KEY) === STORED_ON;
    } catch (error) {
      return false;
    }
  }

  function release() {
    if (sentinel) {
      sentinel.release();
      sentinel = null;
    }
  }

  function setWanted(on) {
    wanted = on;
    button.setAttribute("aria-pressed", String(on));
    remember(on);
  }

  function acquire() {
    return navigator.wakeLock.request("screen").then(function (lock) {
      if (!wanted) { // switched off while the request was on its way
        lock.release();
        return;
      }
      sentinel = lock;
      lock.addEventListener("release", function () {
        if (sentinel === lock) {
          sentinel = null; // dropped by the browser; asked for again when shown
        }
      });
    }).catch(function () {
      setWanted(false);
    });
  }

  function toggle() {
    setWanted(!wanted);
    if (wanted) {
      acquire();
    } else {
      release();
    }
  }

  button.hidden = false;
  button.addEventListener("click", toggle);
  document.addEventListener("visibilitychange", function () {
    if (wanted && !sentinel && document.visibilityState === "visible") {
      acquire();
    }
  });

  if (wasRemembered()) {
    setWanted(true);
    acquire();
  }
})();
