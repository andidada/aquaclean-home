#!/usr/bin/env node
/**
 * Full round trip: 后台上传图文 → 修改内容 → 🚀 发布 → 前台真的显示出来。
 *
 * This is the "run the back office end to end" test. It does not mock the
 * admin's own logic — it boots the real admin/index.html + admin.js in jsdom,
 * drags files onto the real drop zones, clicks the real publish button, then
 * feeds whatever landed in the commit payload to the *real* front-end code
 * (assets/js/product-detail.js DETAIL block, assets/js/home-loader.js).
 *
 * Steps
 *   1. drag two images onto the 详情页 drop zone -> GitHub upload
 *   2. fill the detail body (with [[img:1]]), plus specs / colors / packaging
 *   3. click 🚀 发布到线上, capture the exact JSON that would be committed
 *   4. assert every edited field is in that JSON, and untouched ones survive
 *   5. render that JSON through the real product-detail.js DETAIL block
 *   6. render a CMS-edited home JSON through the real home-loader.js and check
 *      the hero actually updates (and that HTML from the CMS is sanitised)
 *
 * Run:  node scripts/verify_admin_roundtrip.js
 */
'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const { JSDOM } = require(process.env.JSDOM_PATH ||
  'C:/Users/Administrator/.workbuddy/binaries/node/workspace/node_modules/jsdom');

const ROOT = path.dirname(__dirname);
const ADMIN = path.join(ROOT, 'admin');
const ORIGIN = 'https://aquaclean-admin.app.workbuddy.host';
const PUBLIC = 'https://www.hkdmj.net';

