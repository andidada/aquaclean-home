/* Review relay client (customer testimonials)
 * ------------------------------------------------------------------
 * The public site cannot write to the back-office database directly: the cloud
 * data plane requires an exact Origin match, so the browser blocks the request
 * at CORS. This client loads /review-proxy.html (served from the admin domain)
 * in a hidden iframe and hands the payload over with postMessage.
 *
 * Best-effort by design: if the relay is unreachable the visitor is told so
 * honestly rather than seeing a fake success — a review that silently vanished
 * is worse than one the visitor knows to retry.
 */
(function () {
  var RELAY_URL = 'https://aquaclean-admin.app.workbuddy.host/review-proxy.html';
  var READY_TIMEOUT = 20000;
  var REPLY_TIMEOUT = 10000;

  var frame = null;
  var ready = false;
  var failed = false;
  var waiters = [];
  var pending = {};
  var seq = 0;
  // 页面渲染时刻：中继用它做反机器人判断（填表耗时过短=机器人）。必须用页面
  // 加载时间而不是提交时间——后者每次都是「刚刚」，会被一律拒绝。
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
    f.title = 'review relay';
    document.body.appendChild(f);
    frame = f;
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
    if (d.type === 'aqc-review-ready') {
      if (!frame || ev.source !== frame.contentWindow) return;
      ready = true;
      if (d.error) failed = true;
      flushWaiters();
      return;
    }
    if (d.type === 'aqc-review-result') {
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

  function fromForm(form) {
    var p = { hp: '' };
    var KEYS = ['author', 'company', 'country', 'product_line', 'content'];
    for (var i = 0; i < KEYS.length; i++) {
      var el = form.querySelector('[name="' + KEYS[i] + '"]');
      if (el) p[KEYS[i]] = el.value || '';
    }
    // 注意：必须取 :checked。querySelector('[name="rating"]') 返回的是第一个
    // radio（值恒为 1），不是客户实际选中的那颗——那样所有人都会被记成 1 星。
    var rating = form.querySelector('[name="rating"]:checked')
      || form.querySelector('[name="rating"]');
    if (rating) p.rating = rating.value || '';
    return p;
  }

  function submit(payload) {
    if (!payload || typeof payload !== 'object') return Promise.resolve({ ok: false, skipped: true });
    var p = {
      rating: payload.rating || '',
      author: payload.author || '',
      company: payload.company || '',
      country: payload.country || '',
      product_line: payload.product_line || '',
      content: payload.content || '',
      hp: payload.hp || '',
      lang: currentLang(),
      page_path: location.pathname,
      renderedAt: pageLoadAt
    };
    mount();
    return whenReady().then(function (ok) {
      if (!ok) return { ok: false, skipped: true };
      var id = 'r' + (++seq) + '_' + Date.now();
      return new Promise(function (resolve) {
        var timer = setTimeout(function () {
          delete pending[id];
          resolve({ ok: false, skipped: true });
        }, REPLY_TIMEOUT);
        pending[id] = { resolve: resolve, timer: timer };
        try {
          frame.contentWindow.postMessage({ type: 'aqc-review', id: id, payload: p }, '*');
        } catch (e) {
          delete pending[id];
          clearTimeout(timer);
          resolve({ ok: false, skipped: true });
        }
      });
    });
  }

  window.AQCReview = {
    fromForm: fromForm,
    submit: submit,
    relayUrl: RELAY_URL
  };

  // 预热：页面加载就把中继挂上并等它握手。留评表单通常在页面下半部分，客户
  // 要滚动过来、读完、填完再提交，那段时间足够中继 ready；如果等到点提交
  // 才挂载，弱网下 iframe 首次拉后台域（cloud.js + SDK）会超时，客户第一次
  // 提交就失败。
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
})();
