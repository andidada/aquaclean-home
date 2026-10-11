#!/usr/bin/env node
/**
 * verify_cn_reachable.js — 模拟大陆网络：掐断所有非自有域名
 *
 * 「国外能打开、国内打不开」这类问题的根因几乎总是同一个：页面里挂了
 * 大陆不可达的外部资源（Google Fonts / jsDelivr / Formspree / via.placeholder），
 * 而且是阻塞式的 —— 浏览器会一直等到超时才继续渲染，表现为「白屏/打不开」。
 *
 * 本脚本不做猜测，直接模拟：用 CDP 的 Fetch 域把所有「不在白名单里的」请求
 * 一律按 NameNotResolved 掐掉（等价于 DNS 污染），然后看：
 *
 *   公开站  页面还能不能渲染出来、询盘还能不能提交成功（走自有中继）
 *   后台    SDK 还能不能初始化、是不是也全走本地资源
 *
 * 任何一项挂了，就说明还残留着对外部域名的硬依赖。
 *
 * 用法：node scripts/verify_cn_reachable.js
 */
const { spawn } = require('child_process');
const os = require('os');
const path = require('path');
const fs = require('fs');

const EDGE = 'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe';

const SCENARIOS = [
  {
    name: '公开站 www.hkdmj.net',
    url: 'https://www.hkdmj.net/en/index.html',
    allow: ['www.hkdmj.net', 'hkdmj.net', 'aquaclean-admin.app.workbuddy.host'],
    form: true,
  },
  {
    name: '后台 aquaclean-admin',
    url: 'https://aquaclean-admin.app.workbuddy.host/admin/',
    allow: ['aquaclean-admin.app.workbuddy.host'],
    form: false,
  },
];

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }
function hostOf(u) {
  try { return new URL(u).hostname; } catch (e) { return ''; }
}

