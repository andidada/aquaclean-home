#!/usr/bin/env node
/**
 * 类目页（category page）回归测试。
 *
 * 背景：类目页的产品卡片既有静态输出（爬虫 / 禁用 JS 用），又有一段页内脚本
 * 会在运行时读 /data/products/{cat}.json 重新渲染。2026-10-06 修掉的问题：
 * 拉不到数据时那段脚本会把静态卡片整个换成错误占位，一次网络抖动就让整页
 * 产品信息变空白。
 *
 * 断言：
 *   1. 数据可用 → 卡片被 JSON 重新渲染（标题 / 价格 / 链接都来自 JSON）
 *   2. 数据 404 → 静态卡片必须原样保留，不能出现错误占位
 *   3. 静态卡片在 JS 完全不执行时也在（SEO 兜底）
 *
 * Run:  node scripts/verify_category_pages.js
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH ||
  'C:/Users/Administrator/.workbuddy/binaries/node/workspace/node_modules/jsdom');

const ROOT = path.dirname(__dirname);
const PUB = 'https://www.hkdmj.net';
const PAGE = path.join(ROOT, 'en', 'handheld-vacuum', 'index.html');
const DATA = path.join(ROOT, 'data', 'products', 'handheld-vacuum.json');

let pass = 0, fail = 0;
function ok(name, cond, extra) {
  if (cond) { pass++; console.log('  ✓ ' + name); }
  else { fail++; console.log('  ✗ ' + name + (extra !== undefined ? '  → ' + JSON.stringify(extra) : '')); }
}
const sleep = ms => new Promise(r => setTimeout(r, ms));

function boot(mode) {
  const html = fs.readFileSync(PAGE, 'utf8');
  const json = JSON.parse(fs.readFileSync(DATA, 'utf8'));
  // beforeParse 很重要：类目页的渲染脚本是内联的，parse 时就会执行，
  // 之后再挂 window.fetch 就晚了（jsdom 自带 fetch 为 undefined）。
  const dom = new JSDOM(html, {
    url: PUB + '/en/handheld-vacuum/',
    runScripts: 'dangerously',
    beforeParse(win) {
      win.fetch = function (u) {
        const hit = String(u).indexOf('/data/products/handheld-vacuum.json') !== -1;
        if (mode === 'ok' && hit) {
          return Promise.resolve({ ok: true, json: () => Promise.resolve(json) });
        }
        if (mode === 'netfail' && hit) {
          // 真实网络失败：fetch 本身 resolve，但 res.json() 抛
          return Promise.resolve({ ok: false, status: 404, json: () => Promise.reject(new Error('404')) });
        }
        if (mode === 'garbage' && hit) {
          // 更阴的一种：200 但返回的不是产品数据（网关错误页 / 空对象）
          return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) });
        }
        return Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve({}) });
      };
    }
  });
  return dom.window;
}
const cards = w => [...w.document.querySelectorAll('#productsGrid .product-card')];

(async function run() {
  console.log('\n== 1. 数据可用：卡片由 JSON 重新渲染 ==');
  let w = boot('ok');
  await sleep(300);
  let c = cards(w);
  ok('渲染出了卡片', c.length > 0, c.length);
  const first = c[0];
  const j = JSON.parse(fs.readFileSync(DATA, 'utf8')).products[0];
  ok('标题来自 JSON', first.querySelector('h3').textContent === j.name.en,
    { dom: first.querySelector('h3').textContent, json: j.name.en });
  ok('价格来自 price_indicator',
    /\$/.test(first.querySelector('.price-indicator').textContent),
    first.querySelector('.price-indicator').textContent.trim());
  ok('详情链接由 slug + id 拼出', /\/en\/handheld-vacuum-gv18\.html$/.test(first.querySelector('a.btn').getAttribute('href')),
    first.querySelector('a.btn').getAttribute('href'));
  ok('图片指向产品自己的图',
    first.querySelector('.product-img-wrap img').getAttribute('src').indexOf('handheld-vacuum') !== -1,
    first.querySelector('.product-img-wrap img').getAttribute('src'));

  console.log('\n== 2. 数据拉不到：静态卡片必须保留 ==');
  const before = cards(boot('nojs')).length;   // 完全不跑 JS 时的静态卡片数
  ok('静态 HTML 里本来就有卡片（SEO 兜底）', before > 0, before);
  for (const mode of ['netfail', 'garbage']) {
    w = boot(mode);
    await sleep(300);
    c = cards(w);
    ok(mode + '：卡片一张都没少', c.length === before, { before, after: c.length });
    ok(mode + '：没有出现错误/空占位', !w.document.querySelector('#productsGrid .empty-state'),
      w.document.querySelector('#productsGrid').innerHTML.slice(0, 90));
    ok(mode + '：卡片里仍带价格文案', /\$/.test(w.document.querySelector('#productsGrid').textContent));
  }

  console.log('\n== 3. 全站类目页都改到了 ==');
  const files = fs.readdirSync(ROOT, { recursive: true, encoding: 'utf8' })
    .filter(f => f.endsWith('.html'));
  let withCatch = 0; const stillWiping = [];
  for (const f of files) {
    const s2 = fs.readFileSync(path.join(ROOT, f), 'utf8');
    const i2 = s2.indexOf('Failed to load products');
    if (i2 === -1) continue;
    withCatch++;
    const tail = s2.slice(i2, i2 + 700);
    if (tail.indexOf('empty-state-icon') !== -1 || tail.indexOf("productsGrid').innerHTML") !== -1) {
      stillWiping.push(f);
    }
  }
  ok('所有带该 catch 的页面都不会再抹掉卡片（' + withCatch + ' 个）', stillWiping.length === 0, stillWiping.slice(0, 5));

  console.log('\n' + (fail === 0 ? '✅ 全部通过' : '❌ 失败') + '：' + pass + ' passed, ' + fail + ' failed\n');
  process.exit(fail === 0 ? 0 : 1);
})().catch(e => { console.error('测试崩溃：', e); process.exit(1); });
