/**
 * AquaClean Admin — Product Manager + Homepage CMS
 * All functions defined FIRST (IIFE hoisting-safe), event binding at END
 */
(function () {
  'use strict';

  // ── Utilities ──────────────────────────────────────────────────
  function $(id) { return document.getElementById(id); }
  function qsa(sel) { return [].slice.call(document.querySelectorAll(sel)); }

  function setStatus(msg) {
    var el = $('status');
    if (el) el.textContent = msg;
  }

  // ── 统一的"发布到线上"入口 ────────────────────────────────────
  // 以前"部署"藏在「💾 保存草稿」的 confirm 弹窗里：运营点保存只是一个弹窗
  // 问要不要部署，界面上根本看不到发布按钮，常以为压根没有发布能力。
  // 现在草稿和发布是两个动作：保存只写 localStorage，发布才推 GitHub。

  // 本机桥（admin/gh_token_server.py，双击运行即可）。它手上握着 Windows
  // 凭据管理器里的 PAT，所以只要桥在跑，后台就能自己拿到 Token —— 不用每次
  // 打开后台都手工粘贴一遍。
  var AQC_BRIDGE = 'http://127.0.0.1:18765';

  // 向本机桥要 Token；桥没运行 / 被浏览器拦截时静默返回空串。
  async function bridgeToken() {
    try {
      var ctrl = (typeof AbortController === 'function') ? new AbortController() : null;
      var timer = null;
      if (ctrl) timer = setTimeout(function () { ctrl.abort(); }, 1500);
      var r = await fetch(AQC_BRIDGE + '/token', ctrl
        ? { signal: ctrl.signal, cache: 'no-store' }
        : { cache: 'no-store' });
      if (timer) clearTimeout(timer);
      if (!r.ok) return '';
      return String(await r.text() || '').trim();
    } catch (e) {
      return '';   // 桥没运行，或 https 页面请求 http://127.0.0.1 被浏览器拦了
    }
  }

  // 没有 Token 时先问本机桥，桥没有才让人手工填；返回 false 表示放弃。
  async function ensureToken() {
    if (getToken()) return true;
    setStatus('🔑 正在从本机桥获取 Token...');
    var t = await bridgeToken();
    if (t) {
      setToken(t);
      refreshTokenUI();
      setStatus('🔑 已从本机桥自动获取 Token');
      return true;
    }
    var go = confirm('发布需要 GitHub Token（Contents: Read & Write，仅作用于 '
      + AQC_REPO + '）。\n\n本机桥（gh_token_server.py）没有运行，可以手工粘贴 Token。'
      + '\n现在粘贴？');
    if (!go) { setStatus('⚠ 未配置 Token，已取消发布（也可启动本机桥后重试）'); return false; }
    var ok = await promptForToken();
    if (!ok) setStatus('⚠ 未配置 Token，已取消发布');
    return ok;
  }

  // 打开后台就静默试一次本机桥：桥在跑的话，右上角直接显示"已配置"。
  async function autoTokenFromBridge() {
    if (getToken()) { refreshTokenUI(); return; }
    var t = await bridgeToken();
    if (t) {
      setToken(t);
      refreshTokenUI();
      setStatus('🔑 已从本机桥自动获取 GitHub Token · 可直接点「🚀 发布到线上」');
    } else {
      refreshTokenUI();
    }
  }

  function publishJson(path, content, commitMsg) {
    setStatus('🚀 正在发布到 GitHub... (' + path + ')');
    return ghCommit(path, content, commitMsg)
      .then(function (sha) {
        // 产品资料是"运行时读取"的：详情页由 product-detail.js、类目页由页内
        // 脚本、首页由 home-loader.js 各自去读 JSON，所以推上去就生效，不用
        // 重新生成 HTML。（类目页拉不到数据时会保留静态卡片，不会白屏。）
        var extra = /data\/products\/.+\.json$/.test(path)
          ? ' · 详情页 / 类目页 / 首页都是运行时读取这份 JSON，Pages 重建后自动更新'
          : '';
        setStatus('✅ 已发布！commit ' + sha.substring(0, 8)
          + ' · GitHub Pages 1-2 分钟后生效（硬刷新 Ctrl+Shift+R 穿透缓存）' + extra);
        return sha;
      })
      .catch(function (err) {
        setStatus('❌ 发布失败：' + err.message);
        throw err;
      });
  }

  // ── GitHub Deploy Helpers (added 2026-09-04) ────────────────────
  // One-click save: writes JSON / images straight to GitHub via Contents API.
  // Requires a Fine-grained PAT (Contents: Read & Write on andidada/aquaclean-home).
  var AQC_REPO = 'andidada/aquaclean-home';
  var AQC_BRANCH = 'main';
  var AQC_UPLOAD_DIR = 'assets/images/uploads/';
  // 上传后的 URL 必须写全域名：后台跑在 *.workbuddy.host，相对路径
  // '/assets/...' 在后台域是 404，预览图会永远灰着。前台和后台都能用绝对地址。
  var AQC_PUBLIC_BASE = 'https://www.hkdmj.net';
  function publicUrl(path) {
    return AQC_PUBLIC_BASE + '/' + String(path).replace(/^\/+/, '');
  }

  // ── Optional server-side GitHub proxy ────────────────────────────
  // When netlify/functions/github-proxy is configured, the PAT no longer has
  // to live in localStorage: we send the short-lived admin session token and
  // the function signs the upstream call with its own GITHUB_TOKEN.
  // When it is not configured (e.g. the page is served from GitHub Pages)
  // every call below is untouched and the browser keeps using stored PAT.
  var AQC_PROXY = '/.netlify/functions/github-proxy';
  var aqcProxyOn = null; // null = not probed yet, then true / false

  function aqcSession() {
    try { return sessionStorage.getItem('admin_session_token') || ''; } catch (e) { return ''; }
  }

  async function proxyAvailable() {
    if (aqcProxyOn !== null) return aqcProxyOn;
    try {
      var r = await fetch(AQC_PROXY, { headers: { Authorization: 'Bearer ' + aqcSession() } });
      // A catch-all rewrite can answer this with 200 + HTML (GitHub Pages
      // does), so only trust a JSON body.
      var ct = r.headers.get('content-type') || '';
      var d = (r.ok && ct.indexOf('application/json') !== -1)
        ? await r.json().catch(function () { return null; })
        : null;
      aqcProxyOn = !!(d && d.configured);
    } catch (e) { aqcProxyOn = false; }
    return aqcProxyOn;
  }

  function proxyUrl(path, method) {
    return AQC_PROXY + '?path=' + encodeURIComponent(path) + '&method=' + method;
  }

  async function proxyGetSha(path) {
    var r = await fetch(proxyUrl(path, 'GET'), {
      headers: { Authorization: 'Bearer ' + aqcSession() }
    });
    if (r.status === 404) return null;
    if (!r.ok) throw new Error('GET ' + path + ' failed: HTTP ' + r.status);
    var d = await r.json();
    return d.sha;
  }

  async function proxyPut(path, body, what) {
    var r = await fetch(proxyUrl(path, 'PUT'), {
      method: 'POST',
      headers: { Authorization: 'Bearer ' + aqcSession(), 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!r.ok) {
      var err = await r.json().catch(function () { return {}; });
      throw new Error(what + ' ' + r.status + ': ' + (err.message || err.error || ''));
    }
    var result = await r.json();
    return (result.content && result.content.sha) || '';
  }




  // PAT 只存在 sessionStorage：关掉标签页即失效，不会长期躺在浏览器里。
  // 旧版本存在 localStorage 里，这里读到就迁移过来并立刻删掉。
  var AQC_TOKEN_KEY = 'admin_gh_token';

  function getToken() {
    try {
      var s = sessionStorage.getItem(AQC_TOKEN_KEY) || '';
      if (!s) {
        var legacy = localStorage.getItem(AQC_TOKEN_KEY) || '';
        if (legacy) {
          sessionStorage.setItem(AQC_TOKEN_KEY, legacy);
          localStorage.removeItem(AQC_TOKEN_KEY);
          s = legacy;
        }
      }
      return s;
    } catch(e) { return ''; }
  }
  function setToken(t) {
    try {
      if (t) {
        sessionStorage.setItem(AQC_TOKEN_KEY, t.trim());
        localStorage.removeItem(AQC_TOKEN_KEY);
      } else {
        sessionStorage.removeItem(AQC_TOKEN_KEY);
        localStorage.removeItem(AQC_TOKEN_KEY);
      }
    } catch(e) {}
  }
  function b64Utf8(str) { return btoa(unescape(encodeURIComponent(str))); }

  async function ghGetSha(path) {
    if (await proxyAvailable()) return proxyGetSha(path);
    var token = getToken();
    if (!token) return null;
    var url = 'https://api.github.com/repos/' + AQC_REPO + '/contents/' + encodeURI(path) + '?ref=' + AQC_BRANCH + '&t=' + Date.now();
    var r = await fetch(url, {
      headers: { 'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json' }
    });
    if (r.status === 404) return null;
    if (!r.ok) throw new Error('GET ' + path + ' failed: HTTP ' + r.status);
    var d = await r.json();
    return d.sha;
  }

  async function ghCommit(path, content, message) {
    var sha = await ghGetSha(path);
    var body = { message: message, content: b64Utf8(content), branch: AQC_BRANCH };
    if (sha) body.sha = sha;
    if (await proxyAvailable()) return proxyPut(path, body, 'GitHub PUT');

    var token = getToken();
    if (!token) throw new Error('未配置 GitHub Token：请先点击右上角"⚠ 设置 GitHub Token"');
    var r = await fetch('https://api.github.com/repos/' + AQC_REPO + '/contents/' + encodeURI(path), {
      method: 'PUT',
      headers: { 'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!r.ok) {
      var err = await r.json().catch(function(){ return {}; });
      throw new Error('GitHub PUT ' + r.status + ': ' + (err.message || err.error || ''));
    }
    var result = await r.json();
    return (result.content && result.content.sha) || '';
  }

  async function ghUploadImage(file) {
    var token = getToken();
    var viaProxy = await proxyAvailable();
    // With the proxy the PAT lives on the server, so none is needed here.
    if (!viaProxy && !token) throw new Error('未配置 GitHub Token');
    var safeName = (file.name || 'image').replace(/[^a-zA-Z0-9._-]/g, '_').slice(0, 80);
    var stamp = Date.now();
    var path = AQC_UPLOAD_DIR + stamp + '-' + safeName;
    var dataUrl = await new Promise(function(res, rej) {
      var fr = new FileReader();
      fr.onload = function(e) { res(e.target.result); };
      fr.onerror = rej;
      fr.readAsDataURL(file);
    });
    var b64 = dataUrl.split(',')[1];
    var sha = await ghGetSha(path);
    var body = { message: 'admin upload: ' + safeName, content: b64, branch: AQC_BRANCH };
    if (sha) body.sha = sha;
    if (await proxyAvailable()) {
      await proxyPut(path, body, '上传失败');
      return publicUrl(path);
    }
    var r = await fetch('https://api.github.com/repos/' + AQC_REPO + '/contents/' + encodeURI(path), {
      method: 'PUT',
      headers: { 'Authorization': 'Bearer ' + token, 'Accept': 'application/vnd.github+json', 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    if (!r.ok) {
      var err = await r.json().catch(function(){ return {}; });
      throw new Error('上传失败 ' + r.status + ': ' + (err.message || err.error || ''));
    }
    return publicUrl(path);
  }

  // 用遮罩弹窗代替 window.prompt：输入框是 password 类型，PAT 不会明文糊在
  // 屏幕上，也不会被浏览器记住。返回 Promise<boolean>。
  function promptForToken() {
    return new Promise(function (resolve) {
      var cur = getToken();
      var wrap = document.createElement('div');
      wrap.style.cssText = 'position:fixed;inset:0;background:rgba(15,23,42,.55);display:flex;align-items:center;justify-content:center;z-index:99999;';
      wrap.innerHTML =
        '<div style="background:#fff;border-radius:12px;padding:24px;width:min(440px,92vw);box-shadow:0 20px 50px rgba(15,23,42,.3);">' +
        '<h3 style="margin:0 0 8px;font-size:16px;color:#0F172A;">GitHub Personal Access Token</h3>' +
        '<p style="margin:0 0 14px;font-size:13px;line-height:1.7;color:#475569;">' +
          '需 Contents: Read &amp; Write 权限，仅作用于 <b>' + AQC_REPO + '</b>。<br>' +
          '只保存在当前标签页（sessionStorage），关闭标签页即失效。</p>' +
        '<input id="aqcTokenInput" type="password" autocomplete="off" spellcheck="false" placeholder="github_pat_…" ' +
          'style="width:100%;box-sizing:border-box;padding:10px 12px;border:1px solid #CBD5E1;border-radius:8px;font-family:monospace;font-size:13px;">' +
        (cur ? '<p style="margin:8px 0 0;font-size:12px;color:#64748B;">已配置（长度 ' + cur.length + '）。留空提交 = 保持原样</p>' : '') +
        '<div style="display:flex;gap:10px;justify-content:flex-end;margin-top:18px;">' +
        '<button id="aqcTokenClear" style="padding:8px 14px;border:1px solid #E2E8F0;background:#fff;border-radius:8px;cursor:pointer;">清除</button>' +
        '<button id="aqcTokenCancel" style="padding:8px 14px;border:1px solid #E2E8F0;background:#fff;border-radius:8px;cursor:pointer;">取消</button>' +
        '<button id="aqcTokenOk" style="padding:8px 16px;border:0;background:#2563EB;color:#fff;border-radius:8px;cursor:pointer;font-weight:600;">保存</button>' +
        '</div></div>';
      document.body.appendChild(wrap);
      var input = wrap.querySelector('#aqcTokenInput');
      var okBtn = wrap.querySelector('#aqcTokenOk');
      input.focus();
      function close() { if (wrap.parentNode) wrap.parentNode.removeChild(wrap); }
      wrap.addEventListener('click', function (e) { if (e.target === wrap) { close(); resolve(false); } });
      wrap.querySelector('#aqcTokenCancel').onclick = function () { close(); resolve(false); };
      wrap.querySelector('#aqcTokenClear').onclick = function () { setToken(''); refreshTokenUI(); close(); resolve(false); };
      okBtn.onclick = function () {
        var v = input.value.trim();
        if (v) { setToken(v); refreshTokenUI(); close(); resolve(true); return; }
        if (getToken()) { refreshTokenUI(); close(); resolve(true); return; }
        input.focus();
      };
      input.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') { e.preventDefault(); okBtn.click(); }
        if (e.key === 'Escape') { e.preventDefault(); close(); resolve(false); }
      });
    });
  }

  function refreshTokenUI() {
    var link = $('setTokenLink');
    if (!link) return;
    var has = !!getToken();
    link.textContent = has ? '✓ GitHub Token 已配置' : '⚠ 设置 GitHub Token';
    link.style.color = has ? '#22c55e' : '#fbbf24';
    link.style.borderColor = has ? '#22c55e' : '#fbbf24';
    link.title = has
      ? '当前标签页已持有 Token（来自本机桥或手工粘贴）'
      : '双击运行 admin/gh_token_server.py 可自动获取，或点此手工粘贴';
  }

  function slugify(s) {
    return String(s || '').toLowerCase()
      .replace(/[^\w\s-]/g, '')
      .replace(/[\s_-]+/g, '-')
      .replace(/^-+|-+$/g, '');
  }

  function sk(tab, lang, cat) {
    return 'aqc_' + tab + '_' + lang + (cat ? '_' + cat : '');
  }

  // ── Data ───────────────────────────────────────────────────────
  var LANGS = [
    { code:'en', label:'English' },
    { code:'zh', label:'中文' },
    { code:'es', label:'Español' },
    { code:'fr', label:'Français' },
    { code:'ar', label:'العربية' },
    { code:'id', label:'Indonesia' },
    { code:'ru', label:'Русский' },
    { code:'th', label:'ไทย' },
    { code:'vi', label:'Tiếng Việt' },
  ];

  var CATS = [
    { slug:'handheld-vacuum',      label:'手持吸尘器',     enLabel:'Handheld Vacuum Cleaner' },
    { slug:'robot-vacuum',         label:'扫地机器人',      enLabel:'Robot Vacuum Cleaner' },
    { slug:'steam-cleaner',        label:'蒸汽清洁器',      enLabel:'Steam Cleaner' },
    { slug:'uv-mite-remover',      label:'除螨仪',         enLabel:'UV Mite Remover' },
    { slug:'window-cleaner-robot', label:'擦窗机器人',     enLabel:'Window Cleaner Robot' },
    { slug:'car-vacuum',           label:'车载吸尘器',      enLabel:'Car Vacuum Cleaner' },
    { slug:'tire-inflator',        label:'轮胎充气泵',      enLabel:'Digital Tire Inflator' },
    { slug:'coffee-machine',       label:'咖啡机',          enLabel:'Espresso Coffee Machine' },
    { slug:'upright-steam-mop',   label:'立式蒸汽拖把',    enLabel:'Upright Steam Mop' },
  ];

  var CERT_OPTS = ['CE','CB','ETL','FCC','RoHS','REACH','PSE','CCC','KC','BIS'];

  // 首页产品卡片数量。线上 9 个语种首页都只有 9 张卡片（旧文案写的 11 是错的），
  // 多渲染出来的空表单永远填不满，只会让人以为漏填。
  var HOME_CARD_SLOTS = 9;

  // ── State ──────────────────────────────────────────────────────
  var activeTab  = 'product';
  var currentCat  = null;
  var currentLang = null;
  var currentPid  = null;
  var homeSlots   = HOME_CARD_SLOTS;

  // ── HTML builders ──────────────────────────────────────────────
  // Escape for safe embedding into value="..." / textarea bodies.
  // Browsers decode entities on .value read, so the roundtrip stays raw.
  function escVal(s) {
    return String(s == null ? '' : s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function fieldHTML(label, id, type, value) {
    var v = escVal(value);
    var t = type === 'textarea'
      ? '<textarea id="' + id + '" rows="3">' + v + '</textarea>'
      : '<input id="' + id + '" type="text" value="' + v + '">';
    return '<div class="admin-field"><label>' + label + '</label>' + t + '</div>';
  }

  function fieldHTML_note(label, id, type, value, note) {
    var noteHtml = note ? '<div style="font-size:11px;color:#94A3B8;margin-top:3px;">' + note + '</div>' : '';
    var v = escVal(value);
    var t = type === 'textarea'
      ? '<textarea id="' + id + '" rows="3">' + v + '</textarea>'
      : '<input id="' + id + '" type="text" value="' + v + '">';
    return '<div class="admin-field" style="margin-bottom:18px;"><label>' + label + '</label>' + t + noteHtml + '</div>';
  }

  function makeSec(title, html) {
    var d = document.createElement('div');
    d.className = 'admin-sec';
    var h3 = document.createElement('h3');
    h3.textContent = title;
    d.appendChild(h3);
    if (typeof html === 'string') {
      d.innerHTML += html;
    } else if (html) {
      d.appendChild(html);
    }
    return d;
  }

  function makeGrid(html) {
    var d = document.createElement('div');
    d.className = 'admin-grid';
    d.innerHTML = html;
    return d;
  }

  // ── Product form ───────────────────────────────────────────────
  function renderProductForm(data) {
    var f = $('formArea');
    if (!f) return;
    f.innerHTML = '';

    // Basic
    f.appendChild(makeSec('基本信息', makeGrid(
      fieldHTML('产品名称 *', 'p-name', 'text', data.name || '') +
      fieldHTML('型号', 'p-model', 'text', data.model || '') +
      fieldHTML('产品标签语', 'p-tagline', 'text', data.tagline || '')
    )));

    // Specs
    f.appendChild(makeSec('核心参数', makeGrid(
      fieldHTML('功率', 'p-power', 'text', data.power || '') +
      fieldHTML('吸力', 'p-suction', 'text', data.suction || '') +
      fieldHTML('电池/续航', 'p-battery', 'text', data.battery || '') +
      fieldHTML('重量', 'p-weight', 'text', data.weight || '')
    )));

    // Pricing
    f.appendChild(makeSec('价格阶梯（USD）', makeGrid(
      fieldHTML('价格区间文字', 'p-price_display', 'text', data.price_display || '') +
      fieldHTML('MOQ（最小起订量）', 'p-moq', 'text', String(data.moq || 200)) +
      fieldHTML('FOB 单价（≥MOQ）', 'p-fob_price', 'text', data.fob_price || '') +
      fieldHTML('货币单位', 'p-currency', 'text', data.currency || 'USD')
    )));

    // SKU
    f.appendChild(makeSec('SKU 规格', makeGrid(
      fieldHTML('颜色（逗号分隔）', 'p-colors', 'text', (data.colors||[]).join(', ')) +
      fieldHTML('包装规格', 'p-package', 'text', data.package || '') +
      fieldHTML('单件体积/重量', 'p-dims', 'text', data.dims || '')
    )));

    // Certs
    var certDiv = document.createElement('div');
    certDiv.className = 'admin-field';
    certDiv.innerHTML = '<label>认证（多选）</label>';
    var certWrap = document.createElement('div');
    certWrap.id = 'p-certs';
    certWrap.style.cssText = 'display:flex;flex-wrap:wrap;gap:8px;margin-top:6px;';
    CERT_OPTS.forEach(function(c) {
      var lbl = document.createElement('label');
      lbl.style.cssText = 'display:inline-flex;align-items:center;gap:4px;font-size:13px;padding:5px 10px;border:1px solid #E2E8F0;border-radius:6px;cursor:pointer;background:#F8FAFC;';
      lbl.innerHTML = '<input type="checkbox" value="' + c + '" style="width:auto;">' + c;
      if (data.certifications && data.certifications.indexOf(c) > -1) {
        lbl.querySelector('input').checked = true;
      }
      certWrap.appendChild(lbl);
    });
    certDiv.appendChild(certWrap);
    f.appendChild(makeSec('认证', certDiv));

    // Media
    var imgSec = document.createElement('div');
    imgSec.className = 'admin-sec';
    imgSec.innerHTML = '<h3>产品图片</h3>' +
      '<div id="p-img-drop" class="admin-drop">📁 拖放图片到此处上传到 GitHub · 也可直接粘贴 URL（每行一个）</div>' +
      '<textarea id="p-img-urls" rows="3" placeholder="https://...&#10;https://..." style="width:100%;margin-top:8px;"></textarea>' +
      '<div id="p-img-preview" class="admin-imgs" style="margin-top:8px;"></div>';
    f.appendChild(imgSec);
    $('p-img-urls').value = (data.images||[]).join('\n');
    $('p-img-urls').addEventListener('input', renderImgPreview);
    renderImgPreview();
    // Drag-and-drop upload → GitHub Contents API
    var dropZone = $('p-img-drop');
    if (dropZone) {
      dropZone.addEventListener('dragover', function(e) {
        e.preventDefault(); e.stopPropagation();
        dropZone.style.background = '#DBEAFE';
      });
      dropZone.addEventListener('dragleave', function(e) {
        e.preventDefault(); e.stopPropagation();
        dropZone.style.background = '';
      });
      dropZone.addEventListener('drop', async function(e) {
        e.preventDefault(); e.stopPropagation();
        dropZone.style.background = '';
        var files = e.dataTransfer && e.dataTransfer.files;
        if (!files || files.length === 0) return;
        if (!getToken()) {
          setStatus('⚠ 上传需先设置 GitHub Token');
          if (confirm('上传需配置 GitHub Token。现在设置？')) {
            if (!(await promptForToken())) return;
          } else { return; }
        }
        setStatus('🚀 正在上传 ' + files.length + ' 张图片到 GitHub...');
        var urls = [];
        for (var i = 0; i < files.length; i++) {
          try {
            var url = await ghUploadImage(files[i]);
            urls.push(url);
          } catch (err) {
            setStatus('❌ ' + files[i].name + ' 上传失败：' + err.message);
            return;
          }
        }
        var existing = $('p-img-urls').value;
        var newVal = (existing ? existing + '\n' : '') + urls.join('\n');
        $('p-img-urls').value = newVal;
        renderImgPreview();
        autoSaveProduct();
        setStatus('✅ 已上传 ' + urls.length + ' 张图片到 GitHub · 记得点"保存草稿"部署');
      });
    }

    // Tags
    f.appendChild(makeSec('产品卖点（逗号分隔）', '<textarea id="p-tags" rows="2">' + escVal((data.tags||[]).join(', ')) + '</textarea>'));

    // Specs table
    var specsLines = (data.specs||[]).map(function(s){
      var k = s.key || (typeof s.label === 'object' ? (s.label.en || s.label.zh || '') : (s.label || ''));
      var v = (typeof s.value === 'object' ? (s.value.en || s.value.zh || '') : s.value) || '';
      return k + '|' + v;
    }).join('\n');
    f.appendChild(makeSec('规格参数表格（每行：参数|值）', '<textarea id="p-specs" rows="8" style="width:100%;font-family:monospace;" placeholder="Power|120W&#10;Suction|16KPa">' + escVal(specsLines) + '</textarea>'));

    // 详情页（图文混排）
    // 正文按语言合并（与 description 分开：description 是 Alibaba 风格的
    // 摘要文案，detail 是详情页的完整图文），图片不分语言（同 images）。
    var detailSec = document.createElement('div');
    detailSec.className = 'admin-sec';
    detailSec.innerHTML = '<h3>详情页（图文混排）</h3>' +
      '<p style="font-size:12.5px;color:#64748B;line-height:1.7;margin:0 0 10px;">' +
        '这段正文会显示在该产品的详情页上。留空则不显示这一节。<br>' +
        '<b>图文混排：</b>正文里写 <code>[[img:1]]</code> 会在该位置插入第 1 张详情图，' +
        '依次 <code>[[img:2]]</code>、<code>[[img:3]]</code>；没被引用的图片会自动排在正文后面。' +
        '空行分段。当前编辑语言：<b class="aqc-cur-lang"></b></p>' +
      '<div id="p-detail-drop" class="admin-drop">📁 拖放详情图到此处上传到 GitHub · 也可直接粘贴 URL（每行一个）</div>' +
      '<textarea id="p-detail-imgs" rows="3" placeholder="https://..." style="width:100%;margin-top:8px;"></textarea>' +
      '<div id="p-detail-preview" class="admin-imgs" style="margin-top:8px;"></div>' +
      '<textarea id="p-detail" rows="8" placeholder="详情正文，支持多段落。空行分段。">' +
      '</textarea>';
    f.appendChild(detailSec);
    $('p-detail').value = langText(data.detail);
    $('p-detail-imgs').value = (data.detail_images||[]).join('\n');
    $('p-detail-imgs').addEventListener('input', function(){ renderImgPreviewOf('p-detail-imgs', 'p-detail-preview'); });
    renderImgPreviewOf('p-detail-imgs', 'p-detail-preview');
    wireDropUpload('p-detail-drop', 'p-detail-imgs', 'p-detail-preview');
    var langBadge = detailSec.querySelector('.aqc-cur-lang');
    if (langBadge) langBadge.textContent = currentLang || 'en';

    // Packaging
    f.appendChild(makeSec('包装内容（逗号分隔）', '<textarea id="p-packaging" rows="2">' + escVal(Array.isArray(data.packaging) ? data.packaging.join(', ') : (data.packaging || '')) + '</textarea>'));

    // Applications
    f.appendChild(makeSec('适用场景（逗号分隔）', '<textarea id="p-applications" rows="2">' + escVal(Array.isArray(data.applications) ? data.applications.join(', ') : (data.applications || '')) + '</textarea>'));

    // Supplier
    f.appendChild(makeSec('供应商信息', makeGrid(
      fieldHTML('公司名', 'p-company', 'text', data.company||'') +
      fieldHTML('地址', 'p-address', 'text', data.address||'')
    )));

    // Customization
    f.appendChild(makeSec('定制能力', makeGrid(
      fieldHTML('Logo 定制', 'p-logo', 'text', data.logo||'') +
      fieldHTML('包装定制', 'p-packaging_custom', 'text', data.packaging_custom||'')
    )));

    // Description
    f.appendChild(makeSec('产品描述（Alibaba 风格英文）', '<textarea id="p-desc" rows="5">' + escVal(data.description) + '</textarea>'));

    // Actions
    var actions = document.createElement('div');
    actions.style.marginTop = '24px';
    actions.className = 'admin-actions';
    actions.innerHTML =
      '<button class="btn btn-outline" id="p-save">💾 保存草稿（仅本机）</button>' +
      '<button class="btn btn-primary" id="p-publish">🚀 发布到线上</button>' +
      '<button class="btn btn-outline" id="p-export">📤 导出 JSON</button>' +
      '<button class="btn btn-outline" id="p-import">📥 导入 JSON</button>' +
      '<button class="btn btn-outline" id="p-reset">🗑 清空</button>';
    var tipP = document.createElement('div');
    tipP.style.cssText = 'margin-top:10px;font-size:12px;color:#64748B;line-height:1.6;';
    tipP.textContent = '保存草稿只写进本浏览器；「🚀 发布到线上」会把内容提交到 GitHub 仓库，'
      + 'GitHub Pages 约 1-2 分钟后重建站点。';
    actions.appendChild(tipP);
    f.appendChild(actions);

    $('p-save').onclick   = saveProduct;
    $('p-publish').onclick = publishProduct;
    $('p-export').onclick = exportProduct;
    $('p-import').onclick = function() { $('importFile').click(); };
    $('p-reset').onclick  = function() { if(confirm('确认清空？')) renderProductForm({}); };
    $('importFile').onchange = importProduct;

    qsa('#formArea input, #formArea textarea').forEach(function(el){ el.addEventListener('input', autoSaveProduct); });
  }

  // 多语言字段取当前语言（表单是单语言编辑，保存时再合并回去）
  function langText(v) {
    if (v == null) return '';
    if (typeof v === 'string') return v;
    return v[currentLang] || v.en || v.zh || '';
  }

  // 通用缩略图预览：删除按钮会同步回写对应 textarea
  function renderImgPreviewOf(taId, prevId) {
    var container = $(prevId);
    if (!container) return;
    container.innerHTML = '';
    var urls = ($(taId).value||'').split('\n').filter(function(u){return u.trim();});
    urls.forEach(function(url, idx) {
      var div = document.createElement('div');
      div.className = 'admin-img';
      div.style.cssText = 'position:relative;display:inline-block;';
      var img = document.createElement('img');
      img.src = url.trim();
      img.style.cssText = 'max-width:120px;max-height:90px;border-radius:4px;';
      img.onerror = function(){ this.parentElement.style.opacity='0.3'; };
      var rm = document.createElement('button');
      rm.className = 'x';
      rm.textContent = '×';
      rm.style.cssText = 'position:absolute;top:2px;right:2px;background:rgba(0,0,0,0.5);color:#fff;border:none;border-radius:50%;width:20px;height:20px;cursor:pointer;';
      rm.onclick = function() {
        var lines = ($(taId).value||'').split('\n');
        lines.splice(idx, 1);
        $(taId).value = lines.join('\n');
        renderImgPreviewOf(taId, prevId);
        autoSaveProduct();
      };
      div.appendChild(img);
      div.appendChild(rm);
      container.appendChild(div);
    });
  }

  // 通用拖拽上传：把图片推到 GitHub，回填 URL 到目标 textarea
  function wireDropUpload(dropId, taId, prevId) {
    var dropZone = $(dropId);
    if (!dropZone) return;
    dropZone.addEventListener('dragover', function(e) {
      e.preventDefault(); e.stopPropagation();
      dropZone.style.background = '#DBEAFE';
    });
    dropZone.addEventListener('dragleave', function(e) {
      e.preventDefault(); e.stopPropagation();
      dropZone.style.background = '';
    });
    dropZone.addEventListener('drop', async function(e) {
      e.preventDefault(); e.stopPropagation();
      dropZone.style.background = '';
      var files = Array.prototype.slice.call(e.dataTransfer.files || []);
      var images = files.filter(function(f){ return /^image\//.test(f.type); });
      if (!images.length) { setStatus('⚠ 请拖入图片文件'); return; }
      dropZone.classList.add('busy');
      setStatus('📤 正在上传 ' + images.length + ' 张图片…');
      for (var i = 0; i < images.length; i++) {
        try {
          var url = await ghUploadImage(images[i]);
          var cur = $(taId).value.replace(/\s+$/, '');
          $(taId).value = cur ? cur + '\n' + url : url;
          renderImgPreviewOf(taId, prevId);
          autoSaveProduct();
          setStatus('✅ 已上传：' + url);
        } catch (err) {
          setStatus('❌ 上传失败：' + (err && err.message ? err.message : err));
        }
      }
      dropZone.classList.remove('busy');
    });
  }

  function renderImgPreview() {
    renderImgPreviewOf('p-img-urls', 'p-img-preview');
  }

  function collectProduct() {
    var specs_raw = ($('p-specs').value||'').split('\n').filter(Boolean);
    var specs = specs_raw.map(function(l){
      var p = l.split('|');
      return { key: (p[0]||'').trim(), value: (p[1]||'').trim() };
    }).filter(function(s){ return s.key && s.value; });
    var certs = [].slice.call(qsa('#p-certs input:checked')).map(function(cb){ return cb.value; });
    var images = ($('p-img-urls').value||'').split('\n').filter(function(u){return u.trim();});
    function val(id) { var e = $(id); return e ? e.value.trim() : ''; }
    return {
      id:           currentPid || ('p-' + Date.now()),
      slug:         currentCat,
      lang:         currentLang,
      name:         val('p-name'),
      model:        val('p-model'),
      tagline:      val('p-tagline'),
      power:        val('p-power'),
      suction:      val('p-suction'),
      battery:      val('p-battery'),
      weight:       val('p-weight'),
      price_display: val('p-price_display'),
      moq:          parseInt(val('p-moq')) || 200,
      fob_price:    val('p-fob_price'),
      currency:     val('p-currency'),
      colors:       val('p-colors').split(',').map(function(s){return s.trim();}).filter(Boolean),
      package:      val('p-package'),
      dims:         val('p-dims'),
      tags:         val('p-tags').split(',').map(function(s){return s.trim();}).filter(Boolean),
      specs:        specs,
      certifications: certs,
      packaging:    val('p-packaging').split(',').map(function(s){return s.trim();}).filter(Boolean),
      applications:  val('p-applications').split(',').map(function(s){return s.trim();}).filter(Boolean),
      company:      val('p-company'),
      address:      val('p-address'),
      logo:         val('p-logo'),
      packaging_custom: val('p-packaging_custom'),
      description:  val('p-desc'),
      detail:       val('p-detail'),
      detail_images: ($('p-detail-imgs').value||'').split('\n').map(function(u){return u.trim();}).filter(Boolean),
      images:       images,
      updated_at:   new Date().toISOString()
    };
  }

  // ① 只存本机草稿
  function saveProduct() {
    var data = collectProduct();
    localStorage.setItem(sk('product', data.lang, currentCat), JSON.stringify(data));
    var noSlot = noSlotFilled(data);
    setStatus('💾 草稿已保存（只在本机）· 要让网站生效请点「🚀 发布到线上」'
      + (noSlot.length ? ' · 注意：' + noSlot.join(' / ') + ' 站点暂无展示位' : ''));
  }

  // ② 推到 GitHub → GitHub Pages 自动重建
  async function publishProduct() {
    if (!currentCat) { setStatus('❌ 请先在左侧选择一个产品类目'); return; }
    if (!(await ensureToken())) return;
    var data = collectProduct();
    localStorage.setItem(sk('product', data.lang, currentCat), JSON.stringify(data));
    var cat = currentCat;
    var lang = data.lang;
    var path = 'data/products/' + cat + '.json';
    var noSlot = noSlotFilled(data);
    var note = noSlot.length ? '（站点暂无展示位：' + noSlot.join(' / ') + '）' : '';
    try {
      // Read the current file from repo main (source of truth) so the merge
      // below preserves languages and fields this form does not manage.
      setStatus('🔄 正在读取仓库里的 ' + path + ' ...');
      var res = await fetch('https://raw.githubusercontent.com/' + AQC_REPO + '/' + AQC_BRANCH + '/' + path + '?t=' + Date.now());
      var existing = res.ok ? await res.json() : null;
      var merged = mergeProductIntoSchema(existing, lang, data);
      await publishJson(path, JSON.stringify(merged, null, 2), 'admin: update ' + cat + ' (' + lang + ')');
      if (note) setStatus('✅ 已发布 ' + note);
    } catch (err) {
      setStatus('❌ 发布失败：' + err.message);
    }
  }

  // ── Schema-safe merge helpers ──────────────────────────────────
  // The repo's product JSON is multilingual ({en:..., zh:...}) and carries
  // fields (highlights, sku, packaging, customization) this simple form
  // never edits. Overwriting products[0] with the flat form payload used to
  // destroy all of that. These helpers merge only what the form manages.

  // Update one language of an {en,zh} field, preserving the others.
  function mergeLangField(existing, lang, value) {
    if (existing && typeof existing === 'object' && !Array.isArray(existing)) {
      var out = {};
      for (var k in existing) out[k] = existing[k];
      if (value) out[lang] = value;
      return out;
    }
    // 旧值是个扁平字符串：多半是先在英文站建档留下的。把它当作 en 保留下来，
    // 否则这一次编辑会把英文原文换成当前语言的文字。
    if (typeof existing === 'string' && existing) {
      var keep = { en: existing };
      keep[lang] = value;
      return keep;
    }
    // 完全没有旧值：英文仍存扁平串（前端 pick() 两种形状都认）；
    // 其它语言只写自己，绝不把外文塞进 en 里。
    if (lang === 'en') return value;
    var o = {};
    o[lang] = value;
    return o;
  }

  // Merge form spec rows (key|value per line) into existing specs by index,
  // per language. Existing rows the form no longer has are kept as-is.
  function mergeSpecs(existing, lang, formSpecs) {
    var ex = Array.isArray(existing) ? existing : [];
    var n = Math.max(ex.length, formSpecs.length);
    var out = [];
    for (var i = 0; i < n; i++) {
      var e = ex[i], f = formSpecs[i];
      if (!f) { if (e) out.push(e); continue; }
      var lab, val, k;
      if (e && typeof e.label === 'object') { lab = {}; for (k in e.label) lab[k] = e.label[k]; lab[lang] = f.key; }
      else if (e && e.label !== undefined) { lab = (lang === 'en') ? f.key : e.label; }
      else { lab = {}; lab[lang] = f.key; }
      if (e && typeof e.value === 'object') { val = {}; for (k in e.value) val[k] = e.value[k]; val[lang] = f.value; }
      else if (e && e.value !== undefined) { val = (lang === 'en') ? f.value : e.value; }
      else { val = {}; val[lang] = f.value; }
      out.push({ label: lab, value: val });
    }
    return out;
  }

  // ── 仓库真实 schema 的写入助手 ────────────────────────────────
  // 产品 JSON 里没有 power/suction/battery/weight 这类扁平字段，它们都活在
  // specs / quick_specs 的某一行里（label 是多语言对象）。所以表单的"核心
  // 参数"不能另起炉灶写顶层键，必须回写进对应的那一行，否则永远不会显示。

  function labelText(lab) {
    if (lab && typeof lab === 'object') return String(lab.en || lab.zh || '');
    return String(lab == null ? '' : lab);
  }

  // 按英文标签定位一行并写入当前语言；找不到就追加。
  // onlyIfExists=true 时只更新已有行（用于 quick_specs，避免把整份 specs 灌进首页摘要）。
  function upsertSpecRow(list, lang, labelEn, matcher, value, onlyIfExists) {
    var arr = Array.isArray(list) ? list.slice() : [];
    var hit = null;
    for (var i = 0; i < arr.length; i++) {
      if (matcher.test(labelText(arr[i] && arr[i].label).trim())) { hit = arr[i]; break; }
    }
    if (!hit) {
      if (onlyIfExists) return arr;
      var lab = { en: labelEn };
      lab[lang] = labelEn;
      var nv = {}; nv[lang] = value;
      arr.push({ label: lab, value: nv });
      return arr;
    }
    var ex = hit.label, lab2 = {}, k;
    if (ex && typeof ex === 'object') { for (k in ex) lab2[k] = ex[k]; }
    else if (typeof ex === 'string' && ex) { lab2.en = ex; }
    lab2[lang] = labelEn;
    var ev = hit.value, val2 = {};
    if (ev && typeof ev === 'object' && !Array.isArray(ev)) { for (k in ev) val2[k] = ev[k]; }
    else if (typeof ev === 'string' && ev) { val2.en = ev; }
    val2[lang] = value;
    hit.label = lab2; hit.value = val2;
    return arr;
  }

  // 核心参数：specs 一定写；quick_specs 只在已有同名行时同步。
  function setCoreSpec(p, lang, labelEn, matcher, value) {
    if (!value) return;
    p.specs = upsertSpecRow(p.specs, lang, labelEn, matcher, value, false);
    if (Array.isArray(p.quick_specs)) {
      p.quick_specs = upsertSpecRow(p.quick_specs, lang, labelEn, matcher, value, true);
    }
  }

  // 价格区间文字（"$54.00 - 64.00" / "54-64"）→ price_indicator {min,max}
  function parsePriceRange(s) {
    var nums = String(s).match(/\d+(?:\.\d+)?/g);
    if (!nums) return null;
    var vals = nums.map(Number).filter(function (n) { return n > 0; });
    if (!vals.length) return null;
    return { min: Math.min.apply(null, vals), max: Math.max.apply(null, vals) };
  }

  function truthy(v) {
    return /^(yes|true|1|支持|可|可以|on)$/i.test(String(v || '').trim());
  }

  // SKU 规格组（颜色/电压…）：按组名定位，整组替换 values
  function upsertSkuGroup(p, lang, groupEn, matcher, values) {
    var arr = Array.isArray(p.sku) ? p.sku.slice() : [];
    var hit = null;
    for (var i = 0; i < arr.length; i++) {
      if (matcher.test(labelText(arr[i] && arr[i].name).trim())) { hit = arr[i]; break; }
    }
    if (!hit) {
      var nm = { en: groupEn }; nm[lang] = groupEn;
      arr.push({ name: nm, values: values });
      return arr;
    }
    var ex = hit.name, nm2 = {}, k;
    if (ex && typeof ex === 'object') { for (k in ex) nm2[k] = ex[k]; }
    else if (typeof ex === 'string' && ex) { nm2.en = ex; }
    nm2[lang] = groupEn;
    hit.name = nm2;
    hit.values = values;
    return arr;
  }

  // 表单字段 → 落库位置。用于"未落库字段"告警：任何出现在这里的键都算已处理。
  var PRODUCT_FIELD_TARGETS = [
    'id', 'slug', 'lang', 'updated_at',
    'name', 'tagline', 'description', 'detail', 'detail_images',
    'model', 'power', 'suction', 'battery', 'weight',
    'price_display', 'fob_price', 'currency', 'moq',
    'colors', 'package', 'dims', 'tags',
    'specs', 'certifications', 'images',
    'packaging', 'applications', 'company', 'address',
    'logo', 'packaging_custom'
  ];

  // 站点上还没有展示位的字段：仍会存进 JSON（不丢数据），但要明确告诉运营。
  var PRODUCT_FIELDS_NO_SLOT = ['tags', 'company', 'address', 'packaging'];

  function mergeProductIntoSchema(existing, lang, form) {
    var container = (existing && typeof existing === 'object' && !Array.isArray(existing)) ? existing : {};
    var list = Array.isArray(container.products) ? container.products : [];
    var p = list.length ? list[0] : {};

    // —— 多语言字段 ——
    if (form.name)        p.name = mergeLangField(p.name, lang, form.name);
    if (form.tagline)     p.tagline = mergeLangField(p.tagline, lang, form.tagline);
    if (form.description) p.description = mergeLangField(p.description, lang, form.description);
    // 详情页正文按语言合并；详情图与 images 一样是语言无关的，直接覆盖。
    // 空值不覆盖：清空一栏不应该抹掉已有内容。
    if (form.detail) p.detail = mergeLangField(p.detail, lang, form.detail);
    if (form.detail_images && form.detail_images.length) p.detail_images = form.detail_images;

    // —— 规格参数表格（按行索引合并，保留表单里没有的行） ——
    if (form.specs && form.specs.length) p.specs = mergeSpecs(p.specs, lang, form.specs);

    // —— 核心参数：回写进 specs / quick_specs 对应那一行 ——
    setCoreSpec(p, lang, 'Model', /^model$/i, form.model);
    setCoreSpec(p, lang, 'Motor Power', /(motor\s*)?power|^w$/i, form.power);
    setCoreSpec(p, lang, 'Suction Power', /suction/i, form.suction);
    setCoreSpec(p, lang, 'Battery', /^battery$/i, form.battery);
    setCoreSpec(p, lang, 'Net Weight', /weight/i, form.weight);

    // —— 价格 ——
    if (form.moq) p.moq = { value: form.moq, unit: (p.moq && p.moq.unit) || 'pieces' };
    if (form.price_display) {
      var range = parsePriceRange(form.price_display);
      if (range) {
        p.price_indicator = p.price_indicator || {};
        p.price_indicator.min = range.min;
        p.price_indicator.max = range.max;
      }
    }
    if (form.fob_price) {
      var tiers = Array.isArray(p.price_ladder) ? p.price_ladder.slice() : [];
      var price = parseFloat(String(form.fob_price).replace(/[^0-9.]/g, ''));
      if (!isNaN(price)) {
        var moq = form.moq || (p.moq && p.moq.value) || 1;
        var idx = -1;
        for (var ti = 0; ti < tiers.length; ti++) {
          var t = tiers[ti] || {};
          var lo = t.min == null ? 1 : t.min;
          var hi = (t.max == null) ? Infinity : t.max;
          if (moq >= lo && moq <= hi) { idx = ti; break; }
        }
        if (idx === -1 && tiers.length) idx = tiers.length - 1;
        if (idx === -1) tiers.push({ min: moq, max: null, price: price });
        else tiers[idx].price = price;
        p.price_ladder = tiers;
      }
    }
    if (form.currency) {
      p.price_indicator = p.price_indicator || {};
      p.price_indicator.currency = String(form.currency).toUpperCase();
    }

    // —— SKU 规格：颜色 ——
    if (form.colors && form.colors.length) {
      p.sku = upsertSkuGroup(p.sku, lang, 'Colour', /^(colour|color)$/i,
        form.colors.map(function (c) { return { name: c }; }));
    }

    // —— 包装 / 定制 ——
    // packaging 在仓库里是对象 {unit, ctn_size, ...}，详情页按对象读取；
    // 表单给的是字符串，所以写子键，绝不能整块替换成字符串。
    if (form.package || form.dims) {
      p.packaging = (p.packaging && typeof p.packaging === 'object') ? p.packaging : {};
      if (form.package) p.packaging.unit = form.package;
      if (form.dims)    p.packaging.ctn_size = form.dims;
    }
    if (form.packaging && form.packaging.length) {
      p.packaging = (p.packaging && typeof p.packaging === 'object') ? p.packaging : {};
      p.packaging.includes = form.packaging;
    }
    if (form.logo || form.packaging_custom) {
      p.customization = (p.customization && typeof p.customization === 'object') ? p.customization : {};
      // 详情页判断的是 customization.logo/package 是否 === false
      if (form.logo)             p.customization.logo = truthy(form.logo);
      if (form.packaging_custom) p.customization.package = truthy(form.packaging_custom);
    }

    // —— 适用场景（详情页按逗号切分渲染） ——
    if (form.applications && form.applications.length) {
      p.applications = mergeLangField(p.applications, lang, form.applications.join(', '));
    }

    // —— 尚无展示位的字段：照样存，避免"填了白填" ——
    if (form.tags && form.tags.length)     p.tags = form.tags;
    if (form.company)                      p.company = form.company;
    if (form.address)                      p.address = form.address;

    // —— 语言无关数组 ——
    if (form.images && form.images.length) p.images = form.images;
    if (form.certifications && form.certifications.length) p.certifications = form.certifications;

    // —— 漏字段告警：以后再加表单字段却忘了映射，控制台会立刻报出来 ——
    var known = Object.keys(form || {});
    var dropped = known.filter(function (k) { return PRODUCT_FIELD_TARGETS.indexOf(k) === -1; });
    if (dropped.length) console.warn('[AQC] 未落库的产品字段:', dropped);

    if (!list.length) container.products = [p];
    return container;
  }

  // 站点目前没有展示位、但已经存进 JSON 的字段（填了不会立刻显示出来）
  function noSlotFilled(form) {
    return PRODUCT_FIELDS_NO_SLOT.filter(function (k) {
      var v = form && form[k];
      return Array.isArray(v) ? v.length > 0 : !!v;
    });
  }

  function autoSaveProduct() {
    var data = collectProduct();
    localStorage.setItem(sk('product', data.lang, currentCat), JSON.stringify(data));
  }

  function exportProduct() {
    var data = collectProduct();
    var blob = new Blob([JSON.stringify(data, null, 2)], {type:'application/json'});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = (data.slug||'product') + '-' + (data.lang||'en') + '.json';
    a.click();
    setStatus('📤 已导出 JSON');
  }

  function importProduct() {
    var file = $('importFile').files[0];
    if (!file) return;
    var reader = new FileReader();
    reader.onload = function(e) {
      try {
        var d = JSON.parse(e.target.result);
        if (d.hero || d.products) {
          importHomepage(d);
        } else {
          if (d.slug) { currentCat = d.slug; }
          renderProductForm(d);
          saveProduct();
          setStatus('📥 已导入产品 JSON · 检查无误后点「🚀 发布到线上」');
        }
      } catch(err) {
        setStatus('❌ 解析失败：' + err.message);
      }
    };
    reader.readAsText(file);
    $('importFile').value = '';
  }

  // ── Homepage form ───────────────────────────────────────────────
  function renderHomeEditor(data, lang) {
    lang = lang || 'en';
    var f = $('formArea');
    if (!f) return;
    f.innerHTML = '';

    var h = data || {};
    var hero = h.hero || {};
    var products = h.products || [];
    var contact = h.contact || {};
    var footer = h.footer || {};

    // Hero
    var heroDiv = document.createElement('div');
    heroDiv.style.maxWidth = '680px';
    heroDiv.innerHTML =
      fieldHTML_note('徽章文字', 'h-badge', 'text', hero.badge||'', '如：🇨🇳 OEM / ODM Manufacturer · Since 2015') +
      fieldHTML_note('主标题 H1（保留 &lt;br&gt; 和 &lt;span&gt; 标签）', 'h-h1', 'textarea', hero.h1||'', '如：Smart Cleaning Appliances&lt;br&gt;Built for &lt;span&gt;Global Markets&lt;/span&gt;') +
      fieldHTML_note('副标题段落', 'h-sub', 'textarea', hero.sub||'') +
      fieldHTML('主按钮文字', 'h-btn1-text', 'text', hero.btn_primary_text||'') +
      fieldHTML('主按钮链接', 'h-btn1-href', 'text', hero.btn_primary_href||'#quote') +
      fieldHTML('次按钮文字', 'h-btn2-text', 'text', hero.btn_outline_text||'') +
      fieldHTML('次按钮链接', 'h-btn2-href', 'text', hero.btn_outline_href||'#products');
    f.appendChild(makeSec('🏠 Hero 区域', heroDiv.innerHTML));

    // Products
    // 按线上真实的卡片数渲染（旧版本硬编码 11，而首页只有 9 张卡片）
    homeSlots = Math.max(products.length, HOME_CARD_SLOTS);
    var prodHTML = '<div id="h-prod-list">';
    for (var pi = 0; pi < homeSlots; pi++) {
      var prod = products[pi] || {};
      var pid = prod.id || ('p'+(pi+1));
      prodHTML += '<div style="border:1px solid #E2E8F0;border-radius:8px;padding:14px;margin-bottom:14px;background:#F8FAFC;">' +
        '<div style="font-weight:700;margin-bottom:10px;color:#2563EB;">产品 ' + (pi+1) + ': ' + escVal(prod.name || '?') + '</div>' +
        '<input type="hidden" id="hp-id-' + pi + '" value="' + pid + '">' +
        '<div class="admin-grid">' +
        fieldHTML('名称', 'hp-name-'+pi, 'text', prod.name||'') +
        fieldHTML('Slug（对应类目路径）', 'hp-slug-'+pi, 'text', prod.slug||'') +
        fieldHTML('描述', 'hp-desc-'+pi, 'textarea', prod.desc||'') +
        fieldHTML('图片路径', 'hp-img-'+pi, 'text', prod.img||'') +
        fieldHTML('按钮文字', 'hp-btn-'+pi, 'text', prod.btn_text||'') +
        fieldHTML('按钮链接', 'hp-href-'+pi, 'text', prod.btn_href||'') +
        fieldHTML('标签（逗号分隔）', 'hp-tags-'+pi, 'text', (prod.tags||[]).join(', ')) +
        '</div></div>';
    }
    prodHTML += '</div>';

    var actionBar = '<div style="margin-top:20px;">' +
      '<button class="btn btn-outline" id="h-save">💾 保存草稿（仅本机）</button> ' +
      '<button class="btn btn-primary" id="h-publish">🚀 发布到线上</button> ' +
      '<button class="btn btn-outline" id="h-export">📤 导出 JSON</button> ' +
      '<button class="btn btn-outline" id="h-import-home">📥 导入 JSON</button> ' +
      // 后台部署在 *.workbuddy.host，根路径 '/' 不是站点首页 —— 必须写全域名
      '<a class="btn btn-outline" id="h-preview" href="https://www.hkdmj.net/' + lang + '/?v=' + Date.now() + '" target="_blank" style="display:inline-block;text-decoration:none;">🔍 预览首页</a>' +
      '</div>' +
      '<div style="margin-top:20px;padding:14px;background:#EFF6FF;border-radius:8px;font-size:12px;color:#1E40AF;line-height:1.7;">' +
      '<b>📝 使用流程：</b><br>' +
      '1. 选语言 → 编辑内容<br>' +
      '2. 「💾 保存草稿」= 只存到本机浏览器<br>' +
      '3. 「🚀 发布到线上」= 提交到 GitHub 仓库的 <code>/data/pages/home/' + lang + '.json</code>，GitHub Pages 约 1-2 分钟生效<br>' +
      '4. 用「🔍 预览首页」验证（带时间戳参数，穿透缓存）' +
      '</div>';
    f.appendChild(makeSec('📦 产品卡片（' + homeSlots + ' 个）', prodHTML + actionBar));

    // Contact
    var contactDiv = document.createElement('div');
    contactDiv.style.maxWidth = '680px';
    contactDiv.innerHTML =
      fieldHTML('联系区标题', 'h-c-h2', 'text', contact.h2||'') +
      fieldHTML('邮箱', 'h-c-email', 'text', contact.email||'') +
      fieldHTML('电话', 'h-c-phone', 'text', contact.phone||'') +
      fieldHTML('WhatsApp（数字，无+号）', 'h-c-whatsapp', 'text', contact.whatsapp||'') +
      fieldHTML('地址', 'h-c-address', 'text', contact.address||'') +
      fieldHTML('营业时间', 'h-c-hours', 'text', contact.hours||'');
    f.appendChild(makeSec('📞 联系区域', contactDiv.innerHTML));

    // Footer
    var footerDiv = document.createElement('div');
    footerDiv.style.maxWidth = '680px';
    footerDiv.innerHTML =
      fieldHTML('公司名称', 'h-f-name', 'text', footer.company_name||'') +
      fieldHTML('公司描述', 'h-f-desc', 'textarea', footer.description||'') +
      fieldHTML('页脚邮箱', 'h-f-email', 'text', footer.email||'') +
      fieldHTML('页脚电话', 'h-f-phone', 'text', footer.phone||'');
    f.appendChild(makeSec('🔻 页脚', footerDiv.innerHTML));

    // Auto-save
    qsa('#formArea input, #formArea textarea').forEach(function(el){ el.addEventListener('input', autoSaveHome); });

    // Wire buttons
    $('h-save').onclick = saveHome;
    $('h-publish').onclick = publishHome;
    $('h-export').onclick = exportHome;
    $('h-import-home').onclick = function() { $('importFile').click(); };
  }

  function collectHome() {
    var products = [];
    for (var pi = 0; pi < homeSlots; pi++) {
      var tagsVal = $('hp-tags-'+pi) ? $('hp-tags-'+pi).value : '';
      var row = {
        id:       ($('hp-id-'+pi) ? $('hp-id-'+pi).value : '') || ('p'+(pi+1)),
        name:     ($('hp-name-'+pi) ? $('hp-name-'+pi).value : '').trim(),
        slug:     ($('hp-slug-'+pi) ? $('hp-slug-'+pi).value : '').trim(),
        desc:     ($('hp-desc-'+pi) ? $('hp-desc-'+pi).value : '').trim(),
        img:      ($('hp-img-'+pi) ? $('hp-img-'+pi).value : '').trim(),
        btn_text: ($('hp-btn-'+pi) ? $('hp-btn-'+pi).value : '').trim(),
        btn_href: ($('hp-href-'+pi) ? $('hp-href-'+pi).value : '').trim(),
        tags:     tagsVal.split(',').map(function(s){return s.trim();}).filter(Boolean)
      };
      // 整行留空 = 这张卡片不要了，别把空壳写进 JSON
      if (!row.name && !row.desc && !row.img && !row.btn_text) continue;
      products.push(row);
    }
    function hval(id) { var e = $(id); return e ? e.value.trim() : ''; }
    return {
      hero: {
        badge:             hval('h-badge'),
        h1:                hval('h-h1'),
        sub:               hval('h-sub'),
        btn_primary_text:   hval('h-btn1-text'),
        btn_primary_href:   hval('h-btn1-href'),
        btn_outline_text:   hval('h-btn2-text'),
        btn_outline_href:   hval('h-btn2-href')
      },
      products: products,
      contact: {
        h2:       hval('h-c-h2'),
        email:    hval('h-c-email'),
        phone:    hval('h-c-phone'),
        whatsapp: hval('h-c-whatsapp'),
        address:  hval('h-c-address'),
        hours:    hval('h-c-hours')
      },
      footer: {
        company_name: hval('h-f-name'),
        description:  hval('h-f-desc'),
        email:        hval('h-f-email'),
        phone:        hval('h-f-phone')
      }
    };
  }

  // ① 只存本机草稿
  function saveHome() {
    var data = collectHome();
    var lang = $('langSel') ? $('langSel').value : 'en';
    localStorage.setItem(sk('home', lang), JSON.stringify(data));
    setStatus('💾 首页草稿已保存（只在本机）· 要让网站生效请点「🚀 发布到线上」');
  }

  // ② 推到 GitHub
  async function publishHome() {
    if (!(await ensureToken())) return;
    var data = collectHome();
    var lang = $('langSel') ? $('langSel').value : 'en';
    localStorage.setItem(sk('home', lang), JSON.stringify(data));
    try {
      await publishJson('data/pages/home/' + lang + '.json',
        JSON.stringify(data, null, 2), 'admin: update home-' + lang);
    } catch (err) { /* publishJson 已经提示过了 */ }
  }

  function autoSaveHome() {
    var data = collectHome();
    var lang = $('langSel') ? $('langSel').value : 'en';
    localStorage.setItem(sk('home', lang), JSON.stringify(data));
  }

  function exportHome() {
    var data = collectHome();
    var lang = $('langSel') ? $('langSel').value : 'en';
    var blob = new Blob([JSON.stringify(data, null, 2)], {type:'application/json'});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'home-' + lang + '.json';
    a.click();
    setStatus('📤 已导出 home-' + lang + '.json');
  }

  function importHomepage(data) {
    if (!confirm('确认导入首页 JSON？将覆盖当前内容。')) return;
    var lang = $('langSel') ? $('langSel').value : 'en';
    renderHomeEditor(data, lang);
    saveHome();
    setStatus('📥 已导入首页 JSON');
  }

  // ── Load / fetch ───────────────────────────────────────────────
  function loadProduct(cat, lang) {
    cat = cat || currentCat || 'handheld-vacuum';
    lang = lang || $('langSel').value || 'en';
    currentCat = cat;
    currentLang = lang;

    // Restore from localStorage
    var stored = localStorage.getItem(sk('product', lang, cat));
    if (stored) {
      try {
        var d = JSON.parse(stored);
        renderProductForm(d);
        setStatus('📂 已加载本地草稿（' + lang + '/' + cat + '）');
        return;
      } catch(e) {}
    }

    // Fetch from live site
    setStatus('⏳ 正在从线上拉取...');
    var x = new XMLHttpRequest();
    x.open('GET', '/data/products/' + cat + '.json?v=' + Date.now(), true);
    x.onload = function() {
      if (x.status === 200) {
        try {
          var data = JSON.parse(x.responseText);
          var prod = (data.products && data.products[0]) || {};
          // Helper: pick language from {en:..., zh:...} object
          function pl(obj, lang) {
            if (!obj || typeof obj !== 'object') return obj || '';
            if (obj[lang]) return obj[lang];
            return obj.en || obj.zh || '';
          }
          // Helper: array or string to string
          function arrStr(v) {
            if (Array.isArray(v)) return v.join(', ');
            if (typeof v === 'string') return v;
            if (v && typeof v === 'object') return pl(v, lang);
            return '';
          }
          // Helper: specs array [{label:{en,zh}, value}] -> [{key,value}]
          function normSpecs(arr) {
            if (!Array.isArray(arr)) return [];
            return arr.map(function(s) {
              return {
                key:   typeof s.label === 'object' ? pl(s.label, lang) : (s.label || s.key || ''),
                value: typeof s.value === 'object' ? pl(s.value, lang) : (s.value || '')
              };
            }).filter(function(s){ return s.key && s.value; });
          }
          // Flatten product into admin form shape
          var entry = {
            id:            prod.id || '',
            slug:          cat,
            lang:          lang,
            name:          pl(prod.name, lang),
            model:         prod.model || (prod.id ? prod.id.toUpperCase() : ''),
            tagline:       pl(prod.tagline, lang),
            power:         '',
            suction:       '',
            battery:       '',
            weight:        '',
            price_display: (prod.price_indicator ? '$' + prod.price_indicator.min + ' - $' + prod.price_indicator.max : '') || arrStr(prod.price_display),
            moq:           (prod.moq && prod.moq.value) ? prod.moq.value : (prod.moq || 200),
            fob_price:     (prod.price_ladder && prod.price_ladder[0]) ? ('$' + prod.price_ladder[0].price) : '',
            currency:      (prod.price_indicator && prod.price_indicator.currency) || 'USD',
            colors:        [],
            package:       (prod.packaging && typeof prod.packaging === 'object') ? (prod.packaging.unit + ', ' + prod.packaging.ctn_size + ', ' + prod.packaging.ctn_qty) : (prod.package || ''),
            dims:          (prod.packaging && prod.packaging.ctn_size) || '',
            tags:          [],
            specs:         normSpecs(prod.specs || prod.quick_specs || []),
            certifications: prod.certifications || [],
            packaging:    [],
            applications: arrStr(prod.applications),
            company:      '',
            address:      (prod.ship_from ? pl(prod.ship_from, lang) : ''),
            logo:         (prod.customization && prod.customization.logo) ? 'Yes' : 'No',
            packaging_custom: (prod.customization && prod.customization.package) ? 'Yes' : 'No',
            description:  pl(prod.description, lang),
            images:       prod.images || []
          };
          // Extract power/suction/battery/weight from specs
          (prod.specs || []).forEach(function(s) {
            var raw = (typeof s.label === 'object') ? pl(s.label, 'en') : (s.label || '');
            var label = String(raw).toLowerCase();
            var val = (typeof s.value === 'object') ? pl(s.value, 'en') : (s.value || '');
            if (/power/.test(label)) entry.power = val;
            if (/suction/.test(label)) entry.suction = val;
            if (/runtime|battery/.test(label)) entry.battery = val;
            if (/weight/.test(label)) entry.weight = val;
          });
          // Extract tags from highlights
          if (prod.highlights) {
            entry.tags = prod.highlights.map(function(h) { return pl(h.text, lang); }).filter(Boolean);
          }
          // Extract colors from sku
          if (prod.sku) {
            prod.sku.forEach(function(s) {
              var sname = (typeof s.name === 'object') ? pl(s.name, 'en') : s.name;
              if (/color|colour/i.test(sname) && s.values) {
                entry.colors = s.values.map(function(v) { return v.name; }).filter(Boolean);
              }
            });
          }
          renderProductForm(entry);
          setStatus('📂 已从线上加载（' + lang + ' / ' + cat + '）');
        } catch(e) {
          renderProductForm({ slug: cat, lang: lang });
          setStatus('⚠ 线上数据解析失败：' + e.message);
        }
      } else {
        renderProductForm({ slug: cat, lang: lang });
        setStatus('⚠ 找不到线上数据，使用空白表单');
      }
    };
    x.onerror = function() {
      renderProductForm({ slug: cat, lang: lang });
      setStatus('⚠ 网络错误');
    };
    x.send();
  }

  function loadHomepage(lang) {
    lang = lang || $('langSel').value || 'en';
    // localStorage first
    var stored = localStorage.getItem(sk('home', lang));
    if (stored) {
      try {
        var d = JSON.parse(stored);
        renderHomeEditor(d, lang);
        setStatus('📂 已加载本地草稿（' + lang + '）');
        return;
      } catch(e) {}
    }
    loadHomepageLive(lang);
  }

  function loadHomepageLive(lang) {
    lang = lang || $('langSel').value || 'en';
    setStatus('⏳ 正在从线上拉取...');
    var x = new XMLHttpRequest();
    x.open('GET', '/data/pages/home/' + lang + '.json?v=' + Date.now(), true);
    x.onload = function() {
      if (x.status === 200) {
        try {
          var d = JSON.parse(x.responseText);
          renderHomeEditor(d, lang);
          setStatus('🌐 已从线上加载（' + lang + '）');
        } catch(e) {
          setStatus('❌ JSON 解析失败：' + e.message);
        }
      } else {
        setStatus('❌ 找不到 ' + lang + ' 首页数据（HTTP ' + x.status + '）');
      }
    };
    x.onerror = function() { setStatus('❌ 网络错误'); };
    x.send();
  }

  // ── Tab + sidebar builders ─────────────────────────────────────
  function buildSidebar() {
    var side = $('sidebar');
    if (!side) return;

    side.innerHTML = '';

    // Tab switcher
    var tabsDiv = document.createElement('div');
    tabsDiv.style.cssText = 'display:flex;gap:0;margin-bottom:16px;background:#E2E8F0;border-radius:8px;padding:3px;';
    tabsDiv.innerHTML =
      '<button id="tab-product" class="btn btn-primary" style="flex:1;border-radius:6px;font-size:13px;padding:10px 6px;background:#2563EB;color:#fff;">📦 产品</button>' +
      '<button id="tab-home" class="btn btn-outline" style="flex:1;border-radius:6px;font-size:13px;padding:10px 6px;">🏠 首页</button>' +
      '<button id="tab-category" class="btn btn-outline" style="flex:1;border-radius:6px;font-size:13px;padding:10px 6px;">📚 类目页</button>'
      + '<button id="tab-about" class="btn btn-outline" style="flex:1;border-radius:6px;font-size:13px;padding:10px 6px;">ℹ️ 关于</button>';
    side.appendChild(tabsDiv);

    // Status
    var statusDiv = document.createElement('div');
    statusDiv.className = 'admin-status';
    statusDiv.id = 'status';
    statusDiv.textContent = '就绪';

    // Build product controls by default
    buildProductControls(side);
    side.appendChild(statusDiv);

    // Wire tab buttons (NOW — after buildProductControls defines the functions)
    $('tab-product').onclick = function() {
      activeTab = 'product';
      $('tab-product').className = 'btn btn-primary';
      $('tab-home').className = 'btn btn-outline';
      $('tab-product').style.background = '#2563EB';
      $('tab-product').style.color = '#fff';
      $('tab-home').style.background = '';
      $('tab-home').style.color = '';
      // Clear sidebar after hr
      var hrs = qsa('.admin-side hr');
      if (hrs.length) {
        var lastHr = hrs[hrs.length-1];
        while (lastHr.nextSibling) side.removeChild(lastHr.nextSibling);
        side.removeChild(lastHr);
      }
      var hr = document.createElement('hr');
      side.appendChild(hr);
      buildProductControls(side);
      side.appendChild(statusDiv);
      // Auto-load product data (defer 50ms for DOM ready)
      var _cat = currentCat || 'handheld-vacuum';
      var _lang = currentLang || 'en';
      setTimeout(function(){ loadProduct(_cat, _lang); }, 50);
    };

    $('tab-home').onclick = function() {
      activeTab = 'home';
      $('tab-home').className = 'btn btn-primary';
      $('tab-product').className = 'btn btn-outline';
      $('tab-home').style.background = '#2563EB';
      $('tab-home').style.color = '#fff';
      $('tab-product').style.background = '';
      $('tab-product').style.color = '';
      // Clear sidebar after hr
      var hrs = qsa('.admin-side hr');
      if (hrs.length) {
        var lastHr = hrs[hrs.length-1];
        while (lastHr.nextSibling) side.removeChild(lastHr.nextSibling);
        side.removeChild(lastHr);
      }
      var hr = document.createElement('hr');
      side.appendChild(hr);
      buildHomeControls(side);
      side.appendChild(statusDiv);
      // Auto-load homepage data (defer 50ms so DOM from buildHomeControls is ready)
      var _lang = $('langSel') ? $('langSel').value : 'en';
      setTimeout(function(){ loadHomepage(_lang); }, 50);
    };

    $('tab-category').onclick = function() {
      activeTab = 'category';
      $('tab-category').className = 'btn btn-primary';
      $('tab-product').className = 'btn btn-outline';
      $('tab-home').className = 'btn btn-outline';
      $('tab-category').style.background = '#2563EB';
      $('tab-category').style.color = '#fff';
      $('tab-product').style.background = '';
      $('tab-product').style.color = '';
      $('tab-home').style.background = '';
      $('tab-home').style.color = '';
      // Clear sidebar after hr
      var hrs = qsa('.admin-side hr');
      if (hrs.length) {
        var lastHr = hrs[hrs.length-1];
        while (lastHr.nextSibling) side.removeChild(lastHr.nextSibling);
        side.removeChild(lastHr);
      }
      var hr = document.createElement('hr');
      side.appendChild(hr);
      buildCategoryControls(side);
      side.appendChild(statusDiv);
      // Auto-load categories.json
      setTimeout(function(){ loadCategoryPage(); }, 50);
    };

    $('tab-about').onclick = function() {
      activeTab = 'about';
      $('tab-about').className = 'btn btn-primary';
      $('tab-product').className = 'btn btn-outline';
      $('tab-home').className = 'btn btn-outline';
      $('tab-category').className = 'btn btn-outline';
      $('tab-about').style.background = '#2563EB';
      $('tab-about').style.color = '#fff';
      $('tab-product').style.background = '';
      $('tab-product').style.color = '';
      $('tab-home').style.background = '';
      $('tab-home').style.color = '';
      $('tab-category').style.background = '';
      $('tab-category').style.color = '';
      var hrs = qsa('.admin-side hr');
      if (hrs.length) {
        var lastHr = hrs[hrs.length-1];
        while (lastHr.nextSibling) side.removeChild(lastHr.nextSibling);
        side.removeChild(lastHr);
      }
      var hr = document.createElement('hr');
      side.appendChild(hr);
      buildAboutControls(side);
      side.appendChild(statusDiv);
      setTimeout(function(){ loadAboutPage(); }, 50);
    };
  }

  function buildCategoryControls(side) {
    // Category selector
    var catDiv = document.createElement('div');
    catDiv.className = 'admin-field';
    catDiv.innerHTML = '<label>类目</label><select id="catPageSel"></select>';
    side.appendChild(catDiv);
    // Language selector
    var langDiv = document.createElement('div');
    langDiv.className = 'admin-field';
    langDiv.innerHTML = '<label>语言</label><select id="catPageLangSel"></select>';
    side.appendChild(langDiv);
    // Load button
    var loadBtn = document.createElement('button');
    loadBtn.className = 'btn btn-outline';
    loadBtn.style.cssText = 'width:100%;margin-bottom:8px;';
    loadBtn.textContent = '📂 加载类目数据';
    loadBtn.onclick = function() { loadCategoryPage(); };
    side.appendChild(loadBtn);
    // 保存按钮：草稿（本机）与发布（GitHub）分开。以前只有一个按钮，点下去弹
    // 一个 confirm 问要不要部署，运营根本看不出这里有发布能力。
    var saveBtn = document.createElement('button');
    saveBtn.className = 'btn btn-outline';
    saveBtn.style.cssText = 'width:100%;margin-bottom:8px;';
    saveBtn.textContent = '💾 保存草稿（仅本机）';
    saveBtn.onclick = function() { saveCategoryPage(); };
    side.appendChild(saveBtn);
    var pubBtn = document.createElement('button');
    pubBtn.className = 'btn btn-primary';
    pubBtn.style.cssText = 'width:100%;margin-bottom:8px;';
    pubBtn.textContent = '🚀 发布到线上';
    pubBtn.onclick = function() { publishCategoryPage(); };
    side.appendChild(pubBtn);
    // Hint
    var hint = document.createElement('div');
    hint.style.cssText = 'font-size:12px;color:#64748B;margin-top:8px;line-height:1.5;';
    hint.innerHTML = '编辑类目页标题、描述、Banner 图。'
      + '「保存草稿」只写本机；「🚀 发布到线上」提交到 GitHub，Pages 约 1-2 分钟生效。';
    side.appendChild(hint);
    // Populate category select
    var catSel = $('catPageSel');
    if (catSel) {
      var cats = ['handheld-vacuum','robot-vacuum','steam-cleaner','uv-mite-remover','window-cleaner-robot','car-vacuum','tire-inflator','coffee-machine','upright-steam-mop'];
      catSel.innerHTML = cats.map(function(c){ return '<option value="'+c+'">'+c+'</option>'; }).join('');
      if (currentCat) catSel.value = currentCat;
      catSel.onchange = function() { currentCat = catSel.value; loadCategoryPage(); };
    }
    // Populate language select
    var langSel = $('catPageLangSel');
    if (langSel) {
      var langs = [['en','English'],['zh','中文'],['ar','العربية'],['es','Español'],['fr','Français'],['id','Indonesia'],['ru','Русский'],['th','ไทย'],['vi','Tiếng Việt']];
      langSel.innerHTML = langs.map(function(l){ return '<option value="'+l[0]+'">'+l[1]+'</option>'; }).join('');
      if (currentLang) langSel.value = currentLang;
      langSel.onchange = function() { currentLang = langSel.value; loadCategoryPage(); };
    }
  }

  function loadCategoryPage() {
    var cat = $('catPageSel') ? $('catPageSel').value : (currentCat || 'handheld-vacuum');
    var lang = $('catPageLangSel') ? $('catPageLangSel').value : (currentLang || 'en');
    currentCat = cat;
    currentLang = lang;
    setStatus('🔄 加载 categories.json ...');
    var x = new XMLHttpRequest();
    var url = '/data/products/categories.json?v=' + Date.now();
    x.open('GET', url, true);
    x.onload = function() {
      if (x.status !== 200) { setStatus('❌ 加载失败: ' + x.status); return; }
      try {
        var data = JSON.parse(x.responseText);
        var cats = data.categories || [];
        var found = null;
        for (var i = 0; i < cats.length; i++) {
          if (cats[i].slug === cat) { found = cats[i]; break; }
        }
        if (!found) { setStatus('❌ 未找到类目: ' + cat); return; }
        renderCategoryForm(found, lang, data);
        setStatus('✅ 已加载: ' + cat + ' (' + lang + ')');
      } catch (e) {
        setStatus('❌ JSON 解析错误: ' + e.message);
      }
    };
    x.onerror = function() { setStatus('❌ 网络错误'); };
    x.send();
  }

  function renderCategoryForm(cat, lang, fullData) {
    var f = $('formArea');
    if (!f) return;
    f.innerHTML = '';
    var name = (cat.name && cat.name[lang]) || '';
    var desc = (cat.description && cat.description[lang]) || '';
    var banner = cat.banner_image || '';
    var order = cat.order || 0;
    // Section: basic
    f.appendChild(makeSec('类目信息 (' + lang + ')', makeGrid(
      fieldHTML('类目 slug', 'c-slug', 'text', cat.slug || '') +
      fieldHTML('排序', 'c-order', 'number', String(order)) +
      fieldHTML('Banner 图片 URL', 'c-banner', 'text', banner)
    )));
    // Section: multilingual
    f.appendChild(makeSec('多语言内容', makeGrid(
      fieldHTML('类目名称 (' + lang + ') *', 'c-name', 'text', name) +
      fieldHTML('类目描述 (' + lang + ')', 'c-desc', 'textarea', desc)
    )));
    // Preview banner
    if (banner) {
      var prev = document.createElement('div');
      prev.style.cssText = 'margin-top:12px;';
      prev.innerHTML = '<label style="font-size:12px;color:#64748B;">Banner 预览</label><br><img src="'+banner+'" style="max-width:300px;max-height:120px;border-radius:6px;margin-top:4px;border:1px solid #E2E8F0;" onerror="this.style.display=\'none\'">';
      f.appendChild(prev);
    }
    // Stash full data for save
    window._catFullData = fullData;
    window._catCurrent = cat;
    window._catLang = lang;
  }

  // 把表单改动合并回 fullData，并写一份本机草稿
  function buildCategoryJson() {
    var cat = window._catCurrent;
    var lang = window._catLang;
    var fullData = window._catFullData;
    if (!cat || !lang || !fullData) { setStatus('❌ 没有加载的数据'); return null; }
    var nameEl = $('c-name');
    var descEl = $('c-desc');
    var bannerEl = $('c-banner');
    var orderEl = $('c-order');
    if (!nameEl) { setStatus('❌ 表单未准备好'); return null; }
    var newName = nameEl.value.trim();
    if (!newName) { alert('类目名称不能为空'); return null; }
    // Update cat in fullData
    if (!cat.name) cat.name = {};
    if (!cat.description) cat.description = {};
    cat.name[lang] = newName;
    cat.description[lang] = descEl.value.trim();
    cat.banner_image = bannerEl.value.trim();
    if (orderEl) cat.order = parseInt(orderEl.value, 10) || 0;
    // Find and replace in fullData.categories
    var cats = fullData.categories || [];
    var found = false;
    for (var i = 0; i < cats.length; i++) {
      if (cats[i].slug === cat.slug) { cats[i] = cat; found = true; break; }
    }
    if (!found) cats.push(cat);
    fullData.categories = cats;
    var jsonStr = JSON.stringify(fullData, null, 2);
    // Save draft to localStorage
    localStorage.setItem('aqc_cat_draft', jsonStr);
    return { json: jsonStr, cat: cat, lang: lang };
  }

  // ① 只存本机草稿
  function saveCategoryPage() {
    var r = buildCategoryJson();
    if (!r) return;
    setStatus('💾 类目草稿已保存（只在本机）· 要让网站生效请点「🚀 发布到线上」');
  }

  // ② 推到 GitHub
  async function publishCategoryPage() {
    var r = buildCategoryJson();
    if (!r) return;
    if (!(await ensureToken())) return;
    try {
      await publishJson('data/products/categories.json', r.json,
        'admin: update category page ' + r.cat.slug + ' (' + r.lang + ')');
    } catch (err) { /* publishJson 已经提示过了 */ }
  }

function buildAboutControls(side) {
    // Language selector (about page only in en / zh)
    var langDiv = document.createElement('div');
    langDiv.className = 'admin-field';
    langDiv.innerHTML = '<label>语言</label><select id="aboutLangSel"></select>';
    side.appendChild(langDiv);
    var langSel = $('aboutLangSel');
    var langs = [['en','English'],['zh','中文']];
    langSel.innerHTML = langs.map(function(l){ return '<option value="'+l[0]+'">'+l[1]+'</option>'; }).join('');
    if (currentLang) langSel.value = currentLang;
    langSel.onchange = function() { loadAboutPage(); };
    // Load button
    var loadBtn = document.createElement('button');
    loadBtn.className = 'btn btn-primary';
    loadBtn.style.cssText = 'width:100%;margin-bottom:8px;';
    loadBtn.textContent = '📂 加载关于页数据';
    loadBtn.onclick = function() { loadAboutPage(); };
    side.appendChild(loadBtn);
    // Hint
    var hint = document.createElement('div');
    hint.style.cssText = 'font-size:12px;color:#64748B;margin-top:8px;line-height:1.5;';
    hint.innerHTML = '编辑关于页全部内容：Hero、故事、能力、工厂图集、里程碑、CTA。保存即部署到 GitHub Pages（1-2 分钟生效）。';
    side.appendChild(hint);
  }

  function loadAboutPage() {
    var lang = $('aboutLangSel') ? $('aboutLangSel').value : (currentLang || 'en');
    currentLang = lang;
    setStatus('⏳ 正在从线上拉取 about/' + lang + '.json ...');
    var x = new XMLHttpRequest();
    x.open('GET', '/data/pages/about/' + lang + '.json?v=' + Date.now(), true);
    x.onload = function() {
      if (x.status === 200) {
        try {
          var d = JSON.parse(x.responseText);
          renderAboutForm(d, lang);
          setStatus('🌐 已加载关于页（' + lang + '）');
        } catch(e) { setStatus('❌ JSON 解析失败：' + e.message); }
      } else {
        setStatus('❌ 找不到 about/' + lang + '.json（HTTP ' + x.status + '）· 已禁用保存，避免用空表单覆盖该语言');
        // 该语言还没有数据文件时，表单是空的；让用户一保存就生成残缺页面。
        ['saveAboutBtn', 'publishAboutBtn'].forEach(function (id) {
          var el = $(id);
          if (el) { el.disabled = true; el.title = '该语言尚无数据文件，无法保存/发布'; }
        });
      }
    };
    x.onerror = function() { setStatus('❌ 网络错误'); };
    x.send();
  }

  function renderAboutForm(d, lang) {
    var f = $('formArea');
    if (!f) return;
    f.innerHTML = '';
    window._aboutData = d || {};
    window._aboutLang = lang;
    var hero = (d && d.hero) || {};
    var story = (d && d.story) || {};
    var sp = story.paragraphs || ['',''];
    var sb = story.bullets || ['','','',''];
    var cap = (d && d.capabilities) || {};
    var capItems = cap.items || [];
    var gal = (d && d.gallery) || {};
    var galItems = gal.items || [];
    var mil = (d && d.milestones) || {};
    var milItems = mil.items || [];
    var cta = (d && d.cta) || {};

    f.appendChild(makeSec('① Hero 首屏', makeGrid(
      fieldHTML('徽章文字', 'a-hero-badge', 'text', hero.badge || '') +
      fieldHTML('主标题（可含 <span>高亮</span>）', 'a-hero-h1', 'text', hero.h1 || '') +
      fieldHTML_note('首屏介绍语（支持 HTML）', 'a-hero-intro', 'textarea', hero.intro || '') +
      fieldHTML('主按钮文字', 'a-hero-btn1-text', 'text', hero.btn_primary_text || '') +
      fieldHTML('主按钮链接', 'a-hero-btn1-href', 'text', hero.btn_primary_href || '') +
      fieldHTML('次按钮文字', 'a-hero-btn2-text', 'text', hero.btn_outline_text || '') +
      fieldHTML('次按钮链接', 'a-hero-btn2-href', 'text', hero.btn_outline_href || '') +
      fieldHTML('背景图 URL', 'a-hero-bg', 'text', hero.bg_image || '')
    )));

    f.appendChild(makeSec('② 故事区块', makeGrid(
      fieldHTML('小标签', 'a-story-label', 'text', story.label || '') +
      fieldHTML('标题', 'a-story-h2', 'text', story.h2 || '') +
      fieldHTML_note('正文段落 1', 'a-story-p0', 'textarea', sp[0] || '') +
      fieldHTML_note('正文段落 2', 'a-story-p1', 'textarea', sp[1] || '') +
      fieldHTML('要点 1', 'a-story-b0', 'text', sb[0] || '') +
      fieldHTML('要点 2', 'a-story-b1', 'text', sb[1] || '') +
      fieldHTML('要点 3', 'a-story-b2', 'text', sb[2] || '') +
      fieldHTML('要点 4', 'a-story-b3', 'text', sb[3] || '') +
      fieldHTML('配图 URL', 'a-story-img', 'text', story.image || '') +
      fieldHTML('配图 alt', 'a-story-img-alt', 'text', story.image_alt || '')
    )));

    var capHtml = fieldHTML('小标签', 'a-cap-label', 'text', cap.label || '') +
      fieldHTML('标题', 'a-cap-title', 'text', cap.title || '') +
      fieldHTML_note('副标题', 'a-cap-sub', 'textarea', cap.sub || '');
    for (var i = 0; i < 4; i++) {
      var ci = capItems[i] || {};
      capHtml += '<div style="border-top:1px dashed #E2E8F0;margin:10px 0;padding-top:10px;">' +
        '<div style="font-size:12px;color:#94A3B8;margin-bottom:6px;">能力 ' + (i+1) + '</div>' +
        fieldHTML('图标(emoji)', 'a-cap-ico-' + i, 'text', ci.icon || '') +
        fieldHTML('标题', 'a-cap-h4-' + i, 'text', ci.h4 || '') +
        fieldHTML('描述', 'a-cap-p-' + i, 'textarea', ci.p || '') + '</div>';
    }
    f.appendChild(makeSec('③ 能力区块', makeGrid(capHtml)));

    var galHtml = fieldHTML('小标签', 'a-gal-label', 'text', gal.label || '') +
      fieldHTML('标题', 'a-gal-title', 'text', gal.title || '') +
      fieldHTML_note('副标题', 'a-gal-sub', 'textarea', gal.sub || '');
    for (var j = 0; j < 6; j++) {
      var gi = galItems[j] || {};
      galHtml += '<div style="border-top:1px dashed #E2E8F0;margin:10px 0;padding-top:10px;">' +
        '<div style="font-size:12px;color:#94A3B8;margin-bottom:6px;">图集 ' + (j+1) + '</div>' +
        fieldHTML('图片 URL', 'a-gal-img-' + j, 'text', gi.img || '') +
        fieldHTML('图片 alt', 'a-gal-alt-' + j, 'text', gi.alt || '') +
        fieldHTML('标题', 'a-gal-h4-' + j, 'text', gi.h4 || '') +
        fieldHTML('描述', 'a-gal-p-' + j, 'textarea', gi.p || '') + '</div>';
    }
    f.appendChild(makeSec('④ 工厂图集', makeGrid(galHtml)));

    var milHtml = fieldHTML('小标签', 'a-mil-label', 'text', mil.label || '') +
      fieldHTML('标题', 'a-mil-title', 'text', mil.title || '');
    for (var k = 0; k < 5; k++) {
      var mi = milItems[k] || {};
      milHtml += '<div style="border-top:1px dashed #E2E8F0;margin:10px 0;padding-top:10px;">' +
        '<div style="font-size:12px;color:#94A3B8;margin-bottom:6px;">里程碑 ' + (k+1) + '</div>' +
        fieldHTML('年份', 'a-mil-year-' + k, 'text', mi.year || '') +
        fieldHTML('标题', 'a-mil-h4-' + k, 'text', mi.h4 || '') +
        fieldHTML('描述', 'a-mil-p-' + k, 'textarea', mi.p || '') + '</div>';
    }
    f.appendChild(makeSec('⑤ 里程碑', makeGrid(milHtml)));

    f.appendChild(makeSec('⑥ CTA 行动号召', makeGrid(
      fieldHTML('标题', 'a-cta-h2', 'text', cta.h2 || '') +
      fieldHTML_note('描述', 'a-cta-p', 'textarea', cta.p || '') +
      fieldHTML('按钮文字', 'a-cta-btn-text', 'text', cta.btn_text || '') +
      fieldHTML('按钮链接', 'a-cta-btn-href', 'text', cta.btn_href || '')
    )));

    var saveWrap = document.createElement('div');
    saveWrap.style.cssText = 'margin-bottom:16px;';
    saveWrap.innerHTML =
      '<div style="display:flex;gap:10px;flex-wrap:wrap;">' +
      '<button class="btn btn-outline" id="saveAboutBtn" style="flex:1 1 180px;">💾 保存草稿（仅本机）</button>' +
      '<button class="btn btn-primary" id="publishAboutBtn" style="flex:1 1 180px;">🚀 发布到线上</button>' +
      '</div>';
    f.insertBefore(saveWrap, f.firstChild);
    $('saveAboutBtn').onclick = function() { saveAboutPage(); };
    $('publishAboutBtn').onclick = function() { publishAboutPage(); };
  }

  // 把表单收集成目标 JSON，并写一份本机草稿
  function buildAboutJson() {
    var lang = window._aboutLang || ($('aboutLangSel') ? $('aboutLangSel').value : 'en');
    var d = window._aboutData || {};
    d.hero = {
      badge: val('a-hero-badge'), h1: val('a-hero-h1'), intro: val('a-hero-intro'),
      btn_primary_text: val('a-hero-btn1-text'), btn_primary_href: val('a-hero-btn1-href'),
      btn_outline_text: val('a-hero-btn2-text'), btn_outline_href: val('a-hero-btn2-href'),
      bg_image: val('a-hero-bg')
    };
    d.story = {
      label: val('a-story-label'), h2: val('a-story-h2'),
      paragraphs: [val('a-story-p0'), val('a-story-p1')],
      bullets: [val('a-story-b0'), val('a-story-b1'), val('a-story-b2'), val('a-story-b3')],
      image: val('a-story-img'), image_alt: val('a-story-img-alt')
    };
    d.capabilities = { label: val('a-cap-label'), title: val('a-cap-title'), sub: val('a-cap-sub'), items: [] };
    for (var i = 0; i < 4; i++) {
      d.capabilities.items.push({ icon: val('a-cap-ico-' + i), h4: val('a-cap-h4-' + i), p: val('a-cap-p-' + i) });
    }
    d.gallery = { label: val('a-gal-label'), title: val('a-gal-title'), sub: val('a-gal-sub'), items: [] };
    for (var j = 0; j < 6; j++) {
      d.gallery.items.push({ img: val('a-gal-img-' + j), alt: val('a-gal-alt-' + j), h4: val('a-gal-h4-' + j), p: val('a-gal-p-' + j) });
    }
    d.milestones = { label: val('a-mil-label'), title: val('a-mil-title'), items: [] };
    for (var k = 0; k < 5; k++) {
      d.milestones.items.push({ year: val('a-mil-year-' + k), h4: val('a-mil-h4-' + k), p: val('a-mil-p-' + k) });
    }
    d.cta = { h2: val('a-cta-h2'), p: val('a-cta-p'), btn_text: val('a-cta-btn-text'), btn_href: val('a-cta-btn-href') };
    var jsonStr = JSON.stringify(d, null, 2);
    localStorage.setItem('aqc_about_draft_' + lang, jsonStr);
    window._aboutData = d;
    return { json: jsonStr, lang: lang };
  }

  // ① 只存本机草稿
  function saveAboutPage() {
    var r = buildAboutJson();
    if (!r) return;
    setStatus('💾 关于页草稿已保存（只在本机）· 要让网站生效请点「🚀 发布到线上」');
  }

  // ② 推到 GitHub
  async function publishAboutPage() {
    var r = buildAboutJson();
    if (!r) return;
    if (!(await ensureToken())) return;
    try {
      await publishJson('data/pages/about/' + r.lang + '.json', r.json,
        'admin: update about page (' + r.lang + ')');
    } catch (err) { /* publishJson 已经提示过了 */ }
  }

function buildProductControls(side) {
    var catDiv = document.createElement('div');
    catDiv.className = 'admin-field';
    catDiv.innerHTML = '<label>类目</label><select id="catSel"></select>';
    side.appendChild(catDiv);
    var catSel = $('catSel');
    CATS.forEach(function(c){
      var o = document.createElement('option');
      o.value = c.slug;
      o.textContent = c.label + ' / ' + c.enLabel;
      if (c.slug === currentCat) o.selected = true;
      catSel.appendChild(o);
    });
    catSel.onchange = function() {
      currentCat = this.value;
      loadProduct(currentCat);
    };

    var langDiv = document.createElement('div');
    langDiv.className = 'admin-field';
    langDiv.innerHTML = '<label>语言</label><select id="langSel"></select>';
    side.appendChild(langDiv);
    LANGS.forEach(function(l){
      var o = document.createElement('option');
      o.value = l.code;
      o.textContent = l.label;
      if (l.code === (currentLang||'en')) o.selected = true;
      $('langSel').appendChild(o);
    });
    $('langSel').onchange = function() {
      currentLang = this.value;
      loadProduct(currentCat, currentLang);
    };

    var btnDiv = document.createElement('div');
    btnDiv.style.marginTop = '8px';
    btnDiv.innerHTML =
      '<button class="btn btn-primary" id="loadBtn" style="width:100%;margin-bottom:8px;">📂 加载产品</button>' +
      '<button class="btn btn-outline" id="newBtn" style="width:100%;margin-bottom:16px;">🆕 新建空白</button>';
    side.appendChild(btnDiv);

    $('loadBtn').onclick = function() { loadProduct(currentCat, currentLang); };
    $('newBtn').onclick = function() {
      renderProductForm({ slug: currentCat||'handheld-vacuum', lang: currentLang||'en' });
      setStatus('🆕 空白表单已打开');
    };

    side.appendChild(document.createElement('hr'));

    var impDiv = document.createElement('div');
    impDiv.innerHTML =
      '<button class="btn btn-outline" id="exportBtn" style="width:100%;margin-bottom:8px;">📤 导出当前</button>' +
      '<button class="btn btn-outline" id="importBtn" style="width:100%;">📥 导入 JSON</button>';
    side.appendChild(impDiv);
    $('exportBtn').onclick = function() {
      var d = collectProduct();
      if (!d.name) { setStatus('⚠ 请先加载或填写产品'); return; }
      exportProduct();
    };
    $('importBtn').onclick = function() { $('importFile').click(); };
  }

  function buildHomeControls(side) {
    var langDiv = document.createElement('div');
    langDiv.className = 'admin-field';
    langDiv.innerHTML = '<label>语言</label><select id="langSel"></select>';
    side.appendChild(langDiv);
    LANGS.forEach(function(l){
      var o = document.createElement('option');
      o.value = l.code;
      o.textContent = l.label;
      if (l.code === (currentLang||'en')) o.selected = true;
      $('langSel').appendChild(o);
    });
    $('langSel').onchange = function() { loadHomepage(this.value); };

    var btnDiv = document.createElement('div');
    btnDiv.style.marginTop = '8px';
    btnDiv.innerHTML =
      '<button class="btn btn-primary" id="loadHomeBtn" style="width:100%;margin-bottom:8px;">📂 加载首页数据</button>' +
      '<button class="btn btn-outline" id="loadHomeLiveBtn" style="width:100%;margin-bottom:16px;">🌐 从线上拉取</button>';
    side.appendChild(btnDiv);
    $('loadHomeBtn').onclick = function() { loadHomepage($('langSel').value); };
    $('loadHomeLiveBtn').onclick = function() { loadHomepageLive($('langSel').value); };

    side.appendChild(document.createElement('hr'));

    var impDiv = document.createElement('div');
    impDiv.innerHTML =
      '<button class="btn btn-outline" id="exportHomeBtn" style="width:100%;margin-bottom:8px;">📤 导出 JSON</button>' +
      '<button class="btn btn-outline" id="importHomeBtn" style="width:100%;">📥 导入 JSON</button>';
    side.appendChild(impDiv);
    $('exportHomeBtn').onclick = function() { exportHome(); };
    $('importHomeBtn').onclick = function() { $('importFile').click(); };
  }

  // ── Expose API globally (for debugging / tab buttons) ──────────
  window._aqc = {
    loadHomepage:      loadHomepage,
    loadHomepageLive:  loadHomepageLive,
    loadProduct:       loadProduct,
    saveHome:          saveHome,
    exportHome:        exportHome,
    collectHome:       collectHome,
    renderHomeEditor:   renderHomeEditor,
    saveProduct:       saveProduct,
    publishProduct:    publishProduct,
    exportProduct:     exportProduct,
    collectProduct:    collectProduct,
    loadAboutPage:     loadAboutPage,
    saveAboutPage:     saveAboutPage,
    publishAboutPage:  publishAboutPage,
    publishHome:       publishHome,
    publishCategoryPage: publishCategoryPage,
    renderAboutForm:   renderAboutForm
  };

  // ── Init ───────────────────────────────────────────────────────
  function init() {
    buildSidebar();
    // Auto-load default product after sidebar is built
    setTimeout(function(){ loadProduct('handheld-vacuum', 'en'); }, 50);
    // Token UI: click header link to set/update token
    var tokenLink = $('setTokenLink');
    if (tokenLink) tokenLink.addEventListener('click', function(e) {
      e.preventDefault();
      promptForToken();
    });
    refreshTokenUI();
    // 先静默问一次本机桥；桥在跑就再也不用手工粘 Token 了
    autoTokenFromBridge();
    // First-visit nudge for token
    setTimeout(function() {
      if (!getToken()) {
        setStatus('💡 提示：双击运行 admin/gh_token_server.py 后，「🚀 发布到线上」会自动取用 Token；'
          + '否则点右上角「⚠ 设置 GitHub Token」手工粘贴（仅当前标签页有效）');
      }
    }, 2500);
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }


  // ── Drag-and-drop image upload on every image URL field ────────────
  // Product images already shipped with a drop zone; the other image
  // fields (homepage product image, category banner, about-page gallery,
  // story image) were plain URL text boxes, so every image had to be
  // uploaded somewhere else first and pasted in by hand.
  //
  // This is purely additive: it decorates existing inputs after render and
  // dispatches an `input` event so the normal draft/save flow still fires.
  var AQC_IMG_RE = /(^|[-_])(img|image|images|banner|photo|cover|thumb|picture)($|[-_])/i;
  var AQC_ALT_RE = /(^|[-_])alt($|[-_])/i;

  function aqcIsImageUrlField(el) {
    return !!el && el.type === 'text' && !!el.id &&
           !AQC_ALT_RE.test(el.id) && AQC_IMG_RE.test(el.id);
  }

  function aqcMakeDropZone(input) {
    if (!input || input.__aqcDrop) return;
    input.__aqcDrop = 1;

    var LABEL = '\U0001F5BC\uFE0F 拖放图片到此处上传 · 或点击选择文件（也可直接粘贴 URL）';

    var dz = document.createElement('div');
    dz.className = 'aqc-dropzone';

    var text = document.createElement('span');
    text.textContent = LABEL;

    var preview = document.createElement('img');
    preview.className = 'aqc-drop-preview';
    preview.style.display = 'none';

    var picker = document.createElement('input');
    picker.type = 'file';
    picker.accept = 'image/*';
    picker.style.display = 'none';

    dz.appendChild(text);
    dz.appendChild(picker);
    dz.appendChild(preview);

    function setPreview(url) {
      preview.src = url || '';
      preview.style.display = url ? 'block' : 'none';
    }
    if (input.value && /^[\/.]/.test(input.value)) setPreview(input.value);

    async function handle(files) {
      if (!files || !files.length) return;
      if (!getToken()) {
        setStatus('\u26A0 请先点击右上角「设置 GitHub Token」后再上传图片');
        return;
      }
      dz.classList.add('busy');
      text.textContent = '正在上传…';
      try {
        var url = await ghUploadImage(files[0]);
        input.value = url;
        try { input.dispatchEvent(new Event('input', { bubbles: true })); } catch (e) {}
        setPreview(url);
        setStatus('\u2705 图片已上传：' + url + ' · 记得点「保存草稿」或发布');
      } catch (err) {
        setStatus('\u274C 图片上传失败：' + ((err && err.message) || err));
      } finally {
        dz.classList.remove('busy');
        text.textContent = LABEL;
      }
    }

    dz.addEventListener('click', function () { picker.click(); });
    picker.addEventListener('change', function () {
      handle(picker.files);
      picker.value = '';
    });
    ['dragenter', 'dragover'].forEach(function (ev) {
      dz.addEventListener(ev, function (e) {
        e.preventDefault();
        dz.classList.add('drag-over');
      });
    });
    ['dragleave', 'dragend'].forEach(function (ev) {
      dz.addEventListener(ev, function () { dz.classList.remove('drag-over'); });
    });
    dz.addEventListener('drop', function (e) {
      e.preventDefault();
      dz.classList.remove('drag-over');
      handle(e.dataTransfer && e.dataTransfer.files);
    });

    if (input.parentNode) input.parentNode.insertBefore(dz, input.nextSibling);
  }

  function aqcScanImageFields(root) {
    [].slice.call((root || document).querySelectorAll('input[type=text]'))
      .forEach(function (el) {
        if (aqcIsImageUrlField(el)) aqcMakeDropZone(el);
      });
  }

  // Forms are re-rendered on every tab/section switch, so watch the form
  // area and decorate whatever appears.
  function initImageDropZones() {
    var area = $('formArea');
    if (!area) return;
    aqcScanImageFields(area);
    if (typeof MutationObserver === 'function') {
      var mo = new MutationObserver(function () { aqcScanImageFields(area); });
      mo.observe(area, { childList: true, subtree: true });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () {
      setTimeout(initImageDropZones, 700);
    });
  } else {
    setTimeout(initImageDropZones, 700);
  }

})();
