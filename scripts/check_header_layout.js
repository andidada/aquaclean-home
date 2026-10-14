/**
 * check_header_layout.js — 导航栏是否被公司全称撑破
 *
 * 背景：页头 / 页脚的品牌标记从 "AquaClean"（9 字符）换成了
 * "Hong Kong Damaijia Technology Co., Limited"（42 字符）。.logo span 原本是
 * font-size:14px + white-space:nowrap，必须实测各宽度有没有溢出 / 相互压盖。
 *
 * 判据：
 *   overflow            document.scrollWidth - clientWidth，>0 = 整页横向滚动
 *   logoLinksOverlap    logo 右边缘越过 nav-links 左边缘的像素
 *   linksPickerOverlap  nav-links 右边缘越过语言选择器左边缘的像素
 *   logoUnderPicker     logo 是否被固定定位的语言选择器压住
 *
 * 用法：node scripts/check_header_layout.js [baseUrl]
 *      baseUrl 默认 http://127.0.0.1:8899
 */
const { spawn } = require('child_process');
const os = require('os');
const path = require('path');
const fs = require('fs');

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const BASE = (process.argv[2] || 'http://127.0.0.1:8899').replace(/\/$/, '');
const OUTDIR = path.join(process.cwd(), 'scraped', 'header-layout');
const PAGES = [
  ['home-en', '/en/index.html'],
  ['detail-en', '/en/robot-vacuum-x7-d.html'],
  ['home-ar', '/ar/index.html'],
  ['cat-zh', '/zh/handheld-vacuum/index.html'],
];
const WIDTHS = [1440, 1280, 1100, 1024, 960, 900, 860, 820, 768, 560, 390];

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const MEASURE = `(() => {
  const q = (s) => document.querySelector(s);
  const box = (el) => { if (!el) return null; const b = el.getBoundingClientRect();
    return { l: Math.round(b.left), r: Math.round(b.right), t: Math.round(b.top),
             b: Math.round(b.bottom), w: Math.round(b.width), h: Math.round(b.height) }; };
  const logo = q('.navbar .logo');
  const span = q('.navbar .logo span');
  const links = q('.navbar .nav-links');
  const toggle = q('.nav-toggle');
  const picker = q('.lang-current');
  const lb = box(logo), kb = box(links), pb = box(picker), tb = box(toggle);
  const collapsed = kb && (kb.h <= 2 || kb.w <= 2);
  const visible = (el) => { if (!el) return false;
    const s = getComputedStyle(el); return s.display !== 'none' && s.visibility !== 'hidden'; };
  // 用矩形相交量算重叠：RTL（body.lang-ar）下 logo 在右边、语言选择器在左边，
  // 用 lb.r - kb.l 这种单向减法会得出上千像素的假阳性。
  const xOverlap = (a, b) => (a && b)
    ? Math.max(0, Math.min(a.r, b.r) - Math.max(a.l, b.l)) : 0;
  return {
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    logo: lb, links: kb, picker: pb, toggle: tb,
    logoText: span ? span.textContent.trim() : null,
    linksCollapsed: !!collapsed,
    pickerVisible: visible(picker),
    logoLinksOverlap: collapsed ? 0 : xOverlap(lb, kb),
    linksPickerOverlap: (collapsed || !visible(picker)) ? 0 : xOverlap(kb, pb),
    logoUnderPicker: visible(picker) ? xOverlap(lb, pb) : 0,
    logoWraps: span ? Math.round(span.getBoundingClientRect().height) : 0,
    navbarH: (() => { const n = q('.navbar-inner'); return n ? Math.round(n.getBoundingClientRect().height) : null; })(),
    // 整页横向溢出时，列出越界元素（前 6 个），用于定位元凶
    offenders: (() => {
      const cw = document.documentElement.clientWidth;
      const out = [];
      const all = document.querySelectorAll('body *');
      for (const el of all) {
        const b = el.getBoundingClientRect();
        if (b.width === 0 || b.height === 0) continue;
        if (b.right > cw + 1 || b.left < -1) {
          out.push({ tag: el.tagName.toLowerCase(),
                     cls: (el.className || '').toString().slice(0, 40),
                     l: Math.round(b.left), r: Math.round(b.right),
                     w: Math.round(b.width) });
        }
      }
      out.sort((a, b2) => b2.r - a.r);
      return out.slice(0, 6);
    })(),
  };
})()`;

