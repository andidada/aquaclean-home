/* =============================================
   MAIN.JS — Global interactions
   Version: 20260823-fixed
   ============================================= */

// ─── LANGUAGE PICKER (top-right dropdown) ──
(function() {
  const picker = document.getElementById('langPicker');
  if (!picker) return;
  const btn = picker.querySelector('.lang-current');
  const menu = picker.querySelector('.lang-menu');
  if (!btn || !menu) return;
  
  btn.addEventListener('click', function(e) {
    e.stopPropagation();
    const isOpen = picker.classList.toggle('open');
    btn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
  });
  
  document.addEventListener('click', function(e) {
    if (!picker.contains(e.target)) {
      picker.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
    }
  });
  
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      picker.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
    }
  });
})();

// ─── LANGUAGE DETECTION ───────────────────────────
const detectedLang = navigator.language || navigator.userLanguage;
const supportedLangs = ['en','ar','vi','th','id','ru','es','fr'];
function getLangCode(l) {
  const c = l.split('-')[0].toLowerCase();
  if (c === 'ar') return 'ar';
  if (c === 'vi') return 'vi';
  if (c === 'th') return 'th';
  if (c === 'id') return 'id';
  if (c === 'ru') return 'ru';
  if (c === 'es') return 'es';
  if (c === 'fr') return 'fr';
  return null;
}
const detected = getLangCode(detectedLang);
const currentLang = window.location.pathname.split('/')[1] || 'en';

if (detected && detected !== currentLang && detected !== 'en') {
  const banner = document.getElementById('langDetectBanner');
  if (banner) {
    const langNames = { ar:'العربية', vi:'Tiếng Việt', th:'ภาษาไทย', id:'Bahasa Indonesia', ru:'Русский', es:'Español', fr:'Français' };
    banner.querySelector('.lang-name').textContent = langNames[detected] || detected.toUpperCase();
    banner.classList.add('show');
    banner.querySelector('.btn-yes').addEventListener('click', () => {
      window.location.href = '/' + detected + '/';
    });
    banner.querySelector('.btn-no').addEventListener('click', () => {
      banner.classList.remove('show');
      sessionStorage.setItem('langBannerDismissed', '1');
    });
  }
}

// ─── POPUP MODAL (60% scroll, once per session) ──
(function() {
  if (sessionStorage.getItem('popupShown')) return;
  let shown = false;
  function showPopup() {
    if (shown) return;
    shown = true;
    const overlay = document.getElementById('popupOverlay');
    if (overlay) {
      overlay.classList.add('show');
      sessionStorage.setItem('popupShown', '1');
    }
  }
  window.addEventListener('scroll', function() {
    const pct = (window.scrollY / (document.body.scrollHeight - window.innerHeight)) * 100;
    if (pct >= 60) showPopup();
  }, { passive: true });
  setTimeout(showPopup, 45000);
})();

document.addEventListener('DOMContentLoaded', () => {
  const overlay = document.getElementById('popupOverlay');
  if (overlay) {
    overlay.addEventListener('click', (e) => {
      if (e.target === overlay) overlay.classList.remove('show');
    });
    const closeBtn = overlay.querySelector('.popup-close');
    if (closeBtn) closeBtn.addEventListener('click', () => overlay.classList.remove('show'));
  }
});

