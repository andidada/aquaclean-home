#!/usr/bin/env node
/**
 * verify_live_inquiry.js — 真实浏览器跑一遍线上询盘表单
 *
 * 为什么要有这个脚本：jsdom 里的 verify_inquiry_relay.js 只测了中继页本身，
 * 测不到「客户在 www.hkdmj.net 上点提交」这条完整链路。而 2026-10-11 修的
 * 那个 bug 恰好在这条链路上——Formspree 在大陆不可达，于是客户的询盘明明
 * 已经写进后台数据库，页面却弹 "Network error"，客户以为没提交成功。
 *
 * 本脚本用真实 Edge 打开线上页面、填表、提交，然后核对三件事：
 *   1. 页面给出的是「成功」，不是报错弹窗
 *   2. 隐藏中继（inquiry-proxy.html）被真正用过，而不是掉回 Formspree
 *   3. 数据确实落库（用唯一标记串去数据库里捞）
 *
 * 用法：
 *   node scripts/verify_live_inquiry.js [url]
 * 打印出标记串后去后台「询盘」列表搜索即可人工确认。
 */
const { spawn } = require('child_process');
const os = require('os');
const path = require('path');
const fs = require('fs');

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';
const URL = process.argv[2] || 'https://www.hkdmj.net/en/index.html';

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

