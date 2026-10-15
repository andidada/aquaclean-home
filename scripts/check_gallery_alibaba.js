#!/usr/bin/env node
/* 详情页主图区（阿里版式）校验：真实 Edge + CDP
   1) 主图框必须是正方形，且图片铺满（不再被拉成竖长条）
   2) 缩略图竖排在左、点击可切换主图、计数角标跟着变
   3) 悬停放大（scale 2）
   4) 左右列底部落差 ≤ 200px
   5) 窄屏（390）不横向溢出、缩略图转横排
   用法： node scripts/check_gallery_alibaba.js [baseUrl]                       */
'use strict';
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const BASE = process.argv[2] || 'http://127.0.0.1:8899';
const PAGES = process.argv.slice(3).length ? process.argv.slice(3)
  : ['/en/handheld-vacuum-gv18.html', '/en/handheld-vacuum-gv22.html'];
const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let pass = 0, fail = 0;
function ok(name, cond, extra) {
  if (cond) { pass++; console.log('ok   ' + name + (extra ? '  ' + extra : '')); }
  else { fail++; console.log('FAIL ' + name + (extra ? '  ' + extra : '')); }
}

(async () => {
  const port = 9700 + Math.floor(Math.random() * 200);
  const prof = fs.mkdtempSync(path.join(os.tmpdir(), 'aqc-gal-'));
  const edge = spawn(EDGE, [
    '--headless=new', '--disable-gpu', '--no-proxy-server', '--no-first-run',
    '--remote-debugging-port=' + port, '--user-data-dir=' + prof, 'about:blank',
  ], { stdio: 'ignore' });
  await sleep(3000);

  let list;
  for (let i = 0; i < 30; i++) {
    try {
      list = await (await fetch('http://127.0.0.1:' + port + '/json/list')).json();
      if (list.some((t) => t.type === 'page')) break;
    } catch (e) {}
    await sleep(400);
  }
  const ws = new WebSocket(list.find((t) => t.type === 'page').webSocketDebuggerUrl);
  await new Promise((r) => (ws.onopen = r));
  let id = 0; const pend = new Map();
  ws.onmessage = (ev) => { const m = JSON.parse(ev.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } };
  const send = (method, params) => new Promise((res) => { const i = ++id; pend.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
  const evl = async (expr) => {
    const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
    if (r.result && r.result.exceptionDetails) console.error('EVAL-ERR', JSON.stringify(r.result.exceptionDetails).slice(0, 300));
    return r.result && r.result.result ? r.result.result.value : undefined;
  };
  await send('Page.enable'); await send('Runtime.enable');

  for (const W of [1440, 1200, 390]) {
    for (const P of PAGES) {
      await send('Emulation.setDeviceMetricsOverride', { width: W, height: 1000, deviceScaleFactor: 1, mobile: W <= 480 });
      await send('Network.setCacheDisabled', { cacheDisabled: true });
      await send('Page.navigate', { url: BASE + P + '?v=' + Math.random() });
      await sleep(2800);
      const tag = P.replace(/^\/en\//, '') + ' @' + W;

      const geo = await evl(`(function(){
        var box=document.querySelector('.d-gallery-main'), img=document.querySelector('#aqc-main-img');
        var thumbs=document.querySelectorAll('.d-gallery-thumb');
        var left=document.querySelector('.d-left'), info=document.querySelector('.d-info');
        var attrcard=document.querySelector('.d-attr-card');
        function rc(e){ if(!e) return null; var r=e.getBoundingClientRect(); return {w:Math.round(r.width),h:Math.round(r.height)}; }
        var ib=rc(box), ii=rc(img);
        var rows=document.querySelectorAll('.d-attr-row');
        var shown=0; for (var i=0;i<rows.length;i++) if (rows[i].style.display!=='none') shown++;
        return {
          box: ib, img: ii, thumbCount: thumbs.length,
          thumbsDir: thumbs.length ? getComputedStyle(document.querySelector('.d-gallery-thumbs')).flexDirection : 'none',
          activeIdx: (function(){ for (var i=0;i<thumbs.length;i++) if (thumbs[i].classList.contains('active')) return i; return -1; })(),
          count: (document.querySelector('#aqc-gallery-count')||{}).textContent || null,
          leftH: left?Math.round(left.offsetHeight):0, infoH: info?Math.round(info.offsetHeight):0,
          gap: (left&&info)? Math.round((info.getBoundingClientRect().bottom)-(left.getBoundingClientRect().bottom)) : 0,
          attrVisible: !!attrcard && getComputedStyle(attrcard).display!=='none',
          attrRowsShown: shown,
          overflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth
        };
      })()`);

      ok(tag + ' 主图框是正方形', geo.box && Math.abs(geo.box.w - geo.box.h) <= 3, JSON.stringify(geo.box));
      ok(tag + ' 照片铺满框（无大白边）',
        geo.img && geo.box && Math.abs(geo.img.w - geo.box.w) <= 3 && Math.abs(geo.img.h - geo.box.h) <= 3,
        JSON.stringify(geo.img));
      ok(tag + ' 缩略图存在且首张选中', geo.thumbCount >= 2 && geo.activeIdx === 0, 'n=' + geo.thumbCount);
      ok(tag + ' 缩略图排列方向正确', W > 960 ? geo.thumbsDir === 'column' : geo.thumbsDir === 'row', geo.thumbsDir);
      ok(tag + ' 无横向溢出', geo.overflowX <= 2, 'overflowX=' + geo.overflowX);
      // ≤960 是单列堆叠，左右列落差没有意义
      if (W > 960) ok(tag + ' 左右列落差 ≤200px', Math.abs(geo.gap) <= 200, 'gap=' + geo.gap);
      ok(tag + ' 属性卡要么隐藏要么≥3行',
        !geo.attrVisible || geo.attrRowsShown >= 3, 'visible=' + geo.attrVisible + ' rows=' + geo.attrRowsShown);

      // 切换缩略图 + 计数角标（桌面/移动都测）
      const swap = await evl(`(function(){
        var ths=document.querySelectorAll('.d-gallery-thumb'); var img=document.querySelector('#aqc-main-img');
        if (ths.length<3) return {skip:true};
        var before=img.getAttribute('src');
        ths[2].click();
        var after=img.getAttribute('src');
        var cnt=document.querySelector('#aqc-gallery-count');
        return {skip:false, changed: before!==after, count: cnt?cnt.textContent:null,
                active: ths[2].classList.contains('active')};
      })()`);
      if (!swap.skip) {
        ok(tag + ' 点第3张缩略图切换主图', swap.changed && swap.active);
        if (geo.count) ok(tag + ' 计数角标跟着变', swap.count === '3/' + geo.thumbCount, swap.count);
      }

      // 悬停放大（合成 mousemove 即可，监听读的是 clientX/clientY）
      const zoomIn = await evl(`(function(){
        var box=document.querySelector('.d-gallery-main'), img=document.querySelector('#aqc-main-img');
        if(!box||!img) return {skip:true};
        var r=box.getBoundingClientRect();
        box.dispatchEvent(new MouseEvent('mousemove',{bubbles:true,clientX:r.left+r.width*0.3,clientY:r.top+r.height*0.3}));
        var cs=getComputedStyle(img);
        return {skip:false, transform:cs.transform, origin:cs.transformOrigin};
      })()`);
      await sleep(450);   // 等 0.18s 的过渡回落，否则读到的是动画中间态
      const zoomOut = await evl(`(function(){
        var box=document.querySelector('.d-gallery-main');
        box.dispatchEvent(new MouseEvent('mouseleave',{bubbles:true}));
        return true;
      })()`);
      await sleep(450);
      const zoomAfter = await evl(`getComputedStyle(document.querySelector('#aqc-main-img')).transform`);
      if (!zoomIn.skip) {
        ok(tag + ' 悬停放大生效', /matrix\(2,/.test(zoomIn.transform), zoomIn.transform + ' origin=' + zoomIn.origin);
        ok(tag + ' 移开后复原', zoomAfter === 'none' || /matrix\(1,/.test(zoomAfter), zoomAfter);
      }
      console.log('');
    }
  }

  ws.close(); edge.kill();
  try { fs.rmSync(prof, { recursive: true, force: true }); } catch (e) {}
  console.log('===== 共 ' + (pass + fail) + ' 项，通过 ' + pass + '，异常 ' + fail + ' =====');
  process.exit(fail ? 1 : 0);
})().catch((e) => { console.error('FATAL', e); process.exit(1); });
