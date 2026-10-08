// 生产环境默认静音：带 ?aqcDebug=1 或 localStorage.aqcDebug 才输出
var AQC_DEBUG = /[?&]aqcDebug=1/.test(location.search);
try { if (localStorage.getItem('aqcDebug') === '1') AQC_DEBUG = true; } catch (e) {}
function dbg() { if (AQC_DEBUG) console.log.apply(console, arguments); }

/* =============================================
   MAIN.JS — Global interactions
   Version: 20260823-v1 (robust langPicker)
   ============================================= */

// ─── LANGUAGE PICKER (top-right dropdown) ──
(function() {
  'use strict';
  dbg('[langPicker] Initializing...');
  
  var picker = document.getElementById('langPicker');
  if (!picker) {
    console.error('[langPicker] ERROR: #langPicker not found');
    return;
  }
  dbg('[langPicker] #langPicker found');
  
  var btn = picker.querySelector('.lang-current');
  var menu = picker.querySelector('.lang-menu');
  
  if (!btn) {
    console.error('[langPicker] ERROR: .lang-current button not found');
    return;
  }
  if (!menu) {
    console.error('[langPicker] ERROR: .lang-menu not found');
    return;
  }
  dbg('[langPicker] button and menu found, attaching listeners');
  
  // Toggle on button click
  btn.addEventListener('click', function(e) {
    e.preventDefault();
    e.stopPropagation();
    var isOpen = picker.classList.toggle('open');
    btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    dbg('[langPicker] clicked, open =', isOpen);
  });
  
  // Close when clicking outside
  document.addEventListener('click', function(e) {
    if (!picker.contains(e.target)) {
      picker.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
    }
  });
  
  // Close on Escape
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      picker.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
    }
  });
  
  dbg('[langPicker] Initialization complete');
})();

// ─── LANGUAGE DETECTION ───────────────────────────
(function() {
  // 用户点过"不用了"就别再弹了（旧版本只写不读，每次刷新都弹一次）
  try { if (sessionStorage.getItem('langBannerDismissed')) return; } catch (e) {}
  var detectedLang = navigator.language || navigator.userLanguage;
  var supportedLangs = ['en','ar','vi','th','id','ru','es','fr'];
  function getLangCode(l) {
    var c = l.split('-')[0].toLowerCase();
    if (c === 'ar') return 'ar';
    if (c === 'vi') return 'vi';
    if (c === 'th') return 'th';
    if (c === 'id') return 'id';
    if (c === 'ru') return 'ru';
    if (c === 'es') return 'es';
    if (c === 'fr') return 'fr';
    return null;
  }
  var detected = getLangCode(detectedLang);
  var currentLang = window.location.pathname.split('/')[1] || 'en';

  if (detected && detected !== currentLang && detected !== 'en') {
    var banner = document.getElementById('langDetectBanner');
    if (banner) {
      var langNames = { ar:'العربية', vi:'Tiếng Việt', th:'ภาษาไทย', id:'Bahasa Indonesia', ru:'Русский', es:'Español', fr:'Français' };
      var nameEl = banner.querySelector('.lang-name');
      if (nameEl) nameEl.textContent = langNames[detected] || detected.toUpperCase();
      banner.classList.add('show');
      var yesBtn = banner.querySelector('.btn-yes');
      var noBtn = banner.querySelector('.btn-no');
      if (yesBtn) yesBtn.addEventListener('click', function() { window.location.href = '/' + detected + '/'; });
      if (noBtn) noBtn.addEventListener('click', function() { banner.classList.remove('show'); sessionStorage.setItem('langBannerDismissed', '1'); });
    }
  }
})();

// ─── POPUP MODAL (60% scroll, once per session) ──
(function() {
  if (sessionStorage.getItem('popupShown')) return;
  var shown = false;
  function showPopup() {
    if (shown) return;
    shown = true;
    var overlay = document.getElementById('popupOverlay');
    if (overlay) {
      overlay.classList.add('show');
      sessionStorage.setItem('popupShown', '1');
    }
  }
  window.addEventListener('scroll', function() {
    var pct = (window.scrollY / (document.body.scrollHeight - window.innerHeight)) * 100;
    if (pct >= 60) showPopup();
  }, { passive: true });
  setTimeout(showPopup, 45000);
})();

