/**
 * AquaClean Home Loader
 * Fetches page content from /data/pages/home/{lang}.json
 * and updates the DOM sections (hero, product cards, contact, footer).
 * Falls back gracefully if JSON unavailable.
 */
(function () {
  'use strict';

  // Detect language from <html lang="en"> or URL path
  var htmlLang = document.documentElement.lang || 'en';
  var pathLang = location.pathname.match(/^\/([a-z]{2}(?:-[a-z]{2})?)\//);
  var LANG = (pathLang && pathLang[1]) || htmlLang;

  // Normalize lang (ar=rtl handled by CSS)
  var RTL_LANGS = ['ar'];

  // Render hero section
  function renderHero(d) {
    var sec = document.getElementById('hero-section') || document.querySelector('.hero-slides');
    if (!sec) return;
    // Badge
    var badge = sec.querySelector('.hero-badge');
    if (badge && d.badge) badge.innerHTML = d.badge;
    // H1 - replace entire h1 content
    var h1 = sec.querySelector('h1');
    if (h1 && d.h1) h1.innerHTML = d.h1;
    // Sub
    var sub = sec.querySelector('.hero-sub');
    if (sub && d.sub) sub.textContent = d.sub;
    // Buttons
    var actions = sec.querySelector('.hero-actions');
    if (actions) {
      var btns = actions.querySelectorAll('a.btn');
      if (btns[0] && d.btn_primary_text) {
        btns[0].textContent = d.btn_primary_text;
        if (d.btn_primary_href) btns[0].href = d.btn_primary_href;
      }
      if (btns[1] && d.btn_outline_text) {
        btns[1].textContent = d.btn_outline_text;
        if (d.btn_outline_href) btns[1].href = d.btn_outline_href;
      }
    }
  }

  // Render product cards (populates from JSON over existing DOM)
  function renderProducts(d) {
    if (!d || !d.products) return;
    var cards = document.querySelectorAll('.product-card');
    d.products.forEach(function (prod, i) {
      if (i >= cards.length) return;
      var card = cards[i];
      var h3 = card.querySelector('h3');
      var p = card.querySelector('p');
      var img = card.querySelector('img');
      var btn = card.querySelector('a.btn');
      var badge = card.querySelector('.product-badge-tag');
      if (h3 && prod.name) h3.textContent = prod.name;
      if (p && prod.desc) p.textContent = prod.desc;
      if (img && prod.img) {
        img.src = prod.img;
        img.alt = prod.name || '';
      }
      if (btn) {
        if (prod.btn_text) btn.textContent = prod.btn_text;
        if (prod.btn_href) btn.href = prod.btn_href;
        // Remove data-product-id to avoid modal intercepting link navigation
        btn.removeAttribute('data-product-id');
      }
      // Render tags
      if (prod.tags) {
        var tagsEl = card.querySelector('.product-tags');
        if (tagsEl) {
          tagsEl.innerHTML = prod.tags.map(function (t) {
            return '<span class="product-tag">' + escHtml(t) + '</span>';
          }).join('');
        }
      }
    });
  }

  // Render contact section
  function renderContact(d) {
    var sec = document.getElementById('contact');
    if (!sec) return;
    var h2 = sec.querySelector('h2');
    if (h2 && d.h2) h2.textContent = d.h2;
    // Update email
    var emailLink = sec.querySelector('a[href^="mailto:"]');
    if (emailLink && d.email) emailLink.href = 'mailto:' + d.email;
    // Update phone
    var phoneLink = sec.querySelector('a[href^="tel:"]');
    if (phoneLink && d.phone) phoneLink.href = 'tel:' + d.phone.replace(/[^\d+]/g, '');
    // Update WhatsApp
    var waLink = sec.querySelector('a[href*="wa.me"]');
    if (waLink && d.whatsapp) waLink.href = 'https://wa.me/' + d.whatsapp.replace(/[^\d]/g, '');
    // Update address
    var addrEl = sec.querySelector('.contact-address') || sec.querySelector('[class*="address"]');
    if (addrEl && d.address) addrEl.textContent = '📍 ' + d.address;
    // Update hours
    var hoursEl = sec.querySelector('.contact-hours') || sec.querySelector('[class*="hours"]');
    if (hoursEl && d.hours) hoursEl.textContent = '🕐 ' + d.hours;
  }

  // Render footer
  function renderFooter(d) {
    var ft = document.querySelector('footer');
    if (!ft) return;
    // Company name
    var logoLink = ft.querySelector('.footer-logo a, footer a[href="./"], footer a[href="/"]');
    if (logoLink && d.company_name) logoLink.textContent = d.company_name;
    // Description
    var descEl = ft.querySelector('p');
    if (descEl && d.description) descEl.textContent = d.description;
    // Email/phone links
    var links = ft.querySelectorAll('a[href^="mailto:"], a[href^="tel:"]');
    links.forEach(function (a) {
      if (a.href.startsWith('mailto:') && d.email) a.href = 'mailto:' + d.email;
      if (a.href.startsWith('tel:') && d.phone) a.href = 'tel:' + d.phone.replace(/[^\d+]/g, '');
    });
    // WhatsApp
    var waLinks = ft.querySelectorAll('a[href*="wa.me"]');
    waLinks.forEach(function (a) {
      if (d.whatsapp) a.href = 'https://wa.me/' + d.whatsapp.replace(/[^\d]/g, '');
    });
  }

  function escHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // Load JSON and render
  function load() {
    var url = '/data/pages/home/' + LANG + '.json?v=' + Date.now();
    var x = new XMLHttpRequest();
    x.open('GET', url, true);
    x.onload = function () {
      if (x.status === 200) {
        try {
          var d = JSON.parse(x.responseText);
          renderHero(d.hero || {});
          renderProducts(d.products || []);
          renderContact(d.contact || {});
          renderFooter(d.footer || {});
          // Remove data-product-id from all product-card buttons after render
          // (prevents langpicker modal intercepting the link navigation)
          var btns = document.querySelectorAll('.product-card a.btn');
          btns.forEach(function (b) { b.removeAttribute('data-product-id'); });
        } catch (e) {
          console.warn('[home-loader] JSON parse error:', e);
        }
      }
    };
    x.onerror = function () {
      console.warn('[home-loader] Could not load /data/pages/home/' + LANG + '.json');
    };
    x.send();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', load);
  } else {
    load();
  }
})();
