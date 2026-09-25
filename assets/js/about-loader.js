/**
 * AquaClean About Loader
 * Fetches page content from /data/pages/about/{lang}.json
 * and footer contact from /data/pages/home/{lang}.json (shared source of truth),
 * then renders the about page sections. Falls back gracefully if JSON missing.
 */
(function () {
  'use strict';

  var htmlLang = document.documentElement.lang || 'en';
  var pathLang = location.pathname.match(/^\/([a-z]{2}(?:-[a-z]{2})?)\//);
  var LANG = (pathLang && pathLang[1]) || htmlLang;

  function escHtml(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // ── Hero ────────────────────────────────────────────────────────
  function renderHero(d) {
    var sec = document.getElementById('about-hero');
    if (!sec || !d) return;
    var badge = sec.querySelector('.hero-badge');
    if (badge && d.badge) badge.innerHTML = d.badge;
    var h1 = sec.querySelector('h1');
    if (h1 && d.h1) h1.innerHTML = d.h1;
    var intro = sec.querySelector('.hero-intro');
    if (intro && d.intro) intro.innerHTML = d.intro;
    if (d.bg_image) sec.style.backgroundImage = 'url(\'' + d.bg_image + '\')';
    var actions = sec.querySelector('.hero-actions');
    if (actions) {
      var btns = actions.querySelectorAll('a.btn');
      if (btns[0]) {
        if (d.btn_primary_text) btns[0].innerHTML = d.btn_primary_text;
        if (d.btn_primary_href) btns[0].href = d.btn_primary_href;
      }
      if (btns[1]) {
        if (d.btn_outline_text) btns[1].innerHTML = d.btn_outline_text;
        if (d.btn_outline_href) btns[1].href = d.btn_outline_href;
      }
    }
  }

  // ── Story ───────────────────────────────────────────────────────
  function renderStory(d) {
    var sec = document.getElementById('about-story');
    if (!sec || !d) return;
    var label = sec.querySelector('.section-label');
    if (label && d.label) label.textContent = d.label;
    var h2 = sec.querySelector('h2');
    if (h2 && d.h2) h2.textContent = d.h2;
    var img = sec.querySelector('.story-img img');
    if (img) {
      if (d.image) img.src = d.image;
      if (d.image_alt) img.alt = d.image_alt;
    }
    var text = sec.querySelector('.story-text');
    if (text) {
      var ps = text.querySelectorAll('p');
      (d.paragraphs || []).forEach(function (t, i) {
        if (ps[i]) ps[i].innerHTML = t;
      });
      var ul = text.querySelector('ul');
      if (ul && d.bullets) {
        ul.innerHTML = d.bullets.map(function (b) {
          return '<li>' + escHtml(b) + '</li>';
        }).join('');
      }
    }
  }

  // ── Capabilities (rebuild grid) ────────────────────────────────
  function renderCapabilities(d) {
    var sec = document.getElementById('about-capabilities');
    if (!sec || !d) return;
    var label = sec.querySelector('.section-label');
    if (label && d.label) label.textContent = d.label;
    var title = sec.querySelector('h2.section-title');
    if (title && d.title) title.textContent = d.title;
    var sub = sec.querySelector('p.section-sub');
    if (sub && d.sub) sub.innerHTML = d.sub;
    var grid = sec.querySelector('.why-grid');
    if (grid && d.items) {
      grid.innerHTML = (d.items || []).map(function (it) {
        return '<div class="why-item"><div class="why-icon">' + escHtml(it.icon || '') +
          '</div><div><h4>' + escHtml(it.h4 || '') + '</h4><p>' +
          escHtml(it.p || '') + '</p></div></div>';
      }).join('');
    }
  }

  // ── Gallery (rebuild grid) ─────────────────────────────────────
  function renderGallery(d) {
    var sec = document.getElementById('about-gallery');
    if (!sec || !d) return;
    var label = sec.querySelector('.section-label');
    if (label && d.label) label.textContent = d.label;
    var title = sec.querySelector('h2.section-title');
    if (title && d.title) title.textContent = d.title;
    var sub = sec.querySelector('p.section-sub');
    if (sub && d.sub) sub.innerHTML = d.sub;
    var grid = sec.querySelector('.gallery-grid');
    if (grid && d.items) {
      grid.innerHTML = (d.items || []).map(function (it) {
        return '<div class="gallery-card"><img src="' + escHtml(it.img || '') +
          '" alt="' + escHtml(it.alt || '') + '" loading="lazy"><div class="gallery-body"><h4>' +
          escHtml(it.h4 || '') + '</h4><p>' + escHtml(it.p || '') + '</p></div></div>';
      }).join('');
    }
  }

  // ── Milestones (rebuild timeline) ──────────────────────────────
  function renderMilestones(d) {
    var sec = document.getElementById('about-milestones');
    if (!sec || !d) return;
    var label = sec.querySelector('.section-label');
    if (label && d.label) label.textContent = d.label;
    var title = sec.querySelector('h2.section-title');
    if (title && d.title) title.textContent = d.title;
    var tl = sec.querySelector('.timeline');
    if (tl && d.items) {
      tl.innerHTML = (d.items || []).map(function (it) {
        return '<div class="tl-item"><div class="tl-year">' + escHtml(it.year || '') +
          '</div><h4>' + escHtml(it.h4 || '') + '</h4><p>' + escHtml(it.p || '') + '</p></div>';
      }).join('');
    }
  }

  // ── CTA band ────────────────────────────────────────────────────
  function renderCta(d) {
    var sec = document.getElementById('about-cta');
    if (!sec || !d) return;
    var h2 = sec.querySelector('h2');
    if (h2 && d.h2) h2.innerHTML = d.h2;
    var p = sec.querySelector('p');
    if (p && d.p) p.innerHTML = d.p;
    var a = sec.querySelector('a.btn');
    if (a) {
      if (d.btn_text) a.innerHTML = d.btn_text;
      if (d.btn_href) a.href = d.btn_href;
    }
  }

  // ── Footer (shared contact from home JSON) ─────────────────────
  function renderFooter(d) {
    if (!d) return;
    var ft = document.querySelector('footer');
    if (!ft) return;
    var fCompany = d.company_name || '';
    var fDesc = d.description || '';
    var fAddress = d.address || '';
    var fEmail = d.email || '';
    var fPhone = d.phone || '';
    var fWhatsapp = d.whatsapp || '';
    var brandSpan = ft.querySelector('.footer-brand .logo span');
    if (brandSpan && fCompany) brandSpan.textContent = fCompany;
    var descEl = ft.querySelector('.footer-brand > p');
    if (descEl && fDesc) descEl.textContent = fDesc;
    var fbottom = ft.querySelector('.footer-bottom');
    if (fbottom) {
      var year = new Date().getFullYear();
      var lines = fbottom.querySelectorAll('p');
      if (lines[0] && fCompany) {
        lines[0].textContent = '© ' + year + ' ' + fCompany + '. All rights reserved.';
      }
      if (lines[1]) {
        var parts = [];
        if (fAddress) parts.push('📍 ' + fAddress);
        if (fEmail) parts.push('✉ <a href="mailto:' + fEmail + '" style="color:inherit;">' + fEmail + '</a>');
        if (fPhone) parts.push('📞 <a href="tel:' + fPhone.replace(/[^\d+]/g, '') + '" style="color:inherit;">' + fPhone + '</a>');
        if (fWhatsapp) parts.push('💬 WhatsApp: ' + fWhatsapp);
        if (parts.length) lines[1].innerHTML = parts.join('  |  ');
      }
    }
    var links = ft.querySelectorAll('a[href^="mailto:"], a[href^="tel:"]');
    links.forEach(function (a) {
      if (a.href.indexOf('mailto:') === 0 && d.email) a.href = 'mailto:' + d.email;
      if (a.href.indexOf('tel:') === 0 && d.phone) a.href = 'tel:' + d.phone.replace(/[^\d+]/g, '');
    });
    var waLinks = ft.querySelectorAll('a[href*="wa.me"]');
    waLinks.forEach(function (a) {
      if (d.whatsapp) a.href = 'https://wa.me/' + d.whatsapp.replace(/[^\d]/g, '');
    });
  }

  function load() {
    var url = '/data/pages/about/' + LANG + '.json?v=' + Date.now();
    var x = new XMLHttpRequest();
    x.open('GET', url, true);
    x.onload = function () {
      if (x.status === 200) {
        try {
          var d = JSON.parse(x.responseText);
          renderHero(d.hero || {});
          renderStory(d.story || {});
          renderCapabilities(d.capabilities || {});
          renderGallery(d.gallery || {});
          renderMilestones(d.milestones || {});
          renderCta(d.cta || {});
        } catch (e) {
          console.warn('[about-loader] JSON parse error:', e);
        }
      } else {
        console.warn('[about-loader] about/' + LANG + '.json not found (HTTP ' + x.status + ')');
      }
    };
    x.onerror = function () {
      console.warn('[about-loader] Could not load about/' + LANG + '.json');
    };
    x.send();

    // Footer contact: shared with homepage (source of truth = home JSON)
    var fx = new XMLHttpRequest();
    fx.open('GET', '/data/pages/home/' + LANG + '.json?v=' + Date.now(), true);
    fx.onload = function () {
      if (fx.status === 200) {
        try {
          var hd = JSON.parse(fx.responseText);
          renderFooter(hd.footer || {});
        } catch (e) {}
      }
    };
    fx.send();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load);
  } else {
    load();
  }
})();
