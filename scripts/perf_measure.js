/**
 * perf_measure.js — 用真实 Edge（CDP）测量页面加载性能
 *
 * 用法：
 *   node scripts/perf_measure.js <url> [runs]
 *
 * 输出：导航时间线（TTFB / FCP / LCP / DCL / Load）+ 每个资源的耗时，
 *       用于优化前后对比。
 *
 * 注意：必须开真实浏览器（不加 --headless 的旧模式会掐断未完成请求）。
 * 这里用 --headless=new，并用 CDP 等 Page.loadEventFired，不做虚拟时间加速。
 */
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const URL = process.argv[2] || 'https://www.hkdmj.net/en/index.html';
const RUNS = parseInt(process.argv[3] || '3', 10);
// 限速档位：模拟用户真实网络。默认 4g（150ms RTT）贴近移动端/跨境访问。
const THROTTLE = {
  none: null,
  // 每条链路固定加 latency ms 的往返延迟 —— 决定"请求串行"有多痛
  '4g': { offline: false, latency: 150, downloadThroughput: 9 * 1024 * 1024 / 8, uploadThroughput: 3 * 1024 * 1024 / 8 },
  '3g': { offline: false, latency: 300, downloadThroughput: 1.6 * 1024 * 1024 / 8, uploadThroughput: 750 * 1024 / 8 },
  'slow': { offline: false, latency: 400, downloadThroughput: 600 * 1024 / 8, uploadThroughput: 300 * 1024 / 8 },
  // 模拟 Google Fonts 不可达（超时/重置）—— 检验第三方依赖会不会拖垮首屏
  'blocked-fonts': { offline: false, latency: 150, downloadThroughput: 9 * 1024 * 1024 / 8, uploadThroughput: 3 * 1024 * 1024 / 8 },
};
const PROFILE = process.argv[4] || '4g';

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function fetchJson(url) {
  const res = await fetch(url);
  return res.json();
}

