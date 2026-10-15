#!/usr/bin/env node
/* verify_review_form.js — 首页留评表单回归测试（真实 Edge 窗口，非 jsdom）
 *
 * 覆盖三件事：
 *   1. 表单在 9 语种子集(en/zh/ar)正确渲染、默认 5 星
 *   2. 星级交互：hover 点亮到第 N 颗、真实鼠标点击写入正确 rating、
 *      移开鼠标后保持（曾经只有被点的那颗亮，且 radio 恒为 1）
 *   3. 弹窗不挡路：客户正在填留评表单时，60% 滚动触发的获客弹窗不能盖住表单
 *      （这个冲突真实存在过：弹窗把点击整个吞掉，星级根本点不动）
 *
 * 用法：node scripts/verify_review_form.js
 * 退出码 0 = 全部通过。
 */
'use strict';
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const http = require('http');
const path = require('path');

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const ROOT = path.resolve(__dirname, '..');
const PORT = 8898;
const MIME = {
  '.html': 'text/html', '.css': 'text/css', '.js': 'text/javascript',
  '.webp': 'image/webp', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.json': 'application/json'
};
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const ACCENT = 'rgb(245, 158, 11)';
const GREY = 'rgb(203, 213, 225)';

let pass = 0, fail = 0;
function ok(name, cond, extra) {
  if (cond) { pass++; console.log('ok   ' + name + (extra ? '  ' + extra : '')); }
  else { fail++; console.log('FAIL ' + name + (extra ? '  ' + extra : '')); }
}