document.addEventListener('DOMContentLoaded', function() {
  var overlay = document.getElementById('popupOverlay');
  if (overlay) {
    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) overlay.classList.remove('show');
    });
    var closeBtn = overlay.querySelector('.popup-close');
    if (closeBtn) closeBtn.addEventListener('click', function() { overlay.classList.remove('show'); });
  }
});

// ─── PRODUCT MODAL ────────────────────────────────
// 弹窗里的产品数据集（p1~p11）和 openProduct() 已删除：全站没有任何元素带
// data-product-id，这套代码从未被调用过，却是 12KB 死代码，而且卡片文案
// 承诺的"点任意产品看规格"并不存在。产品卡现在直接跳对应类目页。
document.addEventListener('DOMContentLoaded', function() {
  var modal = document.getElementById('productModalOverlay');
  if (modal) {
    modal.addEventListener('click', function(e) {
      if (e.target === modal) { modal.classList.remove('show'); document.body.style.overflow = ''; }
    });
    var closeBtn = modal.querySelector('.product-modal-close');
    if (closeBtn) closeBtn.addEventListener('click', function() { modal.classList.remove('show'); document.body.style.overflow = ''; });
  }
});

// ─── FORM HANDLING ────────────────────────────────
// 三个询盘入口共用一个 endpoint，避免哪天又漏绑一个。
var FORMSPREE_ENDPOINT = 'https://formspree.io/f/xkjwgkjl';

// 第二个投递目标：后台自己的云数据库（assets/js/inquiry-sink.js 里的隐藏
// iframe 中继）。尽力而为 —— 它挂了不影响客户看到的成功提示，因为 Formspree
// 已经收下了。失败只写控制台，不弹窗吓人。
function aqcRelay(form) {
  if (!window.AQCInquiry || !form) return;
  try {
    var p = window.AQCInquiry.submit(window.AQCInquiry.fromForm(form));
    if (p && p.catch) p.catch(function () {});
  } catch (e) { /* never block the visitor */ }
}

