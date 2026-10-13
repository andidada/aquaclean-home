#!/usr/bin/env node
/**
 * collect_alibaba_cdp.js — 借你已登录的 Edge 批量采集阿里国际站详情页
 *
 * 为什么必须这么做
 * ----------------
 * 阿里国际站对未登录请求返回登录墙：实测 HTTP 200 但正文只有 3.5KB，
 * 内容是跳 login.alibaba.com 的脚本。纯 HTTP 抓取拿不到任何产品信息，
 * 只能用**浏览器里已有的登录态**。
 *
 * 这个脚本是「可断点续跑」的，不用在终端按回车：
 *
 *   1) 第一次跑：脚本拉起 Edge（沿用你的用户目录），打开第一个链接。
 *      如果检测到登录墙 → 打印提示、**把浏览器留着不关**，退出码 2。
 *   2) 你在那个 Edge 窗口里登录阿里国际站，直到能正常看到产品页。
 *   3) 再跑一次同样的命令：脚本发现 9333 端口已经在，直接接管采集，
 *      9 个链接全采完，结果落在 scraped/alibaba/*.json。
 *
 * 用法
 * ----
 *   node scripts/collect_alibaba_cdp.js                 # 用 scraped/alibaba_links.txt
 *   node scripts/collect_alibaba_cdp.js <链接文件>       # 自定义
 *   node scripts/collect_alibaba_cdp.js --close         # 采完顺手关掉 Edge
 *
 * 退出码
 * ------
 *   0  全部采集完成
 *   2  需要你先在浏览器里登录（浏览器已留着，登录完重跑本命令）
 *   1  其他错误
 */
const { spawn, execSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const os = require('os');

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const PROFILE = path.join(os.homedir(), 'AppData/Local/Microsoft/Edge/User Data');
const FALLBACK_PROFILE = path.join(process.cwd(), '.cache', 'edge-scrape-profile');
const OUT_DIR = path.join(process.cwd(), 'scraped', 'alibaba');
const PORT = 9333;

const argv = process.argv.slice(2);
const WANT_CLOSE = argv.includes('--close');
// --own-profile：强制用你自己的 Edge 用户目录（登录态直接复用，但必须先完全退出 Edge）
// 默认：Edge 正在跑就用独立目录，不打断你的窗口（代价：新窗口要重新登录一次阿里）
const WANT_OWN = argv.includes('--own-profile');
const LINKS_FILE = argv.filter(a => !a.startsWith('--'))[0] ||
  path.join(process.cwd(), 'scraped', 'alibaba_links.txt');

const sleep = ms => new Promise(r => setTimeout(r, ms));
function die(msg, code) { console.error('\n✗ ' + msg); process.exit(code === undefined ? 1 : code); }

/** 页面里执行的采集逻辑：不依赖阿里的 CSS 类名（构建期哈希会变） */
function collectExpr() {
  return `(function(){
    function txt(el){ return (el && (el.innerText||el.textContent) || '').replace(/\\s+/g,' ').trim(); }
    var IMG_ATTRS=['src','data-src','data-lazy-src','data-original','data-image'];
    var seen=Object.create(null), all=[];
    function pickSrc(img){
      var best='';
      for(var i=0;i<IMG_ATTRS.length;i++){
        var v=(img.getAttribute(IMG_ATTRS[i])||'').trim();
        if(!v) continue;
        if(/^data:|^blob:/.test(v)) continue;
        if(/\\.(gif|svg)$/i.test(v)) continue;
        if(/alicdn\\.com/i.test(v)) return v;
        if(!best) best=v;
      }
      return best;
    }
    var imgs=document.querySelectorAll('img');
    for(var k=0;k<imgs.length;k++){
      var img=imgs[k], src=pickSrc(img);
      if(!src) continue;
      var canonical=src.replace(/\\.(jpg|jpeg|png|webp)_\\d+x\\d+[^.]*\\.?(jpg|jpeg|png|webp)?$/i,'.$1');
      if(seen[canonical]) continue;
      seen[canonical]=1;
      var r=img.getBoundingClientRect();
      all.push({src:src, full:canonical,
        w:img.naturalWidth||Math.round(r.width), h:img.naturalHeight||Math.round(r.height),
        cssW:Math.round(r.width), y:Math.round(r.top+window.scrollY),
        alt:(img.alt||'').trim().slice(0,200)});
    }
    all.sort(function(a,b){return a.y-b.y;});

    var maxW=0;
    for(var i=0;i<all.length;i++) if(all[i].cssW>maxW) maxW=all[i].cssW;
    var wide=Math.max(600, maxW*0.7);
    var firstWide=Infinity;
    for(var i2=0;i2<all.length;i2++) if(all[i2].cssW>=wide) firstWide=Math.min(firstWide, all[i2].y);

    var gallery=[], detail=[], others=[];
    all.forEach(function(it){
      if(firstWide!==Infinity && it.y>=firstWide-200 && it.cssW>=wide*0.8) detail.push(it.full);
      else if(it.y < (firstWide===Infinity?1e9:firstWide)) gallery.push(it.full);
      else others.push(it.full);
    });

    var specs=[];
    var tables=document.querySelectorAll('table');
    for(var t=0;t<tables.length;t++){
      var rows=tables[t].querySelectorAll('tr');
      for(var rr=0;rr<rows.length;rr++){
        var cs=rows[rr].querySelectorAll('th,td');
        if(cs.length===2){var a=txt(cs[0]),b=txt(cs[1]); if(a&&b&&a.length<60) specs.push({label:a,value:b});}
      }
    }
    var dls=document.querySelectorAll('dl');
    for(var d=0;d<dls.length;d++){
      var dts=dls[d].querySelectorAll('dt');
      for(var j=0;j<dts.length;j++){
        var la=txt(dts[j]), va=txt(dts[j].nextElementSibling);
        if(la&&va&&la.length<60) specs.push({label:la,value:va});
      }
    }

    return {
      url: location.href,
      capturedAt: new Date().toISOString(),
      title: document.title||'',
      h1: txt(document.querySelector('h1')),
      specs: specs,
      images:{gallery:gallery, detail:detail, others:others},
      allImages: all,
      bodyText: (document.body.innerText||'').replace(/\\s+/g,' ').trim().slice(0, 8000)
    };
  })()`;
}

/** 判断是否登录墙。真产品页正文很长、且有若干 alicdn 大图 */
function wallProbeExpr() {
  return `(function(){
    var t=(document.body.innerText||'').replace(/\\s+/g,' ').trim();
    var alicdn=0, big=0;
    var imgs=document.querySelectorAll('img');
    for(var i=0;i<imgs.length;i++){
      var s=imgs[i].currentSrc||imgs[i].src||'';
      if(!/alicdn\\.com/i.test(s)) continue;
      alicdn++;
      var r=imgs[i].getBoundingClientRect();
      if(r.width>=180) big++;
    }
    return {href:location.href, textLen:t.length, alicdn:alicdn, big:big, title:document.title||''};
  })()`;
}

async function findPage(port, tries) {
  for (let i = 0; i < (tries || 1); i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const pg = list.find(t => t.type === 'page' && t.webSocketDebuggerUrl);
      if (pg) return pg;
    } catch (e) { /* 还没起来 */ }
    if (i + 1 < (tries || 1)) await sleep(500);
  }
  return null;
}

