/**
 * check_detail_layout.js — 产品详情页左列留白修复验证
 *
 * 背景：.d-layout 原为 align-items:start，左列只有图集（约 530px 高），
 * 右列购买框高得多，图集下方留出一大块空白（用户截图圈出）。
 * 修复：① 描述挪进左列（.d-desc-side）② .d-layout 改 stretch，图集自动长高
 * ③ .d-info 加 align-self:start 保住 sticky。
 *
 * 判据（每页 × 每宽度）：
 *   leftGap   左列内容底边与整行底边的落差 —— 应 ≤ 4px（stretch 后应为 0）
 *   imgOK     主图真实渲染（complete && naturalWidth>0）
 *   descSide  描述卡在左列且非空
 *   stickyOK  桌面宽度下 .d-info 是 sticky
 *   overlap   图集与右列是否横向重叠
 *
 * 用法：node scripts/check_detail_layout.js [baseUrl]
 */
const { spawn } = require('child_process');
const os = require('os');
const path = require('path');
const fs = require('fs');

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const BASE = (process.argv[2] || 'http://127.0.0.1:8899').replace(/\/$/, '');
const OUTDIR = path.join(process.cwd(), 'scraped', 'detail-layout');

// 覆盖极端情况：截图里的那个产品 / 描述最短 / 描述最长 / 无价格阶梯的
const PAGES = [
  ['v18-截图款', '/en/handheld-vacuum-v18.html'],
  ['qjj071-描述最短', '/en/upright-steam-mop-qjj071.html'],
  ['eg16pro-描述最长', '/en/handheld-vacuum-eg16pro.html'],
  ['ymc6628-描述长', '/en/tire-inflator-ymc6628.html'],
];
const WIDTHS = [1440, 1200, 960, 768, 390];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const MEASURE = `(() => {
  const q = (s) => document.querySelector(s);
  const box = (el) => { if (!el) return null; const b = el.getBoundingClientRect();
    return { t: Math.round(b.top + scrollY), b: Math.round(b.bottom + scrollY),
             l: Math.round(b.left), r: Math.round(b.right), h: Math.round(b.height) }; };
  const layout = q('.d-layout');
  const left = q('.d-left');
  const info = q('.d-info');
  const main = q('#aqc-main-img');
  const desc = q('.d-desc-side');
  const lb = box(left), ib = box(info), lob = box(layout);
  const infoSticky = info ? getComputedStyle(info).position === 'sticky' : false;
  // 只有桌面双栏布局下才谈得上"左列没填满"：右列底边 - 左列底边。
  // （≤960 是单列堆叠，没有可比性；.d-layout 自带的 32px 底部内边距也不算留白）
  const sideBySide = lb && ib && lb.t < ib.b && ib.t < lb.b;
  const leftGap = sideBySide ? Math.max(0, ib.b - lb.b) : 0;
  // 左右列"真重叠" = 横向相交 且 纵向也相交（单列堆叠时横向必然同宽，不算）
  const vOv = (lb && ib) ? Math.min(lb.b, ib.b) - Math.max(lb.t, ib.t) : 0;
  const overlap = (sideBySide && vOv > 0)
    ? Math.max(0, Math.min(lb.r, ib.r) - Math.max(lb.l, ib.l)) : 0;
  return {
    layoutH: lob ? lob.h : null,
    leftH: lb ? lb.h : null,
    infoH: ib ? ib.h : null,
    leftGap, overlap, infoSticky,
    galleryH: (() => { const g = q('.d-gallery'); return g ? Math.round(g.getBoundingClientRect().height) : null; })(),
    imgOK: main ? (main.complete && main.naturalWidth > 0) : null,
    imgH: main ? Math.round(main.getBoundingClientRect().height) : null,
    descSide: desc ? desc.textContent.replace(/\\s+/g, ' ').trim().slice(0, 40) : null,
    descH: desc ? Math.round(desc.getBoundingClientRect().height) : null,
    docOverflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    offenders: (() => {
      const cw = document.documentElement.clientWidth;
      const inScroller = (el) => {
        for (let p = el.parentElement; p && p !== document.body; p = p.parentElement) {
          const o = getComputedStyle(p).overflowX;
          if (o === 'auto' || o === 'scroll' || o === 'hidden' || o === 'clip') return true;
        }
        return false;
      };
      const out = [];
      document.querySelectorAll('body *').forEach((el) => {
        const b = el.getBoundingClientRect();
        if (b.width === 0 || b.height === 0) return;
        if (b.right <= cw + 1 && b.left >= -1) return;
        // 在滚动容器里的越界不算数：它被容器裁掉/可滚动，不会撑破整页
        if (inScroller(el)) return;
        out.push({ tag: el.tagName.toLowerCase(), cls: (el.className || '').toString().slice(0, 34),
                   l: Math.round(b.left), r: Math.round(b.right), w: Math.round(b.width) });
      });
      out.sort((a, b2) => b2.r - a.r);
      return out.slice(0, 4);
    })(),
  };
})()`;