// ─── PRODUCT MODAL ────────────────────────────────
const productDataLoc = {
  ru: {
    p1: { name: 'Ручной пылесос', desc: 'Лёгкий беспроводной ручной пылесос мощностью 120 Вт.', specs: [['Мощность','120 Вт, 16 кПа'],['Аккумулятор','2000 мАч, 25 мин'],['Вес','1.2 кг']] },
    p2: { name: 'Робот-пылесос', desc: 'Робот-пылесос с лазерной навигацией LDS.', specs: [['Навигация','Лазер LDS'],['Всасывание','2000 Па'],['Аккумулятор','2600 мАч, 90 мин']] },
    p3: { name: 'Пароочиститель', desc: 'Многофункциональный пароочиститель мощностью 1500 Вт.', specs: [['Мощность','1500 Вт'],['Температура пара','105°C'],['Бак','1.5 л']] },
    p4: { name: 'УФ-пылесос', desc: 'УФ-С стерилизация матраса.', specs: [['УФ-излучение','253.7 нм UV-C'],['Скорость','6000 об/мин'],['Нагрев','горячий воздух 55°C']] },
    p5: { name: 'Робот для мойки окон', desc: 'Робот для мойки окон с искусственным интеллектом.', specs: [['Навигация','ИИ-распознавание краёв'],['Скорость','2.5 мин/м²'],['Аккумулятор','650 мАч']] },
    p6: { name: 'Автомобильный пылесос', desc: 'Компактный автомобильный пылесос 12 В.', specs: [['Напряжение','12 В DC'],['Мощность','150 Вт'],['Всасывание','5000 Па']] },
    p7: { name: 'Автокомпрессор', desc: 'Портативный цифровой насос.', specs: [['Диапазон давления','0-150 PSI'],['Точность','±1 PSI'],['Дисплей','цифровой LED']] }
  },
  es: {
    p1: { name: 'Aspirador de Mano', desc: 'Aspirador de mano inalámbrico ligero con 120 W.', specs: [['Potencia','120 W, 16 kPa'],['Batería','2000 mAh, 25 min'],['Peso','1.2 kg']] },
    p2: { name: 'Robot Aspirador', desc: 'Robot aspirador con navegación láser LDS.', specs: [['Navegación','Láser LDS'],['Succión','2000 Pa'],['Batería','2600 mAh, 90 min']] },
    p3: { name: 'Limpiador a Vapor', desc: 'Limpiador a vapor multisuperficie de 1500 W.', specs: [['Potencia','1500 W'],['Temp. vapor','105°C'],['Depósito','1.5 L']] },
    p4: { name: 'Eliminador de Ácaros UV', desc: 'Esterilizador UV-C para colchones.', specs: [['Longitud de onda UV','253.7 nm UV-C'],['Succión','6000 RPM'],['Calor','aire caliente 55°C']] },
    p5: { name: 'Robot Limpiacristales', desc: 'Robot limpiacristales automático con IA.', specs: [['Navegación','Detección de bordes IA'],['Velocidad','2.5 min/m²'],['Batería','650 mAh']] },
    p6: { name: 'Aspirador para Coche', desc: 'Aspirador compacto 12 V para coche.', specs: [['Voltaje','12 V DC'],['Potencia','150 W'],['Succión','5000 Pa']] },
    p7: { name: 'Inflador de Neumáticos', desc: 'Bomba de aire digital portátil.', specs: [['Rango de presión','0-150 PSI'],['Precisión','±1 PSI'],['Pantalla','LED digital']] }
  },
  fr: {
    p1: { name: 'Aspirateur à Main', desc: 'Aspirateur à main sans fil léger avec 120 W.', specs: [['Puissance','120 W, 16 kPa'],['Batterie','2000 mAh, 25 min'],['Poids','1.2 kg']] },
    p2: { name: 'Robot Aspirateur', desc: 'Robot aspirateur avec navigation laser LDS.', specs: [['Navigation','Laser LDS'],['Aspiration','2000 Pa'],['Batterie','2600 mAh, 90 min']] },
    p3: { name: 'Nettoyeur Vapeur', desc: 'Nettoyeur vapeur multi-surfaces 1500 W.', specs: [['Puissance','1500 W'],['Temp. vapeur','105°C'],['Réservoir','1.5 L']] },
    p4: { name: 'Anti-Acariens UV', desc: 'Stérilisateur UV-C pour matelas.', specs: [['Longueur d onde UV','253.7 nm UV-C'],['Aspiration','6000 tr/min'],['Chaleur','air chaud 55°C']] },
    p5: { name: 'Robot Lave-Vitres', desc: 'Robot lave-vitres automatique à IA.', specs: [['Navigation','Détection de bords IA'],['Vitesse','2.5 min/m²'],['Batterie','650 mAh']] },
    p6: { name: 'Aspirateur Voiture', desc: 'Aspirateur voiture compact 12 V.', specs: [['Tension','12 V DC'],['Puissance','150 W'],['Aspiration','5000 Pa']] },
    p7: { name: 'Gonfleur de Pneus', desc: 'Pompe à air numérique portable.', specs: [['Plage de pression','0-150 PSI'],['Précision','±1 PSI'],['Écran','LED numérique']] }
  }
};

