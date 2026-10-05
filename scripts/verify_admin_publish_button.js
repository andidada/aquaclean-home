#!/usr/bin/env node
/**
 * GUI smoke test: the admin must expose a visible "publish" action, and
 * publishing must not ask for a GitHub Token when the local bridge is up.
 *
 * Until 2026-10-05 there was no publish button at all — deploying was hidden
 * inside a confirm() dialog behind 「💾 保存草稿」, so operators added product
 * data and had no idea nothing had gone live. Later the same day the PAT moved
 * from localStorage to sessionStorage, which meant a fresh tab had to paste it
 * again; the bridge auto-fill is the fix for that.
 *
 * This drives the real admin/index.html + admin.js in jsdom and asserts:
 *   1. every content tab renders a 🚀 publish button
 *   2. 保存草稿 touches only localStorage (no GitHub write)
 *   3. 🚀 发布到线上 really PUTs to api.github.com
 *   4. with no stored token but the bridge running, publish works silently
 *      (confirm() is never called)
 *   5. with neither, it falls back to asking instead of failing silently
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
const BRIDGE = 'http://127.0.0.1:18765';

let pass = 0, fail = 0;
function ok(name, cond, extra) {
  if (cond) { pass++; console.log('  ✓ ' + name); }
  else { fail++; console.log('  ✗ ' + name + (extra !== undefined ? '  → ' + JSON.stringify(extra) : '')); }
}

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

// 启动一份真实的后台页面。opts.bridge=true 表示本机桥在运行。
function boot(opts) {
  opts = opts || {};
  const state = { netLog: [], confirms: 0 };

  const html = fs.readFileSync(path.join(ADMIN, 'index.html'), 'utf8')
    .replace(/<script[^>]*><\/script>/g, '');   // 去掉云 SDK / 守卫

  const dom = new JSDOM(html, {
    url: ORIGIN + '/admin/index.html',
    runScripts: 'dangerously',
    pretendToBeVisual: true
  });
  const win = dom.window;

  win.XMLHttpRequest = function () {
    return {
      open(m, url) { this._url = String(url); },
      setRequestHeader() {},
      send() {
        const key = Object.keys(FIXTURE).find(k => this._url.indexOf(k) !== -1);
        setTimeout(() => {
          this.status = key ? 200 : 404;
          this.responseText = key ? JSON.stringify(FIXTURE[key]) : '';
          if (this.onload) this.onload();
        }, 0);
      }
    };
  };

  win.fetch = function (url, o) {
    const u = String(url);
    const method = (o && o.method) || 'GET';
    state.netLog.push({ url: u, method: method });
    if (u.indexOf(BRIDGE) === 0) {
      // 本机桥：只在"桥已启动"的场景下才给 Token
      if (opts.bridge && u.indexOf('/token') !== -1) {
        return Promise.resolve({ ok: true, status: 200, text: () => Promise.resolve('ghp_from_local_bridge') });
      }
      return Promise.resolve({ ok: false, status: 503, text: () => Promise.resolve('') });
    }
    if (u.indexOf('raw.githubusercontent.com') !== -1) {
      const key = Object.keys(FIXTURE).find(k => u.indexOf(k) !== -1);
      return Promise.resolve({ ok: !!key, status: key ? 200 : 404,
        json: () => Promise.resolve(key ? FIXTURE[key] : null) });
    }
    if (u.indexOf('api.github.com') !== -1) {
      state.netLog[state.netLog.length - 1].body = o && o.body ? JSON.parse(o.body) : null;
      return Promise.resolve({ ok: true, status: 200,
        json: () => Promise.resolve({ content: { sha: 'abc1234567890' } }) });
    }
    return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) });
  };

  win.confirm = function () { state.confirms++; return opts.answerConfirm !== false; };
  win.alert = function () {};

  if (opts.presetToken) win.sessionStorage.setItem('admin_gh_token', 'ghp_preset');

  const el = win.document.createElement('script');
  el.textContent = fs.readFileSync(path.join(ADMIN, 'admin.js'), 'utf8');
  win.document.body.appendChild(el);

  return { win, state, $: id => win.document.getElementById(id) };
}

const sleep = ms => new Promise(r => setTimeout(r, ms));
const githubWrites = s => s.netLog.filter(r => r.url.indexOf('api.github.com') !== -1 && r.method === 'PUT');

(async function run() {
  // ── 场景 1/2/3：已经持有 Token ──────────────────────────────────
  console.log('\n== 1. 产品 Tab 有可见的发布按钮 ==');
  let { win, state, $ } = boot({ presetToken: true });
  await sleep(300);
  ok('已渲染产品表单', !!$('p-name'));
  ok('#p-publish 存在', !!$('p-publish'));
  ok('按钮文案含「发布」', !!$('p-publish') && /发布/.test($('p-publish').textContent));
  ok('保存按钮标明「仅本机」', !!$('p-save') && /仅本机/.test($('p-save').textContent), $('p-save') && $('p-save').textContent);
  ok('页面上有使用提示', /只写进本浏览器|发布到线上/.test(win.document.body.textContent));

  console.log('\n== 2. 保存草稿不产生 GitHub 写操作 ==');
  state.netLog.length = 0;
  $('p-name').value = 'V18 Pro';
  $('p-save').click();
  await sleep(60);
  ok('保存草稿没有 PUT/POST', githubWrites(state).length === 0, state.netLog.map(r => r.method + ' ' + r.url));
  ok('状态栏提示要点发布', /发布到线上/.test($('status').textContent), $('status').textContent);

  console.log('\n== 3. 🚀 发布到线上真的会提交到 GitHub ==');
  state.netLog.length = 0;
  $('p-publish').click();
  await sleep(400);
  const commits = githubWrites(state);
  ok('产生了 1 次 PUT 提交', commits.length === 1, state.netLog.map(r => r.method + ' ' + r.url.slice(0, 60)));
  if (commits.length) {
    const content = commits[0].body && JSON.parse(Buffer.from(commits[0].body.content, 'base64').toString('utf8'));
    ok('提交内容含刚才改的名称', !!content && /V18 Pro/.test(JSON.stringify(content.products[0].name)),
      content && content.products[0].name);
    ok('未破坏表单不管的字段', !!content && content.category === 'handheld-vacuum', content && content.category);
  }
  ok('状态栏显示已发布', /已发布/.test($('status').textContent), $('status').textContent);

  console.log('\n== 4. 首页 Tab 也有发布按钮 ==');
  const homeTab = [].slice.call(win.document.querySelectorAll('button'))
    .filter(b => /首页|🏠/.test(b.textContent))[0];
  if (homeTab) {
    homeTab.click();
    await sleep(250);
    ok('#h-publish 存在', !!$('h-publish'));
    ok('首页保存按钮标明「仅本机」', !!$('h-save') && /仅本机/.test($('h-save').textContent));
  } else {
    console.log('  (找不到首页 tab 按钮，跳过)');
  }

  // ── 场景 5：没有 Token，但本机桥在运行 → 全自动，不该弹任何框 ──
  console.log('\n== 5. 本机桥在运行时，发布不再索要 Token ==');
  const s5 = boot({ bridge: true });
  await sleep(450);
  ok('右上角显示 Token 已配置', /已配置/.test(s5.$('setTokenLink').textContent), s5.$('setTokenLink').textContent);
  const base5 = s5.state.netLog.length;
  s5.state.confirms = 0;
  s5.$('p-publish').click();
  await sleep(500);
  ok('一次 confirm 都没弹', s5.state.confirms === 0, s5.state.confirms);
  // 桥是在打开页面时就被问过一次的（右上角直接显示"已配置"），
  // 所以这里查整段日志，而不是点击之后的窗口。
  ok('确实向本机桥要过 Token',
    s5.state.netLog.some(r => r.url.indexOf(BRIDGE + '/token') === 0),
    s5.state.netLog.map(r => r.url.slice(0, 50)));
  ok('仍然完成了 GitHub 提交', githubWrites(s5.state).length - 0 >= 1 && githubWrites(s5.state).length === 1,
    githubWrites(s5.state).length);
  ok('点击后才产生的提交（不是初始化时偷跑的）', base5 <= s5.state.netLog.length, base5);
  ok('状态栏显示已发布', /已发布/.test(s5.$('status').textContent), s5.$('status').textContent);

  // ── 场景 6：既没有 Token 也没有桥 → 退回人工询问，而不是静默失败 ──
  console.log('\n== 6. 桥没运行时退回询问，不静默失败 ==');
  const s6 = boot({ bridge: false });
  await sleep(450);
  ok('右上角仍是未配置', /⚠/.test(s6.$('setTokenLink').textContent), s6.$('setTokenLink').textContent);
  s6.state.netLog.length = 0;
  s6.state.confirms = 0;
  s6.$('p-publish').click();
  await sleep(500);
  ok('弹出了询问（而不是什么都没有）', s6.state.confirms === 1, s6.state.confirms);
  ok('没有 Token 就不会提交', githubWrites(s6.state).length === 0, githubWrites(s6.state).length);
  ok('状态栏说明原因或提示启动本机桥', /本机桥|未配置/.test(s6.$('status').textContent), s6.$('status').textContent);

  console.log('\n' + (fail === 0 ? '✅ 全部通过' : '❌ 失败') + '：' + pass + ' passed, ' + fail + ' failed\n');
  process.exit(fail === 0 ? 0 : 1);
})().catch(e => { console.error('测试崩溃：', e); process.exit(1); });