document.addEventListener('DOMContentLoaded', function() {
  var mainForm = document.getElementById('mainInquiryForm');
  if (mainForm) {
    mainForm.addEventListener('submit', async function(e) {
      e.preventDefault();
      var btn = mainForm.querySelector('.btn');
      // 记住原始按钮文案，失败时原样还原（旧版本硬编码 'Send Message'，
      // 会把按钮文案改成另一句话）
      if (btn && !btn.dataset.label) btn.dataset.label = btn.textContent;
      btn.disabled = true;
      btn.textContent = 'Sending...';
      var fd = new FormData(mainForm);
      // 让邮件里带上来源语言和页面，回邮件时不用猜客户从哪个语种进来
      fd.append('_lang', document.documentElement.lang || '');
      fd.append('_page', location.pathname);
      aqcRelay(mainForm);
      try {
        var res = await fetch(FORMSPREE_ENDPOINT, {
          method: 'POST',
          body: fd,
          headers: { Accept: 'application/json' }
        });
        if (res.ok) {
          mainForm.style.display = 'none';
          var success = document.getElementById('mainFormSuccess');
          if (success) success.classList.add('show');
        } else {
          btn.disabled = false;
          btn.textContent = btn.dataset.label || 'Send Message';
          alert('Something went wrong. Please try again.');
        }
      } catch (err) {
        btn.disabled = false;
        btn.textContent = btn.dataset.label || 'Send Message';
        alert('Network error. Please try again.');
      }
    });
  }

  // 弹窗里的「Send Request」和产品弹窗里的「Send Quick Inquiry」以前是死按钮：
  // 一个只关窗，另一个 type="submit" 却压根不在 <form> 里。这里把它们包进
  // 真正的 form 并接到同一个 formspree endpoint。
  function wrapInForm(el, id) {
    if (!el) return null;
    if (el.tagName === 'FORM') { if (id && !el.id) el.id = id; return el; }
    var form = document.createElement('form');
    if (id) form.id = id;
    el.parentNode.insertBefore(form, el);
    form.appendChild(el);
    return form;
  }

  function bindInquiry(form, doneMsg, after) {
    if (!form) return;
    form.addEventListener('submit', async function (e) {
      e.preventDefault();
      var btn = form.querySelector('button[type="submit"]');
      if (btn) {
        if (!btn.dataset.label) btn.dataset.label = btn.textContent;
        btn.disabled = true;
        btn.textContent = 'Sending...';
      }
      aqcRelay(form);
      try {
        var res = await fetch(FORMSPREE_ENDPOINT, {
          method: 'POST',
          body: new FormData(form),
          headers: { Accept: 'application/json' }
        });
        if (res.ok) {
          if (doneMsg) { form.innerHTML = '<p style="text-align:center;padding:18px 0;margin:0;">' + doneMsg + '</p>'; }
          if (after) after();
        } else {
          if (btn) { btn.disabled = false; btn.textContent = btn.dataset.label || 'Send'; }
          alert('Something went wrong. Please try again.');
        }
      } catch (err) {
        if (btn) { btn.disabled = false; btn.textContent = btn.dataset.label || 'Send'; }
        alert('Network error. Please try again.');
      }
    });
  }

  // ① 弹窗（Need a Custom Solution?）
  var popupGrid = document.querySelector('#popupOverlay .form-grid');
  var popupForm = wrapInForm(popupGrid, 'popupInquiryForm');
  if (popupForm) {
    var pEmail = popupForm.querySelector('input[type="email"]');
    var pMsg = popupForm.querySelector('textarea');
    if (pEmail) { if (!pEmail.name) pEmail.name = 'email'; pEmail.required = true; }
    if (pMsg) { if (!pMsg.name) pMsg.name = 'message'; pMsg.required = true; }
    var pBtn = popupForm.querySelector('button');
    if (pBtn) {
      // 这个按钮以前是 onclick="…classList.remove('show')"，点了只关窗不发送
      pBtn.removeAttribute('onclick');
      pBtn.setAttribute('type', 'submit');
    }
    var popupOverlay = document.getElementById('popupOverlay');
    bindInquiry(popupForm, '✅ Thanks! We reply within 48 hours.', function () {
      setTimeout(function () {
        if (popupOverlay) popupOverlay.classList.remove('show');
        document.body.style.overflow = '';
      }, 1800);
    });
  }

  // ② 产品弹窗里的快速询盘
  var miniForm = wrapInForm(document.querySelector('.mini-form'), 'quickInquiryForm');
  if (miniForm) {
    var hidden = document.createElement('input');
    hidden.type = 'hidden';
    hidden.name = 'product';
    hidden.id = 'quickProduct';
    miniForm.appendChild(hidden);
    var syncProduct = function () {
      var t = document.querySelector('#productModalOverlay .product-modal-content h2');
      hidden.value = t ? t.textContent : '';
    };
    syncProduct();
    var qBtn = miniForm.querySelector('button[type="submit"]');
    if (qBtn) qBtn.addEventListener('click', syncProduct);
    bindInquiry(miniForm, '✅ Inquiry sent! We reply within 48 hours.');
  }
});

// ─── SMOOTH SCROLL ────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
  var anchors = document.querySelectorAll('a[href^="#"]');
  for (var i = 0; i < anchors.length; i++) {
    anchors[i].addEventListener('click', function(e) {
      var href = this.getAttribute('href');
      // href="#" 会让 querySelector('#') 抛 SyntaxError，异常发生在
      // preventDefault() 之前，结果是页面跳到顶部 + 控制台报错。
      if (!href || href === '#') { e.preventDefault(); return; }
      var target;
      try { target = document.querySelector(href); } catch (err) { return; }
      if (target) { e.preventDefault(); target.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
    });
  }
});
