#!/usr/bin/env node
/**
 * collect_alibaba_v3.js — 阿里详情页终版采集器（主图 + 详情长图 + 英文属性表）
 *
 * 三路数据各自的来源，都是从页面自己暴露的数据里拿，不靠猜：
 *
 *   1. 主图 gallery
 *      <script type="application/ld+json"> 里 @type=Product 的 image 数组。
 *      （会重复写两遍，去重即可）
 *
 *   2. 详情长图 detail
 *      长图不在主文档里，而在独立 iframe：
 *        /product-detail/description/descIframe.html?productId=<id>
 *      直接导航过去 + 滚动触发懒加载，按文档顺序取全分辨率原图。
 *
 *   3. 英文属性表 attrs
 *      主文档里最大的那个内联 <script>（约 22 万字符）里有
 *        {"attrName":"Suction Power","attrValue":"18000Pa"}
 *      这样的成对数据，是英文的标准属性表。
 *      ⚠️ 页面正文按浏览器语言渲染成中文，但**属性表是英文的**，
 *         所以这里正则取 attrName/attrValue，并且只留 ASCII 的 attrName
 *         （页面同时存在一份中文的行业属性，用 ASCII 过滤掉）。
 *
 * 用法（需要已有一个开着 9333 调试端口的 Edge）：
 *   node scripts/collect_alibaba_v3.js
 */
const fs = require('fs');
const path = require('path');

const PORT = 9333;
const OUT_DIR = path.join(process.cwd(), 'scraped', 'alibaba_v3');
const LINKS_FILE = process.argv[2] ||
  path.join(process.cwd(), 'scraped', 'alibaba_links.txt');

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

/** 主文档：h1 + JSON-LD 主图 + 大脚本里的英文属性表 */
const MAIN_EXPR = `(function(){
  function txt(el){ return (el && (el.innerText||el.textContent)||'').replace(/\\s+/g,' ').trim(); }
  var out = {h1:txt(document.querySelector('h1')), title:document.title||'', gallery:[], attrs:{}};

  var lds = document.querySelectorAll('script[type="application/ld+json"]');
  for (var i=0;i<lds.length;i++){
    var o=null; try{ o=JSON.parse((lds[i].textContent||'').trim()); }catch(e){ continue; }
    var nodes = Array.isArray(o)?o:[o];
    for (var n=0;n<nodes.length;n++){
      if (!nodes[n] || nodes[n]['@type']!=='Product') continue;
      var im = nodes[n].image, arr = Array.isArray(im)?im:(im?[im]:[]);
      for (var k=0;k<arr.length;k++){
        var u = typeof arr[k]==='string'?arr[k]:((arr[k]&&arr[k].url)||'');
        if(u) out.gallery.push(u);
      }
      out.jsonldName  = nodes[n].name || '';
      out.jsonldBrand = (nodes[n].brand && nodes[n].brand.name) || '';
    }
  }

  // 最大的内联 script —— 属性表藏在里面
  var scs=document.querySelectorAll('script'), best='';
  for (var s=0;s<scs.length;s++){ var t=scs[s].textContent||''; if(t.length>best.length) best=t; }
  out.bigScriptLen = best.length;

  var RE = /\\{\\s*"attrName"\\s*:\\s*"((?:[^"\\\\]|\\\\.)*)"\\s*,\\s*"attrValue"\\s*:\\s*"((?:[^"\\\\]|\\\\.)*)"\\s*\\}/g;
  var m, n2=0;
  while ((m = RE.exec(best)) !== null && n2 < 200) {
    var name = m[1].replace(/\\\\u002[68]/g,'|').replace(/\\\\u002F/g,'/').replace(/\\\\"/g,'"').trim();
    var val  = m[2].replace(/\\\\u002[68]/g,'|').replace(/\\\\u002F/g,'/').replace(/\\\\"/g,'"').trim();
    // 只留 ASCII 属性名（中文那份是行业属性，不要）
    if (!name || !/^[\\x20-\\x7E]+$/.test(name)) continue;
    if (!val) continue;
    if (!(name in out.attrs)) out.attrs[name] = val;
    n2++;
  }
  return out;
})()`;

/** 详情 iframe：按文档顺序取全分辨率长图 */
const DESC_EXPR = `(function(){
  var out=[]; var seen=Object.create(null);
  var ATTRS=['src','data-src','data-lazy-src','data-original','data-image','data-ks-lazyload'];
  var imgs=document.querySelectorAll('img');
  for(var i=0;i<imgs.length;i++){
    var im=imgs[i], s='';
    for(var a=0;a<ATTRS.length;a++){
      var v=(im.getAttribute(ATTRS[a])||'').trim();
      if(v && !/^data:|^blob:/.test(v)){ s=v; break; }
    }
    if(!s) s=im.currentSrc||im.src||'';
    if(!/alicdn\\.com/.test(s)) continue;
    var full=s.replace(/\\.(jpg|jpeg|png|webp)_\\d+x\\d+[^.]*\\.?(jpg|jpeg|png|webp)?$/i,'.$1');
    if(seen[full]) continue; seen[full]=1;
    var r=im.getBoundingClientRect();
    out.push({url:full, w:im.naturalWidth||0, h:im.naturalHeight||0, y:Math.round(r.top+window.scrollY)});
  }
  out.sort(function(a,b){return a.y-b.y;});
  return {url:location.href, docHeight:document.documentElement.scrollHeight, count:out.length, images:out};
})()`;

