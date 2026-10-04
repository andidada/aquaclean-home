/**
 * Shared gate for the admin surfaces (dashboard.html, index.html).
 *
 * Include this at the TOP of the page. It decides whether the visitor is
 * allowed to stay, and bounces them to login.html if not.
 *
 *   server mode - when /.netlify/functions/admin-auth is configured the
 *                 stored session token is verified against the server, so an
 *                 expired or forged token is rejected even though the check
 *                 starts in the browser.
 *   local mode  - no function available, so fall back to the
 *                 admin_logged_in flag. That is only a speed bump: it stops
 *                 someone typing dashboard.html into the address bar, not
 *                 someone editing sessionStorage by hand.
 *
 * The gate is synchronous-friendly: it runs before the page's own scripts
 * finish, and redirects as soon as it knows.
 */
(function () {
  var AUTH_ENDPOINT = '/.netlify/functions/admin-auth';
  var LOGIN_PAGE = 'login.html';

  function bounce() {
    // Clear whatever was there so we never bounce in a loop.
    try {
      sessionStorage.removeItem('admin_logged_in');
      sessionStorage.removeItem('admin_session_token');
    } catch (e) { /* ignore */ }
    if (window.location.pathname.indexOf(LOGIN_PAGE) === -1) {
      window.location.replace(LOGIN_PAGE);
    }
  }

  function stay() { /* authorised */ }

  function token() {
    try { return sessionStorage.getItem('admin_session_token') || ''; } catch (e) { return ''; }
  }

  function flaggedIn() {
    try { return sessionStorage.getItem('admin_logged_in') === 'true'; } catch (e) { return false; }
  }

  function verifyOnServer() {
    var t = token();
    if (!t) return Promise.reject(new Error('no_token'));
    return fetch(AUTH_ENDPOINT, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ action: 'verify', token: t }),
    }).then(function (r) {
      return r.ok ? r.json() : Promise.reject(new Error('verify_failed'));
    }).then(function (d) {
      return d && d.ok ? stay() : Promise.reject(new Error('invalid_session'));
    });
  }

  // Content-type guard: a catch-all rewrite can answer unknown paths with
  // 200 + HTML (that is exactly what GitHub Pages does), which must not be
  // mistaken for a configured auth endpoint.
  fetch(AUTH_ENDPOINT, { credentials: 'same-origin' })
    .then(function (r) {
      var ct = r.headers.get('content-type') || '';
      if (r.status !== 200 || ct.indexOf('application/json') === -1) return null;
      return r.json().catch(function () { return null; });
    })
    .then(function (d) {
      if (d && d.configured) return verifyOnServer();
      return flaggedIn() ? stay() : Promise.reject(new Error('not_logged_in'));
    })
    .catch(bounce);
})();
