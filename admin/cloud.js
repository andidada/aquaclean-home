/* Cloud wiring for the back office.
 * ------------------------------------------------------------------
 * The back office is published as its own app because the cloud auth
 * service only trusts requests from the app's own registered domain — the
 * public marketing site cannot be used as the origin.
 *
 * endpoint + publishableKey are the only values the front end is allowed to
 * hold (the real environment id and provider keys stay server-side). The
 * server enforces an exact Origin match, so this file is only useful on the
 * published admin domain.
 */
(function () {
  var CFG = {
    endpoint: 'https://aquaclean-admin.app.workbuddy.host',
    publishableKey: 'wbpk_SFEhiWzbGbldZNA2qWs4ZT_Du85EsWOIrGxQbJLDhenYY3fF2xLYy52'
  };
  window.AQC_CLOUD_CONFIG = CFG;

  function build() {
    return window.WorkBuddyCloud.createWorkBuddyCloud(CFG);
  }

  // The SDK is loaded with a plain <script> before this file, but tolerate it
  // arriving late rather than throwing on an undefined global.
  window.aqcCloudReady = new Promise(function (resolve, reject) {
    if (window.WorkBuddyCloud) {
      try { resolve(build()); } catch (e) { reject(e); }
      return;
    }
    var tries = 0;
    var timer = setInterval(function () {
      if (window.WorkBuddyCloud) {
        clearInterval(timer);
        try { resolve(build()); } catch (e) { reject(e); }
      } else if (++tries > 150) {
        clearInterval(timer);
        reject(new Error('云服务 SDK 未能加载，请检查网络后重试'));
      }
    }, 100);
  });

  window.aqcCloudReady.catch(function (err) {
    console.error('[AQC] cloud init failed:', err && err.message);
  });

  /**
   * Does this getSession() result represent a live session?
   *
   * The SDK's minified implementation resolves with the session payload
   * itself, while its own docs describe a { data, error } envelope — and the
   * shape has already differed across builds. Checking a single shape is a
   * silent trap: the guard reads `res.data.session`, finds undefined, and
   * bounces a freshly signed-in user straight back to the login page with no
   * message. So accept every shape we have seen.
   */
  window.aqcHasSession = function (res) {
    if (!res || typeof res !== 'object') return false;
    if (res.error) return false;                 // explicit failure wins
    if (res.session) return true;
    var d = res.data;
    if (d) {
      if (d.session) return true;
      if (d.access_token || d.accessToken || d.user || d.user_id) return true;
    }
    // resolved with the session payload directly
    if (res.access_token || res.accessToken || res.user || res.user_id) return true;
    return false;
  };
})();
