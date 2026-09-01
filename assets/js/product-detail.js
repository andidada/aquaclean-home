/* ============================================================
   AquaClean Product Detail — data-driven renderer
   Loads data/products/{category}.json and renders Alibaba-style
   product detail page. All text is i18n via JSON translations.
   ============================================================ */
(function () {
  'use strict';

  // ---------- Config from page ----------
  var cfg = window.AQC_PRODUCT || {};
  var CATEGORY = cfg.category || '';
  var PRODUCT_ID = cfg.id || '';
  var LANG = cfg.lang || 'en';
  var CATEGORY_NAME = cfg.categoryName || '';

  // ---------- i18n UI strings ----------
  var UI = {
    en: {
      home: 'Home', model: 'Model', moq: 'Min. Order', inStock: 'In Stock',
      priceTitle: 'Price', sampleTitle: 'Sample', getSample: 'Get Sample',
      addToCart: 'Send Inquiry', chatWhatsapp: 'Chat on WhatsApp',
      highlights: 'Product Highlights', specs: 'Key Attributes',
      supplier: 'Supplier Info', verified: 'Verified Supplier', responseTime: 'Response Time',
      rating: 'Rating', transactions: 'Transactions', years: 'Years',
      customization: 'Customization Options', oemTitle: 'OEM / ODM Services',
      packaging: 'Packaging & Shipping', from: 'From', leadTime: 'Lead Time',
      applications: 'Applications', description: 'Detailed Description',
      inquiry: 'Send Inquiry', inquiryTitle: 'Get a Quote for this Product',
      name: 'Your Name *', email: 'Email *', company: 'Company', country: 'Country',
      quantity: 'Quantity (pieces)', message: 'Message *', submit: 'Submit Inquiry',
      successTitle: 'Thank you!', successText: 'Your inquiry has been prepared. We will get back to you within 24 hours.',
      related: 'More Products in this Category', viewAll: 'View All',
      trustShip: 'Ship from', trustLead: 'Lead Time', trustPack: 'Packaging',
      noVideo: 'Video coming soon', homeAlias: 'Home',
      getQuote: 'Get Quote', customLogo: 'Custom Logo', customColor: 'Custom Color',
      customPackage: 'Custom Packaging', customOEM: 'OEM Available', customODM: 'ODM Available',
      sampleLead: 'Sample Lead Time', productionLead: 'Production Lead Time',
      certTitle: 'Certifications', currency: 'US $', per: '/ piece',
      dayUnit: 'days', inqProduct: 'Product', inqModel: 'Model',
      whatsappText: 'Hello, I am interested in'
    },
    zh: {
      home: '首页', model: '型号', moq: '最小起订量', inStock: '有货',
      priceTitle: '价格', sampleTitle: '样品', getSample: '获取样品',
      addToCart: '发送询盘', chatWhatsapp: 'WhatsApp 咨询',
      highlights: '产品亮点', specs: '关键属性',
      supplier: '供应商信息', verified: '认证供应商', responseTime: '响应时间',
      rating: '评分', transactions: '成交记录', years: '年限',
      customization: '定制选项', oemTitle: 'OEM / ODM 服务',
      packaging: '包装与物流', from: '发货地', leadTime: '交期',
      applications: '应用场景', description: '详细描述',
      inquiry: '发送询盘', inquiryTitle: '获取该产品报价',
      name: '您的姓名 *', email: '邮箱 *', company: '公司', country: '国家/地区',
      quantity: '数量（件）', message: '留言 *', submit: '提交询盘',
      successTitle: '感谢您的询盘！', successText: '您的询盘已生成，我们将在24小时内回复您。',
      related: '该类别更多产品', viewAll: '查看全部',
      trustShip: '发货地', trustLead: '交期', trustPack: '包装',
      noVideo: '视频即将上线', homeAlias: '首页',
      getQuote: '获取报价', customLogo: '定制Logo', customColor: '定制颜色',
      customPackage: '定制包装', customOEM: '支持OEM', customODM: '支持ODM',
      sampleLead: '样品交期', productionLead: '大货交期',
      certTitle: '认证资质', currency: 'US $', per: '/ 件',
      dayUnit: '天', inqProduct: '产品', inqModel: '型号',
      whatsappText: '您好，我对以下产品感兴趣'
    }
  };

  // RTL languages
  var RTL = { ar: true };

  // ---------- Helpers ----------
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function pick(obj, lang) {
    if (obj == null) return '';
    if (typeof obj === 'string') return obj;
    return obj[lang] || obj.en || '';
  }
  function iconFor(name) {
    var icons = {
      laser: '◎', mop: '💧', map: '🗺', battery: '🔋', power: '⚡', quiet: '🔇',
      filter: '🌀', app: '📱', auto: '🤖', edge: '🧹', pet: '🐾', eco: '🌿',
      smart: '🧠', dust: '🧺', sweep: '🔄', wet: '💦', climb: '⛰', wifi: '📶',
      clean: '✨', charge: '🔌', voice: '🎙', zone: '▦', spot: '🎯', timer: '⏱'
    };
    return icons[name] || '✓';
  }

  // ---------- State ----------
  var state = {
    data: null,
    product: null,
    lang: LANG,
    selectedSku: {},
    currentMedia: 0
  };

  // ---------- Load data ----------
  function loadData() {
    if (!CATEGORY) { showError('Missing category config'); return; }
    var url = 'data/products/' + CATEGORY + '.json';
    // try absolute path fallback
    var xhr = new XMLHttpRequest();
    xhr.open('GET', url, true);
    xhr.onload = function () {
      if (xhr.status >= 200 && xhr.status < 300) {
        try { render(JSON.parse(xhr.responseText)); }
        catch (e) { showError('Data parse error: ' + e.message); }
      } else {
        // retry with absolute path
        var xhr2 = new XMLHttpRequest();
        xhr2.open('GET', '/data/products/' + CATEGORY + '.json', true);
        xhr2.onload = function () {
          try { render(JSON.parse(xhr2.responseText)); }
          catch (e) { showError('Failed to load product data'); }
        };
        xhr2.onerror = function () { showError('Failed to load product data'); };
        xhr2.send();
      }
    };
    xhr.onerror = function () { showError('Failed to load product data'); };
    xhr.send();
  }

  function showError(msg) {
    var mount = $('#aqc-detail-mount');
    if (mount) mount.innerHTML = '<div class="d-loading"><p>⚠️ ' + esc(msg) + '</p></div>';
  }

  // ---------- Build price ladder from data ----------
  function buildPriceLadder(p) {
    var ladder = p.price_ladder || [];
    if (!ladder.length && p.price_indicator) {
      var lo = p.price_indicator.min || 95;
      var hi = p.price_indicator.max || 165;
      var mid = Math.round((lo + hi) / 2);
      ladder = [
        { min: p.moq ? p.moq.value : 10, max: 499, price: hi },
        { min: 500, max: 999, price: mid },
        { min: 1000, max: null, price: lo }
      ];
    }
    return ladder;
  }

  // ---------- Render ----------
  function render(data) {
    state.data = data;
    var products = (data && data.products) || [];
    var product = products[0];
    if (PRODUCT_ID) {
      for (var i = 0; i < products.length; i++) {
        if (products[i].id === PRODUCT_ID) { product = products[i]; break; }
      }
    }
    if (!product) { showError('Product not found'); return; }
    state.product = product;
    state.product = product;

    var mount = $('#aqc-detail-mount');
    if (!mount) return;
    var ui = UI[state.lang] || UI.en;
    var isRTL = !!RTL[state.lang];
    if (isRTL) mount.setAttribute('dir', 'rtl');

    // images: from product.images; fallback to category image
    var images = (product.images && product.images.length) ? product.images : [];
    var hasVideo = !!(product.video_url);

    var ladder = buildPriceLadder(product);
    var moq = (product.moq && product.moq.value) || 10;

    // sku
    var skus = product.sku || [];
    var quick = (product.quick_specs || []).slice(0, 4);

    var certs = product.certifications || [];
    var highlights = product.highlights || [];
    var specs = product.specs || [];
    var packaging = product.packaging || {};
    var customization = product.customization || {};
    var apps = (product.applications && pick(product.applications, state.lang)) || '';

    // supplier stats
    var rating = product.supplier_rating || '4.8';
    var responseTime = product.response_time || '≤ 2h';
    var transactions = product.transactions || 'US $100K+';
    var years = product.years || '10+';

    var html = '';

    // ===== BREADCRUMB =====
    html += '<div class="d-breadcrumb"><div class="d-breadcrumb-inner">';
    html += '<a href="' + (state.lang === 'zh' ? '../zh/index.html' : '../index.html') + '">' + esc(ui.home) + '</a>';
    html += '<span class="sep">›</span>';
    html += '<a href="' + (state.lang === 'zh' ? '../zh/' + CATEGORY + '/index.html' : '../' + CATEGORY + '/index.html') + '">' + esc(CATEGORY_NAME || pick(data.category_name, state.lang) || CATEGORY) + '</a>';
    html += '<span class="sep">›</span>';
    html += '<span>' + esc(pick(product.name, state.lang)) + '</span>';
    html += '</div></div>';

    // ===== MAIN LAYOUT =====
    html += '<div class="d-layout">';

    // --- Gallery ---
    html += '<div class="d-gallery">';
    html += '<div class="d-gallery-main" id="aqc-gallery-main">';
    if (images.length) {
      html += '<img src="' + esc(images[0]) + '" alt="' + esc(pick(product.name, state.lang)) + '" id="aqc-main-img">';
    } else {
      html += '<div class="d-loading">No image</div>';
    }
    if (hasVideo) {
      html += '<div class="d-gallery-video" id="aqc-video-box"><video id="aqc-video" controls playsinline></video></div>';
    }
    html += '</div>';
    if (images.length > 1 || hasVideo) {
      html += '<div class="d-gallery-thumbs">';
      for (var gi = 0; gi < images.length; gi++) {
        html += '<div class="d-gallery-thumb' + (gi === 0 ? ' active' : '') + '" data-idx="' + gi + '"><img src="' + esc(images[gi]) + '" alt=""></div>';
      }
      if (hasVideo) {
        html += '<div class="d-gallery-thumb video-thumb" data-video="1">▶</div>';
      }
      html += '</div>';
    }
    html += '</div>';

    // --- Info panel ---
    html += '<div class="d-info">';
    html += '<div class="d-model">' + esc(ui.model) + ': <b>' + esc(product.id.toUpperCase()) + '</b></div>';
    html += '<h1>' + esc(pick(product.name, state.lang)) + '</h1>';
    html += '<p class="d-tagline">' + esc(pick(product.tagline, state.lang)) + '</p>';

    // certs
    if (certs.length) {
      html += '<div class="d-certs">';
      html += '<span class="d-cert-badge">🛡 ' + esc(ui.certTitle) + '</span>';
      for (var ci = 0; ci < certs.length; ci++) {
        html += '<span class="d-cert-badge"><span class="cert-star">★</span> ' + esc(certs[ci]) + '</span>';
      }
      html += '</div>';
    }

    // quick specs
    if (quick.length) {
      html += '<div class="d-quick-specs">';
      for (var qi = 0; qi < quick.length; qi++) {
        var q = quick[qi];
        html += '<span class="d-quick-spec">' + esc(pick(q.label, state.lang)) + ': <b>' + esc(q.value) + '</b></span>';
      }
      html += '</div>';
    }

    // price ladder
    if (ladder.length) {
      html += '<div class="d-price-block">';
      html += '<div class="d-price-label" style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:#64748B;margin-bottom:4px;">' + esc(ui.priceTitle) + '</div>';
      for (var li = 0; li < ladder.length; li++) {
        var l = ladder[li];
        var rangeStr = (l.max == null || l.max === -1) ? l.min + '+' : l.min + '–' + l.max;
        html += '<div class="d-price-row"><span class="range">' + esc(rangeStr) + ' ' + esc(ui.per) + '</span><span class="price">' + esc(ui.currency) + l.price + '</span></div>';
      }
      html += '<div class="d-price-moq">' + esc(ui.moq) + ': <b>' + moq + ' ' + esc(ui.per) + '</b> · ' + esc(ui.inStock) + '</div>';
      html += '</div>';
    }

    // SKU selector
    if (skus.length) {
      for (var si = 0; si < skus.length; si++) {
        var skuGroup = skus[si];
        html += '<div class="d-sku">';
        html += '<div class="d-sku-title">' + esc(pick(skuGroup.name, state.lang)) + ': <span id="aqc-sku-val-' + si + '"></span></div>';
        html += '<div class="d-sku-opts">';
        var vals = skuGroup.values || [];
        for (var vi = 0; vi < vals.length; vi++) {
          var v = vals[vi];
          var swatch = v.color ? '<span class="swatch" style="background:' + esc(v.color) + '"></span>' : '';
          html += '<div class="d-sku-opt' + (vi === 0 ? ' active' : '') + '" data-group="' + si + '" data-val="' + esc(v.name) + '">' + swatch + esc(v.name) + '</div>';
        }
        html += '</div></div>';
        // set initial
        state.selectedSku[si] = (vals[0] && vals[0].name) || '';
        var el = $('#aqc-sku-val-' + si, mount);
        if (el) el.textContent = state.selectedSku[si];
      }
    }

    // highlights
    if (highlights.length) {
      html += '<div class="d-highlights">';
      html += '<div class="d-highlights-title">' + esc(ui.highlights) + '</div>';
      for (var hi = 0; hi < highlights.length; hi++) {
        var h = highlights[hi];
        html += '<div class="d-highlight-item"><span class="ico">' + iconFor(h.icon) + '</span><span>' + esc(pick(h.text, state.lang)) + '</span></div>';
      }
      html += '</div>';
    }

    // CTA
    var productName = pick(product.name, state.lang);
    var waNumber = '8617779190118';
    var waMsg = encodeURIComponent(ui.whatsappText + ': ' + productName + ' (' + product.id.toUpperCase() + ')');
    var subject = encodeURIComponent('[Inquiry] ' + productName);
    html += '<div class="d-cta">';
    html += '<a class="btn btn-primary" href="#aqc-inquiry">✉️ ' + esc(ui.addToCart) + '</a>';
    html += '<a class="btn btn-whatsapp" href="https://wa.me/' + waNumber + '?text=' + waMsg + '" target="_blank" rel="noopener">💬 ' + esc(ui.chatWhatsapp) + '</a>';
    if (product.sample && product.sample.enabled !== false) {
      html += '<button class="btn btn-secondary" id="aqc-sample-btn">🧪 ' + esc(ui.getSample) + '</button>';
    }
    html += '</div>';

    // trust strip
    html += '<div class="d-trust">';
    html += '<div class="d-trust-item"><div class="t-ico">🚢</div><div class="t-label">' + esc(ui.trustShip) + '</div><div class="t-value">' + esc((product.ship_from || {}).en || 'Ningbo, China') + '</div></div>';
    var leadTime = (product.customization && product.customization.production_lead) || '25-35 days';
    html += '<div class="d-trust-item"><div class="t-ico">⏱</div><div class="t-label">' + esc(ui.trustLead) + '</div><div class="t-value">' + esc(leadTime) + '</div></div>';
    html += '<div class="d-trust-item"><div class="t-ico">📦</div><div class="t-label">' + esc(ui.trustPack) + '</div><div class="t-value">' + esc((packaging.unit || 'Color box')) + '</div></div>';
    html += '</div>';

    html += '</div>'; // .d-info
    html += '</div>'; // .d-layout

    // ===== SUPPLIER SECTION =====
    html += '<div class="d-section d-section-alt"><div class="d-section-inner">';
    html += '<span class="d-sec-label">' + esc(ui.supplier) + '</span>';
    html += '<h2 class="d-sec-title">' + esc(ui.supplier) + '</h2>';
    html += '<div class="d-supplier">';
    html += '<div class="d-supplier-logo">🏠</div>';
    html += '<div>';
    html += '<h3 class="d-supplier-name">AquaClean Home Appliances Co., Ltd.</h3>';
    html += '<p class="d-supplier-meta">Ningbo, Zhejiang, China · OEM/ODM Manufacturer · <span class="d-supplier-stars">★★★★★</span> ' + esc(rating) + '</p>';
    html += '<div class="d-supplier-stats">';
    html += '<div class="d-supplier-stat"><div class="v">' + esc(rating) + '</div><div class="l">' + esc(ui.rating) + '</div></div>';
    html += '<div class="d-supplier-stat"><div class="v">' + esc(responseTime) + '</div><div class="l">' + esc(ui.responseTime) + '</div></div>';
    html += '<div class="d-supplier-stat"><div class="v">' + esc(transactions) + '</div><div class="l">' + esc(ui.transactions) + '</div></div>';
    html += '<div class="d-supplier-stat"><div class="v">' + esc(years) + '</div><div class="l">' + esc(ui.years) + '</div></div>';
    html += '</div></div>';
    html += '<div class="d-supplier-side"><span class="d-supplier-verified">✔ ' + esc(ui.verified) + '</span></div>';
    html += '</div>';
    html += '</div></div>';

    // ===== KEY ATTRIBUTES =====
    if (specs.length) {
      html += '<div class="d-section"><div class="d-section-inner">';
      html += '<span class="d-sec-label">' + esc(ui.specs) + '</span>';
      html += '<h2 class="d-sec-title">' + esc(ui.specs) + '</h2>';
      html += '<div class="d-attr-grid">';
      for (var spi = 0; spi < specs.length; spi++) {
        var sp = specs[spi];
        html += '<div class="d-attr-item"><span class="d-attr-name">' + esc(pick(sp.label, state.lang)) + '</span><span class="d-attr-value">' + esc(sp.value) + '</span></div>';
      }
      html += '</div>';
      html += '</div></div>';
    }

    // ===== PACKAGING =====
    html += '<div class="d-section d-section-alt"><div class="d-section-inner">';
    html += '<span class="d-sec-label">' + esc(ui.packaging) + '</span>';
    html += '<h2 class="d-sec-title">' + esc(ui.packaging) + '</h2>';
    html += '<table class="d-spec-table"><thead><tr><th>' + esc(ui.packaging) + '</th><th></th></tr></thead><tbody>';
    html += '<tr><td class="spec-label">' + esc(ui.trustPack) + '</td><td>' + esc(packaging.unit || '—') + '</td></tr>';
    html += '<tr><td class="spec-label">Carton Size</td><td>' + esc(packaging.ctn_size || '—') + '</td></tr>';
    html += '<tr><td class="spec-label">Qty / Carton</td><td>' + esc(packaging.ctn_qty || '—') + '</td></tr>';
    html += '<tr><td class="spec-label">Gross Weight</td><td>' + esc(packaging.gross_weight || '—') + '</td></tr>';
    html += '<tr><td class="spec-label">' + esc(ui.trustShip) + '</td><td>' + esc((product.ship_from || {}).en || 'Ningbo, China') + '</td></tr>';
    html += '<tr><td class="spec-label">' + esc(ui.leadTime) + '</td><td>' + esc(leadTime) + '</td></tr>';
    html += '</tbody></table>';
    html += '</div></div>';

    // ===== CUSTOMIZATION =====
    html += '<div class="d-section"><div class="d-section-inner">';
    html += '<span class="d-sec-label">' + esc(ui.customization) + '</span>';
    html += '<h2 class="d-sec-title">' + esc(ui.oemTitle) + '</h2>';
    html += '<div class="d-oem-grid">';
    var oemItems = [
      { k: 'oem', label: ui.customOEM }, { k: 'odm', label: ui.customODM },
      { k: 'logo', label: ui.customLogo }, { k: 'color', label: ui.customColor },
      { k: 'package', label: ui.customPackage }
    ];
    for (var oi = 0; oi < oemItems.length; oi++) {
      var ok = oemItems[oi].k;
      var enabled = customization[ok] !== false;
      if (enabled) {
        html += '<div class="d-oem-item"><span class="d-oem-check">✓</span>' + esc(oemItems[oi].label) + '</div>';
      }
    }
    html += '</div>';
    if (customization.sample_lead || customization.production_lead) {
      html += '<div style="display:flex;gap:24px;flex-wrap:wrap;margin-top:24px;font-size:14px;color:#64748B;">';
      if (customization.sample_lead) html += '<span>🧪 ' + esc(ui.sampleLead) + ': <b style="color:#0F172A;">' + esc(customization.sample_lead) + '</b></span>';
      if (customization.production_lead) html += '<span>🏭 ' + esc(ui.productionLead) + ': <b style="color:#0F172A;">' + esc(customization.production_lead) + '</b></span>';
      html += '</div>';
    }
    html += '</div></div>';

    // ===== APPLICATIONS =====
    if (apps) {
      html += '<div class="d-section d-section-alt"><div class="d-section-inner">';
      html += '<span class="d-sec-label">' + esc(ui.applications) + '</span>';
      html += '<h2 class="d-sec-title">' + esc(ui.applications) + '</h2>';
      html += '<div class="d-app-chips">';
      var appList = apps.split(',').map(function (s) { return s.trim(); });
      for (var ai = 0; ai < appList.length; ai++) {
        html += '<span class="d-app-chip">' + esc(appList[ai]) + '</span>';
      }
      html += '</div>';
      html += '</div></div>';
    }

    // ===== DESCRIPTION =====
    var descText = pick(product.description, state.lang);
    var descImg = product.description_image || '';
    if (descText || descImg) {
      html += '<div class="d-section"><div class="d-section-inner">';
      html += '<span class="d-sec-label">' + esc(ui.description) + '</span>';
      html += '<h2 class="d-sec-title">' + esc(ui.description) + '</h2>';
      html += '<div class="d-desc-text">' + esc(descText).replace(/\n/g, '<br>') + '</div>';
      if (descImg) html += '<img class="d-desc-img" src="' + esc(descImg) + '" alt="' + esc(pick(product.name, state.lang)) + '">';
      html += '</div></div>';
    }

    // ===== INQUIRY FORM =====
    html += '<div class="d-section d-section-alt" id="aqc-inquiry"><div class="d-section-inner">';
    html += '<span class="d-sec-label">' + esc(ui.inquiry) + '</span>';
    html += '<h2 class="d-sec-title" style="text-align:center;">' + esc(ui.inquiryTitle) + '</h2>';
    html += '<div class="d-form-card">';
    html += '<div class="d-form-row">';
    html += '<div class="d-form-field"><label>' + esc(ui.inqProduct) + '</label><input type="text" value="' + esc(productName) + '" readonly></div>';
    html += '<div class="d-form-field"><label>' + esc(ui.inqModel) + '</label><input type="text" value="' + esc(product.id.toUpperCase()) + '" readonly></div>';
    html += '<div class="d-form-field"><label>' + esc(ui.name) + '</label><input type="text" id="aqc-f-name" placeholder="John Smith"></div>';
    html += '<div class="d-form-field"><label>' + esc(ui.email) + '</label><input type="email" id="aqc-f-email" placeholder="name@company.com"></div>';
    html += '<div class="d-form-field"><label>' + esc(ui.company) + '</label><input type="text" id="aqc-f-company" placeholder="Company Ltd."></div>';
    html += '<div class="d-form-field"><label>' + esc(ui.country) + '</label><input type="text" id="aqc-f-country" placeholder="Germany"></div>';
    html += '<div class="d-form-field"><label>' + esc(ui.quantity) + '</label><input type="number" id="aqc-f-qty" value="' + moq + '" min="1"></div>';
    html += '<div class="d-form-field"><label>' + esc(ui.message) + '</label><textarea id="aqc-f-msg" placeholder="Tell us your requirements..."></textarea></div>';
    html += '</div>';
    html += '<div style="text-align:center;margin-top:8px;">';
    html += '<button class="btn btn-primary" id="aqc-submit" style="min-width:240px;">✉️ ' + esc(ui.submit) + '</button>';
    html += '</div>';
    html += '<div class="d-form-success" id="aqc-form-success"><div class="ico">✅</div><h3>' + esc(ui.successTitle) + '</h3><p>' + esc(ui.successText) + '</p></div>';
    html += '</div>';
    html += '</div></div>';

    // ===== RELATED =====
    if (products.length > 1) {
      html += '<div class="d-section"><div class="d-section-inner">';
      html += '<span class="d-sec-label">' + esc(ui.related) + '</span>';
      html += '<h2 class="d-sec-title">' + esc(ui.related) + '</h2>';
      html += '<div class="d-related-grid">';
      for (var ri = 1; ri < products.length && ri < 4; ri++) {
        var rp = products[ri];
        var rImg = (rp.images && rp.images[0]) || '';
        html += '<a class="d-related-card" href="' + (state.lang === 'zh' ? '../zh/' + CATEGORY + '-' + rp.id + '.html' : '../' + CATEGORY + '-' + rp.id + '.html') + '">';
        html += '<div class="d-related-img">' + (rImg ? '<img src="' + esc(rImg) + '" alt="">' : '') + '</div>';
        html += '<div class="d-related-body"><h4>' + esc(pick(rp.name, state.lang)) + '</h4><p>' + esc(pick(rp.tagline, state.lang)) + '</p></div>';
        html += '</a>';
      }
      html += '</div>';
      html += '</div></div>';
    }

    mount.innerHTML = html;

    // ---------- Wire events ----------
    // Gallery thumbs
    $$('.d-gallery-thumb', mount).forEach(function (th) {
      th.addEventListener('click', function () {
        $$('.d-gallery-thumb', mount).forEach(function (x) { x.classList.remove('active'); });
        th.classList.add('active');
        var videoBox = $('#aqc-video-box', mount);
        var mainImg = $('#aqc-main-img', mount);
        if (th.dataset.video) {
          if (videoBox) {
            videoBox.classList.add('show');
            var vid = $('#aqc-video', mount);
            if (vid && state.product.video_url) { vid.src = state.product.video_url; vid.play(); }
          }
          if (mainImg) mainImg.style.display = 'none';
        } else {
          if (videoBox) { videoBox.classList.remove('show'); var vid2 = $('#aqc-video', mount); if (vid2) vid2.pause(); }
          if (mainImg) { mainImg.style.display = ''; mainImg.src = th.querySelector('img').src; }
        }
      });
    });

    // SKU options
    $$('.d-sku-opt', mount).forEach(function (opt) {
      opt.addEventListener('click', function () {
        var g = opt.dataset.group;
        $$('.d-sku-opt[data-group="' + g + '"]', mount).forEach(function (x) { x.classList.remove('active'); });
        opt.classList.add('active');
        state.selectedSku[g] = opt.dataset.val;
        var valEl = $('#aqc-sku-val-' + g, mount);
        if (valEl) valEl.textContent = opt.dataset.val;
      });
    });

    // Sample button -> scroll to inquiry, set qty to sample qty
    var sampleBtn = $('#aqc-sample-btn', mount);
    if (sampleBtn) {
      sampleBtn.addEventListener('click', function () {
        var qtyField = $('#aqc-f-qty', mount);
        if (qtyField && state.product.sample) qtyField.value = state.product.sample.qty || 5;
        var inquiry = $('#aqc-inquiry', mount);
        if (inquiry) inquiry.scrollIntoView({ behavior: 'smooth' });
      });
    }

    // Submit -> build mailto + whatsapp, show success
    var submit = $('#aqc-submit', mount);
    if (submit) {
      submit.addEventListener('click', function () {
        var name = ($('#aqc-f-name', mount) || {}).value || '';
        var email = ($('#aqc-f-email', mount) || {}).value || '';
        var company = ($('#aqc-f-company', mount) || {}).value || '';
        var country = ($('#aqc-f-country', mount) || {}).value || '';
        var qty = ($('#aqc-f-qty', mount) || {}).value || moq;
        var msg = ($('#aqc-f-msg', mount) || {}).value || '';
        var skuStr = '';
        for (var k in state.selectedSku) { if (state.selectedSku[k]) skuStr += ', ' + state.selectedSku[k]; }
        var body = 'Product: ' + productName + ' (' + product.id.toUpperCase() + ')' + skuStr + '\n' +
                   'Quantity: ' + qty + ' pieces\n' +
                   'Name: ' + name + '\n' +
                   'Company: ' + company + '\n' +
                   'Country: ' + country + '\n' +
                   'Email: ' + email + '\n\n' +
                   'Message: ' + msg;
        var mailto = 'mailto:info@aquaclean-home.com?subject=' + subject + '&body=' + encodeURIComponent(body);
        window.location.href = mailto;
        var success = $('#aqc-form-success', mount);
        var card = $('.d-form-card', mount);
        if (success && card) {
          card.style.display = 'none';
          success.classList.add('show');
        }
      });
    }
  }

  // ---------- Init ----------
  document.addEventListener('DOMContentLoaded', loadData);
})();