const productData = {
  p1: { name: 'Handheld Vacuum Cleaner', img: '../assets/images/products/01-handheld-vacuum.png', desc: 'Lightweight cordless handheld vacuum with 120W suction power.', specs: [['Suction','120W, 16KPa'],['Battery','2000mAh, 25 min'],['Weight','1.2 kg']] },
  p2: { name: 'Robot Vacuum Cleaner', img: '../assets/images/products/02-robot-vacuum.png', desc: 'Smart LDS laser navigation robot vacuum.', specs: [['Navigation','LDS Laser'],['Suction','2000Pa'],['Battery','2600mAh, 90 min']] },
  p3: { name: 'Steam Cleaner', img: '../assets/images/products/03-steam-cleaner.png', desc: 'Multi-surface steam cleaner with 1500W power.', specs: [['Power','1500W'],['Steam Temp','105°C'],['Tank','1.5L']] },
  p4: { name: 'UV Mite Remover', img: '../assets/images/products/04-uv-mite-remover.png', desc: 'UV-C sterilization mattress cleaner.', specs: [['UV Wavelength','253.7nm UV-C'],['Suction','6000 RPM'],['Heat','55°C hot air']] },
  p5: { name: 'Smart Window Cleaner Robot', img: '../assets/images/products/05-window-robot.png', desc: 'AI-powered automatic window cleaning robot.', specs: [['Navigation','AI Edge Detection'],['Speed','2.5 min/m²'],['Battery','650mAh UPS']] },
  p6: { name: 'Car Vacuum Cleaner', img: '../assets/images/products/06-car-vacuum.png', desc: 'Compact 12V car vacuum with 150W motor.', specs: [['Voltage','12V DC'],['Power','150W'],['Suction','5000Pa']] },
  p7: { name: 'Digital Tire Inflator', img: '../assets/images/products/07-tire-inflator.png', desc: 'Portable digital air pump with auto shut-off.', specs: [['Pressure Range','0-150 PSI'],['Accuracy','±1 PSI'],['Display','Digital LED']] }
};

function openProduct(id) {
  let d = productData[id];
  if (!d) return;
  const _loc = (typeof productDataLoc !== 'undefined' && productDataLoc[currentLang] && productDataLoc[currentLang][id]) || null;
  if (_loc) d = Object.assign({}, d, _loc);
  const overlay = document.getElementById('productModalOverlay');
  if (!overlay) return;
  overlay.querySelector('.product-modal-img img').src = d.img;
  overlay.querySelector('.product-modal-img img').alt = d.name;
  overlay.querySelector('.product-modal-content h2').textContent = d.name;
  overlay.querySelector('.product-modal-desc').textContent = d.desc;
  const specsEl = overlay.querySelector('.specs');
  specsEl.innerHTML = d.specs.map(([k, v]) => '<div class="spec-item"><span class="key">' + k + '</span><span class="val">' + v + '</span></div>').join('');
  overlay.classList.add('show');
  document.body.style.overflow = 'hidden';
}

document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-product-id]').forEach(btn => {
    btn.addEventListener('click', () => openProduct(btn.dataset.productId));
  });
  const modal = document.getElementById('productModalOverlay');
  if (modal) {
    modal.addEventListener('click', (e) => { if (e.target === modal) { modal.classList.remove('show'); document.body.style.overflow = ''; } });
    const closeBtn = modal.querySelector('.product-modal-close');
    if (closeBtn) closeBtn.addEventListener('click', () => { modal.classList.remove('show'); document.body.style.overflow = ''; });
  }
});

// ─── FORM HANDLING ────────────────────────────────
const i18nForm = {
  en: { sending: 'Sending…', sent: 'Sent!', retry: 'Send Message' },
  ru: { sending: 'Отправка…', sent: '✓ Отправлено!', retry: 'Отправить' },
  es: { sending: 'Enviando…', sent: '¡Enviado!', retry: 'Enviar' },
  fr: { sending: 'Envoi…', sent: 'Envoyé !', retry: 'Envoyer' }
};
function t(key) { const dict = i18nForm[currentLang] || i18nForm.en; return dict[key] || key; }

document.addEventListener('DOMContentLoaded', () => {
  const mainForm = document.getElementById('mainInquiryForm');
  if (mainForm) {
    mainForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = mainForm.querySelector('.btn');
      btn.disabled = true;
      btn.textContent = t('sending');
      try {
        const res = await fetch('https://formspree.io/f/xkjwgkjl', {
          method: 'POST',
          body: new FormData(mainForm),
          headers: { Accept: 'application/json' }
        });
        if (res.ok) {
          mainForm.style.display = 'none';
          const success = document.getElementById('mainFormSuccess');
          if (success) success.classList.add('show');
        } else {
          btn.disabled = false;
          btn.textContent = t('retry');
          alert('Something went wrong.');
        }
      } catch {
        btn.disabled = false;
        btn.textContent = t('retry');
        alert('Network error.');
      }
    });
  }
});

// ─── SMOOTH SCROLL ────────────────────────────────
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    const target = document.querySelector(a.getAttribute('href'));
    if (target) { e.preventDefault(); target.scrollIntoView({ behavior: 'smooth', block: 'start' }); }
  });
});
