/**
 * collect_alibaba_page.js — 在阿里国际站详情页上采集文案与图片清单
 *
 * 用法（不需要装任何东西）
 * ------------------------
 * 1. 用你**已登录**的浏览器打开某个阿里产品详情页
 *    （必须是能正常看到完整内容的页面，而不是登录墙）
 * 2. 按 F12 打开 DevTools → 切到 Console（控制台）
 * 3. 把本文件**全部内容**粘进去，回车
 * 4. 会自动下载一个 `alibaba-<产品ID>.json`，把它发给我就行
 *
 * 为什么用通用提取而不是 CSS 选择器
 * ----------------------------------
 * 阿里的 DOM 类名是构建时生成的哈希、且随时会变，按类名抓很脆。
 * 所以这里只按**语义**提取：图片的 URL / 尺寸 / 在页面里的纵向位置、
 * 表格式的属性对、按标题切分的文本块。换版面也不容易失效。
 *
 * 采集结果分三类图片，方便和站内现有图对照：
 *   gallery —— 顶部主图轮播（一般 6 张左右）
 *   detail  —— 详情区的长图（阿里叫「产品详情」，通常是整屏宽的图文）
 *   others  —— 其余（推荐位、公司信息等，一般不需要）
 */
(function () {
  'use strict';

  var out = {
    url: location.href,
    capturedAt: new Date().toISOString(),
    title: document.title || '',
    h1: '',
    specs: [],
    sections: [],
    images: { gallery: [], detail: [], others: [] },
    allImages: [],
    _notes: []
  };

  // ── 标题 ──────────────────────────────────────────────────────
  var h1el = document.querySelector('h1');
  if (h1el) out.h1 = (h1el.innerText || '').trim();

  // ── 图片：全部抓下来，带尺寸和纵向位置 ─────────────────────────
  // 阿里的图常放在 data-src / data-lazy-src 里做懒加载，src 可能是占位图，
  // 所以这几个属性都要看，取第一个像真 URL 的。
  var IMG_ATTRS = ['src', 'data-src', 'data-lazy-src', 'data-original', 'data-image'];
  var seen = Object.create(null);

  function pickSrc(img) {
    var best = '';
    for (var i = 0; i < IMG_ATTRS.length; i++) {
      var v = img.getAttribute(IMG_ATTRS[i]) || '';
      v = v.trim();
      if (!v) continue;
      if (/^data:|^blob:/.test(v)) continue;          // 占位图/内嵌图
      if (/\.(gif|svg)$/i.test(v)) continue;           // 图标
      // 优先带 alicdn 域名的大图
      if (/alicdn\.com/i.test(v)) return v;
      if (!best) best = v;
    }
    return best;
  }

  var all = [];
  var imgs = document.querySelectorAll('img');
  for (var k = 0; k < imgs.length; k++) {
    var img = imgs[k];
    var src = pickSrc(img);
    if (!src) continue;
    // 去掉尺寸后缀拿到原图：阿里 URL 常带 .jpg_200x200q90.jpg 之类
    var canonical = src.replace(/\.(jpg|jpeg|png|webp)_\d+x\d+[^.]*\.?(jpg|jpeg|png|webp)?$/i, '.$1');
    if (seen[canonical]) continue;
    seen[canonical] = 1;

    var r = img.getBoundingClientRect();
    all.push({
      src: src,
      full: canonical,
      w: img.naturalWidth || Math.round(r.width),
      h: img.naturalHeight || Math.round(r.height),
      cssW: Math.round(r.width),
      y: Math.round(r.top + window.scrollY),
      alt: (img.alt || '').trim().slice(0, 200)
    });
  }
  // 按页面纵向顺序排，这样和详情页的阅读顺序一致
  all.sort(function (a, b) { return a.y - b.y; });
  out.allImages = all;

  if (!all.length) {
    out._notes.push('页面上没抓到任何 <img>。可能是还没登录、或者详情区是懒加载（先手动把页面滚到底再运行一次）。');
  }

  // ── 分类：顶部主图 vs 详情长图 ─────────────────────────────────
  // 启发式：详情长图在阿里一般是整屏宽（cssW 大）且纵向位置靠下；
  // 主图集中在页面最上方、尺寸中等。用「最大 cssW 的 70%」当分界。
  var maxW = 0;
  for (var i = 0; i < all.length; i++) if (all[i].cssW > maxW) maxW = all[i].cssW;
  var wideThreshold = Math.max(600, maxW * 0.7);

  var firstWideY = Infinity;
  for (var i2 = 0; i2 < all.length; i2++) {
    if (all[i2].cssW >= wideThreshold) { firstWideY = Math.min(firstWideY, all[i2].y); }
  }

  all.forEach(function (it) {
    if (firstWideY !== Infinity && it.y >= firstWideY - 200 && it.cssW >= wideThreshold * 0.8) {
      out.images.detail.push(it.full);
    } else if (it.y < (firstWideY === Infinity ? 1e9 : firstWideY)) {
      out.images.gallery.push(it.full);
    } else {
      out.images.others.push(it.full);
    }
  });

  // ── 属性表：找 label / value 成对的结构 ────────────────────────
  function txt(el) { return (el && (el.innerText || el.textContent) || '').replace(/\s+/g, ' ').trim(); }

  // 1) <table> 里两列的
  var tables = document.querySelectorAll('table');
  for (var t = 0; t < tables.length; t++) {
    var rows = tables[t].querySelectorAll('tr');
    for (var rr = 0; rr < rows.length; rr++) {
      var cells = rows[rr].querySelectorAll('th,td');
      if (cells.length === 2) {
        var a = txt(cells[0]), b = txt(cells[1]);
        if (a && b && a.length < 60) out.specs.push({ label: a, value: b });
      }
    }
  }
  // 2) <dl> / dt+dd
  var dls = document.querySelectorAll('dl');
  for (var d = 0; d < dls.length; d++) {
    var dts = dls[d].querySelectorAll('dt');
    for (var j = 0; j < dts.length; j++) {
      var dd = dts[j].nextElementSibling;
      var la = txt(dts[j]), va = txt(dd);
      if (la && va && la.length < 60) out.specs.push({ label: la, value: va });
    }
  }
  // 3) 兜底：带 "属性/Attribute" 标题的区块里，按冒号或换行切分
  if (!out.specs.length) {
    var bodyTxt = (document.body.innerText || '');
    var m = bodyTxt.match(/(?:Attributes?|Product Parameters?|Specifications?)[^\n]*\n([\s\S]{0,1500})/i);
    if (m) {
      m[1].split('\n').forEach(function (line) {
        var kv = line.split(/[:：]/);
        if (kv.length === 2 && kv[0].trim().length < 40 && kv[1].trim()) {
          out.specs.push({ label: kv[0].trim(), value: kv[1].trim() });
        }
      });
    }
  }

  // ── 文本分块：按标题切 ────────────────────────────────────────
  var heads = document.querySelectorAll('h1,h2,h3,h4,[class*="title"],[class*="Title"]');
  var marks = [];
  for (var hh = 0; hh < heads.length; hh++) {
    var el = heads[hh];
    var t = txt(el);
    if (!t || t.length > 120) continue;
    var rect = el.getBoundingClientRect();
    if (!rect.width || !rect.height) continue;   // 隐藏元素
    marks.push({ y: rect.top + window.scrollY, text: t });
  }
  marks.sort(function (a, b) { return a.y - b.y; });

  for (var s = 0; s < marks.length; s++) {
    var start = marks[s].y;
    var end = (s + 1 < marks.length) ? marks[s + 1].y : (start + 1200);
    var imgsHere = all.filter(function (it) { return it.y >= start && it.y < end; })
                      .map(function (it) { return it.full; });
    // 取该标题下方的一段文字
    var seg = (document.body.innerText || '').slice(0, 0); // 占位，下面用元素遍历更准
    var textParts = [];
    var walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
    var node;
    while ((node = walker.nextNode())) {
      var p = node.parentElement;
      if (!p) continue;
      var pr = p.getBoundingClientRect();
      var py = pr.top + window.scrollY;
      if (py >= start && py < end) {
        var v = (node.nodeValue || '').replace(/\s+/g, ' ').trim();
        if (v) textParts.push(v);
      }
    }
    seg = textParts.join(' ').slice(0, 2000);
    if (seg || imgsHere.length) {
      out.sections.push({ heading: marks[s].text, y: Math.round(start), text: seg, images: imgsHere });
    }
  }

  // ── 下载 ──────────────────────────────────────────────────────
  var pid = (location.pathname.match(/_(\d{6,})\.html/) || [])[1]
         || (location.search.match(/[?&]id=(\d+)/) || [])[1]
         || 'page';
  var blob = new Blob([JSON.stringify(out, null, 2)], { type: 'application/json' });
  var a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'alibaba-' + pid + '.json';
  document.body.appendChild(a);
  a.click();
  setTimeout(function () { URL.revokeObjectURL(a.href); a.remove(); }, 1000);

  console.log('%c[采集完成]', 'color:#0a0;font-weight:bold',
    '主图', out.images.gallery.length,
    '· 详情长图', out.images.detail.length,
    '· 其他', out.images.others.length,
    '· 属性', out.specs.length,
    '· 文本块', out.sections.length);
  if (out._notes.length) out._notes.forEach(function (n) { console.warn('⚠ ' + n); });
  console.log('已下载 alibaba-' + pid + '.json —— 把这个文件发给我。');
  console.log('下面也打印一份，方便你直接复制：');
  console.log(JSON.stringify(out, null, 2));

  return out;
})();
