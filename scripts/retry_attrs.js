#!/usr/bin/env node
/**
 * retry_attrs.js — 补抓阿里属性表（把中文行业属性也翻成英文键）
 *
 * 踩过的坑
 * --------
 * v3 只认 `{"attrName":"X","attrValue":"Y"}`，并且用 ASCII 过滤丢掉中文键，
 * 结果 9 个页面里 5 个拿到 0 条属性。
 *
 * 真相是这 5 个 listing 卖家**没填英文自定义属性**，页面上只有中文的
 * 「行业属性」，形状是：
 *     {"attrName":"型号","attrNameId":3,"attrValue":"GV26"}
 *     {"attrName":"最大运行时间","attrNameId":250797649,"attrValue":"30-60分钟","attrValueId":188598543}
 *
 * 所以这里：
 *   1. 两种形状都认（attrNameId / attrValueId 可有可无）；
 *   2. 中文属性名用固定词典翻成英文键（型号→Model、功率 (W)→Power (W)…），
 *      翻不出来的保留中文，标在 attrs_zh 里，方便人工核；
 *   3. 中文值里常见的单位也顺手统一（分钟→mins、小时→hours、千克→kg）；
 *   4. 轮询到拿到属性为止，而不是固定等几秒。
 *
 * 用法
 * ----
 *   node scripts/retry_attrs.js            # 只补属性为空的
 *   node scripts/retry_attrs.js --all      # 9 个全部重抓
 *   node scripts/retry_attrs.js 1601812941902
 */
const fs = require('fs');
const path = require('path');

const PORT = 9333;
const V3_DIR = path.join(process.cwd(), 'scraped', 'alibaba_v3');
const LINKS_FILE = path.join(process.cwd(), 'scraped', 'alibaba_links.txt');
const sleep = ms => new Promise(r => setTimeout(r, ms));

/** 中文属性名 → 英文键。翻不出来的走 attrs_zh */
const ZH_LABEL = {
  '型号': 'Model', '品牌名称': 'Brand Name', '产地': 'Place of Origin',
  '功率 (W)': 'Power (W)', '功率(W)': 'Power (W)', '功率': 'Power (W)',
  '电压 (V)': 'Voltage (V)', '电压(V)': 'Voltage (V)', '电压': 'Voltage (V)',
  '吸力': 'Suction Power', '吸入功率 (AW)': 'Suction Power (AW)',
  '最大运行时间': 'Maximum Runtime', '运行时间': 'Runtime', '续航时间': 'Runtime',
  '集尘量': 'Dust Capacity', '尘盒容量': 'Dustbin Capacity',
  '尘盒容量 (l)': 'Dustbin Capacity', '水箱容量': 'Water Tank Capacity',
  '尘袋容量': 'Dust bag Capacity', '过滤器': 'Filter', '过滤系统': 'Filter',
  '电机类型': 'Motor Type', '电池容量': 'Battery Capacity', '电池类型': 'Battery Type',
  '充电时长': 'Charging Time', '充电时间': 'Charging Time', '噪音': 'Noise Level',
  '功能': 'Function', '应用范围': 'Application', '适用场景': 'Application',
  '电源': 'Power Source', '私模': 'Private Mold', '产品净重': 'Net Weight',
  '保修': 'Warranty', '质保': 'Warranty', '包装类型': 'Packaging Type',
  '喷嘴数量': 'Nozzle Count', '操作语言': 'Operating Language',
  '有尘袋或无尘袋': 'Bag Or Bagless', '导航模式': 'Navigation', '导航': 'Navigation',
  '自动回充': 'Auto Recharge', '类型': 'Type', '材质': 'Material',
  '容量': 'Capacity', '特色功能': 'Special Feature', '手机APP控制': 'App Control',
  'APP操控': 'App Control', '是否带遥控器': 'Remote Control',
  '清洗类型': 'Cleaning Type', '拖地功能': 'Mopping Function',
};

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

/** 两种形状都认；解码 \uXXXX；中文键翻英文 */
const EXPR = (dictJson) => `(function(){
  var DICT = ${dictJson};
  var scs = document.querySelectorAll('script'), all = '';
  for (var i=0;i<scs.length;i++){
    if (scs[i].src) continue;
    var t = scs[i].textContent || '';
    if (t.length > 500) all += t + '\\n';
  }
  function dec(s){
    return s.replace(/\\\\u0028/g,'(').replace(/\\\\u0029/g,')')
            .replace(/\\\\u002C/g,',').replace(/\\\\u0026/g,'&')
            .replace(/\\\\u002F/g,'/').replace(/\\\\"/g,'"')
            .replace(/\\\\u00a0/g,' ').trim();
  }
  // 形状 A: {"attrName":"X","attrValue":"Y"}
  // 形状 B: {"attrName":"X","attrNameId":N,"attrValue":"Y","attrValueId":M}
  var RE = /\\{\\s*"attrName"\\s*:\\s*"((?:[^"\\\\]|\\\\.)*)"\\s*(?:,\\s*"attrNameId"\\s*:\\s*\\d+\\s*)?,\\s*"attrValue"\\s*:\\s*"((?:[^"\\\\]|\\\\.)*)"/g;
  var attrs = {}, zh = {};
  var m, n = 0;
  while ((m = RE.exec(all)) !== null && n < 300) {
    var name = dec(m[1]), val = dec(m[2]);
    if (!name || !val) continue;
    var key = /^[\\x20-\\x7E]+$/.test(name) ? name : (DICT[name] || '');
    if (!key) { zh[name] = val; continue; }
    if (!(key in attrs)) attrs[key] = val;
    n++;
  }
  return {count:Object.keys(attrs).length, attrs:attrs, zh:zh, scannedLen:all.length};
})()`;

