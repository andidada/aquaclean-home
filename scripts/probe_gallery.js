#!/usr/bin/env node
/* 量详情页图集各元素的实际盒子：找出主图区域被撑坏的原因 */
'use strict';
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const BASE = process.argv[2] || 'https://www.hkdmj.net';
const PAGE = process.argv[3] || '/en/handheld-vacuum-gv18.html';
const PORT = 9700 + Math.floor(Math.random() * 200);

function httpJson(url) {
  return new Promise((resolve, reject) => {
    require('http').get(url, (res) => {
      let b = '';
      res.on('data', (c) => (b += c));
      res.on('end', () => { try { resolve(JSON.parse(b)); } catch (e) { reject(e); } });
    }).on('error', reject);
  });
}

(async () => {
  const prof = fs.mkdtempSync(path.join(os.tmpdir(), 'aqc-probe-'));
  const edge = spawn('C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe', [
    '--headless=new', '--remote-debugging-port=' + PORT,
    '--user-data-dir=' + prof, '--no-first-run', '--window-size=1440,1000', 'about:blank',
  ], { stdio: 'ignore' });

  let list;
  for (let i = 0; i < 30; i++) {
    try { list = await httpJson('http://127.0.0.1:' + PORT + '/json/list'); break; }
    catch (e) { await new Promise((r) => setTimeout(r, 500)); }
  }
  const page = list.find((t) => t.type === 'page');
  await new Promise((r) => setTimeout(r, 2000));
  const ws = new WebSocket(page.webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));
  let mid = 0; const pend = new Map();
  ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } };
  const send = (method, params) => new Promise((res) => { const i = ++mid; pend.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });

  const evaluate = async (expr) => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.result && r.result.exceptionDetails) console.error('EVAL-ERR:', JSON.stringify(r.result.exceptionDetails.exception || r.result.exceptionDetails.text).slice(0, 300));
    return r.result && r.result.result ? r.result.result.value : undefined;
  };

  await send('Page.enable');
  await send('Runtime.enable');
  await send('Network.enable');

  for (const W of [1440, 1200, 990]) {
    await send('Emulation.setDeviceMetricsOverride', { width: W, height: 1000, deviceScaleFactor: 1, mobile: false });
    const target = BASE + PAGE + '?v=' + Math.random();
    console.log('TARGET:', JSON.stringify(target));
    const nav = await send('Page.navigate', { url: target });
    console.log('NAV:', JSON.stringify(nav).slice(0, 400));
    await new Promise((r) => setTimeout(r, 4000));
    let dbg = await evaluate('({mount: !!document.querySelector("#aqc-detail-mount"), url: location.href})');
    if (!dbg || !dbg.mount) {
      await send('Page.navigate', { url: BASE + PAGE + '?v=' + Math.random() });
      await new Promise((r) => setTimeout(r, 4500));
      dbg = await evaluate('({mount: !!document.querySelector("#aqc-detail-mount"), url: location.href})');
    }
    console.log('DBG:', JSON.stringify(dbg));
    const out = await evaluate(`(function(){
      var g = document.querySelector('.d-gallery');
      var gm = document.querySelector('.d-gallery-main');
      var gt = document.querySelector('.d-gallery-thumbs');
      var info = document.querySelector('.d-info');
      var left = document.querySelector('.d-left');
      var desc = document.querySelector('.d-desc-side');
      var layout = document.querySelector('.d-layout');
      var img = document.querySelector('#aqc-main-img');
      var attrcard = document.querySelector('.d-attr-card');
      function rc(el){ if(!el) return null; var r=el.getBoundingClientRect(); return {t:Math.round(r.top),l:Math.round(r.left),w:Math.round(r.width),h:Math.round(r.height)}; }
      var o = { width: ${W}, gallery: rc(g), main: rc(gm), thumbs: rc(gt), info: rc(info), left: rc(left), desc: rc(desc), attr: rc(attrcard), layout: rc(layout), img: rc(img) };
      if (o.left && o.info) {
        o.leftBottomGap = Math.round((o.info.t + o.info.h) - (o.left.t + o.left.h));
        o.rightBottomGap = Math.round((o.left.t + o.left.h) - (o.info.t + o.info.h));
      }
      if (gm) { var cs=getComputedStyle(gm); o.mainStyle={aspectRatio:cs.aspectRatio,minHeight:cs.minHeight,height:cs.height,cursor:cs.cursor}; }
      if (gm) { var cs=getComputedStyle(gm); o.mainStyle={aspectRatio:cs.aspectRatio,minHeight:cs.minHeight,height:cs.height}; }
      if (g) { var cg=getComputedStyle(g); o.galleryStyle={flexGrow:cg.flexGrow, flexShrink:cg.flexShrink, flexBasis:cg.flexBasis, alignItems:cg.alignItems}; }
      o.imgNatural = img ? {w:img.naturalWidth,h:img.naturalHeight,complete:img.complete} : null;
      return o;
    })()`);
    console.log('=== width ' + W + ' ===');
    console.log(JSON.stringify(out, null, 1));
  }

  ws.close(); edge.kill();
  try { fs.rmSync(prof, { recursive: true, force: true }); } catch (e) {}
  process.exit(0);
})().catch((e) => { console.error('FATAL', e); process.exit(1); });
