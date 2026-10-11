/**
 * proxy_repro.js — 复现「浏览器打不开网站」
 *
 * 对比同一台机器上 Edge 的两种情况：
 *   A. 不带 --no-proxy-server（用系统/环境代理）→ 复现用户截图里的
 *      ERR_PROXY_CONNECTION_FAILED
 *   B. 带 --no-proxy-server（直连）
 *
 * 用法：node scripts/proxy_repro.js [url]
 */
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const URL = process.argv[2] || 'https://www.hkdmj.net/en/index.html';

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function attempt(label, extraArgs) {
  const port = 9800 + Math.floor(Math.random() * 300);
  const userDir = path.join(os.tmpdir(), 'aqc-px-' + Date.now());
  const proc = spawn(EDGE, [
    '--remote-debugging-port=' + port,
    '--user-data-dir=' + userDir,
    '--no-first-run', '--no-default-browser-check', '--disable-extensions',
    '--headless=new', '--window-size=1280,800',
    ...extraArgs,
    'about:blank',
  ], { stdio: 'ignore' });

  let ws = null;
  for (let i = 0; i < 50; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const p = list.find(t => t.type === 'page');
      if (p) { ws = p.webSocketDebuggerUrl; break; }
    } catch (e) { /* retry */ }
    await sleep(400);
  }
  if (!ws) { try { proc.kill(); } catch (e) {} ; return { label, err: '无法启动 Edge' }; }

  const sock = new WebSocket(ws);
  let id = 0;
  const pending = new Map();
  const failures = [];
  const urlById = new Map();
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
  sock.addEventListener('message', (ev) => {
    const m = JSON.parse(ev.data);
    const p = m.params || {};
    if (m.method === 'Network.requestWillBeSent' && p.request) urlById.set(p.requestId, p.request.url);
    if (m.method === 'Network.loadingFailed') {
      failures.push((urlById.get(p.requestId) || '?') + ' → ' + p.errorText);
    }
  });

  await send('Page.enable');
  await send('Network.enable');
  await send('Runtime.enable');
  await send('Page.navigate', { url: URL });
  await sleep(12000);

  const r = await send('Runtime.evaluate', {
    returnByValue: true,
    expression: `(function(){
      return {
        title: document.title,
        h1: (document.querySelector('h1') || {}).textContent || '',
        len: (document.body && document.body.innerText || '').length,
        text: (document.body && document.body.innerText || '').slice(0,120).replace(/\\s+/g,' ')
      };
    })()`,
  });
  const v = (r.result && r.result.result) ? r.result.result.value : {};

  sock.close();
  try { proc.kill(); } catch (e) {}
  try { fs.rmSync(userDir, { recursive: true, force: true }); } catch (e) {}

  return { label, failed: failures.length, failures: failures.slice(0, 4), title: v.title, len: v.len, text: v.text };
}

async function main() {
  console.log('目标: ' + URL + '\n');
  for (const [label, args] of [
    ['A. 用系统代理（复现用户所见）', []],
    ['B. --no-proxy-server（直连）', ['--no-proxy-server']],
  ]) {
    const r = await attempt(label, args);
    console.log('--- ' + r.label + ' ---');
    if (r.err) { console.log('  ' + r.err); continue; }
    console.log('  失败请求数: ' + r.failed);
    r.failures.forEach(f => console.log('    ❌ ' + f));
    console.log('  标题: ' + JSON.stringify((r.title || '').slice(0, 60)));
    console.log('  正文长度: ' + r.len);
    console.log('  正文片段: ' + JSON.stringify((r.text || '').slice(0, 100)));
    console.log('');
  }
}

main().catch(e => { console.error(e); process.exit(1); });