async function main() {
  fs.mkdirSync(OUTDIR, { recursive: true });
  const port = 9700 + Math.floor(Math.random() * 200);
  const userDir = path.join(os.tmpdir(), 'aqc-det-' + Date.now());
  const proc = spawn(EDGE, [
    '--remote-debugging-port=' + port, '--user-data-dir=' + userDir,
    '--no-proxy-server', '--no-first-run', '--no-default-browser-check',
    '--disable-extensions', '--headless=new', '--window-size=1440,900',
    'about:blank',
  ], { stdio: 'ignore' });

  let ws = null;
  for (let i = 0; i < 60; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const p = list.find((t) => t.type === 'page');
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
  const send = (method, params) => new Promise((res) => {
    const mid = ++id; pending.set(mid, res);
    sock.send(JSON.stringify({ id: mid, method, params: params || {} }));
  });
  await new Promise((r) => { sock.onopen = r; });
  await send('Page.enable');
  await send('Runtime.enable');

  let problems = 0, checks = 0;

  for (const [name, url] of PAGES) {
    for (const w of WIDTHS) {
      await send('Emulation.setDeviceMetricsOverride',
        { width: w, height: 900, deviceScaleFactor: 1, mobile: w <= 768 });
      await send('Page.navigate', { url: BASE + url });
      await sleep(1100);
      const r = await send('Runtime.evaluate', { expression: MEASURE, returnByValue: true });
      const v = r.result && r.result.result && r.result.result.value;
      if (!v) { console.log(`?? ${name} @${w} 取不到测量值`); continue; }
      checks++;
      const bad = [];
      if (w > 960) {
        if (!v.descSide) bad.push('左列没有描述卡');
        if (v.leftGap > 4) bad.push(`左列比右列矮 ${v.leftGap}px（仍有留白）`);
        if (!v.infoSticky) bad.push('.d-info 失去 sticky');
      }
      if (v.imgOK === false) bad.push('主图未渲染');
      if (v.overlap > 1) bad.push(`左右列重叠 ${v.overlap}px`);
      if (v.docOverflow > 1) bad.push(`整页横向溢出 ${v.docOverflow}px`);
      if (bad.length) problems++;
      console.log(`${bad.length ? 'FAIL' : 'ok  '} ${name.padEnd(14)} @${String(w).padStart(4)}  ` +
        `行高=${String(v.layoutH).padStart(4)} 左列=${String(v.leftH).padStart(4)} ` +
        `右列=${String(v.infoH).padStart(4)} 图集=${String(v.galleryH).padStart(4)} ` +
        `落差=${String(v.leftGap).padStart(4)} 主图高=${String(v.imgH).padStart(4)} ` +
        `sticky=${v.infoSticky ? 'Y' : 'N'}` + (bad.length ? '  ← ' + bad.join(' / ') : ''));
      if (v.docOverflow > 1 && v.offenders && v.offenders.length) {
        for (const o of v.offenders) {
          console.log(`        越界: <${o.tag}> class="${o.cls}" l=${o.l} r=${o.r} w=${o.w}`);
        }
      }
      if (v.descSide) console.log(`        描述卡: ${v.descSide}… (${v.descH}px)`);
      const shot = await send('Page.captureScreenshot', { format: 'png' });
      if (shot.result && shot.result.data) {
        fs.writeFileSync(path.join(OUTDIR, `${name}-${w}.png`),
          Buffer.from(shot.result.data, 'base64'));
      }
    }
  }

  console.log(`\n共 ${checks} 项，异常 ${problems} 项`);
  console.log('截图目录：' + OUTDIR);
  proc.kill();
  process.exit(problems ? 1 : 0);
}

main().catch((e) => { console.error(e); process.exit(2); });
