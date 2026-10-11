#!/usr/bin/env node
/**
 * shot_element.js — 用真实浏览器截取「页面上某个元素」的图
 *
 * 用途：改版 / 修 bug 后的视觉留证，以及给人看的前后对照图。
 * 比整页截图好用，因为能精准框住一个区块（例如详情页的亮点区）。
 *
 * 用法：
 *   node scripts/shot_element.js <url> <输出png> [选择器] [宽度] [缩放]
 * 例：
 *   node scripts/shot_element.js https://www.hkdmj.net/en/handheld-vacuum-gv18.html \
 *        out/gv18.png .d-highlights
 *
 * 注意：captureScreenshot 的 clip 用的是「页面绝对坐标」，而
 * getBoundingClientRect() 给的是「视口坐标」—— 必须补上 window.scrollX/Y，
 * 否则会截到别的区块（这里踩过一次）。
 */
const { spawn } = require('child_process');
const os = require('os');
const path = require('path');
const fs = require('fs');

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const URL = process.argv[2];
const OUT = process.argv[3];
const SEL = process.argv[4] || 'body';
const WIDTH = parseInt(process.argv[5] || '1280', 10);
const SCALE = parseFloat(process.argv[6] || '2');

if (!URL || !OUT) {
  console.error('用法: node scripts/shot_element.js <url> <输出png> [选择器] [宽度] [缩放]');
  process.exit(1);
}

const sleep = ms => new Promise(r => setTimeout(r, ms));

(async () => {
  const port = 9500 + Math.floor(Math.random() * 300);
  const userDir = path.join(os.tmpdir(), 'aqc-shot-' + Date.now());
  const proc = spawn(EDGE, [
    '--remote-debugging-port=' + port, '--user-data-dir=' + userDir,
    '--no-proxy-server', '--no-first-run', '--no-default-browser-check',
    '--disable-extensions', '--headless=new',
    '--window-size=' + WIDTH + ',900',
    '--force-device-scale-factor=' + SCALE,
    'about:blank',
  ], { stdio: 'ignore' });

  let ws = null;
  for (let i = 0; i < 60; i++) {
    try {
      const l = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const p = l.find(t => t.type === 'page');
      if (p) { ws = p.webSocketDebuggerUrl; break; }
    } catch (e) { /* retry */ }
    await sleep(500);
  }
  if (!ws) { console.error('无法连接 Edge'); proc.kill(); process.exit(1); }

  const sock = new WebSocket(ws);
  let id = 0;
  const pend = new Map();
  sock.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); }
  };
  await new Promise(r => { sock.onopen = r; });
  const send = (method, params) => {
    const mid = ++id;
    sock.send(JSON.stringify({ id: mid, method, params: params || {} }));
    return new Promise(res => pend.set(mid, res));
  };

  await send('Page.enable');
  await send('Page.navigate', { url: URL });
  await sleep(7000);   // 等首屏脚本把区块渲染出来

  const r = await send('Runtime.evaluate', {
    returnByValue: true,
    expression: `(function(){
      var el = document.querySelector(${JSON.stringify(SEL)});
      if (!el) return null;
      var b = el.getBoundingClientRect();
      return {
        x: Math.max(0, b.left + window.scrollX - 16),
        y: Math.max(0, b.top + window.scrollY - 16),
        width: Math.min(b.width + 32, ${WIDTH}),
        height: b.height + 32
      };
    })()`,
  });
  const box = r.result && r.result.result && r.result.result.value;
  if (!box) {
    console.error('页面上找不到选择器: ' + SEL);
    sock.close(); proc.kill(); process.exit(1);
  }

  const shot = await send('Page.captureScreenshot', {
    format: 'png',
    clip: Object.assign({ scale: 1 }, box),
    captureBeyondViewport: true,
  });
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, Buffer.from(shot.result.data, 'base64'));
  console.log('saved ' + OUT + '  ' + fs.statSync(OUT).size + ' bytes');

  sock.close();
  try { proc.kill(); } catch (e) {}
  try { fs.rmSync(userDir, { recursive: true, force: true }); } catch (e) {}
  process.exit(0);
})();
