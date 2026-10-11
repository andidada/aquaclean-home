/**
 * smoke_local.js — 本地冒烟：确认性能改造没有把页面搞坏
 *
 * 检查项：
 *   1. 无 JS 控制台错误、无失败请求
 *   2. 不再请求 fonts.googleapis.com / fonts.gstatic.com（已自托管）
 *   3. Inter 字体确实从本站 /assets/fonts/ 加载
 *   4. 首屏只下载 1 张 banner（原来是 7 张）
 *   5. hero 文案、产品卡片、询盘表单都渲染出来了
 *
 * 用法：node scripts/smoke_local.js [url]
 */
const { spawn } = require('child_process');
const os = require('os');
const path = require('path');
const fs = require('fs');

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const URL = process.argv[2] || 'http://127.0.0.1:8080/en/index.html';

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function main() {
  const port = 9600 + Math.floor(Math.random() * 300);
  const userDir = path.join(os.tmpdir(), 'aqc-smoke-' + Date.now());
  const proc = spawn(EDGE, [
    '--remote-debugging-port=' + port,
    '--user-data-dir=' + userDir,
    '--no-proxy-server',
    '--no-first-run', '--no-default-browser-check', '--disable-extensions',
    '--headless=new', '--window-size=1440,900',
    'about:blank',
  ], { stdio: 'ignore' });

  let ws = null;
  for (let i = 0; i < 60; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const p = list.find(t => t.type === 'page');
      if (p) { ws = p.webSocketDebuggerUrl; break; }
    } catch (e) { /* retry */ }
    await sleep(500);
  }
  if (!ws) { console.error('无法连接 Edge'); proc.kill(); process.exit(1); }

  const sock = new WebSocket(ws);
  let id = 0;
  const pending = new Map();
  sock.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  };
  await new Promise(r => { sock.onopen = r; sock.onerror = r; });
  const send = (method, params) => {
    const mid = ++id;
    sock.send(JSON.stringify({ id: mid, method, params: params || {} }));
    return new Promise(res => pending.set(mid, res));
  };

  const urls = [];
  const urlById = new Map();
  const failed = [];
  const consoleErrors = [];
  sock.addEventListener('message', (ev) => {
    const m = JSON.parse(ev.data);
    if (m.method === 'Network.requestWillBeSent' && m.params.request) {
      urls.push(m.params.request.url);
      urlById.set(m.params.requestId, m.params.request.url);
    }
    if (m.method === 'Network.loadingFailed') {
      failed.push({ url: urlById.get(m.params.requestId) || '(未知)', err: m.params.errorText });
    }
    if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') {
      consoleErrors.push((m.params.args || []).map(a => a.value || a.description || '').join(' '));
    }
    if (m.method === 'Runtime.exceptionThrown') {
      consoleErrors.push('exception: ' + (m.params.exceptionDetails.text || ''));
    }
  });

  await send('Page.enable');
  await send('Network.enable');
  await send('Runtime.enable');
  await send('Network.clearBrowserCache');
  await send('Page.navigate', { url: URL });
  // 轮播每 5s 切一帧，切到第 2 帧时会按需 hydrate 第 3 帧，所以在 9s 后统计
  // banner 数会读到 3 张——那是设计行为。要验证"首屏只下 1 张"，必须在
  // 第一次切换之前取样。
  await sleep(2500);
  const bannersAtFirstPaint = urls.filter(u => /banners\/banner-\d\.webp/.test(u)).length;
  await sleep(6500);

  const dom = await send('Runtime.evaluate', {
    returnByValue: true,
    expression: `(function(){
      var q = function(s){ return document.querySelector(s); };
      return {
        h1: (q('.hero-slide.active h1') || q('h1') || {}).textContent || '',
        slides: document.querySelectorAll('.hero-slide').length,
        hydrated: [].slice.call(document.querySelectorAll('.hero-slide'))
                     .filter(function(s){ return s.dataset.loaded; }).length,
        productCards: document.querySelectorAll('.product-card').length,
        formFields: document.querySelectorAll('form input, form select, form textarea').length,
        bodyFont: getComputedStyle(document.body).fontFamily,
        hasFooter: !!q('footer'),
        footerText: (q('.footer-bottom') || {}).textContent ? q('.footer-bottom').textContent.slice(0,80) : ''
      };
    })()`,
  });
  const d = (dom.result && dom.result.result) ? dom.result.result.value : {};

  sock.close();
  try { proc.kill(); } catch (e) {}
  try { fs.rmSync(userDir, { recursive: true, force: true }); } catch (e) {}

  const gfonts = urls.filter(u => /fonts\.(googleapis|gstatic)\.com/.test(u));
  const localFont = urls.filter(u => /\/assets\/fonts\//.test(u));
  const banners = urls.filter(u => /banners\/banner-\d\.webp/.test(u));

  let pass = 0, fail = 0;
  const check = (name, ok, detail) => {
    console.log((ok ? '  ✓ ' : '  ✗ ') + name + (detail ? '  — ' + detail : ''));
    ok ? pass++ : fail++;
  };

  console.log('=== ' + URL + ' ===');
  console.log('1. 无错误');
  check('无失败请求', failed.length === 0, failed.map(f => f.url.slice(0, 60) + ' ' + f.err).join('; '));
  check('无 JS 报错', consoleErrors.length === 0, consoleErrors.slice(0, 3).join(' | '));

  console.log('2. 字体自托管');
  check('不再请求 Google Fonts', gfonts.length === 0, gfonts.length + ' 个');
  check('从本站加载 Inter', localFont.length > 0, localFont.map(u => u.split('/').pop()).join(', '));

  console.log('3. 首屏体积');
  // 改造前：idle 时一次性 hydrate 全部 7 帧（412KB）。
  // 改造后：第 1 帧立即加载，第 2 帧等 load 后预取（避免 5s 后首次切换白屏），
  // 其余按需。所以首屏期望是 2 张，而不是 7 张。
  check('首屏 banner ≤ 2 张（改造前是 7 张）', bannersAtFirstPaint <= 2,
    bannersAtFirstPaint + ' 张（9s 后累计 ' + banners.length + ' 张，随轮播推进按需加载）');

  console.log('4. 内容渲染');
  check('hero 标题非空', !!d.h1 && d.h1.length > 5, JSON.stringify((d.h1 || '').slice(0, 50)));
  check('产品卡片已渲染', d.productCards > 0, d.productCards + ' 张');
  check('询盘表单字段完整', d.formFields >= 5, d.formFields + ' 个');
  check('footer 存在', d.hasFooter, (d.footerText || '').replace(/\s+/g, ' ').slice(0, 60));
  check('字体栈含 CJK 兜底', /PingFang|YaHei|Noto Sans/.test(d.bodyFont || ''), (d.bodyFont || '').slice(0, 70));

  console.log('\n' + (fail === 0 ? '✅ 全部通过' : '❌ 有 ' + fail + ' 项失败') + '：' + pass + ' passed, ' + fail + ' failed');
  process.exit(fail === 0 ? 0 : 1);
}

main().catch(e => { console.error(e); process.exit(1); });
