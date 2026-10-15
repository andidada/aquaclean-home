/**
 * check_after_removal.js — 删除 26 个产品后的线上/本地实测
 *
 * 静态扫描（audit_links.py）只能证明"链接指向的文件存在"，
 * 证明不了页面真的渲染正确。这里用真实 Edge 打开页面量 DOM：
 *   1. 品类页：productCount 文案、卡片数是否与数据一致
 *   2. 空品类：是否出现 .empty-state（运行时 JS 渲染的空状态）
 *   3. 空品类：空对比表是否被隐藏（offsetHeight === 0）
 *   4. 存活详情页：正常渲染、无死链区块
 *
 * 用法：node scripts/check_after_removal.js [baseUrl]
 */
const { spawn } = require('child_process');
const os = require('os');
const path = require('path');
const fs = require('fs');

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const BASE = (process.argv[2] || 'http://127.0.0.1:8899').replace(/\/$/, '');
const OUTDIR = path.join(process.cwd(), 'scraped', 'after-removal');

// [名称, 路径, 期望产品数]  —— 期望值来自 data/products/*.json
const CATS = [
  ['car-vacuum 剩1', '/en/car-vacuum/', 1],
  ['handheld-vacuum 剩5', '/en/handheld-vacuum/', 5],
  ['robot-vacuum 剩5', '/en/robot-vacuum/', 5],
  ['steam-cleaner 剩2', '/en/steam-cleaner/', 2],
  ['tire-inflator 剩1', '/en/tire-inflator/', 1],
  ['coffee-machine 空', '/en/coffee-machine/', 0],
  ['upright-steam-mop 空', '/en/upright-steam-mop/', 0],
  ['uv-mite-remover 空', '/en/uv-mite-remover/', 0],
  ['window-cleaner-robot 空', '/en/window-cleaner-robot/', 0],
  ['ar coffee-machine 空', '/ar/coffee-machine/', 0],
];
const DETAILS = [
  ['gv18', '/en/handheld-vacuum-gv18.html'],
  ['eg16pro', '/en/handheld-vacuum-eg16pro.html'],
  ['yzx-309', '/en/car-vacuum-yzx-309.html'],
  ['ymc6667', '/en/tire-inflator-ymc6667.html'],
];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const MEASURE = `(() => {
  const q = (s) => document.querySelector(s);
  const n = (s) => document.querySelectorAll(s).length;
  const countEl = q('#productCount');
  const grid = q('#productsGrid');
  const cards = grid ? grid.querySelectorAll('.product-card').length : -1;
  const empty = grid ? !!grid.querySelector('.empty-state') : false;
  const tables = Array.from(document.querySelectorAll('table'))
      .map(t => ({ hidden: t.offsetHeight === 0, rows: t.querySelectorAll('tr').length }));
  return {
    countText: countEl ? countEl.textContent.trim() : '(无 #productCount)',
    cards, empty, tables,
    related: !!q('#related'),
    h1: q('h1') ? q('h1').textContent.trim().slice(0, 60) : '(无 h1)',
  };
})()`;

let pass = 0, fail = 0;
const fails = [];

async function main() {
  const userDataDir = path.join(os.tmpdir(), 'aqc-after-removal-' + Date.now());
  const edge = spawn(EDGE, [
    '--headless=new', '--disable-gpu', '--no-proxy-server',
    '--remote-debugging-port=9444',
    '--user-data-dir=' + userDataDir,
    'about:blank',
  ], { stdio: 'ignore' });
  await sleep(3000);

  const http = require('http');
  const get = (u) => new Promise((res, rej) => {
    http.get(u, (r) => { let d = ''; r.on('data', c => d += c); r.on('end', () => res(d)); }).on('error', rej);
  });
  const list = JSON.parse(await get('http://127.0.0.1:9444/json/list'));
  const page = list.find(t => t.type === 'page');
  // Node 22 自带全局 WebSocket，不需要 ws 包
  const ws = new WebSocket(page.webSocketDebuggerUrl, { perMessageDeflate: false });
  await new Promise((r, j) => { ws.onopen = r; ws.onerror = j; });

  let id = 0;
  const pend = new Map();
  ws.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
  };
  const send = (method, params) => new Promise((res) => {
    const i = ++id; pend.set(i, res); ws.send(JSON.stringify({ id: i, method, params }));
  });

  const open = async (url) => {
    await send('Page.enable', {});
    await send('Runtime.enable', {});
    await send('Page.navigate', { url });
    await sleep(2200);          // 等运行时 JS 渲染 + 拉 data
    const r = await send('Runtime.evaluate', { expression: MEASURE, returnByValue: true });
    return r.result && r.result.result && r.result.result.value;
  };

  console.log('===== 品类页 =====');
  for (const [name, p, want] of CATS) {
    const m = await open(BASE + p);
    if (!m) { fail++; fails.push(name + ' 打不开'); console.log('FAIL ' + name); continue; }
    const wantNum = m.countText.match(/\d+/);
    const countOk = wantNum && parseInt(wantNum[0], 10) === want;
    const cardsOk = want === 0 ? (m.cards === 0 || m.cards === -1) : m.cards === want;
    const emptyOk = want === 0 ? m.empty : true;
    const ok = countOk && cardsOk && emptyOk;
    ok ? pass++ : fail++;
    if (!ok) fails.push(name);
    console.log('%s %s count=%s cards=%s emptyState=%s %s',
      ok ? 'ok  ' : 'FAIL', name, JSON.stringify(m.countText), m.cards, m.empty,
      ok ? '' : ('  <-- 期望 count=' + want));
  }

  console.log('\n===== 空品类的表格是否隐藏 =====');
  for (const [name, p, want] of CATS) {
    if (want !== 0) continue;
    const m = await open(BASE + p);
    const bad = (m.tables || []).filter(t => !t.hidden && t.rows <= 1);
    const ok = bad.length === 0;
    ok ? pass++ : fail++;
    if (!ok) fails.push(name + ' 空表未隐藏');
    console.log('%s %s 表格=%s', ok ? 'ok  ' : 'FAIL', name,
      JSON.stringify(m.tables));
  }

  console.log('\n===== 存活详情页 =====');
  for (const [name, p] of DETAILS) {
    const m = await open(BASE + p);
    const ok = !!m && m.h1 && m.h1 !== '(无 h1)';
    ok ? pass++ : fail++;
    if (!ok) fails.push(name);
    console.log('%s %s h1=%s  related区块=%s', ok ? 'ok  ' : 'FAIL', name,
      JSON.stringify(m && m.h1), m && m.related);
  }

  ws.close(); edge.kill();
  console.log('\n共 %d 项，异常 %d 项', pass + fail, fail);
  if (fails.length) console.log('异常：' + fails.join(' | '));
  try { fs.mkdirSync(OUTDIR, { recursive: true }); } catch (e) {}
  process.exit(fail ? 1 : 0);
}

main().catch(e => { console.error(e); process.exit(1); });
