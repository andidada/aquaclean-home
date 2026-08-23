/* =============================================
   MAIN.JS — Global interactions
   Version: 20260823-v1 (robust langPicker)
   ============================================= */

// ─── LANGUAGE PICKER (top-right dropdown) ──
(function() {
  'use strict';
  console.log('[langPicker] Initializing...');
  
  var picker = document.getElementById('langPicker');
  if (!picker) {
    console.error('[langPicker] ERROR: #langPicker not found');
    return;
  }
  console.log('[langPicker] #langPicker found');
  
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
  console.log('[langPicker] button and menu found, attaching listeners');
  
  // Toggle on button click
  btn.addEventListener('click', function(e) {
    e.preventDefault();
    e.stopPropagation();
    var isOpen = picker.classList.toggle('open');
    btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
    console.log('[langPicker] clicked, open =', isOpen);
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
  
  console.log('[langPicker] Initialization complete');
})();

// ─── LANGUAGE DETECTION ───────────────────────────
(function() {
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
var productData = {
  p1: { name: 'Handheld Vacuum Cleaner', img: '../assets/images/products/01-handheld-vacuum.png', desc: 'Lightweight cordless handheld vacuum with 120W suction power.', specs: [['Suction','120W, 16KPa'],['Battery','2000mAh, 25 min'],['Weight','1.2 kg']] },
  p2: { name: 'Robot Vacuum Cleaner', img: '../assets/images/products/02-robot-vacuum.png', desc: 'Smart LDS laser navigation robot vacuum.', specs: [['Navigation','LDS Laser'],['Suction','2000Pa'],['Battery','2600mAh, 90 min']] },
  p3: { name: 'Steam Cleaner', img: '../assets/images/products/03-steam-cleaner.png', desc: 'Multi-surface steam cleaner with 1500W power.', specs: [['Power','1500W'],['Steam Temp','105°C'],['Tank','1.5L']] },
  p4: { name: 'UV Mite Remover', img: '../assets/images/products/04-uv-mite-remover.png', desc: 'UV-C sterilization mattress cleaner.', specs: [['UV Wavelength','253.7nm UV-C'],['Suction','6000 RPM'],['Heat','55°C hot air']] },
  p5: { name: 'Smart Window Cleaner Robot', img: '../assets/images/products/05-window-robot.png', desc: 'AI-powered automatic window cleaning robot.', specs: [['Navigation','AI Edge Detection'],['Speed','2.5 min/m²'],['Battery','650mAh UPS']] },
  p6: { name: 'Car Vacuum Cleaner', img: '../assets/images/products/06-car-vacuum.png', desc: 'Compact 12V car vacuum with 150W motor.', specs: [['Voltage','12V DC'],['Power','150W'],['Suction','5000Pa']] },
  p7: { name: 'Digital Tire Inflator', img: '../assets/images/products/07-tire-inflator.png', desc: 'Portable digital air pump with auto shut-off.', specs: [['Pressure Range','0-150 PSI'],['Accuracy','±1 PSI'],['Display','Digital LED']] }
};

function openProduct(id) {
  var d = productData[id];
  if (!d) return;
  var overlay = document.getElementById('productModalOverlay');
  if (!overlay) return;
  var img = overlay.querySelector('.product-modal-img img');
  var titleEl = overlay.querySelector('.product-modal-content h2');
  var descEl = overlay.querySelector('.product-modal-desc');
  var specsEl = overlay.querySelector('.specs');
  if (img) { img.src = d.img; img.alt = d.name; }
  if (titleEl) titleEl.textContent = d.name;
  if (descEl) descEl.textContent = d.desc;
  if (specsEl) specsEl.innerHTML = d.specs.map(function(s) { return '<div class="spec-item"><span class="key">' + s[0] + '</span><span class="val">' + s[1] + '</span></div>'; }).join('');
  overlay.classList.add('show');
  document.body.style.overflow = 'hidden';
}

document.addEventListener('DOMContentLoaded', function() {
  var products = document.querySelectorAll('[data-product-id]');
  for (var i = 0; i < products.length; i++) {
    products[i].addEventListener('click', function() { openProduct(this.getAttribute('data-product-id')); });
  }
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
document.addEventListener('DOMContentLoaded', function() {
  var mainForm = document.getElementById('mainInquiryForm');
  if (mainForm) {
    mainForm.addEventListener('submit', async function(e) {
      e.preventDefault();
      var btn = mainForm.querySelector('.btn');
      btn.disabled = true;
      btn.textContent = 'Sending...';
      try {
        var res = await fetch('https://formspree.io/f/xkjwgkjl', {
          method: 'POST',
          body: new FormData(mainForm),
          headers: { Accept: 'application/json' }
        });
        if (res.ok) {
          mainForm.style.display = 'none';
          var success = document.getElementById('mainFormSuccess');
          if (success) success.classList.add('show');
        } else {
          btn.disabled = false;
          btn.textContent = 'Send Message';
          alert('Something went wrong. Please try again.');
        }
      } catch (err) {
        btn.disabled = false;
        btn.textContent = 'Send Message';
        alert('Network error. Please try again.');
      }
    });
  }
});

// ─── SMOOTH SCROLL ────────────────────────────────
document.addEventListener('DOMContentLoaded', function() {
  var anchors = document.querySelectorAll('a[href^="#"]');
  for (var i = 0; i < anchors.length; i++) {
    anchors[i].addEventListener('click', function(e) {
      var target = document.querySelector(this.getAttribute('href'));
      if (target) { e.preventDefault(); target.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
    });
  }
});
