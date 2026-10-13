#!/usr/bin/env node
/**
 * collect_alibaba_v2.js — 阿里详情页正式采集器（主图 + 详情长图 + 属性）
 *
 * 为什么有 v2
 * -----------
 * v1 用「CSS 宽度 + 页面位置」猜哪些图是产品的，结果全废：
 * 页面里 172px 的推荐位缩略图有 71 张，而真正的详情长图压根没渲染在主文档里，
 * 于是分类出来「主图 224 张、详情 0 张」。
 *
 * v2 不再猜，走两条**页面自己暴露的权威数据**：
 *
 *   1. 主图（gallery）
 *      页面里的 <script type="application/ld+json"> 有且仅有一个 Product 块，
 *      里面的 image 数组就是商品主图（会重复一遍，去重即可）。
 *
 *   2. 详情长图（detail）
 *      长图不在主文档，而在独立 iframe 里：
 *        https://www.alibaba.com/product-detail/description/descIframe.html?productId=<id>
 *      直接导航过去，滚动触发懒加载，按文档顺序取 img —— 拿到的是原图尺寸
 *      （实测 2048x2048 / 1920x1208），不是压缩过的缩略图。
 *
 * 前置：需要有一个开着调试端口 9333 的 Edge（先跑 collect_alibaba_cdp.js 拉起来）。
 *
 * 用法
 * ----
 *   node scripts/collect_alibaba_v2.js
 *   node scripts/collect_alibaba_v2.js scraped/alibaba_links.txt
 */
const fs = require('fs');
const path = require('path');

const PORT = 9333;
const OUT_DIR = path.join(process.cwd(), 'scraped', 'alibaba_v2');
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

/** 主文档：h1 + JSON-LD 主图 + 属性表（多种结构兜底） */
const MAIN_EXPR = `(function(){
  function txt(el){ return (el && (el.innerText||el.textContent)||'').replace(/\\s+/g,' ').trim(); }
  var out = {h1:txt(document.querySelector('h1')), title:document.title||'', gallery:[], specs:[]};

  // ── 主图：JSON-LD Product.image ──
  var lds = document.querySelectorAll('script[type="application/ld+json"]');
  for (var i=0;i<lds.length;i++){
    var raw = (lds[i].textContent||'').trim();
    var o = null; try { o = JSON.parse(raw); } catch(e){ continue; }
    var nodes = Array.isArray(o) ? o : [o];
    for (var n=0;n<nodes.length;n++){
      if (!nodes[n] || nodes[n]['@type'] !== 'Product') continue;
      var im = nodes[n].image;
      var arr = Array.isArray(im) ? im : (im ? [im] : []);
      for (var k=0;k<arr.length;k++){
        var u = typeof arr[k]==='string' ? arr[k] : (arr[k] && arr[k].url) || '';
        if (u) out.gallery.push(u);
      }
      // 顺手把 JSON-LD 里的其它字段也带上，方便核对
      out.jsonldName    = nodes[n].name || '';
      out.jsonldSku     = nodes[n].sku || '';
      out.jsonldBrand   = (nodes[n].brand && nodes[n].brand.name) || '';
      var add = nodes[n].additionalProperty;
      if (Array.isArray(add)) {
        for (var a=0;a<add.length;a++){
          if (add[a] && add[a].name && add[a].value)
            out.specs.push({label:String(add[a].name), value:String(add[a].value)});
        }
      }
    }
  }

  // ── 属性表 ──
  // 站上已有的属性名是英文，而页面按浏览器语言渲染成中文，所以这里
  // 直接抓「左标签 / 右值」的成对结构，不认具体措辞。
  function pairsFromRows(root){
    var rows = root.querySelectorAll('tr');
    for (var r=0;r<rows.length;r++){
      var cs = rows[r].querySelectorAll('th,td');
      if (cs.length===2){ var a=txt(cs[0]), b=txt(cs[1]); if(a&&b&&a.length<40&&b.length<200) out.specs.push({label:a,value:b}); }
    }
    var dts = root.querySelectorAll('dt');
    for (var d=0;d<dts.length;d++){
      var la=txt(dts[d]), va=txt(dts[d].nextElementSibling);
      if(la&&va&&la.length<40&&va.length<200) out.specs.push({label:la,value:va});
    }
  }
  pairsFromRows(document);

  // 阿里属性区是 div 拼的：连续两个小文本块 = 一组。用「行内相邻块」兜底。
  var seenPair = Object.create(null);
  var cells = document.querySelectorAll('div,span,li');
  for (var c=0;c<cells.length && out.specs.length<80; c++){
    var el = cells[c];
    if (el.children.length) continue;
    var t = txt(el);
    if (!t || t.length>40) continue;
    var nx = el.nextElementSibling;
    if (!nx || nx.children.length) continue;
    var v = txt(nx);
    if (!v || v.length>200 || v===t) continue;
    var key = t+'\\u0000'+v;
    if (seenPair[key]) continue;
    seenPair[key]=1;
    out.specs.push({label:t, value:v});
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
    // 去掉 _600x600 之类的缩略图后缀，拿原图
    var full=s.replace(/\\.(jpg|jpeg|png|webp)_\\d+x\\d+[^.]*\\.?(jpg|jpeg|png|webp)?$/i,'.$1');
    if(seen[full]) continue; seen[full]=1;
    var r=im.getBoundingClientRect();
    out.push({url:full, w:im.naturalWidth||0, h:im.naturalHeight||0, y:Math.round(r.top+window.scrollY)});
  }
  out.sort(function(a,b){return a.y-b.y;});
  return {url:location.href, docHeight:document.documentElement.scrollHeight,
          bodyLen:(document.body.innerText||'').length, count:out.length, images:out};
})()`;

