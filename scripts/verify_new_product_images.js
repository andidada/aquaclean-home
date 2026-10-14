#!/usr/bin/env node
/**
 * verify_new_product_images.js — 真实浏览器验证新换上的产品图
 *
 * 静态扫描（文件在不在、0 不 0 字节）只能证明"文件存在"，证明不了
 * "浏览器真的把这张图解码出来了"。这里用真实 Edge 打开页面，滚到底触发
 * 懒加载，然后数有多少张 <img> 的 naturalWidth 是 0（= 没解码出来）。
 *
 * 为什么不用 headless + --virtual-time-budget：那会在预算到点时掐断尚未完成的
 * 网络请求，把"其实没问题"误判成"加载失败"。这里用真实窗口 + 显式等待。
 *
 * 用法
 * ----
 *   1) 先在仓库根目录起静态服务：python -m http.server 8899 --bind 127.0.0.1
 *   2) node scripts/verify_new_product_images.js
 */
/**
 * 校验什么
 * --------
 * product-detail.js 的 render() 会整体重写 #aqc-detail-mount，所以静态 HTML 里的
 * <section id="detail-images"> 在 JS 正常执行时根本不存在（只有爬虫和禁用 JS 的
 * 访客看得到）。真正生效的是运行时渲染出来的：
 *
 *   #aqc-detail-block      详情长图区（数据来源 product.detail_images）
 *   .d-gallery / 主图区     数据来源 product.images
 *
 * 所以判据是「#aqc-detail-block 存在 + 里面每张图都解码出来 + 主图都解码出来」，
 * 而不是去数静态 HTML 的 #detail-images。
 *
 * 🔴 还有一个把"数据明明对"误判成"字段没写进去"的坑：缓存。
 * python -m http.server 不发 Cache-Control，浏览器会套启发式缓存，把
 * data/products/*.json 留在内存缓存里。改完 JSON 重跑本脚本时，页面拿到的还是
 * 上一轮的旧版本，于是 detail_images 明明写进去了，脚本却报"详情节缺失"。
 * 表现为 63 页全红 + 服务端 curl 看 JSON 是好的，两边对不上。
 * 对策：Network.setCacheDisabled + URL 带时间戳。
 */
const PORT = 9333;
const BASE = 'http://127.0.0.1:8899';
const sleep = ms => new Promise(r => setTimeout(r, ms));

const PRODUCTS = [
  ['handheld-vacuum', 'gv22'], ['handheld-vacuum', 'v26'], ['handheld-vacuum', 'gv18'],
  ['robot-vacuum', 'v2g-sj'], ['robot-vacuum', 't20-c800'], ['robot-vacuum', 'v9'],
  ['car-vacuum', 'yzx-309'],
  ['handheld-vacuum', 'eg16pro'],   // 新建产品：EG16Pro洗地机
  // ── 第二批（2026-10-14）：这 3 个原先 detail_images 是空的 ──────────
  ['tire-inflator', 'ymc6667'],
  ['steam-cleaner', 'ytc-sc-004'],
  ['robot-vacuum', 'pt40c800'],
];
const LANGS = ['en', 'zh', 'ar', 'es', 'fr', 'id', 'ru', 'th', 'vi'];
const runStamp = Date.now().toString(36);

