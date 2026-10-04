/**
 * Session gate for the back office (index.html, dashboard.html).
 *
 * Include it AFTER the SDK and cloud.js, at the top of <body>. It asks the
 * cloud auth service whether there is a live session and bounces to the login
 * page if not. Unlike the previous sessionStorage flag — which anyone could
 * set by hand in devtools — this check happens against the server, so a
 * forged or expired session is rejected.
 */
(function () {
  'use strict';

  function onLoginPage() {
    return /login\.html$/.test(window.location.pathname);
  }

  function bounce() {
    if (onLoginPage()) return;
    window.location.replace('login.html');
  }

  if (!window.aqcCloudReady || !window.aqcHasSession) {
    // cloud.js missing or failed to load — fail closed rather than let the
    // page render with no session check at all.
    bounce();
    return;
  }

  window.aqcCloudReady
    .then(function (cloud) { return cloud.auth.getSession(); })
    .then(function (res) {
      if (window.aqcHasSession(res)) return;
      bounce();
    })
    .catch(bounce);
})();