async function main() {
  fs.mkdirSync(OUTDIR, { recursive: true });
  const port = 9700 + Math.floor(Math.random() * 200);
  const userDir = path.join(os.tmpdir(), 'aqc-hdr-' + Date.now());
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

  let problems = 0;
  let checks = 0;

  for (const [name, url] of PAGES) {
    for (const w of WIDTHS) {
      await send('Emulation.setDeviceMetricsOverride',
        { width: w, height: 900, deviceScaleFactor: 1, mobile: w <= 768 });
      await send('Page.navigate', { url: BASE + url });
      await sleep(900);
      const r = await send('Runtime.evaluate',
        { expression: MEASURE, returnByValue: true });
      const v = r.result && r.result.result && r.result.result.value;
      if (!v) { console.log(`?? ${name} @${w} 取不到测量值`); continue; }
      checks++;
      const bad = [];
      if (v.overflow > 1) bad.push(`整页横向溢出 ${v.overflow}px`);
      if (v.logoLinksOverlap > 1) bad.push(`logo 压住导航 ${v.logoLinksOverlap}px`);
      if (v.linksPickerOverlap > 1) bad.push(`导航压住语言选择器 ${v.linksPickerOverlap}px`);
      if (v.logoUnderPicker > 1) bad.push(`logo 被语言选择器压住 ${v.logoUnderPicker}px`);
      if (bad.length) problems++;
      const tag = bad.length ? 'FAIL' : 'ok  ';
      const txt = (v.logoText || '-');
      const short = txt.length > 26 ? txt.slice(0, 24) + '…' : txt;
      console.log(`${tag} ${name.padEnd(10)} @${String(w).padStart(4)}  ` +
        `logo.w=${String(v.logo ? v.logo.w : '-').padStart(4)} 文本高=${String(v.logoWraps).padStart(3)}  ` +
        `[${short}]  ` +
        `导航${v.linksCollapsed ? '收起' : '展开'}  溢出=${v.overflow}` +
        (bad.length ? '  ← ' + bad.join(' / ') : ''));
      if (v.overflow > 1 && v.offenders && v.offenders.length) {
        for (const o of v.offenders) {
          console.log(`        越界: <${o.tag}> class="${o.cls}" ` +
            `l=${o.l} r=${o.r} w=${o.w}`);
        }
      }

      const shot = await send('Page.captureScreenshot', { format: 'png' });
      if (shot.result && shot.result.data) {
        fs.writeFileSync(path.join(OUTDIR, `${name}-${w}.png`),
          Buffer.from(shot.result.data, 'base64'));
      }
    }

    // 页脚 logo 也换成了公司全称，单独看一眼有没有被列宽裁掉 / 溢出
    await send('Emulation.setDeviceMetricsOverride',
      { width: 1440, height: 900, deviceScaleFactor: 1, mobile: false });
    await send('Page.navigate', { url: BASE + url });
    await sleep(900);
    await send('Runtime.evaluate', {
      expression: 'window.scrollTo(0, document.body.scrollHeight)', returnByValue: true });
    await sleep(500);
    const fr = await send('Runtime.evaluate', {
      expression: `(() => {
        const logo = document.querySelector('.footer-brand .logo');
        const span = document.querySelector('.footer-brand .logo span');
        const col = document.querySelector('.footer-brand');
        if (!logo || !span || !col) return null;
        const b = logo.getBoundingClientRect(), c = col.getBoundingClientRect();
        return { logoW: Math.round(b.width), colW: Math.round(c.width),
                 textH: Math.round(span.getBoundingClientRect().height),
                 clipped: Math.round(b.right - c.right),
                 text: span.textContent.trim().slice(0, 40) };
      })()`, returnByValue: true });
    const fv = fr.result && fr.result.result && fr.result.result.value;
    if (fv) {
      checks++;
      const bad = [];
      if (fv.clipped > 1) bad.push(`logo 超出页脚列 ${fv.clipped}px`);
      if (fv.logoW > fv.colW) bad.push('logo 比列还宽');
      if (bad.length) problems++;
      console.log(`${bad.length ? 'FAIL' : 'ok  '} ${name.padEnd(10)} 页脚     ` +
        `logo.w=${fv.logoW} 列宽=${fv.colW} 文本高=${fv.textH} [${fv.text}]` +
        (bad.length ? '  ← ' + bad.join(' / ') : ''));
      const fshot = await send('Page.captureScreenshot', { format: 'png' });
      if (fshot.result && fshot.result.data) {
        fs.writeFileSync(path.join(OUTDIR, `${name}-footer.png`),
          Buffer.from(fshot.result.data, 'base64'));
      }
    }
  }

  console.log(`\n共 ${checks} 项，异常 ${problems} 项`);
  console.log('截图目录：' + OUTDIR);
  proc.kill();
  process.exit(problems ? 1 : 0);
}

main().catch((e) => { console.error(e); process.exit(2); });
