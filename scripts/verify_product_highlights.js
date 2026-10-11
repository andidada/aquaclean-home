#!/usr/bin/env node
/**
 * verify_product_highlights.js — 详情页 "PRODUCT HIGHLIGHTS" 是否真的渲染出文字
 *
 * 起因：数据合并时字段错位，几个产品的 highlights 被写成了整个产品列表，
 * 渲染时 pick(h.text, lang) 取到 undefined，于是页面上只剩一排对勾、文字全空。
 * 光看 JSON 结构合法还不够 —— 这里用真实浏览器打开页面，读 DOM 里的文本。
 *
 * 用法：
 *   node scripts/verify_product_highlights.js <baseUrl> [pages...]
 * 例：
 *   node scripts/verify_product_highlights.js http://127.0.0.1:8080 \
 *        en/handheld-vacuum-gv18.html en/robot-vacuum-gt20.html zh/car-vacuum-yzx-305.html
 */
const { spawn } = require('child_process');
const os = require('os');
const path = require('path');
const fs = require('fs');

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const BASE = (process.argv[2] || 'http://127.0.0.1:8080').replace(/\/$/, '');
const PAGES = process.argv.slice(3).length ? process.argv.slice(3) : [
  'en/handheld-vacuum-gv18.html',
  'en/robot-vacuum-gt20.html',
  'en/car-vacuum-yzx-305.html',
  'en/window-cleaner-robot-gm1-c.html',
];

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function probe(port, url) {
  const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const page = list.find(t => t.type === 'page');
  const sock = new WebSocket(page.webSocketDebuggerUrl);
  let id = 0;
  const pending = new Map();
  const errors = [];
  sock.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  };
  sock.addEventListener('message', (ev) => {
    const m = JSON.parse(ev.data);
    if (m.method === 'Runtime.exceptionThrown') errors.push(m.params.exceptionDetails.text || '');
    if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') {
      errors.push((m.params.args || []).map(a => a.value || a.description || '').join(' '));
    }
  });
  await new Promise(r => { sock.onopen = r; sock.onerror = r; });
  const send = (method, params) => {
    const mid = ++id;
    sock.send(JSON.stringify({ id: mid, method, params: params || {} }));
    return new Promise(res => pending.set(mid, res));
  };

  await send('Page.enable');
  await send('Runtime.enable');
  await send('Network.enable');
  await send('Network.clearBrowserCache');
  await send('Page.navigate', { url });
  await sleep(5000);

  const r = await send('Runtime.evaluate', {
    returnByValue: true,
    expression: `(function(){
      var items = [].slice.call(document.querySelectorAll('.d-highlight-item'));
      // KEY ATTRIBUTES 区块的真实结构：.d-attr-grid > .d-attr-item > (name, value)
      var specs = [].slice.call(document.querySelectorAll('.d-attr-item'));
      return {
        title: (document.querySelector('.d-highlights-title')||{}).textContent||'',
        n: items.length,
        texts: items.map(function(el){
          var spans = el.querySelectorAll('span');
          return spans.length ? spans[spans.length-1].textContent.trim() : el.textContent.trim();
        }),
        specCount: specs.length,
        specSample: specs.slice(0,2).map(function(e){ return (e.textContent||'').replace(/\\s+/g,' ').trim(); })
      };
    })()`,
  });
  sock.close();
  return { data: (r.result && r.result.result) ? r.result.result.value : {}, errors };
}

async function main() {
  const port = 9700 + Math.floor(Math.random() * 150);
  const userDir = path.join(os.tmpdir(), 'aqc-hl-' + Date.now());
  const proc = spawn(EDGE, [
    '--remote-debugging-port=' + port,
    '--user-data-dir=' + userDir, '--no-proxy-server',
    '--no-first-run', '--no-default-browser-check', '--disable-extensions',
    '--headless=new', '--window-size=1440,900', 'about:blank',
  ], { stdio: 'ignore' });

  let up = false;
  for (let i = 0; i < 60 && !up; i++) {
    try { await (await fetch(`http://127.0.0.1:${port}/json/version`)).json(); up = true; }
    catch (e) { await sleep(500); }
  }
  if (!up) { console.error('无法连接 Edge'); proc.kill(); process.exit(1); }

  let pass = 0, fail = 0;
  const check = (name, ok, detail) => {
    console.log((ok ? '  ✓ ' : '  ✗ ') + name + (detail ? '  — ' + detail : ''));
    ok ? pass++ : fail++;
  };

  for (const p of PAGES) {
    const url = BASE + '/' + p;
    console.log('\n=== ' + p + ' ===');
    const { data, errors } = await probe(port, url);
    const texts = data.texts || [];
    const empty = texts.filter(t => !t).length;
    console.log('  标题: ' + JSON.stringify(data.title));
    texts.forEach((t, i) => console.log('   ' + (i + 1) + '. ' + (t || '<空>')));
    check('渲染出 highlight 条目', data.n > 0, data.n + ' 条');
    check('每一条都有文字（不再是空对勾）', data.n > 0 && empty === 0, empty + ' 条为空');
    check('规格表也有内容', data.specCount > 0, data.specCount + ' 行 · ' + (data.specSample || []).join(' / ').slice(0, 70));
    check('无 JS 报错', errors.length === 0, errors.slice(0, 2).join(' | '));
  }

  try { proc.kill(); } catch (e) {}
  try { fs.rmSync(userDir, { recursive: true, force: true }); } catch (e) {}
  console.log('\n' + (fail === 0 ? '✅ 全部通过' : '❌ 有 ' + fail + ' 项失败') + '：' + pass + ' passed, ' + fail + ' failed');
  process.exit(fail === 0 ? 0 : 1);
}

main().catch(e => { console.error(e); process.exit(1); });
