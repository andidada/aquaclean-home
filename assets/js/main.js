/* =============================================
   MAIN.JS — Global interactions
   ============================================= */

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
      window.location.href = `/${detected}/`;
    });
    banner.querySelector('.btn-no').addEventListener('click', () => {
      banner.classList.remove('show');
      sessionStorage.setItem('langBannerDismissed', '1');
    });
  }
}

// ─── LANGUAGE PICKER (top-right dropdown) ──
(function() {
  const picker = document.getElementById('langPicker');
  if (!picker) return;
  const btn = picker.querySelector('.lang-current');
  const menu = picker.querySelector('.lang-menu');
  if (!btn || !menu) return;
  btn.addEventListener('click', (e) => {
    e.stopPropagation();
    const open = picker.classList.toggle('open');
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
  document.addEventListener('click', (e) => {
    if (!picker.contains(e.target)) {
      picker.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
    }
  });
  // Close on Esc
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      picker.classList.remove('open');
      btn.setAttribute('aria-expanded', 'false');
    }
  });
})();

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
  setTimeout(showPopup, 45000); // fallback: 45s
})();

// Close popup
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

// ─── LOCALIZED PRODUCT DATA (ru/es/fr) ────────────
const productDataLoc = {
  ru: {
    p1: {
      name: 'Ручной пылесос',
      desc: 'Лёгкий беспроводной ручной пылесос мощностью 120 Вт. Идеален для быстрой уборки дома, в автомобиле или офисе.',
      specs: [['Мощность','120 Вт, 16 кПа'],['Аккумулятор','2000 мАч, 25 мин'],['Вес','1.2 кг'],['Объём','0.5 л пылесборник'],['Зарядка','USB-C, 3 ч'],['Шум','< 65 дБ']]
    },
    p2: {
      name: 'Робот-пылесос',
      desc: 'Робот-пылесос с лазерной навигацией LDS, приложением, функцией влажной уборки и мощностью всасывания 2000 Па.',
      specs: [['Навигация','Лазер LDS'],['Всасывание','2000 Па'],['Аккумулятор','2600 мАч, 90 мин'],['Пылесборник','0.6 л'],['Бак для воды','0.35 л'],['Приложение','TuyaSmart / SmartLife']]
    },
    p3: {
      name: 'Пароочиститель',
      desc: 'Многофункциональный пароочиститель мощностью 1500 Вт, пар 105°C. Глубокая очистка без химии полов, плитки, окон и других поверхностей.',
      specs: [['Мощность','1500 Вт'],['Температура пара','105°C'],['Бак','1.5 л'],['Нагрев','30 секунд'],['Длина шланга','5 м'],['Насадки','9 штук']]
    },
    p4: {
      name: 'УФ-пылесос для удаления пылевых клещей',
      desc: 'УФ-С стерилизация матраса с подогревом воздуха до 55°C. Уничтожает 99.9% пылевых клещей и бактерий.',
      specs: [['УФ-излучение','253.7 нм UV-C'],['Скорость','6000 об/мин'],['Нагрев','горячий воздух 55°C'],['Фильтр','HEPA H13'],['Мощность','450 Вт'],['Пылесборник','0.5 л']]
    },
    p5: {
      name: 'Робот для мойки окон',
      desc: 'Робот для мойки окон с искусственным интеллектом. Распознаёт края, обходит препятствия и чистит стёкла, плитку и зеркала без участия человека.',
      specs: [['Навигация','ИИ-распознавание краёв'],['Скорость','2.5 мин/м²'],['Аккумулятор','650 мАч (резервный ИБП)'],['Шум','< 65 дБ'],['Подходит для','стёкла, плитка, зеркала'],['Безопасность','удлинитель 4 м в комплекте']]
    },
    p6: {
      name: 'Автомобильный пылесос',
      desc: 'Компактный автомобильный пылесос 12 В с двигателем 150 Вт и набором насадок. Сухая и влажная уборка салона, сидений и приборной панели.',
      specs: [['Напряжение','12 В DC (прикуриватель)'],['Мощность','150 Вт'],['Всасывание','5000 Па'],['Тип','сухая и влажная уборка'],['Кабель','3.5 м'],['Насадки','щелевая + щётка']]
    },
    p7: {
      name: 'Цифровой автомобильный компрессор',
      desc: 'Портативный цифровой насос с автоотключением. 4 единицы измерения (PSI/BAR/KPA/кг/см²). Светодиодная подсветка для использования ночью.',
      specs: [['Диапазон давления','0-150 PSI'],['Точность','±1 PSI'],['Дисплей','цифровой LED'],['Питание','12 В / 10 А'],['Шланг','1 м ПВХ'],['Единицы','PSI BAR KPA кг/см²']]
    }
  },
  es: {
    p1: {
      name: 'Aspirador de Mano',
      desc: 'Aspirador de mano inalámbrico ligero con 120 W de potencia. Perfecto para limpiezas rápidas en casa, coche u oficina.',
      specs: [['Potencia','120 W, 16 kPa'],['Batería','2000 mAh, 25 min'],['Peso','1.2 kg'],['Capacidad','0.5 L'],['Carga','USB-C, 3 h'],['Ruido','< 65 dB']]
    },
    p2: {
      name: 'Robot Aspirador',
      desc: 'Robot aspirador con navegación láser LDS, control por app, función de mopa y 2000 Pa de succión.',
      specs: [['Navegación','Láser LDS'],['Succión','2000 Pa'],['Batería','2600 mAh, 90 min'],['Depósito','0.6 L'],['Tanque de agua','0.35 L'],['App','TuyaSmart / SmartLife']]
    },
    p3: {
      name: 'Limpiador a Vapor',
      desc: 'Limpiador a vapor multisuperficie de 1500 W, vapor a 105°C. Limpieza profunda sin químicos para suelos, azulejos, ventanas y más.',
      specs: [['Potencia','1500 W'],['Temp. vapor','105°C'],['Depósito','1.5 L'],['Calentamiento','30 segundos'],['Cable','5 m'],['Accesorios','9 piezas']]
    },
    p4: {
      name: 'Eliminador de Ácaros UV',
      desc: 'Esterilizador UV-C para colchones con aire caliente a 55°C. Elimina el 99.9% de ácaros y bacterias.',
      specs: [['Longitud de onda UV','253.7 nm UV-C'],['Succión','6000 RPM'],['Calor','aire caliente 55°C'],['Filtro','HEPA H13'],['Potencia','450 W'],['Depósito','0.5 L']]
    },
    p5: {
      name: 'Robot Limpiacristales',
      desc: 'Robot limpiacristales automático con IA. Detecta bordes, evita obstáculos y limpia cristales, azulejos y espejos sin操作 manual.',
      specs: [['Navegación','Detección de bordes IA'],['Velocidad','2.5 min/m²'],['Batería','650 mAh (SAI)'],['Ruido','< 65 dB'],['Apto para','cristal, azulejos, espejos'],['Seguridad','cable extensor 4 m incluido']]
    },
    p6: {
      name: 'Aspirador para Coche',
      desc: 'Aspirador compacto 12 V para coche con motor de 150 W y múltiples accesorios. Uso en seco y húmedo para interior, asientos y salpicadero.',
      specs: [['Voltaje','12 V DC (encendedor)'],['Potencia','150 W'],['Succión','5000 Pa'],['Tipo','seco y húmedo'],['Cable','3.5 m'],['Accesorios','boquilla + cepillo']]
    },
    p7: {
      name: 'Inflador de Neumáticos Digital',
      desc: 'Bomba de aire digital portátil con apagado automático. 4 unidades预设 (PSI/BAR/KPA/kg/cm²). Luz LED para uso nocturno.',
      specs: [['Rango de presión','0-150 PSI'],['Precisión','±1 PSI'],['Pantalla','LED digital'],['Potencia','12 V / 10 A'],['Manguera','1 m PVC'],['Unidades','PSI BAR KPA kg/cm²']]
    }
  },
  fr: {
    p1: {
      name: 'Aspirateur à Main',
      desc: 'Aspirateur à main sans fil léger avec puissance d\'aspiration de 120 W. Parfait pour les nettoyages rapides à la maison, en voiture ou au bureau.',
      specs: [['Puissance', '120 W, 16 kPa'], ['Batterie', '2000 mAh, 25 min'], ['Poids', '1.2 kg'], ['Capacité', '0.5 L'], ['Charge', 'USB-C, 3 h'], ['Bruit', '< 65 dB']]
    },
    p2: {
      name: 'Robot Aspirateur',
      desc: 'Robot aspirateur avec navigation laser LDS, contrôle par appli, fonction serpillière et aspiration 2000 Pa.',
      specs: [['Navigation', 'Laser LDS'], ['Aspiration', '2000 Pa'], ['Batterie', '2600 mAh, 90 min'], ['Réservoir', '0.6 L'], ['Réservoir d\'eau', '0.35 L'], ['Appli', 'TuyaSmart / SmartLife']]
    },
    p3: {
      name: 'Nettoyeur Vapeur',
      desc: 'Nettoyeur vapeur multi-surfaces 1500 W, vapeur à 105°C. Nettoyage en profondeur sans produits chimiques.',
      specs: [['Puissance', '1500 W'], ['Temp. vapeur', '105°C'], ['Réservoir', '1.5 L'], ['Montée en température', '30 secondes'], ['Câble', '5 m'], ['Accessoires', '9 pièces']]
    },
    p4: {
      name: 'Anti-Acariens UV',
      desc: 'Stérilisateur UV-C pour matelas avec air chaud à 55°C. Élimine 99.9% des acariens et bactéries.',
      specs: [['Longueur d\'onde UV', '253.7 nm UV-C'], ['Aspiration', '6000 tr/min'], ['Chaleur', 'air chaud 55°C'], ['Filtre', 'HEPA H13'], ['Puissance', '450 W'], ['Réservoir', '0.5 L']]
    },
    p5: {
      name: 'Robot Lave-Vitres',
      desc: 'Robot lave-vitres automatique à IA. Détecte les bords, évite les obstacles et nettoie vitres, carrelages et miroirs sans intervention manuelle.',
      specs: [['Navigation', 'Détection de bords IA'], ['Vitesse', '2.5 min/m²'], ['Batterie', '650 mAh (onduleur)'], ['Bruit', '< 65 dB'], ['Compatible', 'verre, carrelage, miroirs'], ['Sécurité', 'rallonge 4 m incluse']]
    },
    p6: {
      name: 'Aspirateur Voiture',
      desc: 'Aspirateur voiture compact 12 V avec moteur 150 W et plusieurs accessoires. Aspiration eau et poussière pour intérieur, sièges et tableau de bord.',
      specs: [['Tension', '12 V DC (allume-cigare)'], ['Puissance', '150 W'], ['Aspiration', '5000 Pa'], ['Type', 'sec et humide'], ['Câble', '3.5 m'], ['Accessoires', 'suceur + brosse']]
    },
    p7: {
      name: 'Gonfleur de Pneus Digital',
      desc: 'Pompe à air numérique portable avec arrêt automatique. 4 unités préréglées (PSI/BAR/KPA/kg/cm²). Lumière LED pour usage nocturne.',
      specs: [['Plage de pression', '0-150 PSI'], ['Précision', '±1 PSI'], ['Écran', 'LED numérique'], ['Alimentation', '12 V / 10 A'], ['Tuyau', '1 m PVC'], ['Unités', 'PSI BAR KPA kg/cm²']]
    }
  }
};
const productData = {
  'p1': {
    name: 'Handheld Vacuum Cleaner',
    img: '../assets/images/products/01-handheld-vacuum.png',
    desc: 'Lightweight cordless handheld vacuum with 120W suction power. Perfect for quick clean-ups around the home, car, or office.',
    specs: [
      ['Suction', '120W, 16KPa'],
      ['Battery', '2000mAh, 25 min'],
      ['Weight', '1.2 kg'],
      ['Capacity', '0.5L dust cup'],
      ['Charging', 'USB-C, 3h'],
      ['Noise', '< 65 dB'],
    ]
  },
  'p2': {
    name: 'Robot Vacuum Cleaner',
    img: '../assets/images/products/02-robot-vacuum.png',
    desc: 'Smart LDS laser navigation robot vacuum with app control, mopping function, and 2000Pa deep cleaning suction.',
    specs: [
      ['Navigation', 'LDS Laser'],
      ['Suction', '2000Pa'],
      ['Battery', '2600mAh, 90 min'],
      ['Dustbin', '0.6L'],
      ['Water Tank', '0.35L'],
      ['App', 'TuyaSmart / SmartLife'],
    ]
  },
  'p3': {
    name: 'Steam Cleaner',
    img: '../assets/images/products/03-steam-cleaner.png',
    desc: 'Multi-surface steam cleaner with 1500W power, 105°C super-heated steam. Chemical-free deep cleaning for floors, tiles, windows, and more.',
    specs: [
      ['Power', '1500W'],
      ['Steam Temp', '105°C'],
      ['Tank', '1.5L'],
      ['Heat-up', '30 seconds'],
      ['Cord Length', '5m'],
      ['Attachments', '9 pieces'],
    ]
  },
  'p4': {
    name: 'UV Mite Remover',
    img: '../assets/images/products/04-uv-mite-remover.png',
    desc: 'UV-C sterilization mattress cleaner with 55°C hot air drying. Eliminates 99.9% of dust mites and bacteria.',
    specs: [
      ['UV Wavelength', '253.7nm UV-C'],
      ['Suction', '6000 RPM'],
      ['Heat', '55°C hot air'],
      ['Filter', 'HEPA H13'],
      ['Power', '450W'],
      ['Dust Box', '0.5L'],
    ]
  },
  'p5': {
    name: 'Smart Window Cleaner Robot',
    img: '../assets/images/products/05-window-robot.png',
    desc: 'AI-powered automatic window cleaning robot. Senses edges, avoids obstacles, and cleans glass, tiles, and mirrors without manual operation.',
    specs: [
      ['Navigation', 'AI Edge Detection'],
      ['Speed', '2.5 min/m²'],
      ['Battery', '650mAh UPS backup'],
      ['Noise', '< 65 dB'],
      ['Suitable for', 'Glass, tiles, mirrors'],
      ['Safety', '4m extension cable included'],
    ]
  },
  'p6': {
    name: 'Car Vacuum Cleaner',
    img: '../assets/images/products/06-car-vacuum.png',
    desc: 'Compact 12V car vacuum with 150W motor and multiple attachments. Dry & wet dual-use for car interior, seats, and dashboard.',
    specs: [
      ['Voltage', '12V DC (car cigarette lighter)'],
      ['Power', '150W'],
      ['Suction', '5000Pa'],
      ['Type', 'Dry & wet'],
      ['Cord', '3.5m power cord'],
      ['Attachments', 'Crevice tool + brush'],
    ]
  },
  'p7': {
    name: 'Digital Tire Inflator',
    img: '../assets/images/products/07-tire-inflator.png',
    desc: 'Portable digital air pump with auto shut-off. Preset 4 units (PSI/BAR/KPA/kg/cm²). LED light for night use.',
    specs: [
      ['Pressure Range', '0-150 PSI'],
      ['Accuracy', '±1 PSI'],
      ['Display', 'Digital LED'],
      ['Power', '12V / 10A'],
      ['Air Hose', '1m PVC'],
      ['Units', 'PSI BAR KPA kg/cm²'],
    ]
  },
};

