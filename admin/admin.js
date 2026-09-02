/* AquaClean Admin — product manager (vanilla JS, no backend) */
(function () {
  'use strict';
  var CATS = [
    { slug: 'handheld-vacuum', name: 'Handheld Vacuum' },
    { slug: 'robot-vacuum', name: 'Robot Vacuum' },
    { slug: 'steam-cleaner', name: 'Steam Cleaner' },
    { slug: 'uv-mite-remover', name: 'UV Mite Remover' },
    { slug: 'window-cleaner-robot', name: 'Window Cleaning Robot' },
    { slug: 'car-vacuum', name: 'Car Vacuum' },
    { slug: 'tire-inflator', name: 'Tire Inflator' },
    { slug: 'coffee-machine', name: 'Coffee Machine' },
    { slug: 'upright-steam-mop', name: 'Upright Steam Mop' }
  ];
  var LANG = 'en';
  var state = { images: [], category: CATS[0].slug, data: null };

  function $(id) { return document.getElementById(id); }
  function esc(s) { return (s == null ? '' : String(s)).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
  function setStatus(m) { $('status').textContent = m; }

  function init() {
    var cs = $('catSel');
    CATS.forEach(function (c) {
      var o = document.createElement('option');
      o.value = c.slug; o.textContent = c.name; cs.appendChild(o);
    });
    $('langSel').addEventListener('change', function () { LANG = this.value; });
    cs.addEventListener('change', function () { state.category = this.value; });
    $('loadBtn').addEventListener('click', loadProduct);
    $('newBtn').addEventListener('click', function () { renderForm(blank()); setStatus('New blank product for ' + state.category); });
    $('exportBtn').addEventListener('click', exportJson);
    $('importBtn').addEventListener('click', function () { $('importFile').click(); });
    $('importFile').addEventListener('change', importJson);
    renderForm(blank());
  }

  function blank() {
    return {
      id: state.category + '-001', name: '', tagline: '', model: '',
      images: [], video_url: '', moq: 200,
      certifications: [], highlights: [], specs: [], packaging: [], applications: [],
      price_ladder: [{ min: 200, max: 499, price: 0 }, { min: 500, max: 999, price: 0 }, { min: 1000, max: null, price: 0 }],
      supplier_rating: 4.8, response_time: '<=2h', transactions: 'US$100K+', years: 10, ship_from: 'Ningbo',
      sample: { enable: true, price: 0, moq: 5 },
      description: []
    };
  }

  function renderForm(d) {
    state.data = d;
    if (!d.images) d.images = [];
    state.images = d.images.slice();
    var h = '';
    h += sec('Basic', [
      fld('name', 'Product Name', d.name || '', 'text'),
      fld('model', 'Model', d.model || '', 'text'),
      fld('tagline', 'Tagline', d.tagline || '', 'text'),
      fld('moq', 'MOQ (min order qty)', d.moq || '', 'number')
    ]);
    h += sec('Price Ladder (3 tiers)', renderLadder(d.price_ladder || blank().price_ladder));
    h += sec('Certifications (comma separated)', '<div class="admin-grid"><div class="full">' + fld('certifications', '', (d.certifications || []).join(', '), 'text') + '</div></div>');
    h += sec('Selling Points / Highlights', renderList('highlights', d.highlights || []));
    h += sec('Specifications (key : value)', renderKV('specs', d.specs || []));
    h += sec('Packaging & Shipping (key : value)', renderKV('packaging', d.packaging || []));
    h += sec('Applications (comma/tags)', '<div class="admin-grid"><div class="full">' + fld('applications', '', (d.applications || []).join(', '), 'text') + '</div></div>');
    h += sec('Images & Video', renderImages() + '<div class="admin-drop" id="drop">Click or drop image files here (multiple)</div><input type="file" id="imgInput" accept="image/*" multiple hidden>');
    h += sec('Video URL', fld('video_url', 'YouTube / external video URL', d.video_url || '', 'text'));
    h += sec('Description (paragraphs)', renderList('description', d.description || [], true));
    h += sec('Supplier', [
      fld('supplier_rating', 'Rating', d.supplier_rating || '', 'text'),
      fld('response_time', 'Response Time', d.response_time || '', 'text'),
      fld('transactions', 'Transactions', d.transactions || '', 'text'),
      fld('years', 'Years', d.years || '', 'text'),
      fld('ship_from', 'Ship From', d.ship_from || '', 'text')
    ]);
    h += sec('Sample Order', '<div class="admin-grid"><div>' + fld('sample_price', 'Sample Price', (d.sample && d.sample.price) || '', 'text') + '</div><div>' + fld('sample_moq', 'Sample MOQ', (d.sample && d.sample.moq) || '', 'text') + '</div></div>');
    h += '<div class="admin-actions"><button class="btn-primary" id="saveBtn">Save Draft (local)</button></div>';
    $('formArea').innerHTML = h;
    bindDynamic();
  }

  function sec(title, inner) { return '<div class="admin-sec"><h3>' + esc(title) + '</h3>' + inner + '</div>'; }
  function fld(key, label, val, type) {
    return '<div class="admin-field"><label>' + esc(label) + '</label><input id="f_' + key + '" type="' + type + '" value="' + esc(val) + '"></div>';
  }
  function renderLadder(p) {
    var g = '<div class="admin-grid">';
    p.forEach(function (t, i) {
      g += '<div class="admin-row"><span class="k">Tier ' + (i + 1) + '</span>' +
        '<input placeholder="min" id="pl_min_' + i + '" value="' + esc(t.min == null ? '' : t.min) + '">' +
        '<input placeholder="max" id="pl_max_' + i + '" value="' + esc(t.max == null ? '' : t.max) + '">' +
        '<input placeholder="price" id="pl_price_' + i + '" value="' + esc(t.price == null ? '' : t.price) + '"></div>';
    });
    return g + '</div>';
  }
  function renderList(key, arr, textarea) {
    var id = 'list_' + key;
    var g = '<div id="' + id + '">';
    arr.forEach(function (it, i) {
      var v = typeof it === 'string' ? it : (it.text || '');
      g += '<div class="admin-row"><input value="' + esc(v) + '" data-i="' + i + '">' +
        '<button class="admin-mini del" data-del="' + key + '" data-i="' + i + '">✕</button></div>';
    });
    g += '</div><button class="admin-mini" id="add_' + key + '">+ Add</button>';
    return g;
  }
  function renderKV(key, arr) {
    var id = 'kv_' + key;
    var g = '<div id="' + id + '">';
    arr.forEach(function (it, i) {
      g += '<div class="admin-row"><input class="k" placeholder="key" value="' + esc(it.name || '') + '" data-k="' + i + '">' +
        '<input class="v" placeholder="value" value="' + esc(it.value || '') + '" data-v="' + i + '">' +
        '<button class="admin-mini del" data-kvdel="' + key + '" data-i="' + i + '">✕</button></div>';
    });
    g += '</div><button class="admin-mini" id="addkv_' + key + '">+ Add</button>';
    return g;
  }
  function renderImages() {
    var g = '<div class="admin-imgs" id="imgList">';
    state.images.forEach(function (src, i) {
      g += '<div class="admin-img"><img src="' + esc(src) + '"><button class="x" data-img="' + i + '">✕</button></div>';
    });
    return g + '</div>';
  }
  function bindDynamic() {
    $('saveBtn').addEventListener('click', saveDraft);
    ['highlights', 'description'].forEach(function (k) {
      var el = $('add_' + k); if (el) el.addEventListener('click', function () {
        var arr = collectList(k); arr.push(''); renderForm(Object.assign({}, state.data, listKey(k, arr)));
      });
      document.querySelectorAll('[data-del="' + k + '"]').forEach(function (b) {
        b.addEventListener('click', function () {
          var arr = collectList(k); arr.splice(+b.dataset.i, 1); renderForm(Object.assign({}, state.data, listKey(k, arr)));
        });
      });
    });
    ['specs', 'packaging'].forEach(function (k) {
      var el = $('addkv_' + k); if (el) el.addEventListener('click', function () {
        var arr = collectKV(k); arr.push({ name: '', value: '' }); renderForm(Object.assign({}, state.data, kvKey(k, arr)));
      });
      document.querySelectorAll('[data-kvdel="' + k + '"]').forEach(function (b) {
        b.addEventListener('click', function () {
          var arr = collectKV(k); arr.splice(+b.dataset.i, 1); renderForm(Object.assign({}, state.data, kvKey(k, arr)));
        });
      });
    });
    document.querySelectorAll('[data-img]').forEach(function (b) {
      b.addEventListener('click', function () { state.images.splice(+b.dataset.img, 1); $('imgList').innerHTML = renderImages().replace(/^<div[^>]*>|<\/div>$/g, ''); bindImg(); });
    });
    bindImg();
  }
  function bindImg() {
    var drop = $('drop'), inp = $('imgInput');
    if (!drop) return;
    drop.addEventListener('click', function () { inp.click(); });
    drop.addEventListener('dragover', function (e) { e.preventDefault(); });
    drop.addEventListener('drop', function (e) { e.preventDefault(); handleFiles(e.dataTransfer.files); });
    inp.addEventListener('change', function () { handleFiles(inp.files); });
  }
  function handleFiles(files) {
    Array.prototype.forEach.call(files, function (f) {
      if (!f.type.match(/image\//)) return;
      var r = new FileReader();
      r.onload = function (e) { state.images.push(e.target.result); $('imgList').innerHTML = renderImages().replace(/^<div[^>]*>|<\/div>$/g, ''); bindImg(); };
      r.readAsDataURL(f);
    });
  }
  function listKey(k, arr) { var o = {}; o[k] = arr; return o; }
  function kvKey(k, arr) { var o = {}; o[k] = arr; return o; }
  function collectList(k) {
    var arr = [];
    document.querySelectorAll('#list_' + k + ' input').forEach(function (i) { arr.push(i.value); });
    return arr;
  }
  function collectKV(k) {
    var arr = [];
    document.querySelectorAll('#kv_' + k + ' .admin-row').forEach(function (row) {
      arr.push({ name: row.querySelector('.k').value, value: row.querySelector('.v').value });
    });
    return arr;
  }
  function saveDraft() {
    var d = state.data;
    d.name = val('name'); d.model = val('model'); d.tagline = val('tagline'); d.moq = num('moq');
    d.certifications = splitCsv(val('certifications'));
    d.highlights = collectList('highlights').map(function (t) { return { text: t, icon: '💡' }; }).filter(function (x) { return x.text; });
    d.specs = collectKV('specs').filter(function (x) { return x.name || x.value; });
    d.packaging = collectKV('packaging').filter(function (x) { return x.name || x.value; });
    d.applications = splitCsv(val('applications'));
    d.images = state.images.slice();
    d.video_url = val('video_url');
    d.description = collectList('description').filter(function (t) { return t; });
    d.supplier_rating = val('supplier_rating'); d.response_time = val('response_time');
    d.transactions = val('transactions'); d.years = num('years'); d.ship_from = val('ship_from');
    d.price_ladder = [0, 1, 2].map(function (i) { return { min: num('pl_min_' + i), max: num('pl_max_' + i), price: num('pl_price_' + i) }; });
    d.sample = { enable: true, price: val('sample_price'), moq: num('sample_moq') };
    d.id = state.category + '-' + (d.model || '001').toString().replace(/[^A-Za-z0-9]/g, '').toUpperCase().slice(0, 6) || (state.category + '-001');
    d.category_name = (CATS.filter(function (c) { return c.slug === state.category; })[0] || {}).name || '';
    try { localStorage.setItem('aqc_admin_' + LANG + '_' + state.category, JSON.stringify(d)); } catch (e) {}
    setStatus('Draft saved locally for ' + LANG + ' / ' + state.category + ' at ' + new Date().toLocaleTimeString());
  }
  function exportJson() {
    saveDraft();
    var blob = new Blob([JSON.stringify(state.data, null, 2)], { type: 'application/json' });
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = state.category + '.json';
    a.click();
    setStatus('Exported ' + state.category + '.json — send it to publish.');
  }
  function importJson(e) {
    var f = e.target.files[0]; if (!f) return;
    var r = new FileReader();
    r.onload = function (ev) { try { renderForm(JSON.parse(ev.target.result)); setStatus('Imported ' + f.name); } catch (x) { setStatus('Invalid JSON'); } };
    r.readAsText(f);
  }
  function loadProduct() {
    var url = '/data/products/' + state.category + '.json?v=' + Date.now();
    var x = new XMLHttpRequest();
    x.open('GET', url, true);
    x.onload = function () {
      if (x.status === 200) { try { var d = JSON.parse(x.responseText); renderForm(d); setStatus('Loaded live ' + state.category + '.json'); } catch (e) { setStatus('Parse error'); } }
      else { renderForm(blank()); setStatus('No live data, started blank for ' + state.category); }
    };
    x.onerror = function () { renderForm(blank()); setStatus('Network error, started blank'); };
    x.send();
  }
  function val(k) { var el = $('f_' + k); return el ? el.value : ''; }
  function num(k) { var v = val(k); return v === '' || v == null ? null : (isNaN(+v) ? v : +v); }
  function splitCsv(s) { return (s || '').split(',').map(function (x) { return x.trim(); }).filter(function (x) { return x; }); }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
