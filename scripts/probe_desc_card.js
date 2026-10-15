const { spawn } = require('child_process');
const os = require('os');
const path = require('path');

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const URL = process.argv[2] || 'http://127.0.0.1:8899/en/handheld-vacuum-v18.html';
const W = parseInt(process.argv[3] || '390', 10);

(async () => {
  const port = 9780 + Math.floor(Math.random() * 15);
  const ud = path.join(os.tmpdir(), 'aqc-probe-' + Date.now());
  const p = spawn(EDGE, [
    '--remote-debugging-port=' + port, '--user-data-dir=' + ud, '--no-proxy-server',
    '--headless=new', '--window-size=' + W + ',900', 'about:blank',
  ], { stdio: 'ignore' });
  let ws = null;
  for (let i = 0; i < 40; i++) {
    try {
      const l = await (await fetch('http://127.0.0.1:' + port + '/json/list')).json();
      const t = l.find((x) => x.type === 'page');
      if (t) { ws = t.webSocketDebuggerUrl; break; }
    } catch (e) {}
    await new Promise((r) => setTimeout(r, 400));
  }
  const s = new WebSocket(ws);
  let id = 0; const pend = new Map();
  s.onmessage = (e) => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } };
  const send = (me, pa) => new Promise((r) => { const i = ++id; pend.set(i, r); s.send(JSON.stringify({ id: i, method: me, params: pa || {} })); });
  await new Promise((r) => (s.onopen = r));
  await send('Runtime.enable');
  await send('Emulation.setDeviceMetricsOverride', { width: W, height: 900, deviceScaleFactor: 1, mobile: W <= 768 });
  await send('Page.navigate', { url: URL });
  await new Promise((r) => setTimeout(r, 1500));
  const expr = `(() => {
    const out = [];
    const walk = (el, depth) => {
      if (out.length > 14 || depth > 5) return;
      for (const c of el.children) {
        const b = c.getBoundingClientRect();
        if (b.height < 30) continue;
        const cs = getComputedStyle(c);
        out.push({
          sel: c.tagName.toLowerCase() + (c.className ? '.' + String(c.className).split(' ')[0] : ''),
          top: Math.round(b.top + scrollY), h: Math.round(b.height), w: Math.round(b.width),
          border: cs.borderWidth + ' ' + cs.borderColor,
          bg: cs.backgroundColor, shadow: cs.boxShadow.slice(0, 48),
        });
        walk(c, depth + 1);
      }
    };
    walk(document.querySelector('.d-layout'), 0);
    return out;
  })()`;
  const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
  for (const row of (r.result.result.value || [])) {
    console.log(String(row.top).padStart(5), String(row.h).padStart(5), String(row.w).padStart(5),
      row.sel.padEnd(24), row.border.padEnd(16), row.bg.padEnd(12), row.shadow);
  }
  p.kill();
  process.exit(0);
})().catch((e) => { console.error(e); process.exit(1); });
