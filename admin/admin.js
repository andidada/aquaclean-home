/**
 * AquaClean Admin — Product Manager + Homepage CMS
 * All functions defined FIRST (IIFE hoisting-safe), event binding at END
 */
(function () {
  'use strict';

  // ── Utilities ──────────────────────────────────────────────────
  function $(id) { return document.getElementById(id); }
  function qsa(sel) { return [].slice.call(document.querySelectorAll(sel)); }

  function setStatus(msg) {
    var el = $('status');
    if (el) el.textContent = msg;
  }

  function slugify(s) {
    return String(s || '').toLowerCase()
      .replace(/[^\w\s-]/g, '')
      .replace(/[\s_-]+/g, '-')
      .replace(/^-+|-+$/g, '');
  }

  function sk(tab, lang, cat) {
    return 'aqc_' + tab + '_' + lang + (cat ? '_' + cat : '');
  }

  // ── Data ───────────────────────────────────────────────────────
  var LANGS = [
    { code:'en', label:'English' },
    { code:'zh', label:'中文' },
    { code:'es', label:'Español' },
    { code:'fr', label:'Français' },
    { code:'ar', label:'العربية' },
    { code:'id', label:'Indonesia' },
    { code:'ru', label:'Русский' },
    { code:'th', label:'ไทย' },
    { code:'vi', label:'Tiếng Việt' },
  ];

  var CATS = [
    { slug:'handheld-vacuum',      label:'手持吸尘器',     enLabel:'Handheld Vacuum Cleaner' },
    { slug:'robot-vacuum',         label:'扫地机器人',      enLabel:'Robot Vacuum Cleaner' },
    { slug:'steam-cleaner',        label:'蒸汽清洁器',      enLabel:'Steam Cleaner' },
    { slug:'uv-mite-remover',      label:'除螨仪',         enLabel:'UV Mite Remover' },
    { slug:'window-cleaner-robot', label:'擦窗机器人',     enLabel:'Window Cleaner Robot' },
    { slug:'car-vacuum',           label:'车载吸尘器',      enLabel:'Car Vacuum Cleaner' },
    { slug:'tire-inflator',        label:'轮胎充气泵',      enLabel:'Digital Tire Inflator' },
    { slug:'coffee-machine',       label:'咖啡机',          enLabel:'Espresso Coffee Machine' },
    { slug:'upright-steam-mop',   label:'立式蒸汽拖把',    enLabel:'Upright Steam Mop' },
  ];

  var CERT_OPTS = ['CE','CB','ETL','FCC','RoHS','REACH','PSE','CCC','KC','BIS'];

  // ── State ──────────────────────────────────────────────────────
  var activeTab  = 'product';
  var currentCat  = null;
  var currentLang = null;
  var currentPid  = null;

  // ── HTML builders ──────────────────────────────────────────────
  function fieldHTML(label, id, type, value) {
    var t = type === 'textarea'
      ? '<textarea id="' + id + '" rows="3">' + (value || '') + '</textarea>'
      : '<input id="' + id + '" type="text" value="' + (value || '') + '">';
    return '<div class="admin-field"><label>' + label + '</label>' + t + '</div>';
  }

  function fieldHTML_note(label, id, type, value, note) {
    var noteHtml = note ? '<div style="font-size:11px;color:#94A3B8;margin-top:3px;">' + note + '</div>' : '';
    var t = type === 'textarea'
      ? '<textarea id="' + id + '" rows="3">' + (value || '') + '</textarea>'
      : '<input id="' + id + '" type="text" value="' + (value || '') + '">';
    return '<div class="admin-field" style="margin-bottom:18px;"><label>' + label + '</label>' + t + noteHtml + '</div>';
  }

  function makeSec(title, html) {
    var d = document.createElement('div');
    d.className = 'admin-sec';
    var h3 = document.createElement('h3');
    h3.textContent = title;
    d.appendChild(h3);
    if (typeof html === 'string') {
      d.innerHTML += html;
    } else if (html) {
      d.appendChild(html);
    }
    return d;
  }

  function makeGrid(html) {
    var d = document.createElement('div');
    d.className = 'admin-grid';
    d.innerHTML = html;
    return d;
  }

  // ── Product form ───────────────────────────────────────────────
  function renderProductForm(data) {
    var f = $('formArea');
    if (!f) return;
    f.innerHTML = '';

    // Basic
    f.appendChild(makeSec('基本信息', makeGrid(
      fieldHTML('产品名称 *', 'p-name', 'text', data.name || '') +
      fieldHTML('型号', 'p-model', 'text', data.model || '') +
      fieldHTML('产品标签语', 'p-tagline', 'text', data.tagline || '')
    )));

    // Specs
    f.appendChild(makeSec('核心参数', makeGrid(
      fieldHTML('功率', 'p-power', 'text', data.power || '') +
      fieldHTML('吸力', 'p-suction', 'text', data.suction || '') +
      fieldHTML('电池/续航', 'p-battery', 'text', data.battery || '') +
      fieldHTML('重量', 'p-weight', 'text', data.weight || '')
    )));

    // Pricing
    f.appendChild(makeSec('价格阶梯（USD）', makeGrid(
      fieldHTML('价格区间文字', 'p-price_display', 'text', data.price_display || '') +
      fieldHTML('MOQ（最小起订量）', 'p-moq', 'text', String(data.moq || 200)) +
      fieldHTML('FOB 单价（≥MOQ）', 'p-fob_price', 'text', data.fob_price || '') +
      fieldHTML('货币单位', 'p-currency', 'text', data.currency || 'USD')
    )));

    // SKU
    f.appendChild(makeSec('SKU 规格', makeGrid(
      fieldHTML('颜色（逗号分隔）', 'p-colors', 'text', (data.colors||[]).join(', ')) +
      fieldHTML('包装规格', 'p-package', 'text', data.package || '') +
      fieldHTML('单件体积/重量', 'p-dims', 'text', data.dims || '')
    )));

    // Certs
    var certDiv = document.createElement('div');
    certDiv.className = 'admin-field';
    certDiv.innerHTML = '<label>认证（多选）</label>';
    var certWrap = document.createElement('div');
    certWrap.style.cssText = 'display:flex;flex-wrap:wrap;gap:8px;margin-top:6px;';
    CERT_OPTS.forEach(function(c) {
      var lbl = document.createElement('label');
      lbl.style.cssText = 'display:inline-flex;align-items:center;gap:4px;font-size:13px;padding:5px 10px;border:1px solid #E2E8F0;border-radius:6px;cursor:pointer;background:#F8FAFC;';
      lbl.innerHTML = '<input type="checkbox" value="' + c + '" style="width:auto;">' + c;
      if (data.certifications && data.certifications.indexOf(c) > -1) {
        lbl.querySelector('input').checked = true;
      }
      certWrap.appendChild(lbl);
    });
    certDiv.appendChild(certWrap);
    f.appendChild(makeSec('认证', certDiv));

    // Media
    var imgSec = document.createElement('div');
    imgSec.className = 'admin-sec';
    imgSec.innerHTML = '<h3>产品图片</h3>' +
      '<div id="p-img-drop" class="admin-drop">📁 拖放图片或粘贴 URL（每行一个）</div>' +
      '<textarea id="p-img-urls" rows="3" placeholder="https://...&#10;https://..." style="width:100%;margin-top:8px;"></textarea>' +
      '<div id="p-img-preview" class="admin-imgs" style="margin-top:8px;"></div>';
    f.appendChild(imgSec);
    $('p-img-urls').value = (data.images||[]).join('\n');
    $('p-img-urls').addEventListener('input', renderImgPreview);
    renderImgPreview();

    // Tags
    f.appendChild(makeSec('产品卖点（逗号分隔）', '<textarea id="p-tags" rows="2">' + ((data.tags||[]).join(', ')) + '</textarea>'));

    // Specs table
    var specsLines = (data.specs||[]).map(function(s){
      var k = s.key || (typeof s.label === 'object' ? (s.label.en || s.label.zh || '') : (s.label || ''));
      var v = (typeof s.value === 'object' ? (s.value.en || s.value.zh || '') : s.value) || '';
      return k + '|' + v;
    }).join('\n');
    f.appendChild(makeSec('规格参数表格（每行：参数|值）', '<textarea id="p-specs" rows="8" style="width:100%;font-family:monospace;" placeholder="Power|120W&#10;Suction|16KPa">' + specsLines + '</textarea>'));

    // Packaging
    f.appendChild(makeSec('包装内容（逗号分隔）', '<textarea id="p-packaging" rows="2">' + (Array.isArray(data.packaging) ? data.packaging.join(', ') : (data.packaging || '')) + '</textarea>'));

    // Applications
    f.appendChild(makeSec('适用场景（逗号分隔）', '<textarea id="p-applications" rows="2">' + (Array.isArray(data.applications) ? data.applications.join(', ') : (data.applications || '')) + '</textarea>'));;

    // Supplier
    f.appendChild(makeSec('供应商信息', makeGrid(
      fieldHTML('公司名', 'p-company', 'text', data.company||'') +
      fieldHTML('地址', 'p-address', 'text', data.address||'')
    )));

    // Customization
    f.appendChild(makeSec('定制能力', makeGrid(
      fieldHTML('Logo 定制', 'p-logo', 'text', data.logo||'') +
      fieldHTML('包装定制', 'p-packaging_custom', 'text', data.packaging_custom||'')
    )));

    // Description
    f.appendChild(makeSec('产品描述（Alibaba 风格英文）', '<textarea id="p-desc" rows="5">' + (data.description||'') + '</textarea>'));

    // Actions
    var actions = document.createElement('div');
    actions.style.marginTop = '24px';
    actions.className = 'admin-actions';
    actions.innerHTML =
      '<button class="btn btn-primary" id="p-save">💾 保存草稿</button>' +
      '<button class="btn btn-outline" id="p-export">📤 导出 JSON</button>' +
      '<button class="btn btn-outline" id="p-import">📥 导入 JSON</button>' +
      '<button class="btn btn-outline" id="p-reset">🗑 清空</button>';
    f.appendChild(actions);

    $('p-save').onclick   = saveProduct;
    $('p-export').onclick = exportProduct;
    $('p-import').onclick = function() { $('importFile').click(); };
    $('p-reset').onclick  = function() { if(confirm('确认清空？')) renderProductForm({}); };
    $('importFile').onchange = importProduct;

    qsa('#formArea input, #formArea textarea').forEach(function(el){ el.addEventListener('input', autoSaveProduct); });
  }

  function renderImgPreview() {
    var container = $('p-img-preview');
    if (!container) return;
    container.innerHTML = '';
    var urls = ($('p-img-urls').value||'').split('\n').filter(function(u){return u.trim();});
    urls.forEach(function(url, idx) {
      var div = document.createElement('div');
      div.className = 'admin-img';
      div.style.cssText = 'position:relative;display:inline-block;';
      var img = document.createElement('img');
      img.src = url.trim();
      img.style.cssText = 'max-width:120px;max-height:90px;border-radius:4px;';
      img.onerror = function(){ this.parentElement.style.opacity='0.3'; };
      var rm = document.createElement('button');
      rm.className = 'x';
      rm.textContent = '×';
      rm.style.cssText = 'position:absolute;top:2px;right:2px;background:rgba(0,0,0,0.5);color:#fff;border:none;border-radius:50%;width:20px;height:20px;cursor:pointer;';
      rm.onclick = function() {
        var lines = ($('p-img-urls').value||'').split('\n');
        lines.splice(idx, 1);
        $('p-img-urls').value = lines.join('\n');
        renderImgPreview();
        autoSaveProduct();
      };
      div.appendChild(img);
      div.appendChild(rm);
      container.appendChild(div);
    });
  }

  function collectProduct() {
    var specs_raw = ($('p-specs').value||'').split('\n').filter(Boolean);
    var specs = specs_raw.map(function(l){
      var p = l.split('|');
      return { key: (p[0]||'').trim(), value: (p[1]||'').trim() };
    }).filter(function(s){ return s.key && s.value; });
    var certs = [].slice.call(qsa('#p-certs input:checked')).map(function(cb){ return cb.value; });
    var images = ($('p-img-urls').value||'').split('\n').filter(function(u){return u.trim();});
    function val(id) { var e = $(id); return e ? e.value.trim() : ''; }
    return {
      id:           currentPid || ('p-' + Date.now()),
      slug:         currentCat,
      lang:         currentLang,
      name:         val('p-name'),
      model:        val('p-model'),
      tagline:      val('p-tagline'),
      power:        val('p-power'),
      suction:      val('p-suction'),
      battery:      val('p-battery'),
      weight:       val('p-weight'),
      price_display: val('p-price_display'),
      moq:          parseInt(val('p-moq')) || 200,
      fob_price:    val('p-fob_price'),
      currency:     val('p-currency'),
      colors:       val('p-colors').split(',').map(function(s){return s.trim();}).filter(Boolean),
      package:      val('p-package'),
      dims:         val('p-dims'),
      tags:         val('p-tags').split(',').map(function(s){return s.trim();}).filter(Boolean),
      specs:        specs,
      certifications: certs,
      packaging:    val('p-packaging').split(',').map(function(s){return s.trim();}).filter(Boolean),
      applications:  val('p-applications').split(',').map(function(s){return s.trim();}).filter(Boolean),
      company:      val('p-company'),
      address:      val('p-address'),
      logo:         val('p-logo'),
      packaging_custom: val('p-packaging_custom'),
      description:  val('p-desc'),
      images:       images,
      updated_at:   new Date().toISOString()
    };
  }

  function saveProduct() {
    var data = collectProduct();
    localStorage.setItem(sk('product', data.lang, currentCat), JSON.stringify(data));
    setStatus('💾 已保存草稿（刷新前请导出）');
  }

  function autoSaveProduct() {
    var data = collectProduct();
    localStorage.setItem(sk('product', data.lang, currentCat), JSON.stringify(data));
  }

  function exportProduct() {
    var data = collectProduct();
    var blob = new Blob([JSON.stringify(data, null, 2)], {type:'application/json'});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = (data.slug||'product') + '-' + (data.lang||'en') + '.json';
    a.click();
    setStatus('📤 已导出 JSON');
  }

  function importProduct() {
    var file = $('importFile').files[0];
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function(e) {
      try {
        var d = JSON.parse(e.target.result);
        if (d.hero || d.products) {
          importHomepage(d);
        } else {
          if (d.slug) { currentCat = d.slug; }
          renderProductForm(d);
          saveProduct();
          setStatus('📥 已导入产品 JSON');
        }
      } catch(err) {
        setStatus('❌ 解析失败：' + err.message);
      }
    };
    reader.readAsText(file);
    $('importFile').value = '';
  }

  // ── Homepage form ───────────────────────────────────────────────
  function renderHomeEditor(data, lang) {
    lang = lang || 'en';
    var f = $('formArea');
    if (!f) return;
    f.innerHTML = '';

    var h = data || {};
    var hero = h.hero || {};
    var products = h.products || [];
    var contact = h.contact || {};
    var footer = h.footer || {};

    // Hero
    var heroDiv = document.createElement('div');
    heroDiv.style.maxWidth = '680px';
    heroDiv.innerHTML =
      fieldHTML_note('徽章文字', 'h-badge', 'text', hero.badge||'', '如：🇨🇳 OEM / ODM Manufacturer · Since 2015') +
      fieldHTML_note('主标题 H1（保留 &lt;br&gt; 和 &lt;span&gt; 标签）', 'h-h1', 'textarea', hero.h1||'', '如：Smart Cleaning Appliances&lt;br&gt;Built for &lt;span&gt;Global Markets&lt;/span&gt;') +
      fieldHTML_note('副标题段落', 'h-sub', 'textarea', hero.sub||'') +
      fieldHTML('主按钮文字', 'h-btn1-text', 'text', hero.btn_primary_text||'') +
      fieldHTML('主按钮链接', 'h-btn1-href', 'text', hero.btn_primary_href||'#quote') +
      fieldHTML('次按钮文字', 'h-btn2-text', 'text', hero.btn_outline_text||'') +
      fieldHTML('次按钮链接', 'h-btn2-href', 'text', hero.btn_outline_href||'#products');
    f.appendChild(makeSec('🏠 Hero 区域', heroDiv.innerHTML));

    // Products
    var prodHTML = '<div id="h-prod-list">';
    for (var pi = 0; pi < 11; pi++) {
      var prod = products[pi] || {};
      var pid = prod.id || ('p'+(pi+1));
      prodHTML += '<div style="border:1px solid #E2E8F0;border-radius:8px;padding:14px;margin-bottom:14px;background:#F8FAFC;">' +
        '<div style="font-weight:700;margin-bottom:10px;color:#2563EB;">产品 ' + (pi+1) + ': ' + (prod.name||'?') + '</div>' +
        '<input type="hidden" id="hp-id-' + pi + '" value="' + pid + '">' +
        '<div class="admin-grid">' +
        fieldHTML('名称', 'hp-name-'+pi, 'text', prod.name||'') +
        fieldHTML('Slug（对应类目路径）', 'hp-slug-'+pi, 'text', prod.slug||'') +
        fieldHTML('描述', 'hp-desc-'+pi, 'textarea', prod.desc||'') +
        fieldHTML('图片路径', 'hp-img-'+pi, 'text', prod.img||'') +
        fieldHTML('按钮文字', 'hp-btn-'+pi, 'text', prod.btn_text||'') +
        fieldHTML('按钮链接', 'hp-href-'+pi, 'text', prod.btn_href||'') +
        fieldHTML('标签（逗号分隔）', 'hp-tags-'+pi, 'text', (prod.tags||[]).join(', ')) +
        '</div></div>';
    }
    prodHTML += '</div>';

    var actionBar = '<div style="margin-top:20px;">' +
      '<button class="btn btn-primary" id="h-save">💾 保存草稿</button> ' +
      '<button class="btn btn-outline" id="h-export">📤 导出 JSON</button> ' +
      '<button class="btn btn-outline" id="h-import-home">📥 导入 JSON</button> ' +
      '<a class="btn btn-outline" id="h-preview" href="/' + lang + '/?v=' + Date.now() + '" target="_blank" style="display:inline-block;text-decoration:none;">🔍 预览首页</a>' +
      '</div>' +
      '<div style="margin-top:20px;padding:14px;background:#EFF6FF;border-radius:8px;font-size:12px;color:#1E40AF;line-height:1.7;">' +
      '<b>📝 使用流程：</b><br>' +
      '1. 编辑内容 → 点「💾 保存草稿」<br>' +
      '2. 点「📤 导出 JSON」下载文件<br>' +
      '3. 将 JSON 内容更新到 GitHub 仓库的 <code>/data/pages/home/' + lang + '.json</code><br>' +
      '4. Push 到 GitHub → 等待约 2 分钟 → 访问预览链接验证' +
      '</div>';
    f.appendChild(makeSec('📦 产品卡片（11 个）', prodHTML + actionBar));

    // Contact
    var contactDiv = document.createElement('div');
    contactDiv.style.maxWidth = '680px';
    contactDiv.innerHTML =
      fieldHTML('联系区标题', 'h-c-h2', 'text', contact.h2||'') +
      fieldHTML('邮箱', 'h-c-email', 'text', contact.email||'') +
      fieldHTML('电话', 'h-c-phone', 'text', contact.phone||'') +
      fieldHTML('WhatsApp（数字，无+号）', 'h-c-whatsapp', 'text', contact.whatsapp||'') +
      fieldHTML('地址', 'h-c-address', 'text', contact.address||'') +
      fieldHTML('营业时间', 'h-c-hours', 'text', contact.hours||'');
    f.appendChild(makeSec('📞 联系区域', contactDiv.innerHTML));

    // Footer
    var footerDiv = document.createElement('div');
    footerDiv.style.maxWidth = '680px';
    footerDiv.innerHTML =
      fieldHTML('公司名称', 'h-f-name', 'text', footer.company_name||'') +
      fieldHTML('公司描述', 'h-f-desc', 'textarea', footer.description||'') +
      fieldHTML('页脚邮箱', 'h-f-email', 'text', footer.email||'') +
      fieldHTML('页脚电话', 'h-f-phone', 'text', footer.phone||'');
    f.appendChild(makeSec('🔻 页脚', footerDiv.innerHTML));

    // Auto-save
    qsa('#formArea input, #formArea textarea').forEach(function(el){ el.addEventListener('input', autoSaveHome); });

    // Wire buttons
    $('h-save').onclick = saveHome;
    $('h-export').onclick = exportHome;
    $('h-import-home').onclick = function() { $('importFile').click(); };
  }

  function collectHome() {
    var products = [];
    for (var pi = 0; pi < 11; pi++) {
      var tagsVal = $('hp-tags-'+pi) ? $('hp-tags-'+pi).value : '';
      products.push({
        id:       ($('hp-id-'+pi) ? $('hp-id-'+pi).value : '') || ('p'+(pi+1)),
        name:     ($('hp-name-'+pi) ? $('hp-name-'+pi).value : '').trim(),
        slug:     ($('hp-slug-'+pi) ? $('hp-slug-'+pi).value : '').trim(),
        desc:     ($('hp-desc-'+pi) ? $('hp-desc-'+pi).value : '').trim(),
        img:      ($('hp-img-'+pi) ? $('hp-img-'+pi).value : '').trim(),
        btn_text: ($('hp-btn-'+pi) ? $('hp-btn-'+pi).value : '').trim(),
        btn_href: ($('hp-href-'+pi) ? $('hp-href-'+pi).value : '').trim(),
        tags:     tagsVal.split(',').map(function(s){return s.trim();}).filter(Boolean)
      });
    }
    function hval(id) { var e = $(id); return e ? e.value.trim() : ''; }
    return {
      hero: {
        badge:             hval('h-badge'),
        h1:                hval('h-h1'),
        sub:               hval('h-sub'),
        btn_primary_text:   hval('h-btn1-text'),
        btn_primary_href:   hval('h-btn1-href'),
        btn_outline_text:   hval('h-btn2-text'),
        btn_outline_href:   hval('h-btn2-href')
      },
      products: products,
      contact: {
        h2:       hval('h-c-h2'),
        email:    hval('h-c-email'),
        phone:    hval('h-c-phone'),
        whatsapp: hval('h-c-whatsapp'),
        address:  hval('h-c-address'),
        hours:    hval('h-c-hours')
      },
      footer: {
        company_name: hval('h-f-name'),
        description:  hval('h-f-desc'),
        email:        hval('h-f-email'),
        phone:        hval('h-f-phone')
      }
    };
  }

  function saveHome() {
    var data = collectHome();
    var lang = $('langSel') ? $('langSel').value : 'en';
    localStorage.setItem(sk('home', lang), JSON.stringify(data));
    setStatus('💾 首页草稿已保存（刷新前请导出 JSON）');
  }

  function autoSaveHome() {
    var data = collectHome();
    var lang = $('langSel') ? $('langSel').value : 'en';
    localStorage.setItem(sk('home', lang), JSON.stringify(data));
  }

  function exportHome() {
    var data = collectHome();
    var lang = $('langSel') ? $('langSel').value : 'en';
    var blob = new Blob([JSON.stringify(data, null, 2)], {type:'application/json'});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'home-' + lang + '.json';
    a.click();
    setStatus('📤 已导出 home-' + lang + '.json');
  }

  function importHomepage(data) {
    if (!confirm('确认导入首页 JSON？将覆盖当前内容。')) return;
    var lang = $('langSel') ? $('langSel').value : 'en';
    renderHomeEditor(data, lang);
    saveHome();
    setStatus('📥 已导入首页 JSON');
  }

  // ── Load / fetch ───────────────────────────────────────────────
  function loadProduct(cat, lang) {
    cat = cat || currentCat || 'handheld-vacuum';
    lang = lang || $('langSel').value || 'en';
    currentCat = cat;
    currentLang = lang;

    // Restore from localStorage
    var stored = localStorage.getItem(sk('product', lang, cat));
    if (stored) {
      try {
        var d = JSON.parse(stored);
        renderProductForm(d);
        setStatus('📂 已加载本地草稿（' + lang + '/' + cat + '）');
        return;
      } catch(e) {}
    }

    // Fetch from live site
    setStatus('⏳ 正在从线上拉取...');
    var x = new XMLHttpRequest();
    x.open('GET', '/data/products/' + cat + '.json?v=' + Date.now(), true);
    x.onload = function() {
      if (x.status === 200) {
        try {
          var data = JSON.parse(x.responseText);
          var prod = (data.products && data.products[0]) || {};
          // Helper: pick language from {en:..., zh:...} object
          function pl(obj, lang) {
            if (!obj || typeof obj !== 'object') return obj || '';
            if (obj[lang]) return obj[lang];
            return obj.en || obj.zh || '';
          }
          // Helper: array or string to string
          function arrStr(v) {
            if (Array.isArray(v)) return v.join(', ');
            if (typeof v === 'string') return v;
            if (v && typeof v === 'object') return pl(v, lang);
            return '';
          }
          // Helper: specs array [{label:{en,zh}, value}] -> [{key,value}]
          function normSpecs(arr) {
            if (!Array.isArray(arr)) return [];
            return arr.map(function(s) {
              return {
                key:   typeof s.label === 'object' ? pl(s.label, lang) : (s.label || s.key || ''),
                value: typeof s.value === 'object' ? pl(s.value, lang) : (s.value || '')
              };
            }).filter(function(s){ return s.key && s.value; });
          }
          // Flatten product into admin form shape
          var entry = {
            id:            prod.id || '',
            slug:          cat,
            lang:          lang,
            name:          pl(prod.name, lang),
            model:         prod.model || (prod.id ? prod.id.toUpperCase() : ''),
            tagline:       pl(prod.tagline, lang),
            power:         '',
            suction:       '',
            battery:       '',
            weight:        '',
            price_display: (prod.price_indicator ? '$' + prod.price_indicator.min + ' - $' + prod.price_indicator.max : '') || arrStr(prod.price_display),
            moq:           (prod.moq && prod.moq.value) ? prod.moq.value : (prod.moq || 200),
            fob_price:     (prod.price_ladder && prod.price_ladder[0]) ? ('$' + prod.price_ladder[0].price) : '',
            currency:      (prod.price_indicator && prod.price_indicator.currency) || 'USD',
            colors:        [],
            package:       (prod.packaging && typeof prod.packaging === 'object') ? (prod.packaging.unit + ', ' + prod.packaging.ctn_size + ', ' + prod.packaging.ctn_qty) : (prod.package || ''),
            dims:          (prod.packaging && prod.packaging.ctn_size) || '',
            tags:          [],
            specs:         normSpecs(prod.specs || prod.quick_specs || []),
            certifications: prod.certifications || [],
            packaging:    [],
            applications: arrStr(prod.applications),
            company:      '',
            address:      (prod.ship_from ? pl(prod.ship_from, lang) : ''),
            logo:         (prod.customization && prod.customization.logo) ? 'Yes' : 'No',
            packaging_custom: (prod.customization && prod.customization.package) ? 'Yes' : 'No',
            description:  pl(prod.description, lang),
            images:       prod.images || []
          };
          // Extract power/suction/battery/weight from specs
          (prod.specs || []).forEach(function(s) {
            var raw = (typeof s.label === 'object') ? pl(s.label, 'en') : (s.label || '');
            var label = String(raw).toLowerCase();
            var val = (typeof s.value === 'object') ? pl(s.value, 'en') : (s.value || '');
            if (/power/.test(label)) entry.power = val;
            if (/suction/.test(label)) entry.suction = val;
            if (/runtime|battery/.test(label)) entry.battery = val;
            if (/weight/.test(label)) entry.weight = val;
          });
          // Extract tags from highlights
          if (prod.highlights) {
            entry.tags = prod.highlights.map(function(h) { return pl(h.text, lang); }).filter(Boolean);
          }
          // Extract colors from sku
          if (prod.sku) {
            prod.sku.forEach(function(s) {
              var sname = (typeof s.name === 'object') ? pl(s.name, 'en') : s.name;
              if (/color|colour/i.test(sname) && s.values) {
                entry.colors = s.values.map(function(v) { return v.name; }).filter(Boolean);
              }
            });
          }
          renderProductForm(entry);
          setStatus('📂 已从线上加载（' + lang + ' / ' + cat + '）');
        } catch(e) {
          renderProductForm({ slug: cat, lang: lang });
          setStatus('⚠ 线上数据解析失败：' + e.message);
        }
      } else {
        renderProductForm({ slug: cat, lang: lang });
        setStatus('⚠ 找不到线上数据，使用空白表单');
      }
    };
    x.onerror = function() {
      renderProductForm({ slug: cat, lang: lang });
      setStatus('⚠ 网络错误');
    };
    x.send();
  }

  function loadHomepage(lang) {
    lang = lang || $('langSel').value || 'en';
    // localStorage first
    var stored = localStorage.getItem(sk('home', lang));
    if (stored) {
      try {
        var d = JSON.parse(stored);
        renderHomeEditor(d, lang);
        setStatus('📂 已加载本地草稿（' + lang + '）');
        return;
      } catch(e) {}
    }
    loadHomepageLive(lang);
  }

  function loadHomepageLive(lang) {
    lang = lang || $('langSel').value || 'en';
    setStatus('⏳ 正在从线上拉取...');
    var x = new XMLHttpRequest();
    x.open('GET', '/data/pages/home/' + lang + '.json?v=' + Date.now(), true);
    x.onload = function() {
      if (x.status === 200) {
        try {
          var d = JSON.parse(x.responseText);
          renderHomeEditor(d, lang);
          setStatus('🌐 已从线上加载（' + lang + '）');
        } catch(e) {
          setStatus('❌ JSON 解析失败：' + e.message);
        }
      } else {
        setStatus('❌ 找不到 ' + lang + ' 首页数据（HTTP ' + x.status + '）');
      }
    };
    x.onerror = function() { setStatus('❌ 网络错误'); };
    x.send();
  }

  // ── Tab + sidebar builders ─────────────────────────────────────
  function buildSidebar() {
    var side = $('sidebar');
    if (!side) return;

    side.innerHTML = '';

    // Tab switcher
    var tabsDiv = document.createElement('div');
    tabsDiv.style.cssText = 'display:flex;gap:0;margin-bottom:16px;background:#E2E8F0;border-radius:8px;padding:3px;';
    tabsDiv.innerHTML =
      '<button id="tab-product" class="btn btn-primary" style="flex:1;border-radius:6px;font-size:13px;padding:10px 6px;background:#2563EB;color:#fff;">📦 产品</button>' +
      '<button id="tab-home" class="btn btn-outline" style="flex:1;border-radius:6px;font-size:13px;padding:10px 6px;">🏠 首页</button>';
    side.appendChild(tabsDiv);

    // Status
    var statusDiv = document.createElement('div');
    statusDiv.className = 'admin-status';
    statusDiv.id = 'status';
    statusDiv.textContent = '就绪';

    // Build product controls by default
    buildProductControls(side);
    side.appendChild(statusDiv);

    // Wire tab buttons (NOW — after buildProductControls defines the functions)
    $('tab-product').onclick = function() {
      activeTab = 'product';
      $('tab-product').className = 'btn btn-primary';
      $('tab-home').className = 'btn btn-outline';
      $('tab-product').style.background = '#2563EB';
      $('tab-product').style.color = '#fff';
      $('tab-home').style.background = '';
      $('tab-home').style.color = '';
      // Clear sidebar after hr
      var hrs = qsa('.admin-side hr');
      if (hrs.length) {
        var lastHr = hrs[hrs.length-1];
        while (lastHr.nextSibling) side.removeChild(lastHr.nextSibling);
        side.removeChild(lastHr);
      }
      var hr = document.createElement('hr');
      side.appendChild(hr);
      buildProductControls(side);
      side.appendChild(statusDiv);
      // Auto-load product data (defer 50ms for DOM ready)
      var _cat = currentCat || 'handheld-vacuum';
      var _lang = currentLang || 'en';
      setTimeout(function(){ loadProduct(_cat, _lang); }, 50);
    };

    $('tab-home').onclick = function() {
      activeTab = 'home';
      $('tab-home').className = 'btn btn-primary';
      $('tab-product').className = 'btn btn-outline';
      $('tab-home').style.background = '#2563EB';
      $('tab-home').style.color = '#fff';
      $('tab-product').style.background = '';
      $('tab-product').style.color = '';
      // Clear sidebar after hr
      var hrs = qsa('.admin-side hr');
      if (hrs.length) {
        var lastHr = hrs[hrs.length-1];
        while (lastHr.nextSibling) side.removeChild(lastHr.nextSibling);
        side.removeChild(lastHr);
      }
      var hr = document.createElement('hr');
      side.appendChild(hr);
      buildHomeControls(side);
      side.appendChild(statusDiv);
      // Auto-load homepage data (defer 50ms so DOM from buildHomeControls is ready)
      var _lang = $('langSel') ? $('langSel').value : 'en';
      setTimeout(function(){ loadHomepage(_lang); }, 50);
    };
  }

  function buildProductControls(side) {
    var catDiv = document.createElement('div');
    catDiv.className = 'admin-field';
    catDiv.innerHTML = '<label>类目</label><select id="catSel"></select>';
    side.appendChild(catDiv);
    var catSel = $('catSel');
    CATS.forEach(function(c){
      var o = document.createElement('option');
      o.value = c.slug;
      o.textContent = c.label + ' / ' + c.enLabel;
      if (c.slug === currentCat) o.selected = true;
      catSel.appendChild(o);
    });
    catSel.onchange = function() {
      currentCat = this.value;
      loadProduct(currentCat);
    };

    var langDiv = document.createElement('div');
    langDiv.className = 'admin-field';
    langDiv.innerHTML = '<label>语言</label><select id="langSel"></select>';
    side.appendChild(langDiv);
    LANGS.forEach(function(l){
      var o = document.createElement('option');
      o.value = l.code;
      o.textContent = l.label;
      if (l.code === (currentLang||'en')) o.selected = true;
      $('langSel').appendChild(o);
    });
    $('langSel').onchange = function() {
      currentLang = this.value;
      loadProduct(currentCat, currentLang);
    };

    var btnDiv = document.createElement('div');
    btnDiv.style.marginTop = '8px';
    btnDiv.innerHTML =
      '<button class="btn btn-primary" id="loadBtn" style="width:100%;margin-bottom:8px;">📂 加载产品</button>' +
      '<button class="btn btn-outline" id="newBtn" style="width:100%;margin-bottom:16px;">🆕 新建空白</button>';
    side.appendChild(btnDiv);

    $('loadBtn').onclick = function() { loadProduct(currentCat, currentLang); };
    $('newBtn').onclick = function() {
      renderProductForm({ slug: currentCat||'handheld-vacuum', lang: currentLang||'en' });
      setStatus('🆕 空白表单已打开');
    };

    side.appendChild(document.createElement('hr'));

    var impDiv = document.createElement('div');
    impDiv.innerHTML =
      '<button class="btn btn-outline" id="exportBtn" style="width:100%;margin-bottom:8px;">📤 导出当前</button>' +
      '<button class="btn btn-outline" id="importBtn" style="width:100%;">📥 导入 JSON</button>';
    side.appendChild(impDiv);
    $('exportBtn').onclick = function() {
      var d = collectProduct();
      if (!d.name) { setStatus('⚠ 请先加载或填写产品'); return; }
      exportProduct();
    };
    $('importBtn').onclick = function() { $('importFile').click(); };
  }

  function buildHomeControls(side) {
    var langDiv = document.createElement('div');
    langDiv.className = 'admin-field';
    langDiv.innerHTML = '<label>语言</label><select id="langSel"></select>';
    side.appendChild(langDiv);
    LANGS.forEach(function(l){
      var o = document.createElement('option');
      o.value = l.code;
      o.textContent = l.label;
      if (l.code === (currentLang||'en')) o.selected = true;
      $('langSel').appendChild(o);
    });
    $('langSel').onchange = function() { loadHomepage(this.value); };

    var btnDiv = document.createElement('div');
    btnDiv.style.marginTop = '8px';
    btnDiv.innerHTML =
      '<button class="btn btn-primary" id="loadHomeBtn" style="width:100%;margin-bottom:8px;">📂 加载首页数据</button>' +
      '<button class="btn btn-outline" id="loadHomeLiveBtn" style="width:100%;margin-bottom:16px;">🌐 从线上拉取</button>';
    side.appendChild(btnDiv);
    $('loadHomeBtn').onclick = function() { loadHomepage($('langSel').value); };
    $('loadHomeLiveBtn').onclick = function() { loadHomepageLive($('langSel').value); };

    side.appendChild(document.createElement('hr'));

    var impDiv = document.createElement('div');
    impDiv.innerHTML =
      '<button class="btn btn-outline" id="exportHomeBtn" style="width:100%;margin-bottom:8px;">📤 导出 JSON</button>' +
      '<button class="btn btn-outline" id="importHomeBtn" style="width:100%;">📥 导入 JSON</button>';
    side.appendChild(impDiv);
    $('exportHomeBtn').onclick = function() { exportHome(); };
    $('importHomeBtn').onclick = function() { $('importFile').click(); };
  }

  // ── Expose API globally (for debugging / tab buttons) ──────────
  window._aqc = {
    loadHomepage:      loadHomepage,
    loadHomepageLive:  loadHomepageLive,
    loadProduct:       loadProduct,
    saveHome:          saveHome,
    exportHome:        exportHome,
    collectHome:       collectHome,
    renderHomeEditor:   renderHomeEditor,
    saveProduct:       saveProduct,
    exportProduct:     exportProduct,
    collectProduct:    collectProduct
  };

  // ── Init ───────────────────────────────────────────────────────
  function init() {
    buildSidebar();
    // Auto-load default product after sidebar is built
    setTimeout(function(){ loadProduct('handheld-vacuum', 'en'); }, 50);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