async function main() {
  const argv = process.argv.slice(2);
  const all = argv.includes('--all');
  const argvIds = argv.filter(a => /^\d{8,}$/.test(a));
  // 链接文件可覆盖：采集是分批做的，每批一个链接文件。写死alibaba_links.txt
  // 的话，第二批开始就"跳过（无链接或无记录）"——而且它不报错，看着像采到了。
  const linksArg = argv.filter(a => !a.startsWith('--') && !/^\d{8,}$/.test(a))[0];
  const linksFile = linksArg ? path.resolve(process.cwd(), linksArg) : LINKS_FILE;

  let todo;
  if (argvIds.length) todo = argvIds.slice();
  else if (all) todo = fs.readdirSync(V3_DIR).filter(f => f.endsWith('.json')).map(f => f.slice(0, -5));
  else {
    todo = [];
    for (const f of fs.readdirSync(V3_DIR)) {
      if (!f.endsWith('.json')) continue;
      const d = JSON.parse(fs.readFileSync(path.join(V3_DIR, f), 'utf8'));
      if (!Object.keys(d.attrs || {}).length) todo.push(d.productId);
    }
  }
  if (!todo.length) { console.log('没有需要补抓的页面。'); return; }

  if (!fs.existsSync(linksFile)) { console.error('✗ 链接文件不存在：' + linksFile); process.exit(1); }
  const links = fs.readFileSync(linksFile, 'utf8').split('\n')
    .map(s => s.trim()).filter(s => s && s.startsWith('http'));
  const urlOf = {};
  links.forEach(u => { const m = u.match(/_(\d{10,})\.html/); if (m) urlOf[m[1]] = u; });
  // 显式点名要抓的 id 必须都能在链接文件里找到，否则就是白跑一趟
  const missing = todo.filter(id => !urlOf[id]);
  if (missing.length) {
    console.error('✗ 这些 id 在链接文件里没有对应链接：' + missing.join(', '));
    console.error('  链接文件：' + linksFile);
    process.exit(1);
  }

  const target = await findPage();
  if (!target) { console.error('✗ 9333 上没 Edge。先跑 collect_alibaba_cdp.js'); process.exit(1); }
  const { sock, send } = await connect(target.webSocketDebuggerUrl);
  await send('Page.enable'); await send('Runtime.enable');
  const expr = EXPR(JSON.stringify(ZH_LABEL));

  for (const pid of todo) {
    const url = urlOf[pid];
    const recPath = path.join(V3_DIR, pid + '.json');
    if (!url || !fs.existsSync(recPath)) { console.log(pid + ' 跳过（无链接或无记录）'); continue; }
    console.log('\n[' + pid + '] ' + url.slice(0, 76));

    await send('Page.navigate', { url });
    await sleep(5000);

    let got = null;
    for (let round = 0; round < 16 && !got; round++) {
      await send('Runtime.evaluate', { expression: 'window.scrollBy(0, window.innerHeight*0.8)', returnByValue: true });
      await sleep(900);
      const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
      const v = (r.result && r.result.result) ? r.result.result.value : null;
      if (v && v.count > 0) got = v;
    }

    const rec = JSON.parse(fs.readFileSync(recPath, 'utf8'));
    if (!got) { console.log('   ✗ 仍然 0 条'); continue; }

    rec.attrs = got.attrs;
    rec.attrsZh = got.zh;
    rec.attrsScannedLen = got.scannedLen;
    fs.writeFileSync(recPath, JSON.stringify(rec, null, 2), 'utf8');
    console.log('   ✓ ' + got.count + ' 条英文键' +
                (Object.keys(got.zh).length ? '（另有 ' + Object.keys(got.zh).length + ' 条未译中文键）' : ''));
    ['Model', 'Suction Power', 'Power (W)', 'Navigation', 'Runtime', 'Maximum Runtime', 'Dustbin Capacity', 'Battery Capacity']
      .filter(k => got.attrs[k])
      .forEach(k => console.log('       ' + k + ' = ' + got.attrs[k]));
    await sleep(1000);
  }
  sock.close();
  console.log('\n完成。');
}

main().catch(e => { console.error(e); process.exit(1); });