async function main() {
  // 唯一标记，方便在数据库里捞出这一条
  const MARK = 'E2E' + Date.now().toString(36).toUpperCase();
  const port = 9800 + Math.floor(Math.random() * 150);
  const userDir = path.join(os.tmpdir(), 'aqc-inq-' + Date.now());
  const proc = spawn(EDGE, [
    '--remote-debugging-port=' + port,
    '--user-data-dir=' + userDir,
    '--no-proxy-server',
    '--no-first-run', '--no-default-browser-check', '--disable-extensions',
    '--headless=new', '--window-size=1440,900',
    'about:blank',
  ], { stdio: 'ignore' });

  let ws = null;
  for (let i = 0; i < 60; i++) {
    try {
      const list = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
      const p = list.find(t => t.type === 'page');
      if (p) { ws = p.webSocketDebuggerUrl; break; }
    } catch (e) { /* retry */ }
    await sleep(500);
  }
  if (!ws) { console.error('无法连接 Edge'); proc.kill(); process.exit(1); }

  const sock = new WebSocket(ws);
  let id = 0;
  const pending = new Map();
  const urls = [];
  const dialogs = [];
  const consoleErrors = [];

  sock.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  };
  sock.addEventListener('message', (ev) => {
    const m = JSON.parse(ev.data);
    if (m.method === 'Network.requestWillBeSent' && m.params.request) {
      urls.push(m.params.request.url);
    }
    if (m.method === 'Page.javascriptDialogOpening') {
      dialogs.push(m.params.message || '');
      // 不关掉的话 alert 会把页面卡死，后面什么都读不到
      send('Page.handleJavaScriptDialog', { accept: true }).catch(() => {});
    }
    if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') {
      consoleErrors.push((m.params.args || []).map(a => a.value || a.description || '').join(' '));
    }
  });

  await new Promise(r => { sock.onopen = r; sock.onerror = r; });
  const send = (method, params) => {
    const mid = ++id;
    sock.send(JSON.stringify({ id: mid, method, params: params || {} }));
    return new Promise(res => pending.set(mid, res));
  };

  await send('Page.enable');
  await send('Network.enable');
  await send('Runtime.enable');
  await send('Network.clearBrowserCache');
  await send('Page.navigate', { url: URL });

  // 等页面 + 隐藏中继 iframe 就绪
  await sleep(6000);

  const ready = await send('Runtime.evaluate', {
    returnByValue: true,
    expression: `({ relay: typeof window.AQCInquiry, form: !!document.getElementById('mainInquiryForm') })`,
  });
  const r0 = (ready.result && ready.result.result) ? ready.result.result.value : {};

  // 填表。中继页有 MIN_FILL_MS=1500 的防机器人规则，所以填完再等 2s 才提交。
  const fill = await send('Runtime.evaluate', {
    returnByValue: true,
    expression: `(function(){
      var MARK = ${JSON.stringify(MARK)};
      var set = function(id, v){
        var el = document.getElementById(id);
        if (!el) return 'missing:' + id;
        if (el.tagName === 'SELECT') {
          // 踩过坑：country 下拉里并没有 CN 选项，直接塞 'CN' 会把 value 清空，
          // required 校验不过 -> 浏览器压根不触发 submit，表现为"什么都没发生"。
          // 所以这里只挑真实存在的 option，取不到就明确报错。
          var opt = [].slice.call(el.options).filter(function(o){ return o.value === v; })[0];
          if (!opt) return 'no-option:' + id + '=' + v;
        }
        el.value = v;
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        return el.value === v ? 'ok' : 'stuck:' + id + '=' + el.value;
      };
      var res = [
        set('name', 'E2E Test Lead'),
        set('email', 'e2e-' + MARK.toLowerCase() + '@example.com'),
        set('company', 'AquaClean QA'),
        set('country', 'OTHER'),
        set('products_interested', 'robot-vacuum'),
        set('quantity', '500 units'),
        set('message', 'AUTOMATED END-TO-END TEST ' + MARK + ' — safe to delete.')
      ].join(',');
      var f = document.getElementById('mainInquiryForm');
      var bad = [].slice.call(f.querySelectorAll('input,select,textarea'))
        .filter(function(el){ return !el.checkValidity(); })
        .map(function(el){ return (el.name || el.id) + ':' + (el.validationMessage || 'invalid'); });
      return res + ' || valid=' + f.checkValidity() + (bad.length ? ' || invalid: ' + bad.join('; ') : '');
    })()`,
  });
  const fillRes = (fill.result && fill.result.result) ? fill.result.result.value : '';
  console.log('  填表结果: ' + fillRes);

  await sleep(2200);

  await send('Runtime.evaluate', {
    returnByValue: true,
    expression: `document.getElementById('mainInquiryForm').querySelector('button[type=submit], .btn').click()`,
  });

  // 轮询结果：成功块拿到 .show 即为成功
  let shown = false, btnText = '', sawSending = false;
  for (let i = 0; i < 30; i++) {
    await sleep(700);
    const r = await send('Runtime.evaluate', {
      returnByValue: true,
      expression: `(function(){
        var s = document.getElementById('mainFormSuccess');
        var f = document.getElementById('mainInquiryForm');
        var b = f && f.querySelector('.btn');
        return {
          shown: !!(s && s.classList.contains('show')),
          formHidden: !!(f && f.style.display === 'none'),
          btn: b ? b.textContent.trim() : '',
          disabled: !!(b && b.disabled)
        };
      })()`,
    });
    const v = (r.result && r.result.result) ? r.result.result.value : {};
    // 按钮进入过 disabled/'Sending...' 才能证明 submit 处理器真的跑起来了；
    // 否则就是表单校验没过、事件压根没触发，和"投递失败"是两回事。
    if (v.disabled || /Sending/i.test(v.btn)) sawSending = true;
    shown = v.shown; btnText = v.btn;
    if (shown || dialogs.length) break;
  }

  sock.close();
  try { proc.kill(); } catch (e) {}
  try { fs.rmSync(userDir, { recursive: true, force: true }); } catch (e) {}

  const relayUsed = urls.filter(u => /inquiry-proxy\.html/.test(u));
  const formspree = urls.filter(u => /formspree\.io/.test(u));
  const relayDomain = urls.filter(u => /aquaclean-admin\.app\.workbuddy\.host/.test(u));

  let pass = 0, fail = 0;
  const check = (name, ok, detail) => {
    console.log((ok ? '  ✓ ' : '  ✗ ') + name + (detail ? '  — ' + detail : ''));
    ok ? pass++ : fail++;
  };

  console.log('=== 线上询盘端到端：' + URL + ' ===');
  console.log('标记串: ' + MARK + '   （去后台「询盘」列表搜它确认落库）\n');
  console.log('1. 前置条件');
  check('表单存在', r0.form === true);
  check('隐藏中继已挂载（window.AQCInquiry）', r0.relay === 'object', 'typeof=' + r0.relay);

  console.log('2. 提交结果');
  check('表单校验通过、submit 处理器确实执行', sawSending === true,
    sawSending ? '' : '按钮从未进入 Sending 状态 —— 多半是必填项校验没过，事件没触发');
  check('页面显示成功，而不是报错弹窗', shown === true && dialogs.length === 0,
    dialogs.length ? '弹窗: ' + dialogs.join(' | ') : (shown ? '' : '未显示成功，按钮文案=' + btnText));
  check('提交后表单隐藏 / 成功块可见', shown === true);

  console.log('3. 走了哪条路');
  check('用到了自有中继 inquiry-proxy.html', relayUsed.length > 0, relayUsed.length + ' 次');
  check('访问了后台域（国内外均可达）', relayDomain.length > 0, relayDomain.length + ' 个请求');
  // Formspree 只作为邮件通知的尽力而为，出现也属正常，这里只做信息披露
  console.log('  · Formspree 请求 ' + formspree.length + ' 个（仅邮件通知，成败不影响结果）');

  console.log('4. 无脚本错误');
  check('无 JS 报错', consoleErrors.length === 0, consoleErrors.slice(0, 2).join(' | '));

  console.log('\n' + (fail === 0 ? '✅ 全部通过' : '❌ 有 ' + fail + ' 项失败') + '：' + pass + ' passed, ' + fail + ' failed');
  console.log('落库标记: ' + MARK);
  process.exit(fail === 0 ? 0 : 1);
}

main().catch(e => { console.error(e); process.exit(1); });