async function main() {
  let links = fs.readFileSync(LINKS_FILE, 'utf8').split('\n')
    .map(s => s.trim()).filter(s => s && s.startsWith('http'));
  if (!links.length) { console.error('✗ 没有链接'); process.exit(1); }

  const target = await findPage();
  if (!target) {
    console.error('✗ 9333 端口上没有 Edge。先跑：node scripts/collect_alibaba_cdp.js');
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
    if (!pid) { bad.push(url + ' (取不到 productId)'); continue; }
    console.log('\n[' + (i + 1) + '/' + links.length + '] ' + pid);

    // ── 主文档 ──
    await send('Page.navigate', { url });
    await sleep(5000);
    for (let s = 0; s < 6; s++) {
      await send('Runtime.evaluate', { expression: 'window.scrollBy(0, window.innerHeight)', returnByValue: true });
      await sleep(500);
    }
    await send('Runtime.evaluate', { expression: 'window.scrollTo(0,0)', returnByValue: true });
    await sleep(1000);

    const rm = await send('Runtime.evaluate', { expression: MAIN_EXPR, returnByValue: true });
    const main = (rm.result && rm.result.result) ? rm.result.result.value : null;
    if (!main) { bad.push(url + ' (主文档采集失败)'); continue; }

    // 主图去重（JSON-LD 会把同一组图写两遍）
    const seenG = Object.create(null);
    const gallery = [];
    main.gallery.forEach(u => {
      const f = u.replace(/^https?:?/, '').replace(/^\/\//, 'https://');
      const key = f.replace(/^https?:\/\/[^/]+/, '');
      if (seenG[key]) return;
      seenG[key] = 1;
      gallery.push(f);
    });

    // 属性去重
    const seenS = Object.create(null);
    const specs = [];
    main.specs.forEach(s => {
      const key = s.label + '\u0000' + s.value;
      if (seenS[key]) return;
      seenS[key] = 1;
      specs.push(s);
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

    const rec = {
      productId: pid,
      sourceUrl: url,
      descIframeUrl: descUrl,
      capturedAt: new Date().toISOString(),
      h1: main.h1,
      title: main.title,
      jsonldName: main.jsonldName || '',
      jsonldSku: main.jsonldSku || '',
      jsonldBrand: main.jsonldBrand || '',
      gallery: gallery,
      detail: detail.map(d => d.url),
      detailMeta: detail,
      specs: specs,
      docHeight: desc ? desc.docHeight : 0,
    };
    fs.writeFileSync(path.join(OUT_DIR, pid + '.json'), JSON.stringify(rec, null, 2), 'utf8');

    console.log('   h1     : ' + (main.h1 || '(无)').slice(0, 78));
    console.log('   主图   : ' + gallery.length + ' 张');
    console.log('   详情   : ' + detail.length + ' 张（iframe 高 ' + rec.docHeight + 'px）');
    console.log('   属性   : ' + specs.length + ' 条');
    if (!gallery.length || !detail.length) bad.push(url + ' (主图/详情有空缺)');
    else ok++;

    await sleep(1200);
  }

  sock.close();
  console.log('\n完成：' + ok + ' / ' + links.length + ' 完整');
  if (bad.length) { console.log('有问题的：'); bad.forEach(b => console.log('   ' + b)); }
  console.log('结果目录：' + OUT_DIR);
}

main().catch(e => { console.error(e); process.exit(1); });
