#!/usr/bin/env node
/**
 * Inquiry relay: the path a website visitor's lead takes into the back office.
 *
 * The public site cannot write to the cloud database directly — the data plane
 * enforces an exact Origin match, so a browser on www.hkdmj.net is refused at
 * CORS. Instead the public site hands the payload to /inquiry-proxy.html,
 * which is served from the back-office domain and therefore CAN write. That
 * makes the proxy a public, attacker-reachable input surface, so this suite
 * boots the real proxy page and checks what it actually lets through:
 *
 *   1. an allowed origin with a good payload     -> exactly one INSERT
 *   2. a foreign origin                          -> no INSERT at all
 *   3. honeypot filled / submitted too fast      -> rejected, no INSERT
 *   4. malformed email, missing name             -> rejected, no INSERT
 *   5. over-long fields                          -> truncated, not rejected
 *   6. empty optional fields                     -> omitted (column default)
 *   7. per-browser throttle                      -> 7th submission refused
 *   8. the public side reads a form correctly    -> fromForm()
 *
 * Run:  node scripts/verify_inquiry_relay.js
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require(process.env.JSDOM_PATH ||
  'C:/Users/Administrator/.workbuddy/binaries/node/workspace/node_modules/jsdom');

const ROOT = path.resolve(__dirname, '..');
const PROXY = path.join(ROOT, '..', 'aquaclean-admin-app', 'inquiry-proxy.html');

let pass = 0, fail = 0;
function ok(cond, label, extra) {
  if (cond) { pass++; console.log('  \u2713 ' + label); }
  else { fail++; console.log('  \u2717 ' + label + (extra ? '  -> ' + extra : '')); }
}
function section(s) { console.log('\n' + s); }

/* ── boot the real proxy page with a fake cloud SDK ───────────────── */
function bootProxy() {
  const html = fs.readFileSync(PROXY, 'utf8');
  const inserts = [];

  const dom = new JSDOM(html, {
    url: 'https://aquaclean-admin.app.workbuddy.host/inquiry-proxy.html',
    runScripts: 'dangerously',
    beforeParse(win) {
      // The page loads the real SDK + /admin/cloud.js from the network; jsdom
      // fetches neither, so stand in for both. The config values are the ones
      // cloud.js ships.
      win.AQC_CLOUD_CONFIG = {
        endpoint: 'https://aquaclean-admin.app.workbuddy.host',
        publishableKey: 'wbpk_test_only'
      };
      win.WorkBuddyCloud = {
        createWorkBuddyCloud(cfg) {
          ok(cfg && cfg.endpoint && cfg.publishableKey,
            'proxy passes both endpoint and publishableKey to createWorkBuddyCloud');
          return {
            database: {
              from(table) {
                return {
                  insert(row) {
                    // The real PostgREST builder is thenable on its own, and
                    // .select() is optional — the proxy deliberately does NOT
                    // chain it (the read-back would be blocked by RLS). So the
                    // stub has to satisfy both call shapes.
                    inserts.push({ table, row });
                    var p = Promise.resolve({ data: [{ id: inserts.length }], error: null });
                    return {
                      select: function () { return p; },
                      then: function (a, b) { return p.then(a, b); },
                      catch: function (a) { return p.catch(a); },
                      finally: function (a) { return p.finally(a); }
                    };
                  }
                };
              }
            }
          };
        }
      };
    }
  });
  return { win: dom.window, inserts };
}

/** Fire a postMessage at the proxy exactly as a host page would. */
function send(win, origin, payload, type) {
  const ev = new win.MessageEvent('message', {
    data: { type: type || 'aqc-inquiry', id: 't1', payload },
    origin
  });
  win.dispatchEvent(ev);
}

const GOOD = {
  name: 'Sarah Johnson',
  email: 'sarah@company.com',
  company: 'ACME Ltd',
  country: 'US',
  products_interested: 'handheld-vacuum',
  quantity: '500 units',
  message: 'Need CE certification and OEM branding.',
  lang: 'en',
  page_path: '/en/index.html',
  referrer: 'https://www.google.com/',
  renderedAt: Date.now() - 30000,
  hp: ''
};