function openProduct(id) {
  let d = productData[id];
  if (!d) return;
  // Merge localized data if available for current page language
  const _loc = (typeof productDataLoc !== 'undefined' && productDataLoc[currentLang] && productDataLoc[currentLang][id]) || null;
  if (_loc) d = Object.assign({}, d, _loc);
  const overlay = document.getElementById('productModalOverlay');
  if (!overlay) return;
  overlay.querySelector('.product-modal-img img').src = d.img;
  overlay.querySelector('.product-modal-img img').alt = d.name;
  overlay.querySelector('.product-modal-content h2').textContent = d.name;
  overlay.querySelector('.product-modal-desc').textContent = d.desc;
  const specsEl = overlay.querySelector('.specs');
  specsEl.innerHTML = d.specs.map(([k, v]) =>
    `<div class="spec-item"><span class="key">${k}</span><span class="val">${v}</span></div>`
  ).join('');
  overlay.classList.add('show');
  document.body.style.overflow = 'hidden';
}

document.addEventListener('DOMContentLoaded', () => {
  // Product card clicks
  document.querySelectorAll('[data-product-id]').forEach(btn => {
    btn.addEventListener('click', () => openProduct(btn.dataset.productId));
  });
  // Modal close
  const modal = document.getElementById('productModalOverlay');
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });
    const closeBtn = modal.querySelector('.product-modal-close');
    if (closeBtn) closeBtn.addEventListener('click', closeModal);
  }
  function closeModal() {
    modal.classList.remove('show');
    document.body.style.overflow = '';
  }
});

