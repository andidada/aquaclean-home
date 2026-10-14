#!/usr/bin/env node
/**
 * probe_login.js — 探测 CDP 浏览器里阿里登录态是否还在
 *
 * ⚠️ 关键：探测在**独立的新标签**里做，绝不动用户正在登录的那个标签页，
 *    否则每次轮询都会把登录页导航走，用户永远登不上。
 *
 * 用法：node scripts/probe_login.js <url> [url...]
 * 输出：[OK] 能拿到完整详情页 / [WALL] 还是登录墙
 */
const PORT = 9333;
const sleep = ms => new Promise(r => setTimeout(r, ms));
const URLS = process.argv.slice(2);

async function http(path) {
  const r = await fetch(`http://127.0.0.1:${PORT}${path}`);
  return r.json();
}
async function connect(wsUrl) {
  const sock = new WebSocket(wsUrl);
  let id = 0; const pending = new Map();
  sock.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  };
  await new Promise((res, rej) => { sock.onopen = res; sock.onerror = rej; });
  const send = (method, params, sessionId) => {
    const mid = ++id;
    const msg = { id: mid, method, params: params || {} };
    if (sessionId) msg.sessionId = sessionId;
    sock.send(JSON.stringify(msg));
    return new Promise(res => pending.set(mid, res));
  };
  return { sock, send };
}

(async () => {
  const ver = await http('/json/version').catch(() => null);
  if (!ver) { console.log('NOPORT'); process.exit(2); }

  const { sock, send } = await connect(ver.webSocketDebuggerUrl);
  await send('Target.setDiscoverTargets', { discover: false });

  let anyOk = false;
  for (const u of URLS) {
    const { result } = await send('Target.createTarget', { url: 'about:blank' });
    const tid = result && result.targetId;
    if (!tid) { console.log(`[ERR] 建标签失败`); continue; }
    const att = await send('Target.attachToTarget', { targetId: tid, flatten: true });
    const sid = att && att.result && att.result.sessionId;

    await send('Page.enable', {}, sid);
    await send('Runtime.enable', {}, sid);
    await send('Page.navigate', { url: u }, sid);
    await sleep(6000);
    const r = await send('Runtime.evaluate', {
      expression: `JSON.stringify({u: location.href, len: document.body?document.body.innerHTML.length:0, h1: (document.querySelector('h1')||{}).innerText||''})`,
      returnByValue: true
    }, sid);
    const v = JSON.parse((r.result && r.result.result && r.result.result.value) || '{}');
    const wall = /login\.alibaba\.com/.test(v.u || '') || (v.len || 0) < 20000;
    if (!wall) anyOk = true;
    console.log(`[${wall ? 'WALL' : 'OK'}] len=${v.len} | ${(v.h1 || '').slice(0, 60)} | ${(v.u || '').slice(0, 80)}`);

    await send('Target.closeTarget', { targetId: tid });
  }
  sock.close();
  process.exit(anyOk ? 0 : 1);
})();
