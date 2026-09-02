/**
 * AquaClean Admin — Product Manager + Homepage CMS
 * Tab 1: 产品详情 (existing)
 * Tab 2: 首页内容 (new)
 */
(function () {
  'use strict';

  // ── Tab routing ───────────────────────────────────────────────
  var activeTab = 'product'; // 'product' | 'home'

  // ── Shared helpers ─────────────────────────────────────────────
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

  // ── Storage key ────────────────────────────────────────────────
  function sk(tab, lang, cat) {
    return 'aqc_' + tab + '_' + lang + (cat ? '_' + cat : '');
  }

  // ── Language list ───────────────────────────────────────────────
  var LANGS = [
    { code: 'en',  label: 'English' },
    { code: 'zh',  label: '中文' },
    { code: 'es',  label: 'Español' },
    { code: 'fr',  label: 'Français' },
    { code: 'ar',  label: 'العربية' },
    { code: 'id',  label: 'Indonesia' },
    { code: 'ru',  label: 'Русский' },
    { code: 'th',  label: 'ไทย' },
    { code: 'vi',  label: 'Tiếng Việt' },
  ];

  var LANGS_9 = [
    'en','zh','es','fr','ar','id','ru','th','vi'
  ];

  // ── Tab 1: Product ──────────────────────────────────────────────
  var CATS = [
    { slug:'handheld-vacuum',     label:'手持吸尘器',       enLabel:'Handheld Vacuum Cleaner' },
    { slug:'robot-vacuum',        label:'扫地机器人',        enLabel:'Robot Vacuum Cleaner' },
    { slug:'steam-cleaner',       label:'蒸汽清洁器',        enLabel:'Steam Cleaner' },
    { slug:'uv-mite-remover',     label:'除螨仪',           enLabel:'UV Mite Remover' },
    { slug:'window-cleaner-robot',label:'擦窗机器人',       enLabel:'Window Cleaner Robot' },
    { slug:'car-vacuum',          label:'车载吸尘器',        enLabel:'Car Vacuum Cleaner' },
    { slug:'tire-inflator',       label:'轮胎充气泵',        enLabel:'Digital Tire Inflator' },
    { slug:'coffee-machine',      label:'咖啡机',            enLabel:'Espresso Coffee Machine' },
    { slug:'upright-steam-mop',   label:'立式蒸汽拖把',      enLabel:'Upright Steam Mop' },
  ];

  var CERT_OPTS = ['CE','CB','ETL','FCC','RoHS','REACH','PSE','CCC','KC','BIS'];
  var CURRENCY_OPTS = ['USD','EUR','GBP','CNY','AUD','CAD','AED','SAR'];
  var UNIT_OPTS    = ['units','pcs','sets','pairs','kg','g'];

  var currentCat  = null;
  var currentLang = null;
  var currentPid  = null;
  var rawData     = {};

  // ── Product render ─────────────────────────────────────────────
  function renderProductForm(data) {
    var f = $('formArea');
    if (!f) return;
    f.innerHTML = '';

    function sec(title, html) {
      var d = document.createElement('div');
      d.className = 'admin-sec';
      d.innerHTML = '<h3>' + title + '</h3>' + (html || '');
      f.appendChild(d);
    }

    function grid(html) {
      return '<div class="admin-grid">' + html + '</div>';
    }

    function field(label, id, type, placeholder) {
      placeholder = placeholder || '';
      var t = type === 'textarea'
        ? '<textarea id="' + id + '" rows="3" placeholder="' + placeholder + '"></textarea>'
        : '<input id="' + id + '" type="text" placeholder="' + placeholder + '">';
      return '<div class="admin-field"><label>' + label + '</label>' + t + '</div>';
    }

    // Basic info
    sec('基本信息', grid(
      field('产品名称 *', 'p-name', 'text', '如：Handheld Vacuum Cleaner') +
      field('型号', 'p-model', 'text', '如：HV-100') +
      field('产品标签语', 'p-tagline', 'text', '如：Best Seller')
    ));

    // Specs
    sec('核心参数', grid(
      field('功率', 'p-power', 'text', '如：120W') +
      field('吸力', 'p-suction', 'text', '如：16KPa') +
      field('电池/续航', 'p-battery', 'text', '如：2000mAh / 25min') +
      field('重量', 'p-weight', 'text', '如：0.8kg')
    ));

    // Pricing
    sec('价格阶梯（USD）', grid(
      field('价格区间文字', 'p-price_display', 'text', '如：$45 - $75') +
      field('MOQ', 'p-moq', 'text', '如：200') +
      field('FOB 单价（≥MOQ）', 'p-fob_price', 'text', '如：$45') +
      field('货币单位', 'p-currency', 'select') +
      field('最小订量单位', 'p-moq_unit', 'select')
    ));

    // SKUs
    sec('SKU 规格', grid(
      field('颜色选项（逗号分隔）', 'p-colors', 'text', '如：White, Black, Blue') +
      field('包装规格', 'p-package', 'text', '如：10 pcs/carton, 52×38×30 cm') +
      field('单件体积/重量', 'p-dims', 'text', '如：28×12×15 cm / 1.2 kg')
    ));

    // Certs
    sec('认证', '<div class="admin-field"><label>认证（多选）</label>' +
      '<div id="p-certs" style="display:flex;flex-wrap:wrap;gap:8px;margin-top:6px;"></div></div>');

    // Media
    sec('产品图片', '<div id="p-img-drop" class="admin-drop">📁 拖放图片到这里，或粘贴 URL（每行一个）</div>' +
      '<textarea id="p-img-urls" rows="3" placeholder="https://example.com/img1.jpg&#10;https://example.com/img2.jpg" style="width:100%;margin-top:8px;"></textarea>' +
      '<div id="p-img-preview" class="admin-imgs"></div>');

    // Tags
    sec('产品卖点标签（逗号分隔）', '<textarea id="p-tags" rows="2" placeholder="如：120W / 16KPa, USB-C, 25min Runtime"></textarea>');

    // Specs table
    sec('规格参数表格（格式：参数|值，每行一组）', '<textarea id="p-specs" rows="8" style="width:100%;font-family:monospace;" placeholder="Power|120W&#10;Suction|16KPa&#10;Battery|2000mAh"></textarea>');

    // Packaging
    sec('包装内容（逗号分隔）', '<textarea id="p-packaging" rows="2" placeholder="主机×1, 配件套装×1, USB-C线×1, 说明书×1"></textarea>');

    // Applications
    sec('适用场景（逗号分隔）', '<textarea id="p-applications" rows="2" placeholder="Home, Car, Office, Pet owner"></textarea>');

    // Supplier
    sec('供应商信息', grid(
      field('公司名', 'p-company', 'text', 'Hong Kong Damaijia Technology Co., Limited') +
      field('地址', 'p-address', 'text', 'Ningbo, Zhejiang, China')
    ));

    // Customization
    sec('定制能力', grid(
      field('Logo 定制', 'p-logo', 'text', '如：OEM / ODM / Custom color') +
      field('包装定制', 'p-packaging_custom', 'text', '如：Custom box printing')
    ));

    // Description
    sec('产品描述（Alibaba 风格英文）', '<textarea id="p-desc" rows="5" placeholder="详细介绍产品特点、优势、适用场景..."></textarea>');

    // Actions
    var actions = document.createElement('div');
    actions.className = 'admin-actions';
    actions.style.marginTop = '24px';
    actions.innerHTML =
      '<button class="btn btn-primary" id="p-save">💾 保存草稿</button>' +
      '<button class="btn btn-outline" id="p-export">📤 导出 JSON</button>' +
      '<button class="btn btn-outline" id="p-import">📥 导入 JSON</button>' +
      '<button class="btn btn-outline" id="p-reset">🗑 清空</button>';
    f.appendChild(actions);

    // Wire cert checkboxes
    var certsEl = $('p-certs');
    CERT_OPTS.forEach(function (c) {
      var label = document.createElement('label');
      label.style.cssText = 'display:inline-flex;align-items:center;gap:4px;font-size:13px;padding:5px 10px;border:1px solid #E2E8F0;border-radius:6px;cursor:pointer;background:#F8FAFC;';
      label.innerHTML = '<input type="checkbox" value="' + c + '" style="width:auto;">' + c;
      certsEl.appendChild(label);
    });

    // Wire actions
    $('p-save').onclick   = saveProduct;
    $('p-export').onclick = exportProduct;
    $('p-import').onclick = function () { $('importFile').click(); };
    $('p-reset').onclick  = function () { if (confirm('确认清空当前表单？')) renderProductForm({}); };

    $('importFile').onchange = importProduct;

    // Populate from data
    populateProduct(data || {});

    // Auto-save on input
    qsa('#formArea input, #formArea textarea, #formArea select').forEach(function (el) {
      el.addEventListener('input', autoSaveProduct);
    });
  }

  function populateProduct(d) {
    function set(id, val) {
      var el = $(id);
      if (el) el.value = (val !== undefined && val !== null) ? val : '';
    }
    set('p-name',         d.name);
    set('p-model',        d.model);
    set('p-tagline',      d.tagline);
    set('p-power',        d.power);
    set('p-suction',      d.suction);
    set('p-battery',      d.battery);
    set('p-weight',       d.weight);
    set('p-price_display',d.price_display);
    set('p-moq',          d.moq);
    set('p-fob_price',    d.fob_price);
    set('p-currency',     d.currency || 'USD');
    set('p-moq_unit',     d.moq_unit || 'units');
    set('p-colors',       (d.colors || []).join(', '));
    set('p-package',      d.package);
    set('p-dims',         d.dims);
    set('p-tags',         (d.tags || []).join(', '));
    set('p-specs',        (d.specs || []).map(function(s){return s.key+'|'+s.value;}).join('\n'));
    set('p-packaging',    (d.packaging || []).join(', '));
    set('p-applications', (d.applications || []).join(', '));
    set('p-company',      d.company);
    set('p-address',     d.address);
    set('p-logo',         d.logo);
    set('p-packaging_custom', d.packaging_custom);
    set('p-desc',        d.description);

    // Certs
    if (d.certifications) {
      d.certifications.forEach(function(c) {
        var cb = qsa('#p-certs input[value="'+c+'"]')[0];
        if (cb) cb.checked = true;
      });
    }

    // Img URLs
    set('p-img-urls', (d.images || []).join('\n'));
    renderImgPreview();

    currentPid = d.id || null;
    // auto-select category from slug
    if (d.slug && currentCat) {
      // already set
    }
  }

  function collectProduct() {
    var specs_raw = ($('p-specs').value || '').split('\n').filter(Boolean);
    var specs = specs_raw.map(function (l) {
      var parts = l.split('|');
      return { key: (parts[0]||'').trim(), value: (parts[1]||'').trim() };
    }).filter(function(s){ return s.key && s.value; });

    var certs = [].slice.call(qsa('#p-certs input:checked')).map(function(cb){ return cb.value; });

    var images = ($('p-img-urls').value || '').split('\n').filter(function(u){ return u.trim(); });

    return {
      id:          currentPid || ('p-' + Date.now()),
      slug:        currentCat,
      lang:        $('langSel') ? $('langSel').value : currentLang,
      name:        $('p-name').value.trim(),
      model:       $('p-model').value.trim(),
      tagline:     $('p-tagline').value.trim(),
      power:       $('p-power').value.trim(),
      suction:     $('p-suction').value.trim(),
      battery:     $('p-battery').value.trim(),
      weight:      $('p-weight').value.trim(),
      price_display: $('p-price_display').value.trim(),
      moq:         parseInt($('p-moq').value) || 200,
      fob_price:   $('p-fob_price').value.trim(),
      currency:    $('p-currency').value || 'USD',
      moq_unit:    $('p-moq_unit').value || 'units',
      colors:      $('p-colors').value.split(',').map(function(s){return s.trim();}).filter(Boolean),
      package:     $('p-package').value.trim(),
      dims:        $('p-dims').value.trim(),
      tags:        $('p-tags').value.split(',').map(function(s){return s.trim();}).filter(Boolean),
      specs:       specs,
      certifications: certs,
      packaging:   $('p-packaging').value.split(',').map(function(s){return s.trim();}).filter(Boolean),
      applications: $('p-applications').value.split(',').map(function(s){return s.trim();}).filter(Boolean),
      company:     $('p-company').value.trim(),
      address:     $('p-address').value.trim(),
      logo:        $('p-logo').value.trim(),
      packaging_custom: $('p-packaging_custom').value.trim(),
      description: $('p-desc').value.trim(),
      images:      images,
      updated_at:  new Date().toISOString()
    };
  }

  function saveProduct() {
    var data = collectProduct();
    localStorage.setItem(sk('product', data.lang, currentCat), JSON.stringify(data));
    setStatus('💾 已保存草稿（刷新页面前请导出）');
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
    setStatus('📤 已导出 JSON 文件');
  }

  function importProduct() {
    var file = $('importFile').files[0];
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function(e) {
      try {
        var d = JSON.parse(e.target.result);
        // detect type
        if (d.hero || d.products) {
          // homepage JSON
          importHomepage(d);
        } else {
          // product JSON
          if (d.slug) selectCat(d.slug);
          populateProduct(d);
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

  function renderImgPreview() {
    var container = $('p-img-preview');
    if (!container) return;
    container.innerHTML = '';
    var urls = ($('p-img-urls').value || '').split('\n').filter(function(u){return u.trim();});
    urls.forEach(function(url, i) {
      var div = document.createElement('div');
      div.className = 'admin-img';
      var img = document.createElement('img');
      img.src = url.trim();
      img.onerror = function(){ this.parentElement.style.opacity='0.3'; };
      var rm = document.createElement('button');
      rm.className = 'x';
      rm.textContent = '×';
      rm.onclick = function() {
        var lines = $('p-img-urls').value.split('\n').filter(function(u,l){ return l!==i; });
        $('p-img-urls').value = lines.join('\n');
        renderImgPreview();
        autoSaveProduct();
      };
      div.appendChild(img);
      div.appendChild(rm);
      container.appendChild(div);
    });
  }

  // ── Tab 2: Homepage CMS ────────────────────────────────────────
  function renderHomeEditor(data, lang) {
    var f = $('formArea');
    if (!f) return;
    f.innerHTML = '';

    function sec(title, html) {
      var d = document.createElement('div');
      d.className = 'admin-sec';
      d.innerHTML = '<h3>' + title + '</h3>' + (html || '');
      f.appendChild(d);
    }

    function field(label, id, type, placeholder, note) {
      placeholder = placeholder || '';
      var noteHtml = note ? '<div style="font-size:11px;color:#94A3B8;margin-top:3px;">' + note + '</div>' : '';
      var t = type === 'textarea'
        ? '<textarea id="' + id + '" rows="3" placeholder="' + placeholder + '"></textarea>'
        : '<input id="' + id + '" type="text" placeholder="' + placeholder + '">';
      return '<div class="admin-field" style="margin-bottom:18px;"><label>' + label + '</label>' + t + noteHtml + '</div>';
    }

    var h = data || {};
    var hero = h.hero || {};
    var products = h.products || [];
    var contact = h.contact || {};
    var footer = h.footer || {};

    // Hero
    sec('🏠 Hero 区域', '<div style="max-width:640px;">' +
      field('徽章文字（emoji+公司定位）', 'h-badge', 'text', hero.badge || '', '如：🇨🇳 OEM / ODM Manufacturer · Since 2015') +
      field('主标题 H1（保留 &lt;br&gt; 和 &lt;span&gt; 标签）', 'h-h1', 'textarea', hero.h1 || '', '支持 HTML：Smart Cleaning Appliances<br>Built for <span>Global Markets</span>') +
      field('副标题段落', 'h-sub', 'textarea', hero.sub || '') +
      field('主按钮文字', 'h-btn1-text', 'text', hero.btn_primary_text || '', '如：📩 Get a Free Quote') +
      field('主按钮链接', 'h-btn1-href', 'text', hero.btn_primary_href || '#quote') +
      field('次按钮文字', 'h-btn2-text', 'text', hero.btn_outline_text || '', '如：Browse Products') +
      field('次按钮链接', 'h-btn2-href', 'text', hero.btn_outline_href || '#products') +
      '</div>');

    // Products
    var prodHtml = '<div id="h-prod-list">';
    products.forEach(function(prod, i) {
      prodHtml += '<div style="border:1px solid #E2E8F0;border-radius:8px;padding:14px;margin-bottom:14px;background:#F8FAFC;">' +
        '<div style="font-weight:700;margin-bottom:10px;color:#2563EB;">产品 ' + (i+1) + ': ' + (prod.name || '?') + '</div>' +
        '<input type="hidden" id="hp-id-' + i + '" value="' + (prod.id||'') + '">' +
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">' +
        field('名称', 'hp-name-'+i, 'text', prod.name||'') +
        field('Slug', 'hp-slug-'+i, 'text', prod.slug||slugify(prod.name||''), '对应类目路径，如：handheld-vacuum') +
        field('描述', 'hp-desc-'+i, 'textarea', prod.desc||'') +
        field('图片路径', 'hp-img-'+i, 'text', prod.img||'', '相对于网站根目录，如：../assets/images/products/01-handheld-vacuum.png') +
        field('按钮文字', 'hp-btn-'+i, 'text', prod.btn_text||'') +
        field('按钮链接', 'hp-href-'+i, 'text', prod.btn_href||'') +
        field('标签（逗号分隔）', 'hp-tags-'+i, 'text', (prod.tags||[]).join(', ')) +
        '</div></div>';
    });
    prodHtml += '</div>';
    prodHtml += '<button class="btn btn-outline" id="h-save" style="margin-top:4px;">💾 保存草稿</button> ';
    prodHtml += '<button class="btn btn-outline" id="h-export">📤 导出 JSON</button> ';
    prodHtml += '<button class="btn btn-outline" id="h-import-home">📥 导入 JSON</button> ';
    prodHtml += '<a class="btn btn-outline" id="h-preview" href="/' + lang + '/?v=' + Date.now() + '" target="_blank" style="display:inline-block;text-decoration:none;">🔍 预览</a>';
    prodHtml += '<div style="margin-top:20px;padding:12px;background:#EFF6FF;border-radius:8px;font-size:12px;color:#1E40AF;line-height:1.6;">' +
      '<b>📝 使用说明：</b> 修改内容后点「保存草稿」→ 导出 JSON → 将 JSON 内容更新到 <code>/data/pages/home/' + lang + '.json</code> → 推送到 GitHub → 等待约2分钟后刷新预览页验证。' +
      '<br><br><b>🔧 GitHub 发布流程：</b> 将导出 JSON 内容粘贴到 GitHub 仓库对应文件，或使用本地 git push 命令。' +
      '</div>';
    sec('📦 产品卡片（' + products.length + ' 个）', prodHtml);

    // Contact
    sec('📞 联系区域', '<div style="max-width:640px;">' +
      field('联系区标题', 'h-c-h2', 'text', contact.h2 || '') +
      field('邮箱', 'h-c-email', 'text', contact.email || '') +
      field('电话', 'h-c-phone', 'text', contact.phone || '') +
      field('WhatsApp（数字，无+号）', 'h-c-whatsapp', 'text', contact.whatsapp || '') +
      field('地址', 'h-c-address', 'text', contact.address || '') +
      field('营业时间', 'h-c-hours', 'text', contact.hours || '') +
      '</div>');

    // Footer
    sec('🔻 页脚', '<div style="max-width:640px;">' +
      field('公司名称', 'h-f-name', 'text', footer.company_name || '') +
      field('公司描述', 'h-f-desc', 'textarea', footer.description || '') +
      field('页脚邮箱', 'h-f-email', 'text', footer.email || '') +
      field('页脚电话', 'h-f-phone', 'text', footer.phone || '') +
      '</div>');

    // Auto-save
    qsa('#formArea input, #formArea textarea').forEach(function(el){
      el.addEventListener('input', autoSaveHome);
    });

    // Wire buttons
    $('h-save').onclick = saveHome;
    $('h-export').onclick = exportHome;
    $('h-import-home').onclick = function() { $('importFile').click(); };
  }

  function collectHome() {
    var prodCount = 11;
    var products = [];
    for (var i = 0; i < prodCount; i++) {
      var tagsVal = ($('hp-tags-'+i).value || '');
      products.push({
        id:       $('hp-id-'+i).value || ('p'+(i+1)),
        name:     ($('hp-name-'+i).value||'').trim(),
        slug:     ($('hp-slug-'+i).value||'').trim(),
        desc:     ($('hp-desc-'+i).value||'').trim(),
        img:      ($('hp-img-'+i).value||'').trim(),
        btn_text: ($('hp-btn-'+i).value||'').trim(),
        btn_href: ($('hp-href-'+i).value||'').trim(),
        tags:     tagsVal.split(',').map(function(s){return s.trim();}).filter(Boolean)
      });
    }
    return {
      hero: {
        badge:              ($('h-badge').value||'').trim(),
        h1:                 ($('h-h1').value||'').trim(),
        sub:                ($('h-sub').value||'').trim(),
        btn_primary_text:   ($('h-btn1-text').value||'').trim(),
        btn_primary_href:   ($('h-btn1-href').value||'').trim(),
        btn_outline_text:   ($('h-btn2-text').value||'').trim(),
        btn_outline_href:   ($('h-btn2-href').value||'').trim()
      },
      products: products,
      contact: {
        h2:        ($('h-c-h2').value||'').trim(),
        email:     ($('h-c-email').value||'').trim(),
        phone:     ($('h-c-phone').value||'').trim(),
        whatsapp:  ($('h-c-whatsapp').value||'').trim(),
        address:   ($('h-c-address').value||'').trim(),
        hours:     ($('h-c-hours').value||'').trim()
      },
      footer: {
        company_name: ($('h-f-name').value||'').trim(),
        description: ($('h-f-desc').value||'').trim(),
        email:       ($('h-f-email').value||'').trim(),
        phone:       ($('h-f-phone').value||'').trim()
      }
    };
  }

  function saveHome() {
    var data = collectHome();
    var lang = $('langSel') ? $('langSel').value : 'en';
    localStorage.setItem(sk('home', lang), JSON.stringify(data));
    setStatus('💾 首页草稿已保存（刷新页面前请导出 JSON）');
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
    if (confirm('确认导入首页 JSON？将覆盖当前编辑内容。')) {
      var lang = $('langSel') ? $('langSel').value : 'en';
      renderHomeEditor(data, lang);
      saveHome();
      setStatus('📥 已导入首页 JSON');
    }
  }

  // ── Sidebar: re-build with tabs ────────────────────────────────
  function buildSidebar() {
    var side = document.querySelector('.admin-side');
    side.innerHTML = '';

    // Tab switcher
    var tabs = document.createElement('div');
    tabs.style.cssText = 'display:flex;gap:0;margin-bottom:16px;background:#E2E8F0;border-radius:8px;padding:3px;';
    tabs.innerHTML =
      '<button id="tab-product" class="btn btn-primary" style="flex:1;border-radius:6px;font-size:13px;padding:8px;">📦 产品</button>' +
      '<button id="tab-home" class="btn btn-outline" style="flex:1;border-radius:6px;font-size:13px;padding:8px;">🏠 首页</button>';
    side.appendChild(tabs);

    $('tab-product').onclick = function() {
      activeTab = 'product';
      $('tab-product').className = 'btn btn-primary';
      $('tab-home').className = 'btn btn-outline';
      $('tab-home').style.background = '';
      $('tab-product').style.background = '#2563EB';
      $('tab-product').style.color = '#fff';
      $('tab-home').style.color = '';
      var curLang = $('langSel').value;
      buildProductControls(side, curLang);
    };
    $('tab-home').onclick = function() {
      activeTab = 'home';
      $('tab-home').className = 'btn btn-primary';
      $('tab-product').className = 'btn btn-outline';
      $('tab-home').style.background = '#2563EB';
      $('tab-home').style.color = '#fff';
      $('tab-product').style.color = '';
      $('tab-product').style.background = '';
      var curLang = $('langSel').value;
      buildHomeControls(side, curLang);
    };

    // Default to product tab
    var defaultLang = $('langSel') ? $('langSel').value : 'en';
    $('tab-product').style.background = '#2563EB';
    $('tab-product').style.color = '#fff';
    buildProductControls(side, defaultLang);
  }

  function buildProductControls(side, curLang) {
    var hr = document.createElement('hr');
    side.appendChild(hr);

    // Category
    var catDiv = document.createElement('div');
    catDiv.className = 'admin-field';
    catDiv.innerHTML = '<label>类目</label><select id="catSel"></select>';
    side.appendChild(catDiv);
    var catSel = $('catSel');
    CATS.forEach(function(c){
      var opt = document.createElement('option');
      opt.value = c.slug;
      opt.textContent = c.label + ' / ' + c.enLabel;
      catSel.appendChild(opt);
    });
    catSel.onchange = function() {
      currentCat = this.value;
      loadProduct(currentCat, curLang);
    };

    // Language
    var langDiv = document.createElement('div');
    langDiv.className = 'admin-field';
    langDiv.innerHTML = '<label>语言</label><select id="langSel2"></select>';
    side.appendChild(langDiv);
    var langSel2 = $('langSel2');
    LANGS.forEach(function(l){
      var opt = document.createElement('option');
      opt.value = l.code;
      opt.textContent = l.label;
      if (l.code === curLang) opt.selected = true;
      langSel2.appendChild(opt);
    });
    langSel2.onchange = function() {
      var ls = $('langSel');
      if (ls) ls.value = this.value;
      var curCat = $('catSel') ? $('catSel').value : currentCat;
      loadProduct(curCat, this.value);
    };

    var btnDiv = document.createElement('div');
    btnDiv.style.marginTop = '8px';
    btnDiv.innerHTML =
      '<button class="btn btn-primary" id="loadBtn2">📂 加载产品</button>' +
      '<button class="btn btn-outline" id="newBtn2" style="margin-top:8px;">🆕 新建空白</button>';
    side.appendChild(btnDiv);

    $('loadBtn2').onclick = function() {
      var cat = $('catSel') ? $('catSel').value : currentCat;
      var lang = $('langSel2') ? $('langSel2').value : curLang;
      loadProduct(cat, lang);
    };
    $('newBtn2').onclick = function() {
      var cat = $('catSel') ? $('catSel').value : currentCat;
      var lang = $('langSel2') ? $('langSel2').value : curLang;
      selectCat(cat);
      renderProductForm({ slug: cat, lang: lang });
      setStatus('🆕 空白表单已打开，请填写后保存');
    };

    var hr2 = document.createElement('hr');
    side.appendChild(hr2);

    var impDiv = document.createElement('div');
    impDiv.innerHTML =
      '<button class="btn btn-outline" id="exportBtn2">📤 导出当前</button>' +
      '<button class="btn btn-outline" id="importBtn2" style="margin-top:8px;">📥 导入 JSON</button>';
    side.appendChild(impDiv);

    $('exportBtn2').onclick = function() {
      var d = collectProduct();
      if (!d.name) { setStatus('⚠ 请先加载或填写产品'); return; }
      exportProduct();
    };
    $('importBtn2').onclick = function() { $('importFile').click(); };

    $('importFile').onchange = importProduct;

    // Status
    var statusDiv = document.createElement('div');
    statusDiv.className = 'admin-status';
    statusDiv.id = 'status';
    statusDiv.textContent = '就绪';
    side.appendChild(statusDiv);
  }

  function buildHomeControls(side, curLang) {
    // Remove old controls
    qsa('.admin-side > *').forEach(function(el) {
      if (el.tagName !== 'DIV' || !el.querySelector('#tab-product')) side.removeChild(el);
    });
    // Find last hr and remove everything after it
    var hr = qsa('.admin-side hr');
    if (hr.length) {
      var lastHr = hr[hr.length-1];
      while (lastHr.nextSibling) side.removeChild(lastHr.nextSibling);
      side.removeChild(lastHr);
    }

    var hr2 = document.createElement('hr');
    side.appendChild(hr2);

    // Language selector for homepage
    var langDiv = document.createElement('div');
    langDiv.className = 'admin-field';
    langDiv.innerHTML = '<label>语言</label><select id="langSel"></select>';
    side.appendChild(langDiv);
    LANGS.forEach(function(l){
      var opt = document.createElement('option');
      opt.value = l.code;
      opt.textContent = l.label;
      if (l.code === curLang) opt.selected = true;
      $('langSel').appendChild(opt);
    });
    $('langSel').onchange = function() {
      loadHomepage(this.value);
    };

    var btnDiv = document.createElement('div');
    btnDiv.style.marginTop = '8px';
    btnDiv.innerHTML =
      '<button class="btn btn-primary" id="loadHomeBtn">📂 加载首页数据</button>' +
      '<button class="btn btn-outline" id="loadHomeLiveBtn" style="margin-top:8px;">🌐 从线上拉取</button>';
    side.appendChild(btnDiv);

    $('loadHomeBtn').onclick = function() {
      var lang = $('langSel') ? $('langSel').value : curLang;
      loadHomepage(lang);
    };
    $('loadHomeLiveBtn').onclick = function() {
      var lang = $('langSel') ? $('langSel').value : curLang;
      loadHomepageLive(lang);
    };

    var hr3 = document.createElement('hr');
    side.appendChild(hr3);

    var impDiv = document.createElement('div');
    impDiv.innerHTML =
      '<button class="btn btn-outline" id="exportHomeBtn">📤 导出 JSON</button>' +
      '<button class="btn btn-outline" id="importHomeBtn" style="margin-top:8px;">📥 导入 JSON</button>';
    side.appendChild(impDiv);

    $('exportHomeBtn').onclick = function() {
      var d = collectHome();
      exportHome();
    };
    $('importHomeBtn').onclick = function() { $('importFile').click(); };

    $('importFile').onchange = importProduct;

    var statusDiv = document.createElement('div');
    statusDiv.className = 'admin-status';
    statusDiv.id = 'status';
    statusDiv.textContent = '就绪';
    side.appendChild(statusDiv);

    // Load default
    loadHomepage(curLang);
  }

  // ── Load / fetch ───────────────────────────────────────────────
  function selectCat(slug) {
    var sel = $('catSel');
    if (sel) {
      [].slice.call(sel.options).forEach(function(o){
        o.selected = o.value === slug;
      });
    }
    currentCat = slug;
  }

  function loadProduct(cat, lang) {
    cat = cat || currentCat;
    lang = lang || 'en';
    selectCat(cat);
    currentLang = lang;

    // Try localStorage first
    var stored = localStorage.getItem(sk('product', lang, cat));
    if (stored) {
      try {
        var d = JSON.parse(stored);
        renderProductForm(d);
        setStatus('📂 已加载本地草稿（' + lang + '/' + cat + '）');
        return;
      } catch(e) {}
    }

    // Fetch from site
    var url = '/data/products/' + cat + '.json?v=' + Date.now();
    var x = new XMLHttpRequest();
    x.open('GET', url, true);
    x.onload = function() {
      if (x.status === 200) {
        try {
          var all = JSON.parse(x.responseText);
          // find matching lang entry
          var entry = all.find(function(item){ return item.lang === lang; }) || all[0] || {};
          entry.lang = lang;
          entry.slug = cat;
          renderProductForm(entry);
          setStatus('📂 已从线上加载（' + lang + '）');
        } catch(e) {
          renderProductForm({ slug: cat, lang: lang });
          setStatus('⚠ 解析线上数据失败，使用空白表单');
        }
      } else {
        renderProductForm({ slug: cat, lang: lang });
        setStatus('⚠ 找不到线上数据，使用空白表单');
      }
    };
    x.onerror = function() {
      renderProductForm({ slug: cat, lang: lang });
      setStatus('⚠ 网络错误，使用空白表单');
    };
    x.send();
  }

  function loadHomepage(lang) {
    lang = lang || 'en';
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
    lang = lang || 'en';
    var url = '/data/pages/home/' + lang + '.json?v=' + Date.now();
    setStatus('⏳ 正在从线上拉取...');
    var x = new XMLHttpRequest();
    x.open('GET', url, true);
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

  // ── Init ───────────────────────────────────────────────────────
  // Expose importHomepage globally for importProduct
  window.importHomepage = importHomepage;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', buildSidebar);
  } else {
    buildSidebar();
  }

  // Also rebuild langSel if page already loaded
  var existingLangSel = $('langSel');
  if (existingLangSel) {
    // Replace the simple langSel with our full sidebar
    buildSidebar();
  }

})();