// ─── FORM HANDLING ────────────────────────────────
// Localized UI strings (form buttons, alerts) — keyed by currentLang
const i18nForm = {
  en: { sending: 'Sending…', sent: 'Sent!', retry: 'Send Message', errGeneric: 'Something went wrong. Please try again or email us directly.', errNetwork: 'Network error. Please check your connection and try again.' },
  ru: { sending: 'Отправка…', sent: '✓ Отправлено!', retry: 'Отправить', errGeneric: 'Что-то пошло не так. Попробуйте снова или напишите нам на email.', errNetwork: 'Ошибка сети. Проверьте подключение и попробуйте снова.' },
  es: { sending: 'Enviando…', sent: '¡Enviado!', retry: 'Enviar', errGeneric: 'Algo salió mal. Inténtelo de nuevo o escríbanos por email.', errNetwork: 'Error de red. Verifique su conexión e inténtelo de nuevo.' },
  fr: { sending: 'Envoi en cours…', sent: 'Envoyé !', retry: 'Envoyer', errGeneric: 'Une erreur est survenue. Veuillez réessayer ou nous écrire par email.', errNetwork: 'Erreur réseau. Vérifiez votre connexion et réessayez.' }
};
function t(key) { const dict = i18nForm[currentLang] || i18nForm.en; return dict[key] || key; }