let pass = 0, fail = 0;
function ok(name, cond, extra) {
  if (cond) { pass++; console.log('  ✓ ' + name); }
  else { fail++; console.log('  ✗ ' + name + (extra !== undefined ? '  → ' + JSON.stringify(extra) : '')); }
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

const EXISTING = {
  category: 'handheld-vacuum',
  products: [{
    id: 'gv18',
    name: { en: 'V18 Cordless Stick Vacuum', zh: 'V18 无线立式吸尘器' },
    tagline: { en: '400W Brushless' },
    images: [PUBLIC + '/assets/images/products/handheld-vacuum-gv18/01-main.webp'],
    moq: { value: 2, unit: 'pieces' },
    certifications: [],
    specs: [
      { label: { en: 'Model' }, value: { en: 'GV18' } },
      { label: { en: 'Motor Power' }, value: { en: '400W' } },
      { label: { en: 'Net Weight' }, value: { en: '2.4kg' } }
    ],
    quick_specs: [{ label: { en: 'Motor Power' }, value: { en: '400W' } }],
    packaging: { unit: 'Color Box', ctn_size: '45x34x21cm', ctn_qty: '—', gross_weight: '3.0kg' },
    customization: { oem: true, odm: true, logo: null, color: true, package: null },
    applications: { en: 'Household', zh: '家庭' },
    price_indicator: { min: 54, max: 64, currency: 'USD' },
    price_ladder: [{ min: 2, max: 199, price: 64 }, { min: 200, max: 999, price: 62 }],
    sku: [{ name: { en: 'Colour' }, values: [{ name: 'Purple' }] }],
    description: { en: 'old description' },
    highlights: [{ id: 'gv18' }],
    supplier: { country: 'HK' }
  }]
};

const HOME_FIXTURE = {
  hero: { badge: 'old badge', h1: 'old h1', sub: 'old sub',
          btn_primary_text: 'Quote', btn_primary_href: '#contact',
          btn_outline_text: 'Products', btn_outline_href: '#products' },
  products: [
    { id: 'p1', name: 'Handheld Vacuum', slug: 'handheld-vacuum', desc: 'd1',
      img: '../assets/images/products/01-handheld-vacuum.webp',
      btn_text: 'More Products', btn_href: '/en/handheld-vacuum/', tags: ['120W'] }
  ],
  contact: { h2: 'Contact', email: 'a@b.c', phone: '+8617779190118', whatsapp: '', address: '', hours: '' },
  footer: { company_name: 'AquaClean', description: '', email: '', phone: '' }
};

// ── 1~4：真实后台跑一遍 ────────────────────────────────────────────
function bootAdmin() {
  const state = { netLog: [], repo: {} };
  // 模拟真实仓库：raw.githubusercontent 读它，PUT 写它。
  // （固定返回初始 fixture 的话，后一步"切语言再发布"就会拉到旧值，
  //   测不出"中文发布会不会覆盖英文"这种真问题。）
  const repoPath = u => {
    const m = String(u).match(/\/main\/(.+?)(\?|$)/);
    return m ? m[1] : null;
  };
  const html = fs.readFileSync(path.join(ADMIN, 'index.html'), 'utf8')
    .replace(/<script[^>]*><\/script>/g, '');
  const dom = new JSDOM(html, { url: ORIGIN + '/admin/index.html', runScripts: 'dangerously', pretendToBeVisual: true });
  const win = dom.window;

  win.XMLHttpRequest = function () {
    return { open(m, u) { this._u = String(u); }, setRequestHeader() {},
      send() { setTimeout(() => {
        const key = repoPath(this._u);
        const want = key && state.repo[key] !== undefined;
        if (!want && this._u.indexOf('pages/home/en.json') !== -1) {
          this.status = 200; this.responseText = JSON.stringify(HOME_FIXTURE);
        } else {
          this.status = want ? 200 : 404;
          this.responseText = want ? JSON.stringify(state.repo[key]) : '';
        }
        if (this.onload) this.onload();
      }, 0); } };
  };
  win.fetch = function (url, o) {
    const u = String(url);
    const method = (o && o.method) || 'GET';
    const rec = { url: u, method, body: o && o.body ? JSON.parse(o.body) : null };
    state.netLog.push(rec);
    if (u.indexOf('raw.githubusercontent.com') !== -1) {
      const key = repoPath(u);
      const has = key && state.repo[key] !== undefined;
      return Promise.resolve({ ok: !!has, status: has ? 200 : 404,
        json: () => Promise.resolve(has ? JSON.parse(JSON.stringify(state.repo[key])) : null) });
    }
    if (u.indexOf('api.github.com') !== -1) {
      if (method === 'PUT' && rec.body && rec.body.content) {
        const key = decodeURIComponent((u.match(/contents\/(.+?)(\?|$)/) || ['', ''])[1]);
        // 只有 JSON 文件才回写仓库；图片是二进制，解析会抛
        if (/\.json$/i.test(key)) {
          try {
            state.repo[key] = JSON.parse(Buffer.from(rec.body.content, 'base64').toString('utf8'));
          } catch (e) { /* 忽略非 JSON 内容 */ }
        }
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ content: { sha: 'deadbeefcafe' } }) });
    }
    return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) });
  };
  win.confirm = () => true;
  win.alert = () => {};
  win.sessionStorage.setItem('admin_gh_token', 'ghp_roundtrip');

  const el = win.document.createElement('script');
  el.textContent = fs.readFileSync(path.join(ADMIN, 'admin.js'), 'utf8');
  win.document.body.appendChild(el);
  // 仓库初始内容
  state.repo['data/products/handheld-vacuum.json'] = JSON.parse(JSON.stringify(EXISTING));
  state.repo['data/pages/home/en.json'] = JSON.parse(JSON.stringify(HOME_FIXTURE));
  return { win, state, $: id => win.document.getElementById(id) };
}

function dropFiles(win, el, files) {
  const ev = new win.Event('drop', { bubbles: true, cancelable: true });
  ev.dataTransfer = { files: files };
  el.dispatchEvent(ev);
}