async function main() {
  const links = fs.readFileSync(LINKS_FILE, 'utf8').split('\n')
    .map(s => s.trim()).filter(s => s && s.startsWith('http'));
  if (!links.length) { console.error('✗ 没有链接'); process.exit(1); }

  const target = await findPage();
  if (!target) {
    console.error('✗ 9333 上没 Edge。先跑：node scripts/collect_alibaba_cdp.js');
    process.exit(1);
  }
  const { sock, send } = await connect(target.webSocketDebuggerUrl);
  await send('Page.enable');
  await send('Runtime.enable');
  fs.mkdirSync(OUT_DIR, { recursive: true });

  let ok = 0, bad = [];
  for (let i = 0; i < links.length; i++) {
    const url = links[i];
    const pid = (url.match(/_(\d{10,})\.html/) || [])[1];
    if (!pid) { bad.push(url + ' (无 productId)'); continue; }
    console.log('\n[' + (i + 1) + '/' + links.length + '] ' + pid);

    // ── 主文档 ──
    await send('Page.navigate', { url });
    await sleep(6000);
    for (let s = 0; s < 10; s++) {
      await send('Runtime.evaluate', { expression: 'window.scrollBy(0, window.innerHeight)', returnByValue: true });
      await sleep(450);
    }
    await send('Runtime.evaluate', { expression: 'window.scrollTo(0,0)', returnByValue: true });
    await sleep(1500);

    const rm = await send('Runtime.evaluate', { expression: MAIN_EXPR, returnByValue: true });
    const main = (rm.result && rm.result.result) ? rm.result.result.value : null;
    if (!main) { bad.push(url + ' (主文档失败)'); continue; }

    const seenG = Object.create(null), gallery = [];
    main.gallery.forEach(u => {
      const f = u.replace(/^https?:?\/\//, 'https://').replace(/^\/\//, 'https://');
      const key = f.replace(/^https?:\/\/[^/]+/, '');
      if (seenG[key]) return;
      seenG[key] = 1;
      gallery.push(f);
    });

    // ── 详情 iframe ──
    const descUrl = 'https://www.alibaba.com/product-detail/description/descIframe.html?productId=' + pid;
    await send('Runtime.evaluate', { expression: 'location.href=' + JSON.stringify(descUrl), returnByValue: true });
    await sleep(5000);
    for (let s = 0; s < 40; s++) {
      await send('Runtime.evaluate', { expression: 'window.scrollBy(0, window.innerHeight*0.9)', returnByValue: true });
      await sleep(320);
    }
    await send('Runtime.evaluate', { expression: 'window.scrollTo(0,0)', returnByValue: true });
    await sleep(1200);

    const rd = await send('Runtime.evaluate', { expression: DESC_EXPR, returnByValue: true });
    const desc = (rd.result && rd.result.result) ? rd.result.result.value : null;
    const detail = (desc && desc.images) || [];

    const attrNames = Object.keys(main.attrs);
    const rec = {
      productId: pid,
      sourceUrl: url,
      descIframeUrl: descUrl,
      capturedAt: new Date().toISOString(),
      h1: main.h1,
      title: main.title,
      jsonldName: main.jsonldName || '',
      jsonldBrand: main.jsonldBrand || '',
      bigScriptLen: main.bigScriptLen,
      attrs: main.attrs,
      gallery: gallery,
      detail: detail.map(d => d.url),
      detailMeta: detail,
      docHeight: desc ? desc.docHeight : 0,
    };
    fs.writeFileSync(path.join(OUT_DIR, pid + '.json'), JSON.stringify(rec, null, 2), 'utf8');

    console.log('   h1       : ' + (main.h1 || '(无)').slice(0, 70));
    console.log('   主图     : ' + gallery.length + ' 张');
    console.log('   详情     : ' + detail.length + ' 张（' + rec.docHeight + 'px）');
    console.log('   英文属性 : ' + attrNames.length + ' 条');
    ['Model', 'Suction Power', 'Power (W)', 'Navigation', 'Runtime', 'Dustbin Capacity', 'Battery Capacity']
      .filter(k => main.attrs[k])
      .forEach(k => console.log('       ' + k + ' = ' + main.attrs[k]));

    if (!gallery.length || !detail.length) bad.push(url + ' (主图/详情有空缺)');
    else ok++;

    await sleep(1200);
  }

  sock.close();
  console.log('\n完成：' + ok + ' / ' + links.length);
  if (bad.length) { console.log('有问题的：'); bad.forEach(b => console.log('   ' + b)); }
  console.log('结果目录：' + OUT_DIR);
}

main().catch(e => { console.error(e); process.exit(1); });