async function findPage() {
  const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
  return list.find(t => t.type === 'page' && t.webSocketDebuggerUrl) || null;
}
async function connect(wsUrl) {
  const sock = new WebSocket(wsUrl);
  let id = 0; const pending = new Map();
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

const CHECK = `(function(){
  // 只数本产品自己的两个区域：.d-gallery 是主图区，#aqc-detail-block 是详情长图区。
  // 不要图省事去数整个 #aqc-detail-mount —— 里面还混着"同类目其它产品"卡片
  // 的缩略图，会把别人的破图算到本产品头上，也会把别人的图算成本产品的主图。
  //
  // 🔴 判定"破图"必须同时满足 complete && !naturalWidth。
  // 只看 naturalWidth===0 会把"还在下载中"误判成"图坏了"：详情长图全是
  // loading="lazy"，滚到底才触发，十几张 100KB+ 的 webp 串行解码要好几秒。
  // 固定 sleep 等一下就采样，得到的必然是一大批假破图 —— 63 页全红，
  // 而 PIL 逐个打开文件全是好的。pending 单独返回，由外层轮询到它归零为止。
  function scan(sel) {
    var n = 0, pending = 0, broken = [];
    var els = document.querySelectorAll(sel);
    for (var i = 0; i < els.length; i++) {
      var el = els[i];
      n++;
      if (el.complete) {
        if (!el.naturalWidth) broken.push(el.getAttribute('src'));
      } else {
        pending++;
      }
    }
    return { n: n, pending: pending, broken: broken };
  }
  var g = scan('.d-gallery img');
  var d = scan('#aqc-detail-block img');
  return {
    gallery: g.n, galleryBroken: g.broken.slice(0, 6),
    detail: d.n, detailBroken: d.broken.slice(0, 6),
    pending: g.pending + d.pending,
    brokenCount: g.broken.length + d.broken.length,
    hasDetailBlock: !!document.getElementById('aqc-detail-block'),
    title: document.title || ''
  };
})()`;

async function main() {
  const target = await findPage();
  if (!target) { console.error('✗ 9333 上没有 Edge'); process.exit(1); }
  const { sock, send } = await connect(target.webSocketDebuggerUrl);
  await send('Page.enable'); await send('Runtime.enable');
  // 🔴 关缓存。python -m http.server 不发 Cache-Control，浏览器会套启发式缓存把
  // data/products/*.json 留在内存缓存里。结果是：改了 JSON 之后重跑本脚本，
  // 页面拿到的还是上一轮那个版本，于是"明明字段已经写进去了，脚本却报字段缺失"。
  // 这个坑表现为数据明明对、验证却全红，非常容易误判成改动没生效。
  await send('Network.enable');
  await send('Network.setCacheDisabled', { cacheDisabled: true });

  let pass = 0, fail = 0;
  const failures = [];

  // 冒烟用：node scripts/verify_new_product_images.js en/handheld-vacuum-v26
  //     node scripts/verify_new_product_images.js handheld-vacuum-v26
  // 只跑指定页，改判据时先花几秒验一条，别每次都等满 6 分钟。
  const onlyArg = (process.argv[2] || '').trim();
  const prodList = onlyArg && onlyArg !== 'all'
    ? PRODUCTS.filter(([c, p]) => onlyArg === `${c}-${p}`)
    : PRODUCTS;
  const langList = LANGS;
  if (onlyArg && !prodList.length) { console.error('✗ 没有匹配的产品：' + onlyArg); process.exit(1); }

  for (const [cat, pid] of prodList) {
    for (const lang of langList) {
      // URL 上带时间戳，双保险地把内存缓存也绕开
      const url = `${BASE}/${lang}/${cat}-${pid}.html?_=${runStamp}_${lang}`;
      await send('Page.navigate', { url });
      await sleep(900);

      // 🔴🔴 最关键的一步，别删。
      // CDP 驱动的那个 Edge 窗口不是前台窗口，document.visibilityState 是
      // "hidden"。**Chrome 在隐藏标签页里完全不加载 loading="lazy" 的图片** ——
      // 不管你怎么滚、滚多久，11 张详情长图永远停在 complete=false。
      // 实测：滚动到文档底部后 11/11 未加载；把 loading 改成 eager 并重设 src
      // 之后 0.7 秒全部加载完成。
      // 所以"滚到底触发懒加载"这个常见套路在这里根本不成立，必须显式 kick。
      await send('Runtime.evaluate', {
        returnByValue: true,
        expression: `(function(){
          var sel = '.d-gallery img, #aqc-detail-block img';
          var els = [].slice.call(document.querySelectorAll(sel));
          var kicked = 0;
          els.forEach(function (im) {
            if (im.complete) return;
            im.loading = 'eager';
            var s = im.getAttribute('src');
            if (s) { im.src = s; kicked++; }   // 重设 src 才会真的发起加载
          });
          return kicked;
        })()`,
      });

      // 轮询到「没有图片还处于加载中」或超时为止。固定 sleep 采样必然误判。
      let v = null;
      for (let tries = 0; tries < 30; tries++) {
        const r = await send('Runtime.evaluate', { expression: CHECK, returnByValue: true });
        v = (r.result && r.result.result) ? r.result.result.value : null;
        if (v && v.pending === 0) break;
        await sleep(700);
      }
      if (!v) { fail++; failures.push(`${lang}/${cat}-${pid}: 取不到结果`); continue; }
      if (v.pending > 0) {
        // kick 之后还有图不落地：既没解码也没报错，这才是真问题
        failures.push(`${lang}/${cat}-${pid}: 超时仍有 ${v.pending} 张未完成加载`);
      }

      const ok = v.brokenCount === 0 && v.hasDetailBlock && v.detail > 0 && v.gallery > 0;
      if (ok) {
        pass++;
        console.log(`  ✓ ${lang} ${cat}-${pid}  主图 ${v.gallery} · 长图 ${v.detail} · 全部解码`);
      } else {
        fail++;
        const msg = `${lang}/${cat}-${pid}: 破图 ${v.brokenCount} 张 / 详情节 ${v.hasDetailBlock ? v.detail + '张' : '缺失'} / 主图 ${v.gallery}`;
        failures.push(msg);
        console.log(`  ✗ ${msg}`);
        v.galleryBroken.concat(v.detailBroken).forEach(b => console.log('       ' + b));
      }
    }
  }
  sock.close();
  console.log(`\n结果：${pass} 通过 / ${fail} 失败（共 ${pass + fail} 页）`);
  if (failures.length) { console.log('失败清单：'); failures.forEach(f => console.log('   ' + f)); }
  process.exit(fail ? 1 : 0);
}

main().catch(e => { console.error(e); process.exit(1); });