async function main() {
  const port = 9333 + Math.floor(Math.random() * 300);
  const userDir = path.join(os.tmpdir(), 'aqc-perf-' + Date.now());
  const args = [
    '--remote-debugging-port=' + port,
    '--user-data-dir=' + userDir,
    '--no-proxy-server',
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-extensions',
    '--headless=new',
    '--window-size=1440,900',
    'about:blank',
  ];
  const proc = spawn(EDGE, args, { stdio: 'ignore' });

  let ws = null;
  for (let i = 0; i < 60; i++) {
    try {
      const list = await fetchJson(`http://127.0.0.1:${port}/json/list`);
      const page = list.find(t => t.type === 'page');
      if (page) { ws = page.webSocketDebuggerUrl; break; }
    } catch (e) { /* not up yet */ }
    await sleep(500);
  }
  if (!ws) { console.error('无法连接 Edge CDP'); proc.kill(); process.exit(1); }

  const sock = new WebSocket(ws);
  let id = 0;
  const pending = new Map();
  const events = [];

  sock.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      pending.get(msg.id)(msg);
      pending.delete(msg.id);
    } else if (msg.method) {
      events.push(msg);
    }
  };
  await new Promise(r => { sock.onopen = r; sock.onerror = r; });

  function send(method, params) {
    const mid = ++id;
    sock.send(JSON.stringify({ id: mid, method, params: params || {} }));
    return new Promise(resolve => pending.set(mid, resolve));
  }

  await send('Page.enable');
  await send('Network.enable');
  await send('Runtime.enable');

  const prof = THROTTLE[PROFILE] || THROTTLE['4g'];
  if (prof) {
    await send('Network.emulateNetworkConditions', prof);
    console.log('网络限速档位: ' + PROFILE + ' (RTT +' + prof.latency + 'ms)');
  }
  // 模拟 Google Fonts 不可达：直接把该域名请求掐掉，观察是否阻塞首屏
  if (PROFILE === 'blocked-fonts') {
    await send('Network.setBlockedURLs', { urls: ['*fonts.googleapis.com*', '*fonts.gstatic.com*'] });
    console.log('已阻断 fonts.googleapis.com / fonts.gstatic.com');
  }

  // LCP 必须在导航前埋点，否则 buffered 拿不到
  await send('Page.addScriptToEvaluateOnNewDocument', {
    source: `
      window.__lcp = 0; window.__lcpEl = '';
      try {
        new PerformanceObserver(function (list) {
          var es = list.getEntries();
          var last = es[es.length - 1];
          if (last) { window.__lcp = last.startTime; window.__lcpEl = (last.element && last.element.tagName) || ''; }
        }).observe({ type: 'largest-contentful-paint', buffered: true });
      } catch (e) {}
      try {
        new PerformanceObserver(function (list) {
          list.getEntries().forEach(function (e) {
            if (!e.hadRecentInput) { (window.__cls = (window.__cls || 0) + e.value); }
          });
        }).observe({ type: 'layout-shift', buffered: true });
      } catch (e) {}
    `,
  });

  const runs = [];
  for (let r = 0; r < RUNS; r++) {
    events.length = 0;
    const reqs = new Map();
    const onReq = (ev) => {
      const p = ev.params;
      if (p.request && p.requestId) {
        reqs.set(p.requestId, { url: p.request.url, start: p.timestamp, type: p.type });
      }
    };
    sock.addEventListener('message', (ev) => {
      const m = JSON.parse(ev.data);
      if (m.method === 'Network.requestWillBeSent') onReq(m);
      if (m.method === 'Network.responseReceived') {
        const e = reqs.get(m.params.requestId);
        if (e) { e.ttfb = m.params.timestamp - e.start; e.status = m.params.response.status; e.mime = m.params.response.mimeType; }
      }
      if (m.method === 'Network.loadingFinished') {
        const e = reqs.get(m.params.requestId);
        if (e) { e.total = m.params.timestamp - e.start; e.bytes = m.params.encodedDataLength; }
      }
      if (m.method === 'Network.loadingFailed') {
        const e = reqs.get(m.params.requestId);
        if (e) { e.failed = true; e.total = m.params.timestamp - e.start; e.err = m.params.errorText; }
      }
    });

    await send('Network.clearBrowserCache');
    await send('Page.navigate', { url: URL + (URL.includes('?') ? '&' : '?') + '_perf=' + Date.now() });

    // 等 load 事件，最多 45s
    const t0 = Date.now();
    let loaded = false;
    while (Date.now() - t0 < 45000) {
      if (events.some(e => e.method === 'Page.loadEventFired')) { loaded = true; break; }
      await sleep(200);
    }
    await sleep(1500); // 让 LCP 稳定

    const metrics = await send('Runtime.evaluate', {
      returnByValue: true,
      expression: `(function(){
        var nav = performance.getEntriesByType('navigation')[0] || {};
        var paints = {};
        performance.getEntriesByType('paint').forEach(function(p){ paints[p.name] = p.startTime; });
        return {
          ttfb: nav.responseStart || 0,
          dcl: nav.domContentLoadedEventEnd || 0,
          load: nav.loadEventEnd || 0,
          domInteractive: nav.domInteractive || 0,
          fcp: paints['first-contentful-paint'] || 0,
          lcp: window.__lcp || 0,
          lcpEl: window.__lcpEl || '',
          cls: window.__cls || 0,
          transfer: nav.transferSize || 0
        };
      })()`,
    });

    const m = metrics.result && metrics.result.result ? metrics.result.result.value : {};
    m.loaded = loaded;
    m.resources = Array.from(reqs.values()).map(x => ({
      url: x.url.replace(/^https?:\/\//, '').split('?')[0],
      ms: Math.round((x.total || 0) * 1000),
      ttfb: Math.round((x.ttfb || 0) * 1000),
      kb: Math.round((x.bytes || 0) / 1024),
      failed: !!x.failed,
      err: x.err,
    })).sort((a, b) => b.ms - a.ms);
    runs.push(m);
  }

  sock.close();
  try { proc.kill(); } catch (e) {}
  try { fs.rmSync(userDir, { recursive: true, force: true }); } catch (e) {}

  // 汇总：取中位数
  function med(arr) { const s = arr.slice().sort((a, b) => a - b); return s[Math.floor(s.length / 2)] || 0; }
  const agg = {
    ttfb: med(runs.map(r => Math.round(r.ttfb))),
    fcp: med(runs.map(r => Math.round(r.fcp))),
    lcp: med(runs.map(r => Math.round(r.lcp))),
    dcl: med(runs.map(r => Math.round(r.dcl))),
    load: med(runs.map(r => Math.round(r.load))),
    kb: med(runs.map(r => Math.round(r.transfer / 1024))),
  };
  console.log('=== ' + URL + ' ===');
  console.log('中位数（' + RUNS + ' 次）: TTFB ' + agg.ttfb + 'ms | FCP ' + agg.fcp +
    'ms | LCP ' + agg.lcp + 'ms | DCL ' + agg.dcl + 'ms | Load ' + agg.load +
    'ms | 传输 ' + agg.kb + 'KB');
  console.log('LCP 元素: ' + (runs[runs.length - 1].lcpEl || '(未捕获)') +
    ' | CLS: ' + (runs[runs.length - 1].cls || 0).toFixed(4));
  console.log('');
  const last = runs[runs.length - 1];
  console.log('--- 资源耗时（最后一次，降序）---');
  last.resources.slice(0, 20).forEach(r => {
    console.log(
      String(r.ms).padStart(6) + 'ms  ttfb=' + String(r.ttfb).padStart(5) +
      'ms  ' + String(r.kb).padStart(5) + 'KB  ' + (r.failed ? '❌ ' + (r.err || 'failed') + '  ' : '') + r.url
    );
  });
}

main().catch(e => { console.error(e); process.exit(1); });
