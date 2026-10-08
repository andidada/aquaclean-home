/* Inquiry relay client
 * ------------------------------------------------------------------
 * The public site and the back office live on different domains, and the
 * cloud data plane refuses requests whose Origin is not the app's own
 * registered domain — a browser on www.hkdmj.net cannot POST into the
 * back-office database at all (CORS rejects it before the request goes out).
 *
 * So the write is done from a page that IS served by the back-office domain:
 * /inquiry-proxy.html, loaded here in a hidden iframe and talked to with
 * postMessage. Formspree keeps handling the email notification; this is an
 * additional sink so leads also land in the admin's own 『询盘』 list.
 *
 * The relay is best-effort by design. If it is unreachable, the visitor still
 * sees the normal success message because Formspree already accepted the
 * inquiry — we never block or alarm on a relay failure.
 */
(function () {
  var RELAY_URL = 'https://aquaclean-admin.app.workbuddy.host/inquiry-proxy.html';
  var READY_TIMEOUT = 8000;

  var frame = null;
  var ready = false;
  var failed = false;
  var waiters = [];
  var pending = {};
  var seq = 0;
  var pageLoadAt = Date.now();

  function currentLang() {
    var l = document.documentElement.lang;
    if (l) return String(l).slice(0, 16);
    var m = location.pathname.match(/^\/([a-z]{2})\//);
    return m ? m[1] : 'en';
  }

  function mount() {
    if (frame) return frame;
    var f = document.createElement('iframe');
    f.src = RELAY_URL;
    f.style.cssText = 'position:absolute;width:0;height:0;border:0;visibility:hidden;';
    f.setAttribute('aria-hidden', 'true');
    f.setAttribute('tabindex', '-1');
    f.title = 'inquiry relay';
    document.body.appendChild(f);
    frame = f;
    // If the relay never answers (offline, blocked, admin app unpublished),
    // stop waiting and let every queued submit resolve as "skipped".
    setTimeout(function () {
      if (!ready) { failed = true; flushWaiters(); }
    }, READY_TIMEOUT);
    return f;
  }

  function flushWaiters() {
    var w = waiters; waiters = [];
    for (var i = 0; i < w.length; i++) w[i]();
  }

  window.addEventListener('message', function (ev) {
    var d = ev.data;
    if (!d || typeof d !== 'object') return;
    if (d.type === 'aqc-ready') {
      // Only trust the frame we created.
      if (!frame || ev.source !== frame.contentWindow) return;
      ready = true;
      if (d.error) failed = true;
      flushWaiters();
      return;
    }
    if (d.type === 'aqc-result') {
      var p = pending[d.id];
      if (!p) return;
      delete pending[d.id];
      clearTimeout(p.timer);
      p.resolve({ ok: !!d.ok, error: d.error || null });
    }
  });

  function whenReady() {
    if (ready || failed) return Promise.resolve(ready && !failed);
    return new Promise(function (resolve) {
      waiters.push(function () { resolve(ready && !failed); });
    });
  }

  /** Pull the known fields out of a <form>, tolerating missing inputs. */
  function fromForm(form) {
    var p = { hp: '' };
    var KEYS = ['name', 'email', 'company', 'country', 'products_interested', 'quantity', 'message', 'product'];
    for (var i = 0; i < KEYS.length; i++) {
      var el = form.querySelector('[name="' + KEYS[i] + '"]');
      if (el) p[KEYS[i]] = el.value || '';
    }
    // A hidden "product" field (quick inquiry) is the closest thing we have to
    // products_interested on those forms; do not overwrite a real selection.
    if (!p.products_interested && p.product) p.products_interested = p.product;
    delete p.product;
    return p;
  }

  function submit(payload) {
    if (!payload || typeof payload !== 'object') return Promise.resolve({ ok: false, skipped: true });
    var p = {
      name: payload.name || '',
      email: payload.email || '',
      company: payload.company || '',
      country: payload.country || '',
      products_interested: payload.products_interested || '',
      quantity: payload.quantity || '',
      message: payload.message || '',
      hp: payload.hp || '',
      lang: currentLang(),
      page_path: location.pathname,
      referrer: document.referrer || '',
      renderedAt: pageLoadAt
    };
    mount();
    return whenReady().then(function (ok) {
      if (!ok) return { ok: false, skipped: true };
      var id = 'q' + (++seq) + '_' + Date.now();
      return new Promise(function (resolve) {
        var timer = setTimeout(function () {
          delete pending[id];
          resolve({ ok: false, skipped: true });
        }, 8000);
        pending[id] = { resolve: resolve, timer: timer };
        try {
          frame.contentWindow.postMessage({ type: 'aqc-inquiry', id: id, payload: p }, '*');
        } catch (e) {
          delete pending[id];
          clearTimeout(timer);
          resolve({ ok: false, skipped: true });
        }
      });
    });
  }

  window.AQCInquiry = {
    fromForm: fromForm,
    submit: submit,
    relayUrl: RELAY_URL
  };
})();
