/**
 * capture_fonts.js — 抓取 Google Fonts 的 Inter 字体，改为自托管
 *
 * 为什么要做：站内 462 个页面都引用了
 *   <link href="https://fonts.googleapis.com/css2?family=Inter...">
 * 这是一条**阻塞渲染**的外部样式表。该域名在部分网络（含中国大陆常见链路）
 * 不可达时会挂起 ~2s，浏览器必须等它加载或失败才能绘制，首屏直接被拖垮。
 * 自托管后：@font-face 并入 style.css（零额外请求），woff2 走本站域名，
 * 不再依赖任何第三方。
 *
 * 做法：curl 在这台机器上访问不了 fonts.googleapis.com（代理拦截），
 * 但真实浏览器可以（--no-proxy-server）。所以这里用 CDP 驱动 Edge，
 * 在页面上下文里 fetch 资源并回传 base64。fonts.gstatic.com 带
 * Access-Control-Allow-Origin: *，允许跨域 fetch。
 *
 * 产出：
 *   assets/fonts/inter-<subset>.woff2
 *   assets/css/fonts.css     （url 已改写为 ../fonts/...，供并入 style.css）
 *
 * 用法：node scripts/capture_fonts.js
 */
const { spawn } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const ROOT = path.resolve(__dirname, '..');
const OUT_FONTS = path.join(ROOT, 'assets', 'fonts');
const CSS_URL = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap';
// 现代 UA 才会拿到 woff2 + unicode-range 分片；老 UA 会拿到 ttf
const UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36';
// 站点实际用得到的子集。希腊语没有内容，跳过以省体积。
const WANT = ['latin', 'latin-ext', 'cyrillic', 'cyrillic-ext', 'vietnamese'];

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function main() {
  fs.mkdirSync(OUT_FONTS, { recursive: true });
  const port = 9500 + Math.floor(Math.random() * 300);
  const userDir = path.join(os.tmpdir(), 'aqc-font-' + Date.now());
  const proc = spawn(EDGE, [
    '--remote-debugging-port=' + port,
    '--user-data-dir=' + userDir,
    '--no-proxy-server',
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-extensions',
    '--headless=new',
    '--window-size=1440,900',
    'about:blank',
  ], { stdio: 'ignore' });

  let ws = null;
  for (let i = 0; i < 60; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const page = list.find(t => t.type === 'page');
      if (page) { ws = page.webSocketDebuggerUrl; break; }
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
  const evaluate = async (expression) => {
    const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (r.result && r.result.exceptionDetails) throw new Error(JSON.stringify(r.result.exceptionDetails));
    return r.result && r.result.result ? r.result.result.value : null;
  };

  await send('Page.enable');
  await send('Runtime.enable');
  await send('Network.enable');
  await send('Network.setUserAgentOverride', { userAgent: UA });
  await send('Page.navigate', { url: 'https://www.hkdmj.net/en/index.html' });
  await sleep(6000);   // 等页面就绪，拿到一个真实的 https 源（about:blank 的源是 null）

  // 1) 取 CSS
  const css = await evaluate(`(async () => {
    const r = await fetch(${JSON.stringify(CSS_URL)});
    return await r.text();
  })()`);
  if (!css || css.indexOf('@font-face') < 0) {
    console.error('未取到 Google Fonts CSS: ' + String(css).slice(0, 200));
    sock.close(); proc.kill(); process.exit(1);
  }
  console.log('取到 CSS，' + css.length + 'B，' + (css.match(/@font-face/g) || []).length + ' 个 @font-face');

  // 2) 解析：注释里带子集名，紧跟其后的 url(...) 就是该子集的字体
  const blocks = [...css.matchAll(/\/\*\s*([a-z-]+)\s*\*\/\s*@font-face\s*\{([^}]+)\}/g)]
    .map(m => ({ subset: m[1], url: (m[2].match(/url\(([^)]+)\)/) || [])[1], range: (m[2].match(/unicode-range:\s*([^;]+);/) || [])[1] }));
  const seen = new Map();
  blocks.forEach(b => { if (b.url && !seen.has(b.subset)) seen.set(b.subset, b); });
  console.log('子集: ' + [...seen.keys()].join(', '));

  // 3) 下载需要的子集
  const tasks = [...seen.entries()].filter(([k]) => WANT.indexOf(k) >= 0);
  const mapping = {};   // 远端 url -> 本地文件名
  for (const [subset, info] of tasks) {
    const b64 = await evaluate(`(async () => {
      const r = await fetch(${JSON.stringify(info.url)});
      const b = await r.arrayBuffer();
      let s = '';
      const u = new Uint8Array(b);
      for (let i = 0; i < u.length; i++) s += String.fromCharCode(u[i]);
      return btoa(s);
    })()`);
    if (!b64) { console.warn('下载失败，跳过 ' + subset); continue; }
    const buf = Buffer.from(b64, 'base64');
    const name = 'inter-' + subset + '.woff2';
    fs.writeFileSync(path.join(OUT_FONTS, name), buf);
    mapping[info.url] = name;
    console.log('  ' + name.padEnd(28) + String(buf.length).padStart(7) + 'B   ' + subset);
  }

  // 4) 重写 CSS：只保留已下载子集的 @font-face，url 指向本地
  const outBlocks = blocks.filter(b => mapping[b.url]).map(b => {
    return '/* ' + b.subset + ' */\n@font-face {\n' +
      "  font-family: 'Inter';\n" +
      '  font-style: normal;\n' +
      '  font-weight: 400 900;\n' +     // 可变字体，一次覆盖全部字重
      '  font-display: swap;\n' +
      '  src: url(../fonts/' + mapping[b.url] + ") format('woff2');\n" +
      '  unicode-range: ' + b.range + ';\n}';
  });
  // 同一个子集在 CSS 里按字重重复了 6 次，去重
  const uniq = [];
  const seenName = new Set();
  blocks.filter(b => mapping[b.url]).forEach(b => {
    if (seenName.has(b.subset)) return;
    seenName.add(b.subset);
    uniq.push('/* ' + b.subset + ' */\n@font-face {\n' +
      "  font-family: 'Inter';\n" +
      '  font-style: normal;\n' +
      '  font-weight: 400 900;\n' +
      '  font-display: swap;\n' +
      '  src: url(../fonts/' + mapping[b.url] + ") format('woff2');\n" +
      '  unicode-range: ' + b.range + ';\n}');
  });

  const header = '/* Inter（自托管，来自 Google Fonts，SIL Open Font License 1.1）\n' +
    '   原为 fonts.googleapis.com 的阻塞式外链，在部分网络不可达时会挂起约 2s\n' +
    '   并阻塞首屏渲染，故改为本站托管。woff2 为可变字体，一个文件覆盖 400-900 字重。 */\n';
  const out = header + uniq.join('\n') + '\n';
  fs.writeFileSync(path.join(ROOT, 'assets', 'css', 'fonts.css'), out, 'utf8');
  console.log('\n写出 assets/css/fonts.css  ' + out.length + 'B，' + uniq.length + ' 个子集');

  sock.close();
  try { proc.kill(); } catch (e) {}
  try { fs.rmSync(userDir, { recursive: true, force: true }); } catch (e) {}
}

main().catch(e => { console.error(e); process.exit(1); });