// Main inquiry form
document.addEventListener('DOMContentLoaded', () => {
  const mainForm = document.getElementById('mainInquiryForm');
  if (mainForm) {
    mainForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const formData = new FormData(mainForm);
      const btn = mainForm.querySelector('.btn');
      btn.disabled = true;
      btn.textContent = 'Sending…';
      try {
        // Replace xkjwgkjl with actual Formspree endpoint
        const res = await fetch('https://formspree.io/f/xkjwgkjl', {
          method: 'POST',
          body: formData,
          headers: { Accept: 'application/json' }
        });
        if (res.ok) {
          mainForm.style.display = 'none';
          const success = document.getElementById('mainFormSuccess');
          if (success) success.classList.add('show');
        } else {
          btn.disabled = false;
          btn.textContent = 'Send Message';
          alert('Something went wrong. Please try again or email us directly.');
        }
      } catch {
        btn.disabled = false;
        btn.textContent = 'Send Message';
        alert('Network error. Please check your connection and try again.');
      }
    });
  }

  // Mini forms inside product modal
  document.querySelectorAll('.mini-form').forEach(miniForm => {
    miniForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const btn = miniForm.querySelector('button[type=submit]');
      const orig = btn.textContent;
      btn.disabled = true;
      btn.textContent = 'Sending…';
      try {
        const res = await fetch('https://formspree.io/f/xkjwgkjl', {
          method: 'POST',
          body: new FormData(miniForm),
          headers: { Accept: 'application/json' }
        });
        btn.disabled = false;
        btn.textContent = res.ok ? '✓ Sent!' : orig;
        if (res.ok) {
          setTimeout(() => {
            btn.textContent = orig;
            miniForm.reset();
          }, 2500);
        }
      } catch {
        btn.disabled = false;
        btn.textContent = orig;
      }
    });
  });
});

// ─── SMOOTH SCROLL ────────────────────────────────
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    const target = document.querySelector(a.getAttribute('href'));
    if (target) {
      e.preventDefault();
      target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  });
});

// ─── MOBILE MENU TOGGLE ───────────────────────────
// (placeholder — can be expanded)

// ─── LANGUAGE PICKER (top-right dropdown) ──────────
(function () {
  const picker = document.getElementById('langPicker');
  if (!picker) return;
  const btn = picker.querySelector('.lang-current');
  function closePicker() {
    picker.classList.remove('open');
    btn.setAttribute('aria-expanded', 'false');
  }
  btn.addEventListener('click', function (e) {
    e.stopPropagation();
    const open = picker.classList.toggle('open');
    btn.setAttribute('aria-expanded', open ? 'true' : 'false');
  });
  document.addEventListener('click', function (e) {
    if (!picker.contains(e.target)) closePicker();
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') closePicker();
  });
})();
