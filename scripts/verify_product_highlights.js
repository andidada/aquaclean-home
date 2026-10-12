#!/usr/bin/env node
/**
 * verify_product_highlights.js — 详情页亮点区 / 规格药丸的真实渲染校验
 *
 * 由来（两次）
 * --------
 * 1. 2026-10-12 早些时候：数据合并时字段错位，几个产品的 highlights 被写成
 *    整个产品列表，pick(h.text, lang) 取到 undefined，页面上只剩一排对勾、
 *    文字全空。光看 JSON 结构合法不够，得用真实浏览器读 DOM。
 * 2. 2026-10-12 晚些时候（用户截图反馈）：36 个产品的 highlights 整个就是
 *    规格回音，页面把同一组数字显示两遍——顶部 quick_specs 药丸一遍，
 *    PRODUCT HIGHLIGHTS 下面再一遍。已按"留药丸、删亮点里的重复条目"修掉
 *    （scripts/dedupe_highlights_from_specs.py）。
 *
 * 所以这个脚本现在同时守两件事：
 *   A. 有真亮点的产品，亮点必须真的渲染出文字（不能退回空对勾）；
 *   B. 任何页面都不允许"亮点文本 == 药丸文本"（防重复再长回来）。
 * 没有亮点的产品，亮点区应当整个不出现，但规格药丸和规格表必须在。
 *
 * 用法：
 *   node scripts/verify_product_highlights.js <baseUrl> [pages...]
 * 例：
 *   node scripts/verify_product_highlights.js http://127.0.0.1:8080 \
 *        en/handheld-vacuum-gv18.html en/car-vacuum-yzx-305.html
 */
const { spawn } = require('child_process');
const os = require('os');
const path = require('path');
const fs = require('fs');

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const BASE = (process.argv[2] || 'http://127.0.0.1:8080').replace(/\/$/, '');
// 默认抽这三类：有真亮点 / 已去重 / 用户截图反馈的那个
const PAGES = process.argv.slice(3).length ? process.argv.slice(3) : [
  'en/handheld-vacuum-gv18.html',      // 4 条真亮点
  'en/robot-vacuum-gt20.html',         // 4 条真亮点
  'en/tire-inflator-ymc6628.html',     // 4 条真亮点
  'en/car-vacuum-yzx-305.html',        // 已去重 → 亮点区应消失
  'en/window-cleaner-robot-gm1-c.html',// 已去重 → 亮点区应消失
  'en/handheld-vacuum-v22-2.html',     // 截图里那个
  'zh/handheld-vacuum-v22-2.html',     // 换语种再确认一次
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
      function txt(el){
        var spans = el.querySelectorAll('span');
        return (spans.length ? spans[spans.length-1] : el).textContent.replace(/\\s+/g,' ').trim();
      }
      var items = [].slice.call(document.querySelectorAll('.d-highlight-item'));
      var pills = [].slice.call(document.querySelectorAll('.d-quick-spec'));
      // KEY ATTRIBUTES 区块的真实结构：.d-attr-grid > .d-attr-item > (name, value)
      var specs = [].slice.call(document.querySelectorAll('.d-attr-item'));
      return {
        title: (document.querySelector('.d-highlights-title')||{}).textContent||'',
        n: items.length,
        texts: items.map(txt),
        pillCount: pills.length,
        pillTexts: pills.map(txt),
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
    const pillTexts = data.pillTexts || [];
    const empty = texts.filter(t => !t).length;
    console.log('  亮点区标题: ' + JSON.stringify(data.title) + ' · ' + data.n + ' 条');
    texts.forEach((t, i) => console.log('     ' + (i + 1) + '. ' + (t || '<空>')));
    console.log('  规格药丸 ' + data.pillCount + ' 个: ' + pillTexts.join(' | ').slice(0, 110));

    // A. 只要有亮点，每条都必须有文字（不能退回空对勾）
    check('亮点每条都有文字', data.n === 0 || empty === 0, empty + ' 条为空');
    // B. 亮点文本不得与药丸文本重复（本次修复的核心不变量）
    const dup = texts.filter(t => pillTexts.indexOf(t) !== -1);
    check('亮点与规格药丸无重复', dup.length === 0,
          dup.length ? '重复: ' + dup.join(' / ') : data.n + ' 条亮点 vs ' + data.pillCount + '个药丸');
    // 规格仍然可见：要么有药丸，要么有亮点，不能两样都没
    check('规格信息仍在页面上', data.pillCount > 0 || data.n > 0,
          '药丸 ' + data.pillCount + ' / 亮点 ' + data.n);
    check('规格表也有内容', data.specCount > 0,
          data.specCount + ' 行 · ' + (data.specSample || []).join(' / ').slice(0, 70));
    check('无 JS 报错', errors.length === 0, errors.slice(0, 2).join(' | '));
  }

  try { proc.kill(); } catch (e) {}
  try { fs.rmSync(userDir, { recursive: true, force: true }); } catch (e) {}
  console.log('\n' + (fail === 0 ? '✅ 全部通过' : '❌ 有 ' + fail + ' 项失败') + '：' + pass + ' passed, ' + fail + ' failed');
  process.exit(fail === 0 ? 0 : 1);
}

main().catch(e => { console.error(e); process.exit(1); });