async function run(sc) {
  const port = 9900 + Math.floor(Math.random() * 90);
  const userDir = path.join(os.tmpdir(), 'aqc-cn-' + Date.now());
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
  if (!ws) { console.error('无法连接 Edge'); proc.kill(); return null; }

  const sock = new WebSocket(ws);
  let id = 0;
  const pending = new Map();
  const blocked = [];
  const failedAllowed = [];
  const consoleErrors = [];
  const dialogs = [];
  // Network.loadingFailed 不带 URL，只有 requestId，所以自己维护一张表。
  // 没有这张表就没法区分「白名单内真失败」和「我自己主动掐断的外部域名」，
  // 后者会被误报成失败。
  const urlById = new Map();

  sock.onmessage = (ev) => {
    const m = JSON.parse(ev.data);
    if (m.id && pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
  };
  await new Promise(r => { sock.onopen = r; sock.onerror = r; });
  const send = (method, params) => {
    const mid = ++id;
    sock.send(JSON.stringify({ id: mid, method, params: params || {} }));
    return new Promise(res => pending.set(mid, res));
  };

  sock.addEventListener('message', (ev) => {
    const m = JSON.parse(ev.data);
    if (m.method === 'Fetch.requestPaused') {
      const url = m.params.request ? m.params.request.url : '';
      const host = hostOf(url);
      const allowed = sc.allow.some(a => host === a || host.endsWith('.' + a));
      if (allowed) {
        send('Fetch.continueRequest', { requestId: m.params.requestId }).catch(() => {});
      } else {
        blocked.push(host || url.slice(0, 40));
        // NameNotResolved ≈ 大陆 DNS 污染的表现
        send('Fetch.failRequest', { requestId: m.params.requestId, errorReason: 'NameNotResolved' }).catch(() => {});
      }
      return;
    }
    if (m.method === 'Network.requestWillBeSent' && m.params.request) {
      urlById.set(m.params.requestId, m.params.request.url);
    }
    if (m.method === 'Network.loadingFailed') {
      // 只关心「白名单内却失败」的请求。被我们主动掐掉的外部域名也会走到这里，
      // 必须按 host 过滤掉，否则会把自己的模拟行为误报成故障。
      const host = hostOf(urlById.get(m.params.requestId) || '');
      const isAllowed = sc.allow.some(a => host === a || host.endsWith('.' + a));
      if (host && isAllowed) {
        failedAllowed.push(host + ' ' + m.params.errorText);
      }
    }
    if (m.method === 'Runtime.consoleAPICalled' && m.params.type === 'error') {
      consoleErrors.push((m.params.args || []).map(a => a.value || a.description || '').join(' '));
    }
    if (m.method === 'Page.javascriptDialogOpening') {
      dialogs.push(m.params.message || '');
      send('Page.handleJavaScriptDialog', { accept: true }).catch(() => {});
    }
  });

  await send('Page.enable');
  await send('Runtime.enable');
  await send('Network.enable');
  await send('Fetch.enable', { patterns: [{ urlPattern: '*' }] });
  await send('Network.clearBrowserCache');
  await send('Page.navigate', { url: sc.url });
  await sleep(6000);

  let result = {};
  if (sc.form) {
    const fill = await send('Runtime.evaluate', {
      returnByValue: true,
      expression: `(function(){
        var MARK = 'CN' + Date.now().toString(36).toUpperCase();
        var set = function(id, v){
          var el = document.getElementById(id);
          if (!el) return 'missing:' + id;
          if (el.tagName === 'SELECT') {
            var o = [].slice.call(el.options).filter(function(x){ return x.value === v; })[0];
            if (!o) return 'no-option:' + id;
          }
          el.value = v;
          el.dispatchEvent(new Event('input', { bubbles: true }));
          el.dispatchEvent(new Event('change', { bubbles: true }));
          return el.value === v ? 'ok' : 'stuck:' + id;
        };
        set('name', 'CN Sim Test'); set('email', 'cn-' + MARK.toLowerCase() + '@example.com');
        set('company', 'AquaClean QA'); set('country', 'OTHER');
        set('products_interested', 'robot-vacuum'); set('quantity', '100');
        set('message', 'CN SIMULATION ' + MARK + ' — safe to delete.');
        return { mark: MARK, valid: document.getElementById('mainInquiryForm').checkValidity() };
      })()`,
    });
    const fv = (fill.result && fill.result.result) ? fill.result.result.value : {};
    await sleep(2200);

    await send('Runtime.evaluate', {
      returnByValue: true,
      expression: `document.getElementById('mainInquiryForm').querySelector('button[type=submit], .btn').click()`,
    });

    let shown = false;
    for (let i = 0; i < 25; i++) {
      await sleep(700);
      const r = await send('Runtime.evaluate', {
        returnByValue: true,
        expression: `!!(document.getElementById('mainFormSuccess') && document.getElementById('mainFormSuccess').classList.contains('show'))`,
      });
      shown = !!(r.result && r.result.result && r.result.result.value);
      if (shown || dialogs.length) break;
    }
    result = { mark: fv.mark, valid: fv.valid, shown: shown };
  } else {
    const r = await send('Runtime.evaluate', {
      returnByValue: true,
      expression: `(function(){
        return {
          sdk: typeof window.WorkBuddyCloud,
          ready: !!window.aqcCloudReady || (window.__aqc && !!window.__aqc.ready),
          text: (document.body.innerText || '').replace(/\\s+/g, ' ').slice(0, 120)
        };
      })()`,
    });
    result = (r.result && r.result.result) ? r.result.result.value : {};
  }

  sock.close();
  try { proc.kill(); } catch (e) {}
  try { fs.rmSync(userDir, { recursive: true, force: true }); } catch (e) {}

  return { result, blocked, failedAllowed, consoleErrors, dialogs };
}

(async function main() {
  let pass = 0, fail = 0;
  const check = (name, ok, detail) => {
    console.log((ok ? '  ✓ ' : '  ✗ ') + name + (detail ? '  — ' + detail : ''));
    ok ? pass++ : fail++;
  };

  for (const sc of SCENARIOS) {
    console.log('\n=== ' + sc.name + ' ===');
    console.log('（已掐断白名单外所有域名：' + sc.allow.join(', ') + ' 除外）');
    const out = await run(sc);
    if (!out) { fail++; continue; }

    const uniqBlocked = [...new Set(out.blocked)];
    console.log('  被掐断的域名: ' + (uniqBlocked.length ? uniqBlocked.join(', ') : '无（说明压根没请求外部资源）'));
    check('白名单内的请求没有失败', out.failedAllowed.length === 0, out.failedAllowed.slice(0, 3).join('; '));

    if (sc.form) {
      check('页面仍然渲染出内容（未白屏）', out.result.valid === true, '表单可填=' + out.result.valid);
      check('询盘提交成功（外部域名全断也能送到后台库）',
        out.result.shown === true && out.dialogs.length === 0,
        out.dialogs.length ? '弹窗: ' + out.dialogs.join(' | ') : (out.result.shown ? '' : '未显示成功'));
    } else {
      check('云服务 SDK 已加载（未依赖 CDN）', out.result.sdk === 'object' || out.result.sdk === 'function',
        'typeof=' + out.result.sdk);
      check('后台页面渲染出内容', (out.result.text || '').length > 10, (out.result.text || '').slice(0, 60));
    }
    check('无 JS 报错', out.consoleErrors.length === 0, out.consoleErrors.slice(0, 2).join(' | '));
    if (out.result.mark) console.log('  落库标记: ' + out.result.mark + '（测试行，可在后台删掉）');
  }

  console.log('\n' + (fail === 0 ? '✅ 全部通过' : '❌ 有 ' + fail + ' 项失败') + '：' + pass + ' passed, ' + fail + ' failed');
  process.exit(fail === 0 ? 0 : 1);
})();