(async function run() {
  console.log('\n== 1. 拖放上传详情图 ==');
  const { win, state, $ } = bootAdmin();
  await sleep(300);
  ok('产品表单已渲染', !!$('p-detail-drop'));

  const f1 = new win.File([new Uint8Array([1, 2, 3])], 'detail shot 1.webp', { type: 'image/webp' });
  const f2 = new win.File([new Uint8Array([4, 5, 6])], 'detail-2.webp', { type: 'image/webp' });
  dropFiles(win, $('p-detail-drop'), [f1, f2]);
  await sleep(600);

  const urls = ($('p-detail-imgs').value || '').split('\n').filter(Boolean);
  ok('两张图都回填进了 URL 框', urls.length === 2, urls);
  ok('URL 是绝对地址（后台域也能预览）',
    urls.every(u => u.indexOf(PUBLIC + '/assets/images/uploads/') === 0), urls);
  ok('文件名被安全化（空格转下划线）', urls.every(u => !/\s/.test(u)), urls);
  ok('预览区渲染出缩略图', ($('p-detail-preview').querySelectorAll('img') || []).length === 2,
    $('p-detail-preview').innerHTML.slice(0, 80));

  console.log('\n== 2. 填写图文与其它字段 ==');
  $('p-detail').value = '第一段介绍文案。\n\n[[img:1]]\n\n第二段介绍文案。';
  $('p-name').value = 'V18 Pro Max';
  $('p-power').value = '500W';
  $('p-colors').value = 'Black, White';
  $('p-package').value = 'Gift Box';
  $('p-dims').value = '50x40x30cm';
  $('p-logo').value = 'yes';
  $('p-applications').value = 'Home, Office';
  $('p-price_display').value = '$58.00 - 68.00';

  console.log('\n== 3. 点「🚀 发布到线上」 ==');
  state.netLog.length = 0;                       // 只统计发布这一步（上传的 PUT 不算）
  $('p-publish').click();
  await sleep(700);
  const put = state.netLog.filter(r => r.method === 'PUT'
    && (r.url.indexOf('data%2Fproducts%2F') !== -1 || r.url.indexOf('data/products/') !== -1));
  ok('发布了 1 次（且是产品 JSON）', put.length === 1, state.netLog.map(r => r.method + ' ' + r.url.slice(-40)));
  if (!put.length) { console.log('\n❌ 没有提交，后续断言跳过\n'); process.exit(1); }

  const published = JSON.parse(Buffer.from(put[0].body.content, 'base64').toString('utf8'));
  const p = published.products[0];

  console.log('\n== 4. 提交内容核对 ==');
  ok('类别字段没被抹掉', published.category === 'handheld-vacuum', published.category);
  ok('highlights / supplier 等表单不管的字段仍在',
    !!p.highlights && !!p.supplier, { h: !!p.highlights, s: !!p.supplier });
  ok('名称已更新（英文）', p.name.en === 'V18 Pro Max', p.name);
  ok('中文名没被覆盖', p.name.zh === 'V18 无线立式吸尘器', p.name);
  ok('详情页正文已写入 detail', !!p.detail && /第一段介绍文案/.test(p.detail.en || p.detail), p.detail);
  ok('正文里的 [[img:1]] 保留', /\[\[img:1\]\]/.test(p.detail.en || p.detail));
  ok('详情图 2 张都进了 detail_images', Array.isArray(p.detail_images) && p.detail_images.length === 2, p.detail_images);
  ok('功率写进了 specs[Motor Power]',
    (p.specs.find(s => s.label.en === 'Motor Power') || {}).value &&
    /500W/.test(JSON.stringify(p.specs.find(s => s.label.en === 'Motor Power').value)),
    p.specs.find(s => s.label.en === 'Motor Power'));
  ok('quick_specs 同步（首页摘要）',
    /500W/.test(JSON.stringify(p.quick_specs[0].value)), p.quick_specs[0]);
  ok('颜色写进 sku[Colour]',
    JSON.stringify(p.sku[0].values) === JSON.stringify([{ name: 'Black' }, { name: 'White' }]), p.sku[0]);
  ok('包装规格写进 packaging.unit', p.packaging.unit === 'Gift Box', p.packaging);
  ok('体积写进 packaging.ctn_size', p.packaging.ctn_size === '50x40x30cm', p.packaging);
  ok('packaging 仍是对象（详情页靠它渲染）', typeof p.packaging === 'object' && !Array.isArray(p.packaging));
  ok('Logo 定制变成 true', p.customization.logo === true, p.customization);
  ok('适用场景是字符串', typeof p.applications === 'object' && /Home, Office/.test(p.applications.en), p.applications);
  ok('价格区间解析进 price_indicator', p.price_indicator.min === 58 && p.price_indicator.max === 68, p.price_indicator);

  console.log('\n== 5. 用前台真实的 product-detail.js 渲染这段详情 ==');
  const src = fs.readFileSync(path.join(ROOT, 'assets', 'js', 'product-detail.js'), 'utf8');
  const start = src.indexOf('// ===== DETAIL (图文混排) =====');
  const end = src.indexOf('// ===== INQUIRY FORM =====');
  ok('找到了 DETAIL 渲染块', start > 0 && end > start);
  const block = src.slice(start, end);
  const sandbox = {
    html: '', state: { lang: 'en' }, product: p,
    ui: { detail: 'Product Details' },
    pick: (o, lang) => (o == null ? '' : typeof o === 'string' ? o : (o[lang] || o.en || '')),
    esc: s => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'),
    localImg: u => String(u || '').replace(/^https?:\/\/[^/]+/i, '')
  };
  vm.createContext(sandbox);
  vm.runInContext(block, sandbox);
  const out = sandbox.html;
  ok('渲染出了详情区块', out.indexOf('aqc-detail-block') !== -1);
  ok('两段正文都在', /第一段介绍文案/.test(out) && /第二段介绍文案/.test(out));
  ok('[[img:1]] 位置的图插进去了', (out.match(/aqc-inline-img/g) || []).length === 1,
    (out.match(/aqc-inline-img/g) || []).length);
  ok('没被引用的第 2 张图自动排在后面', (out.match(/aqc-detail-imgs/g) || []).length === 1);
  ok('图片 src 已转成本站相对路径（不会走后台域）',
    out.indexOf(PUBLIC) === -1 && /src="\/assets\/images\/uploads\//.test(out),
    (out.match(/src="[^"]*"/g) || []).slice(0, 2));

  console.log('\n== 6. 前台 home-loader 真的会改 Hero（并做 HTML 消毒） ==');
  const homeJson = {
    hero: {
      badge: '新徽章',
      h1: '改过的标题<script>alert(1)</script>',
      sub: '改过的副标题',
      btn_primary_text: '立即询价', btn_primary_href: '#contact',
      btn_outline_text: '看产品', btn_outline_href: '#products'
    },
    products: [], contact: {}, footer: {}
  };
  const dom2 = new JSDOM(fs.readFileSync(path.join(ROOT, 'en', 'index.html'), 'utf8')
    .replace(/<script src="[^"]*"><\/script>/g, ''),   // 不跑外部脚本
    { url: PUBLIC + '/en/', runScripts: 'dangerously' });
  const win2 = dom2.window;
  win2.XMLHttpRequest = function () {
    return { open(m, u) { this._u = String(u); }, setRequestHeader() {},
      send() { setTimeout(() => {
        const want = this._u.indexOf('/data/pages/home/en.json') !== -1;
        this.status = want ? 200 : 404;
        this.responseText = want ? JSON.stringify(homeJson) : '';
        if (this.onload) this.onload();
      }, 0); } };
  };
  const hl = win2.document.createElement('script');
  hl.textContent = fs.readFileSync(path.join(ROOT, 'assets', 'js', 'home-loader.js'), 'utf8');
  win2.document.body.appendChild(hl);
  await sleep(300);

  const h1 = win2.document.querySelector('#heroCarousel .hero-slide h1');
  ok('英文站 H1 被 CMS 改掉了', !!h1 && /改过的标题/.test(h1.textContent), h1 && h1.textContent);
  ok('注入的 <script> 被剥掉了（只剩文字）', !!h1 && h1.querySelector('script') === null,
    h1 && h1.innerHTML.slice(0, 60));
  ok('副标题也更新了', /改过的副标题/.test(win2.document.body.textContent));
  ok('移动端汉堡按钮由 nav.js 注入', (function () {
    const nav = win2.document.createElement('script');
    // 页面里已引用 /assets/js/nav.js，这里等价地跑一次它的逻辑
    nav.textContent = fs.readFileSync(path.join(ROOT, 'assets', 'js', 'nav.js'), 'utf8');
    win2.document.body.appendChild(nav);
    return !!win2.document.querySelector('.nav-toggle');
  })());

  console.log('\n== 7. 首页 Tab：改 Hero 后发布 ==');
  const homeTab = [].slice.call(win.document.querySelectorAll('button'))
    .filter(b => /首页|🏠/.test(b.textContent))[0];
  if (homeTab) {
    homeTab.click();
    await sleep(400);
    // 首页数据线上拉不到（XHR 一律 404），表单字段会是空的，直接填值即可
    if ($('h-h1')) $('h-h1').value = 'Smart Cleaning Appliances<br>Built for <span>Global Markets</span>';
    if ($('h-badge')) $('h-badge').value = '🇨🇳 OEM / ODM · Since 2015';
    state.netLog.length = 0;
    $('h-publish').click();
    await sleep(600);
    const hput = state.netLog.filter(r => r.method === 'PUT'
      && (r.url.indexOf('data%2Fpages%2Fhome%2F') !== -1 || r.url.indexOf('data/pages/home/') !== -1));
    ok('首页发布了 1 次', hput.length === 1, state.netLog.map(r => r.method + ' ' + r.url.slice(-35)));
    if (hput.length) {
      const hj = JSON.parse(Buffer.from(hput[0].body.content, 'base64').toString('utf8'));
      ok('Hero H1 原样写进 JSON', hj.hero.h1.indexOf('Global Markets') !== -1, hj.hero.h1);
      ok('徽章写进 JSON', hj.hero.badge.indexOf('OEM') !== -1, hj.hero.badge);
      ok('全空的卡片行不会写进 JSON（避免空壳）',
        Array.isArray(hj.products) && hj.products.every(x => x.name || x.img || x.desc),
        hj.products && hj.products.length);
    }
  } else {
    console.log('  (找不到首页 tab 按钮，跳过)');
  }

  console.log('\n== 8. 切到中文再发布：中文要写进 zh，不能覆盖英文 ==');
  if (win._aqc && typeof win._aqc.loadProduct === 'function') {
    win._aqc.loadProduct('handheld-vacuum', 'zh');
    await sleep(300);
    $('p-name').value = 'V18 Pro Max 无线';
    state.netLog.length = 0;
    $('p-publish').click();
    await sleep(700);
    const zput = state.netLog.filter(r => r.method === 'PUT' && r.url.indexOf('products') !== -1);
    if (zput.length) {
      const z = JSON.parse(Buffer.from(zput[zput.length - 1].body.content, 'base64').toString('utf8'));
      const zp = z.products[0];
      ok('英文名仍然是 V18 Pro Max', zp.name.en === 'V18 Pro Max', zp.name);
      ok('中文名写进了 zh', zp.name.zh === 'V18 Pro Max 无线', zp.name);
    } else {
      ok('中文发布产生了提交', false, state.netLog.map(r => r.method + ' ' + r.url.slice(-30)));
    }
  } else {
    console.log('  (window._aqc.loadProduct 不可用，跳过)');
  }

  console.log('\n' + (fail === 0 ? '✅ 全部通过' : '❌ 失败') + '：' + pass + ' passed, ' + fail + ' failed\n');
  process.exit(fail === 0 ? 0 : 1);
})().catch(e => { console.error('测试崩溃：', e); process.exit(1); });
