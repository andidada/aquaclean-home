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
    // 中继此前加载失败（弱网/瞬时抖动）时，别让这次访问永远失去留评能力：
    // 丢掉旧 iframe 重挂一次，给客户多一次机会。mount() 本身幂等。
    if (frame && failed) {
      try { frame.parentNode.removeChild(frame); } catch (e) { /* 已不在 DOM */ }
      frame = null; ready = false; failed = false;
    }
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

  // 预热：不在页面加载时挂 iframe。首页是 HTTP/1.1、请求数即瓶颈，而绝大多数
  // 访客根本不留评——为 1% 的提交让 100% 的访客多拉一个跨域 iframe（后台域
  // cloud.js + SDK）不划算。改成「有留注意图才挂」：
  //   · 焦点进入留评表单 / 输入内容 / 滚到留评区 → 挂载并等握手
  //   · 客户从看到表单到提交通常有几十秒，足够中继 ready，弱网也不会首次超时
  var prewarmed = false;
  function prewarm() {
    if (prewarmed) return;
    prewarmed = true;
    mount();
  }
  function bindPrewarm() {
    var scope = document.querySelector('.review-collect');
    if (scope) {
      scope.addEventListener('focusin', prewarm, true);
      scope.addEventListener('pointerdown', prewarm, true);
    }
    if ('IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (entries) {
        for (var i = 0; i < entries.length; i++) {
          if (entries[i].isIntersecting) { prewarm(); io.disconnect(); return; }
        }
      }, { rootMargin: '300px' });
      var target = scope || document.body;
      io.observe(target);
    } else {
      prewarm();
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindPrewarm);
  } else {
    bindPrewarm();
  }
})();
