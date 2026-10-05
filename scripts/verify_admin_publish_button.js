#!/usr/bin/env node
/**
 * GUI smoke test: the admin must expose a visible "publish" action.
 *
 * Until 2026-10-05 there was no publish button at all — deploying was hidden
 * inside a confirm() dialog behind 「💾 保存草稿」, so operators added product
 * data and had no idea nothing had gone live. This test drives the real
 * admin/index.html + admin.js in jsdom and asserts:
 *
 *   1. every content tab renders a 🚀 publish button
 *   2. 保存草稿 touches only localStorage (no GitHub write)
 *   3. 🚀 发布到线上 really PUTs to api.github.com
 *
 * Run:  node scripts/verify_admin_publish_button.js
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH ||
  'C:/Users/Administrator/.workbuddy/binaries/node/workspace/node_modules/jsdom');

const ROOT = path.dirname(__dirname);
const ADMIN = path.join(ROOT, 'admin');
const ORIGIN = 'https://aquaclean-admin.app.workbuddy.host';

let pass = 0, fail = 0;
function ok(name, cond, extra) {
  if (cond) { pass++; console.log('  ✓ ' + name); }
  else { fail++; console.log('  ✗ ' + name + (extra !== undefined ? '  → ' + JSON.stringify(extra) : '')); }
}

// 去掉外部脚本（云 SDK / 守卫），只保留容器；admin.js 由我们手动注入
let html = fs.readFileSync(path.join(ADMIN, 'index.html'), 'utf8')
  .replace(/<script[^>]*><\/script>/g, '');

const dom = new JSDOM(html, {
  url: ORIGIN + '/admin/index.html',
  runScripts: 'dangerously',
  pretendToBeVisual: true
});
const win = dom.window;

// ── 假网络层 ────────────────────────────────────────────────────
const netLog = [];
const FIXTURE = {
  'data/products/handheld-vacuum.json': {
    category: 'handheld-vacuum',
    products: [{
      id: 'gv18', name: { en: 'V18', zh: 'V18 无线' }, tagline: { en: '400W' },
      specs: [{ label: { en: 'Model' }, value: { en: 'GV18' } }],
      quick_specs: [], images: [], moq: { value: 2, unit: 'pieces' },
      packaging: { unit: 'Color Box' }, customization: {}, applications: {},
      price_indicator: { min: 54, max: 64, currency: 'USD' }, price_ladder: [], sku: []
    }]
  },
  'data/pages/home/en.json': {
    hero: { badge: 'b', h1: 'h1', sub: 'sub', btn_primary_text: 'a', btn_primary_href: '#x',
            btn_outline_text: 'b', btn_outline_href: '#y' },
    products: [{ id: 'p1', name: 'x', slug: '', desc: 'd', img: '', btn_text: '', btn_href: '', tags: [] }],
    contact: { h2: 'c', email: '', phone: '', whatsapp: '', address: '', hours: '' },
    footer: { company_name: '', description: '', email: '', phone: '' }
  }
};

function fakeXhr() {
  return {
    open(method, url) { this._url = String(url); },
    setRequestHeader() {},
    send() {
      const key = Object.keys(FIXTURE).find(k => this._url.indexOf(k) !== -1);
      setTimeout(() => {
        if (key) {
          this.status = 200;
          this.responseText = JSON.stringify(FIXTURE[key]);
          if (this.onload) this.onload();
        } else {
          this.status = 404;
          if (this.onload) this.onload();
          else if (this.onerror) this.onerror();
        }
      }, 0);
    }
  };
}
win.XMLHttpRequest = fakeXhr;

win.fetch = function (url, opts) {
  const u = String(url);
  const method = (opts && opts.method) || 'GET';
  let record = { url: u, method };
  if (u.indexOf('raw.githubusercontent.com') !== -1) {
    const key = Object.keys(FIXTURE).find(k => u.indexOf(k) !== -1);
    netLog.push(record);
    return Promise.resolve({ ok: !!key, status: key ? 200 : 404, json: () => Promise.resolve(key ? FIXTURE[key] : null) });
  }
  if (u.indexOf('api.github.com') !== -1) {
    record.body = opts && opts.body ? JSON.parse(opts.body) : null;
    netLog.push(record);
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ content: { sha: 'abc1234567890' } }) });
  }
  netLog.push(record);
  return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) });
};

// 预置 Token：否则会弹出我们自己做的 Token 模态框等待人工点击
win.sessionStorage.setItem('admin_gh_token', 'ghp_fake_token_for_test');

win.confirm = function () { return true; };
win.alert = function () {};
win.prompt = function () { return 'ghp_fake_token_for_test'; };

// ── 注入真实 admin.js ───────────────────────────────────────────
const src = fs.readFileSync(path.join(ADMIN, 'admin.js'), 'utf8');
const scriptEl = win.document.createElement('script');
scriptEl.textContent = src;
win.document.body.appendChild(scriptEl);

function $(id) { return win.document.getElementById(id); }
function byText(re) {
  return [].slice.call(win.document.querySelectorAll('button'))
    .filter(b => re.test(b.textContent));
}

(async function run() {
  await new Promise(r => setTimeout(r, 300));   // 等 init + loadProduct 的 50ms 定时器

  console.log('\n== 1. 产品 Tab 有可见的发布按钮 ==');
  ok('已渲染产品表单', !!$('p-name'), !!$('p-name'));
  const pub = $('p-publish');
  ok('#p-publish 存在', !!pub);
  ok('按钮文案含「发布」', !!pub && /发布/.test(pub.textContent), pub && pub.textContent);
  ok('保存按钮标明「仅本机」', !!$('p-save') && /仅本机/.test($('p-save').textContent), $('p-save') && $('p-save').textContent);
  ok('页面上有使用提示', /只写进本浏览器|发布到线上/.test(win.document.body.textContent));

  console.log('\n== 2. 保存草稿不产生 GitHub 写操作 ==');
  netLog.length = 0;
  $('p-name').value = 'V18 Pro';
  $('p-save').click();
  await new Promise(r => setTimeout(r, 50));
  const writesAfterSave = netLog.filter(r => r.url.indexOf('api.github.com') !== -1);
  ok('保存草稿没有 PUT/POST', writesAfterSave.length === 0, writesAfterSave.map(r => r.method + ' ' + r.url));
  ok('状态栏提示要点发布', /发布到线上/.test($('status').textContent), $('status').textContent);

  console.log('\n== 3. 🚀 发布到线上真的会提交到 GitHub ==');
  netLog.length = 0;
  $('p-publish').click();
  await new Promise(r => setTimeout(r, 400));
  const commits = netLog.filter(r => r.url.indexOf('api.github.com') !== -1 && r.method === 'PUT');
  ok('产生了 1 次 PUT 提交', commits.length === 1, netLog.map(r => r.method + ' ' + r.url.slice(0, 60)));
  if (commits.length) {
    ok('提交路径是 data/products/handheld-vacuum.json',
      commits[0].url.indexOf('data%2Fproducts%2Fhandheld-vacuum.json') !== -1
      || commits[0].url.indexOf('data/products/handheld-vacuum.json') !== -1, commits[0].url);
    const content = commits[0].body && JSON.parse(atob(commits[0].body.content));
    ok('提交内容含刚才改的名称', !!content && /V18 Pro/.test(JSON.stringify(content.products[0].name)),
      content && content.products[0].name);
    ok('未破坏 JSON 中表单不管的字段', !!content && content.category === 'handheld-vacuum', content && content.category);
  }
  ok('状态栏显示已发布', /已发布/.test($('status').textContent), $('status').textContent);

  console.log('\n== 4. 首页 Tab 也有发布按钮 ==');
  const homeTab = byText(/首页|🏠/)[0];
  if (homeTab) {
    homeTab.click();
    await new Promise(r => setTimeout(r, 200));
    ok('#h-publish 存在', !!$('h-publish'));
    ok('首页保存按钮标明「仅本机」', !!$('h-save') && /仅本机/.test($('h-save').textContent));
  } else {
    console.log('  (找不到首页 tab 按钮，跳过)');
  }

  console.log('\n' + (fail === 0 ? '✅ 全部通过' : '❌ 失败') + '：' + pass + ' passed, ' + fail + ' failed\n');
  process.exit(fail === 0 ? 0 : 1);
})().catch(e => { console.error('测试崩溃：', e); process.exit(1); });