(async () => {
  // ── 静态服务（和被测页同源）──
  const server = http.createServer((req, res) => {
    const p = path.join(ROOT, decodeURIComponent(req.url.split('?')[0]));
    fs.readFile(p, (e, d) => {
      if (e) { res.statusCode = 404; res.end('nf'); return; }
      res.setHeader('Content-Type', MIME[path.extname(p).toLowerCase()] || 'application/octet-stream');
      res.end(d);
    });
  });
  await new Promise((r) => server.listen(PORT, '127.0.0.1', r));

  // ── 真实 Edge 窗口：无头模式下 CDP 鼠标事件不投递，指针交互必须用真窗口 ──
  const prof = fs.mkdtempSync(path.join(os.tmpdir(), 'aqc-rvform-'));
  const edge = spawn(EDGE, ['--disable-gpu', '--no-proxy-server', '--no-first-run',
    '--window-size=1280,1000', '--remote-debugging-port=9444', '--user-data-dir=' + prof,
    'about:blank'], { stdio: 'ignore' });
  const cleanup = () => { try { edge.kill(); } catch (e) {} try { server.close(); } catch (e) {} };
  process.on('exit', cleanup);

  let ws = null;
  for (let i = 0; i < 20 && !ws; i++) {
    await sleep(500);
    try {
      const list = await (await fetch('http://127.0.0.1:9444/json/list')).json();
      const page = list.find((t) => t.type === 'page');
      if (page) {
        ws = new global.WebSocket(page.webSocketDebuggerUrl);
        await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
      }
    } catch (e) { /* 还没起来 */ }
  }
  if (!ws) { console.error('无法连接 Edge'); process.exit(2); }

  let id = 0; const pending = {};
  ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pending[m.id]) pending[m.id](m); };
  const send = (method, params) => new Promise((res) => {
    const i = ++id; pending[i] = res; ws.send(JSON.stringify({ id: i, method, params }));
  });
  const evalJs = async (expr) => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.result && r.result.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails));
    return r.result.result.value;
  };
  await send('Page.enable');

  const colors = () => evalJs(`JSON.stringify([].map.call(
    document.querySelectorAll('.rc-star span'), s => getComputedStyle(s).color))`).then(JSON.parse);
  const litIdx = (arr) => arr.map((c, i) => (c === ACCENT ? i : -1)).filter((i) => i >= 0);

  // 把第 i 颗星滚到视口内 200px 处（页面 scroll-behavior:smooth，
  // 必须用 instant，否则 1 万像素的平滑滚动还没到位点击就落空了）
  const starPoint = async (i) => {
    await evalJs(`(() => {
      const el = document.querySelectorAll('.rc-star')[${i}];
      const doc = el.getBoundingClientRect().top + window.scrollY;
      const max = Math.max(0, document.documentElement.scrollHeight - window.innerHeight);
      window.scrollTo({ top: Math.max(0, Math.min(doc - 200, max)), behavior: 'instant' });
      return 1; })()`);
    await sleep(400);
    return evalJs(`(() => { const r = document.querySelectorAll('.rc-star')[${i}].getBoundingClientRect();
      return JSON.stringify({ x: r.x + r.width/2, y: r.y + r.height/2 }); })()`).then(JSON.parse);
  };
  const clickAt = async (p) => {
    await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: p.x, y: p.y });
    await sleep(200);
    await send('Input.dispatchMouseEvent', { type: 'mousePressed', x: p.x, y: p.y, button: 'left', clickCount: 1 });
    await send('Input.dispatchMouseEvent', { type: 'mouseReleased', x: p.x, y: p.y, button: 'left', clickCount: 1 });
    await sleep(300);
  };

  // ═══════════ 语种渲染 + 校验 + 星级 ═══════════
  for (const lang of ['en', 'zh', 'ar']) {
    await send('Page.navigate', { url: `http://127.0.0.1:${PORT}/${lang}/index.html` });
    await sleep(4000);

    ok(`${lang} 表单已渲染`, (await evalJs(`!!document.querySelector('.rc-form')`)) === true);

    const def = await colors();
    ok(`${lang} 默认 5 星全亮`, litIdx(def).join(',') === '0,1,2,3,4', 'lit=' + litIdx(def).join(','));

    // hover 第 2 颗 → 只亮 1、2
    await clickAt(await starPoint(1));
    let c = await colors();
    ok(`${lang} hover 第2颗只亮 1、2`, litIdx(c).join(',') === '0,1', 'lit=' + litIdx(c).join(','));

    // 真实点击第 3 颗 → 亮 1、2、3 且 radio=3
    await clickAt(await starPoint(2));
    c = await colors();
    ok(`${lang} 点击第3颗亮 1、2、3`, litIdx(c).join(',') === '0,1,2', 'lit=' + litIdx(c).join(','));
    const rv = await evalJs(`(document.querySelector('[name="rating"]:checked')||{}).value`);
    ok(`${lang} 点击第3颗 rating=3`, String(rv) === '3', 'value=' + rv);

    // 鼠标移开后保持 3 颗
    await send('Input.dispatchMouseEvent', { type: 'mouseMoved', x: 5, y: 5 });
    await sleep(300);
    c = await colors();
    ok(`${lang} 移开鼠标仍亮 3 颗`, litIdx(c).join(',') === '0,1,2', 'lit=' + litIdx(c).join(','));

    // 校验：空提交被拦（不发起请求）
    await evalJs(`document.querySelector('.rc-submit').click(); 1`);
    await sleep(500);
    const m1 = await evalJs(`(document.querySelector('[data-review-msg]')||{}).textContent||''`);
    ok(`${lang} 未选星级被拦截提示`, !!m1, JSON.stringify(m1));

    // 校验：内容过短被拦
    await evalJs(`(() => { const f = document.querySelector('.rc-form');
      f.querySelector('[name="author"]').value = 'Test Buyer';
      f.querySelector('[name="content"]').value = 'short';
      f.querySelector('.rc-submit').click(); return 1; })()`);
    await sleep(500);
    const m2 = await evalJs(`(document.querySelector('[data-review-msg]')||{}).textContent||''`);
    ok(`${lang} 过短内容被拦截提示`, !!m2 && m2 !== m1, JSON.stringify(m2));

    // ═══ 弹窗不挡路 ═══
    // 场景 A：已在表单里填了内容 → 滚到 100% 也不弹
    await evalJs(`(() => { const f = document.querySelector('.rc-form');
      f.querySelector('[name="author"]').value = 'Popup Guard Test';
      window.scrollTo({ top: document.documentElement.scrollHeight, behavior: 'instant' });
      return 1; })()`);
    await sleep(1200);
    const popA = await evalJs(`document.getElementById('popupOverlay').classList.contains('show')`);
    ok(`${lang} 填表中滚动不弹获客弹窗`, popA === false, 'show=' + popA);

    // 场景 B：弹窗已弹出 → 焦点进入留评表单即收起
    await evalJs(`(() => { sessionStorage.removeItem('popupShown');
      const o = document.getElementById('popupOverlay');
      o.classList.add('show');
      document.querySelector('.rc-form [name="company"]').focus();
      return 1; })()`);
    await sleep(400);
    const popB = await evalJs(`document.getElementById('popupOverlay').classList.contains('show')`);
    ok(`${lang} 弹窗已开时聚焦表单会收起`, popB === false, 'show=' + popB);
  }

  console.log(`\n${pass} passed, ${fail} failed`);
  cleanup();
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error('ERR', e); process.exit(2); });
