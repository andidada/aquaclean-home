#!/usr/bin/env node
/**
 * inspect_alibaba_dom.js — 探查阿里详情页到底把图片清单藏在哪
 *
 * collect_alibaba_cdp.js 的按「位置 + CSS 宽度」分类太脆了：
 * 页面里塞满了推荐位缩略图（172px 一大堆），而真正的详情长图要么没渲染、
 * 要么躺在 <script> 的 JSON 里（cssW=0 / y=0 那一批）。
 *
 * 这个脚本不猜，直接把证据摆出来：
 *   1. og:image / JSON-LD
 *   2. 所有 iframe（详情长图常被塞进独立 iframe）
 *   3. 页面里所有 <script> 中出现过的 kf/Hxxx 图片路径，按脚本分组
 *   4. DOM 里可见的 img 按尺寸分组
 *   5. window 上可能挂着的数据变量名
 *
 * 用法（需先有一个开着调试端口 9333 的 Edge）：
 *   node scripts/inspect_alibaba_dom.js <url>
 */
const fs = require('fs');
const path = require('path');

const PORT = 9333;
const URL = process.argv[2] ||
  'https://www.alibaba.com/product-detail/Hot-selling-Stick-Cordless-Vacuum-Cleaner_1601719491601.html';

const sleep = ms => new Promise(r => setTimeout(r, ms));

async function findPage() {
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  return list.find(t => t.type === 'page' && t.webSocketDebuggerUrl) || null;
}

async function connect(wsUrl) {
  const sock = new WebSocket(wsUrl);
  let id = 0;
  const pending = new Map();
  sock.onmessage = ev => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  };
  await new Promise((res, rej) => { sock.onopen = res; sock.onerror = rej; });
  const send = (method, params) => {
    const mid = ++id;
    sock.send(JSON.stringify({ id: mid, method, params: params || {} }));
    return new Promise(res => pending.set(mid, res));
  };
  return { sock, send };
}

const PROBE = `(function(){
  var out = {};

  // 1. meta og:image / JSON-LD
  out.ogImage = (document.querySelector('meta[property="og:image"]')||{}).content || '';
  out.jsonld = [];
  var lds = document.querySelectorAll('script[type="application/ld+json"]');
  for (var i=0;i<lds.length;i++){
    var t = (lds[i].textContent||'').trim();
    var imgs = (t.match(/alicdn\\.com[^"\\\\ ]+/g) || []).slice(0,20);
    out.jsonld.push({len:t.length, type:(t.match(/"@type"\\s*:\\s*"([^"]+)"/)||[])[1]||'?', images:imgs});
  }

  // 2. iframe（详情长图常被塞进独立 iframe）
  out.iframes = [];
  var ifs = document.querySelectorAll('iframe');
  for (var f=0; f<ifs.length; f++){
    var r = ifs[f].getBoundingClientRect();
    out.iframes.push({src:(ifs[f].src||ifs[f].getAttribute('data-src')||'').slice(0,180),
                      w:Math.round(r.width), h:Math.round(r.height)});
  }

  // 3. 所有 <script> 里的 kf/ 图片路径
  out.scriptImages = [];
  var scs = document.querySelectorAll('script');
  for (var s=0; s<scs.length; s++){
    var txt = scs[s].textContent || '';
    if (txt.length < 200) continue;
    var hits = txt.match(/(?:https?:)?\\/\\/[a-z0-9.]*alicdn\\.com\\/[^"'\\\\ )]+/g) || [];
    if (!hits.length) continue;
    var uniq = []; var seen = Object.create(null);
    for (var h=0; h<hits.length; h++){
      var u = hits[h].replace(/\\\\u002F/g,'/').replace(/\\\\\\//g,'/');
      if (seen[u]) continue; seen[u]=1; uniq.push(u);
    }
    if (uniq.length < 2) continue;
    out.scriptImages.push({scriptLen:txt.length, count:uniq.length, sample:uniq.slice(0,25)});
  }
  out.scriptImages.sort(function(a,b){return b.count-a.count;});

  // 4. DOM 里可见 img 按 cssW 分组
  var byW = {};
  var imgs = document.querySelectorAll('img');
  var visible = 0;
  for (var m2=0; m2<imgs.length; m2++){
    var r2 = imgs[m2].getBoundingClientRect();
    var w = Math.round(r2.width);
    if (w>0 && r2.height>0) visible++;
    var key = 'w'+w;
    byW[key] = (byW[key]||0)+1;
  }
  out.imgTotal = imgs.length;
  out.imgVisible = visible;
  out.imgByWidth = byW;

  // 5. window 上挂的数据变量
  out.windowKeys = [];
  for (var k in window){
    if (!Object.prototype.hasOwnProperty.call(window,k)) continue;
    if (/^(data|DATA|__|_|g_|page|PAGE)/.test(k) && typeof window[k]==='object' && window[k]!==null){
      try { JSON.stringify(window[k]); out.windowKeys.push(k); } catch(e){}
    }
  }

  return out;
})()`;

async function main() {
  const target = await findPage();
  if (!target) {
    console.error('✗ 9333 端口上没有可用的 Edge 页面。先跑：node scripts/collect_alibaba_cdp.js');
    process.exit(1);
  }
  const { sock, send } = await connect(target.webSocketDebuggerUrl);
  await send('Page.enable');
  await send('Runtime.enable');

  console.log('打开：' + URL);
  await send('Page.navigate', { url: URL });
  await sleep(5000);
  for (let s = 0; s < 16; s++) {
    await send('Runtime.evaluate', { expression: 'window.scrollBy(0, window.innerHeight*0.85)', returnByValue: true });
    await sleep(650);
  }
  await send('Runtime.evaluate', { expression: 'window.scrollTo(0,0)', returnByValue: true });
  await sleep(1500);

  const r = await send('Runtime.evaluate', { expression: PROBE, returnByValue: true });
  const out = (r.result && r.result.result) ? r.result.result.value : null;
  sock.close();
  if (!out) { console.error('✗ 探查失败'); process.exit(1); }

  const dumpDir = path.join(process.cwd(), 'scraped', 'inspect');
  fs.mkdirSync(dumpDir, { recursive: true });
  const slug = (URL.match(/_(\d{10,})\.html/) || [])[1] || 'probe';
  fs.writeFileSync(path.join(dumpDir, slug + '.json'), JSON.stringify(out, null, 2), 'utf8');

  console.log('\nog:image      : ' + (out.ogImage || '(无)'));
  console.log('JSON-LD       : ' + out.jsonld.length + ' 块');
  out.jsonld.forEach(j => console.log('   type=' + j.type + ' len=' + j.len + ' images=' + j.images.length));
  console.log('iframe        : ' + out.iframes.length);
  out.iframes.forEach(f => console.log('   ' + f.w + 'x' + f.h + '  ' + f.src));
  console.log('img 总数/可见 : ' + out.imgTotal + ' / ' + out.imgVisible);
  console.log('img 按宽度    : ' + JSON.stringify(out.imgByWidth));
  console.log('window 数据键 : ' + (out.windowKeys.join(', ') || '(无)'));
  console.log('\n含图片的 <script>（按图片数倒序，前 6 个）：');
  out.scriptImages.slice(0, 6).forEach((s, i) => {
    console.log('  [' + (i + 1) + '] scriptLen=' + s.scriptLen + ' 图片=' + s.count);
    s.sample.slice(0, 8).forEach(u => console.log('       ' + u.slice(0, 130)));
  });
  console.log('\n完整结果：' + path.join(dumpDir, slug + '.json'));
}

main().catch(e => { console.error(e); process.exit(1); });