(async function main() {
  console.log('Inquiry relay regression suite');
  console.log('proxy: ' + PROXY);

  /* 1 ── happy path */
  section('1. allowed origin, complete payload');
  {
    const { win, inserts } = bootProxy();
    send(win, 'https://www.hkdmj.net', GOOD);
    await new Promise(r => setTimeout(r, 60));
    ok(inserts.length === 1, 'exactly one INSERT was attempted', 'got ' + inserts.length);
    if (inserts.length) {
      const r = inserts[0].row;
      ok(inserts[0].table === 'inquiries', 'writes to the inquiries table', inserts[0].table);
      ok(r.name === GOOD.name && r.email === GOOD.email, 'name and email carried through');
      ok(r.company === 'ACME Ltd' && r.country === 'US', 'company and country carried through');
      ok(r.products_interested === 'handheld-vacuum', 'products_interested carried through');
      ok(r.quantity === '500 units', 'quantity carried through');
      ok(r.message === GOOD.message, 'message carried through');
      ok(r.lang === 'en' && r.page_path === '/en/index.html', 'lang and page_path recorded');
      ok(r.status === 'new', 'new rows start at status "new"', r.status);
      ok(!('hp' in r), 'the honeypot field is never persisted');
    }
  }

  /* 2 ── origin allow-list */
  section('2. foreign origins are refused');
  for (const bad of ['https://evil.example', 'http://localhost:3000', 'null', '']) {
    const { win, inserts } = bootProxy();
    send(win, bad, GOOD);
    await new Promise(r => setTimeout(r, 40));
    ok(inserts.length === 0, 'no INSERT from origin "' + bad + '"', 'got ' + inserts.length);
  }

  /* 3 ── bot heuristics */
  section('3. bot heuristics');
  {
    const { win, inserts } = bootProxy();
    send(win, 'https://www.hkdmj.net', Object.assign({}, GOOD, { hp: 'bot' }));
    await new Promise(r => setTimeout(r, 40));
    ok(inserts.length === 0, 'honeypot filled -> rejected');
  }
  {
    const { win, inserts } = bootProxy();
    send(win, 'https://www.hkdmj.net',
      Object.assign({}, GOOD, { renderedAt: Date.now() - 200 }));
    await new Promise(r => setTimeout(r, 40));
    ok(inserts.length === 0, 'submitted <1.5s after page load -> rejected');
  }

  /* 4 ── required fields */
  section('4. required fields');
  {
    const { win, inserts } = bootProxy();
    send(win, 'https://www.hkdmj.net', Object.assign({}, GOOD, { email: 'not-an-email' }));
    await new Promise(r => setTimeout(r, 40));
    ok(inserts.length === 0, 'malformed email -> rejected');
  }
  {
    const { win, inserts } = bootProxy();
    send(win, 'https://www.hkdmj.net', Object.assign({}, GOOD, { name: '  ' }));
    await new Promise(r => setTimeout(r, 40));
    ok(inserts.length === 0, 'blank name -> rejected');
  }

  /* 5 ── caps */
  section('5. over-long input is trimmed, not dropped');
  {
    const { win, inserts } = bootProxy();
    send(win, 'https://www.hkdmj.net', Object.assign({}, GOOD, {
      message: 'x'.repeat(9000),
      company: 'y'.repeat(900)
    }));
    await new Promise(r => setTimeout(r, 60));
    ok(inserts.length === 1, 'still inserted after trimming');
    if (inserts.length) {
      const r = inserts[0].row;
      ok(r.message.length === 5000, 'message capped at 5000', 'len ' + r.message.length);
      ok(r.company.length === 300, 'company capped at 300', 'len ' + r.company.length);
    }
  }

  /* 6 ── empty optionals */
  section('6. empty optional fields are omitted');
  {
    const { win, inserts } = bootProxy();
    send(win, 'https://www.hkdmj.net', {
      name: 'Li Wei', email: 'li@example.com',
      company: '', country: '', products_interested: '', quantity: '', message: '',
      lang: 'zh', page_path: '/zh/index.html', renderedAt: Date.now() - 9000, hp: ''
    });
    await new Promise(r => setTimeout(r, 60));
    ok(inserts.length === 1, 'minimal payload still inserted');
    if (inserts.length) {
      const r = inserts[0].row;
      ok(!('company' in r) && !('message' in r) && !('quantity' in r),
        'empty optionals omitted so column defaults apply');
      ok(r.name === 'Li Wei' && r.lang === 'zh', 'required fields intact');
    }
  }

  /* 7 ── throttle */
  section('7. per-browser throttle');
  {
    const { win, inserts } = bootProxy();
    for (let i = 0; i < 8; i++) send(win, 'https://www.hkdmj.net', GOOD);
    await new Promise(r => setTimeout(r, 120));
    ok(inserts.length === 6, 'only 6 submissions accepted per 10 minutes', 'got ' + inserts.length);
  }

  /* 8 ── the public side reads a form */
  section('8. public site: AQCInquiry.fromForm()');
  {
    const sink = fs.readFileSync(path.join(ROOT, 'assets', 'js', 'inquiry-sink.js'), 'utf8');
    const dom = new JSDOM(
      '<form id="f"><input name="name" value="Ana"><input name="email" value="a@b.com">'
      + '<select name="country"><option value="DE" selected>DE</option></select>'
      + '<input name="quantity" value="120"><textarea name="message">hi</textarea>'
      + '<input type="hidden" name="product" value="Robot Vacuum"></form>',
      { url: 'https://www.hkdmj.net/en/index.html', runScripts: 'outside-only' }
    );
    dom.window.eval(sink);
    const api = dom.window.AQCInquiry;
    ok(!!api, 'AQCInquiry is exposed on window');
    const p = api.fromForm(dom.window.document.getElementById('f'));
    ok(p.name === 'Ana' && p.email === 'a@b.com', 'text fields read');
    ok(p.country === 'DE' && p.quantity === '120' && p.message === 'hi', 'select / textarea read');
    ok(p.products_interested === 'Robot Vacuum',
      'hidden product falls back to products_interested', p.products_interested);
    ok(api.relayUrl.indexOf('aquaclean-admin.app.workbuddy.host') > -1,
      'relay points at the back-office origin', api.relayUrl);
  }

  console.log('\n' + '='.repeat(52));
  console.log(pass + ' passed, ' + fail + ' failed');
  process.exit(fail ? 1 : 0);
})();
