// Signs this browser in to vid2sub (spec §6.1): posts the launch token from the URL's fragment
// to /auth, which answers with the launch cookie, then opens the app. A file, not an inline
// script, because the CSP allows only the engine's own files (spec §6.3).
"use strict";

(function () {
  const status = document.getElementById("status");
  const stale = "This link is out of date: open the URL vid2sub printed when it started.";
  const token = new URLSearchParams(location.hash.slice(1)).get("t");
  // The token leaves the address bar and the history before anything else happens.
  history.replaceState(null, "", location.pathname);
  if (!token) {
    status.textContent = stale;
    return;
  }
  fetch("/auth", {
    method: "POST",
    // Exactly this: WriteGuard refuses any other Content-Type, a charset included (spec §6.2).
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ token: token }),
    credentials: "same-origin",
    cache: "no-store",
  }).then(
    function (response) {
      if (response.status === 204) {
        location.replace("/");
      } else {
        status.textContent = stale;
      }
    },
    function () {
      status.textContent = "vid2sub isn't answering: start it again and open the URL it prints.";
    },
  );
})();