function edgeRunning() {
  // 别用 tasklist /FI：Git Bash 会把 /FI 当路径转写掉（MSYS 路径转换），
  // 直接列全部进程再在 JS 里过滤最稳。
  try {
    const out = execSync('tasklist', { encoding: 'utf8', windowsHide: true });
    return out.split('\n').filter(l => /^msedge\.exe/i.test(l.trim())).length > 0;
  } catch (e) { return false; }
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

async function main() {
  if (!fs.existsSync(EDGE)) die('找不到 Edge：' + EDGE);

  let links = [];
  if (fs.existsSync(LINKS_FILE)) {
    links = fs.readFileSync(LINKS_FILE, 'utf8').split('\n')
      .map(s => s.trim()).filter(s => s && s.startsWith('http'));
  }
  if (!links.length) die('没有读到链接。请确认 ' + LINKS_FILE + ' 里每行一个 http(s) 链接。');
  console.log('待采集 ' + links.length + ' 个链接。');

  // ── 先看看 9333 是否已经在（第二次跑就是这个分支） ────────────
  let target = await findPage(PORT, 1);
  let launched = null;

  if (target) {
    console.log('✓ 检测到已开着的调试 Edge，直接接管（不再新起进程）。');
  } else {
    // ── 选用户目录 ────────────────────────────────────────────
    let profileDir;
    if (WANT_OWN) {
      if (edgeRunning()) {
        die('你要求用 --own-profile，但 Edge 正在运行。\n' +
            '请先**完全退出 Edge**（含后台进程，托盘里也退出），再重跑；\n' +
            '或者去掉 --own-profile，改用独立窗口（会在新窗口里重新登录一次）。', 1);
      }
      profileDir = PROFILE;
      console.log('\n用你的 Edge 用户目录启动（登录态应该还在）...');
    } else if (edgeRunning()) {
      profileDir = FALLBACK_PROFILE;
      console.log('\n检测到你的 Edge 正在运行 —— 为了不打断你，改用**独立用户目录**。');
      console.log('代价：这个新窗口里需要重新登录一次阿里国际站（只需一次）。');
      console.log('（若想直接复用登录态，请先完全退出 Edge 后加 --own-profile 重跑）');
    } else {
      profileDir = PROFILE;
      console.log('\nEdge 没在跑，直接用你的用户目录启动（登录态大概率还在）...');
    }

    const launchEdge = (dir) => spawn(EDGE, [
      '--remote-debugging-port=' + PORT,
      '--user-data-dir=' + dir,
      '--no-first-run', '--no-default-browser-check',
      '--no-proxy-server',
      '--window-size=1440,1000',
      links[0],
    ], { stdio: 'ignore' });

    fs.mkdirSync(profileDir, { recursive: true });
    launched = launchEdge(profileDir);
    target = await findPage(PORT, 60);

    if (!target && profileDir === PROFILE) {
      // 新版 Chromium 有时会拒绝给默认 profile 开调试端口 → 退到独立目录
      console.log('   默认用户目录起不来调试端口，退到独立目录（需要重新登录一次）...');
      try { launched.kill(); } catch (e) {}
      await sleep(2000);
      profileDir = FALLBACK_PROFILE;
      fs.mkdirSync(profileDir, { recursive: true });
      launched = launchEdge(profileDir);
      target = await findPage(PORT, 60);
    }

    if (!target) die('连不上 Edge 的调试端口（两种用户目录都试过了）。', 1);
    console.log('✓ Edge 已启动，调试端口 ' + PORT + '，用户目录：' + profileDir);
  }

  const { sock, send } = await connect(target.webSocketDebuggerUrl);
  await send('Page.enable');
  await send('Runtime.enable');

  // ── 打开第一个链接，等它加载完，判断是否登录墙 ────────────────
  await send('Page.navigate', { url: links[0] });
  let probe = null;
  for (let i = 0; i < 30; i++) {
    await sleep(1500);
    const r = await send('Runtime.evaluate', { expression: wallProbeExpr(), returnByValue: true });
    const v = (r.result && r.result.result) ? r.result.result.value : null;
    if (v) { probe = v; if (v.textLen > 1500 && v.big >= 3) break; }
  }

  if (!probe) die('页面探测失败。', 1);
  console.log('\n首页探测：' + JSON.stringify(probe));

  const isWall = probe.textLen < 1500 || probe.big < 3 || /login\.alibaba|login\.alibaba\.com/i.test(probe.href);
  if (isWall) {
    sock.close();
    console.log('\n' + '='.repeat(64));
    console.log('⚠️  当前是登录墙 —— 需要你手动登录一次（只需要这一次）');
    console.log('='.repeat(64));
    console.log('1. 看那个刚打开的 Edge 窗口，在阿里国际站登录（扫码 / 短信 / 账号密码都行）；');
    console.log('2. 一直点到能正常看到产品详情页：有产品大图、有参数表；');
    console.log('3. **不要关那个 Edge 窗口**（关了登录态进程就没了）；');
    console.log('4. 回到终端，再跑一次：');
    console.log('     node scripts/collect_alibaba_cdp.js');
    console.log('   脚本会接管这个已登录的浏览器，把 9 个链接全部采集完。');
    console.log('='.repeat(64) + '\n');
    process.exit(2);
  }

  console.log('✓ 登录态正常，开始采集。\n');
  fs.mkdirSync(OUT_DIR, { recursive: true });

  let ok = 0, failed = [];
  for (let i = 0; i < links.length; i++) {
    const url = links[i];
    process.stdout.write('[' + (i + 1) + '/' + links.length + '] ' + url.slice(0, 84) + '\n');

    await send('Page.navigate', { url });
    await sleep(4000);

    // 慢慢滚到底，触发懒加载，否则详情长图拿不到
    for (let s = 0; s < 16; s++) {
      await send('Runtime.evaluate', {
        expression: 'window.scrollBy(0, window.innerHeight*0.85)', returnByValue: true
      });
      await sleep(700);
    }
    await send('Runtime.evaluate', { expression: 'window.scrollTo(0,0)', returnByValue: true });
    await sleep(1500);

    const r = await send('Runtime.evaluate', { expression: collectExpr(), returnByValue: true });
    const data = (r.result && r.result.result) ? r.result.result.value : null;
    if (!data) { failed.push(url); console.log('   ✗ 采集失败（没拿到返回值）'); continue; }

    const total = data.images.gallery.length + data.images.detail.length + data.images.others.length;
    const slug = (url.match(/_(\d{10,})\.html/) || [])[1] || ('p' + (i + 1));
    const outFile = path.join(OUT_DIR, slug + '.json');
    fs.writeFileSync(outFile, JSON.stringify(data, null, 2), 'utf8');

    console.log('   h1: ' + (data.h1 || '(无)').slice(0, 72));
    console.log('   主图 ' + data.images.gallery.length +
                ' · 详情 ' + data.images.detail.length +
                ' · 其他 ' + data.images.others.length +
                ' · 属性 ' + data.specs.length);
    if (total === 0) {
      console.log('   ⚠️ 一张图都没有，八成是登录掉了');
      failed.push(url);
    } else { ok++; }
    console.log('   → ' + path.relative(process.cwd(), outFile));

    await sleep(1800);   // 别太快，避免触发风控
  }

  sock.close();
  if (WANT_CLOSE && launched) { try { launched.kill(); } catch (e) {} }

  console.log('\n完成：成功 ' + ok + ' / ' + links.length);
  if (failed.length) {
    console.log('失败的链接：');
    failed.forEach(u => console.log('   ' + u));
  }
  console.log('结果目录：' + OUT_DIR);
}

main().catch(e => { console.error(e); process.exit(1); });
