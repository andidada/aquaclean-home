/**
 * Admin authentication for the AquaClean back office.
 *
 * Why this exists: the login page only ever ran in the browser, so its check
 * could be skipped by anyone who opened dashboard.html directly or set
 * sessionStorage by hand. This function moves the actual decision to the
 * server side and hands back a signed, expiring session token.
 *
 * The password is never stored here - only its salted SHA-256 digest, in the
 * ADMIN_PASSWORD_HASH environment variable. Generate one with:
 *     python scripts/hash_admin_password.py
 *
 * Required environment variables (set in the Netlify UI, never in git):
 *   ADMIN_SESSION_SECRET  - HMAC key for signing session tokens
 *   ADMIN_PASSWORD_HASH   - sha256("<salt>:<password>"), hex, lowercase
 *   ADMIN_USERNAME        - optional, defaults to "admin"
 *
 * Progressive enhancement: if ADMIN_SESSION_SECRET is missing the function
 * answers 501, and the login page falls back to its client-side hash check
 * rather than locking the user out.
 */
const crypto = require('crypto');

// Must match AQC_ADMIN_SALT in admin/login.html and scripts/hash_admin_password.py
const SALT = 'AQC-Admin-Login-v1';
const SESSION_TTL_MS = 8 * 60 * 60 * 1000; // 8 hours
const MAX_ATTEMPTS = 8;
const ATTEMPT_WINDOW_MS = 10 * 60 * 1000;

// Per-instance counter. Netlify may run several instances, so this is a
// speed bump against brute force, not a hard guarantee.
const attempts = new Map();

function b64url(buf) {
  return Buffer.from(buf).toString('base64url');
}

function hashPassword(password) {
  return crypto.createHash('sha256').update(SALT + ':' + password).digest('hex');
}

function safeEqual(a, b) {
  const ba = Buffer.from(String(a || ''), 'utf8');
  const bb = Buffer.from(String(b || ''), 'utf8');
  if (ba.length !== bb.length) return false;
  return crypto.timingSafeEqual(ba, bb);
}

function sign(payload, secret) {
  const body = b64url(Buffer.from(JSON.stringify(payload), 'utf8'));
  const mac = crypto.createHmac('sha256', secret).update(body).digest();
  return body + '.' + b64url(mac);
}

function verify(token, secret) {
  const parts = String(token || '').split('.');
  if (parts.length !== 2) return null;
  const expected = b64url(crypto.createHmac('sha256', secret).update(parts[0]).digest());
  if (!safeEqual(parts[1], expected)) return null;
  let payload;
  try {
    payload = JSON.parse(Buffer.from(parts[0], 'base64url').toString('utf8'));
  } catch (e) {
    return null;
  }
  if (!payload || !payload.exp || payload.exp < Date.now()) return null;
  return payload;
}

function tooManyAttempts(key) {
  const now = Date.now();
  const hits = (attempts.get(key) || []).filter((t) => now - t < ATTEMPT_WINDOW_MS);
  attempts.set(key, hits);
  return hits.length >= MAX_ATTEMPTS;
}

function recordAttempt(key, ok) {
  const now = Date.now();
  if (ok) {
    attempts.delete(key);
    return;
  }
  const hits = (attempts.get(key) || []).filter((t) => now - t < ATTEMPT_WINDOW_MS);
  hits.push(now);
  attempts.set(key, hits);
}

function json(status, body) {
  return {
    statusCode: status,
    headers: {
      'Content-Type': 'application/json; charset=utf-8',
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
    },
    body: JSON.stringify(body),
  };
}

function clientKey(event) {
  const fwd = (event.headers || {})['x-forwarded-for'] || '';
  return fwd.split(',')[0].trim() || 'unknown';
}

exports.handler = async function (event) {
  const secret = process.env.ADMIN_SESSION_SECRET;
  const storedHash = (process.env.ADMIN_PASSWORD_HASH || '').trim().toLowerCase();
  const username = (process.env.ADMIN_USERNAME || 'admin').trim();

  // Not configured -> tell the page to use its own fallback.
  if (!secret || !storedHash) {
    return json(501, { ok: false, configured: false, reason: 'server_auth_not_configured' });
  }

  if (event.httpMethod === 'GET') {
    return json(200, { ok: true, configured: true, ttlMs: SESSION_TTL_MS });
  }

  if (event.httpMethod !== 'POST') {
    return json(405, { ok: false, error: 'method_not_allowed' });
  }

  let payload;
  try {
    payload = JSON.parse(event.body || '{}');
  } catch (e) {
    return json(400, { ok: false, error: 'bad_json' });
  }

  const key = clientKey(event);

  // ── verify an existing session ────────────────────────────────
  if (payload.action === 'verify') {
    const session = verify(payload.token, secret);
    if (!session) return json(401, { ok: false, error: 'invalid_session' });
    return json(200, { ok: true, user: session.u, exp: session.exp });
  }

  // ── log in ────────────────────────────────────────────────────
  if (payload.action === 'login') {
    if (tooManyAttempts(key)) {
      return json(429, { ok: false, error: 'too_many_attempts' });
    }

    const user = String(payload.username || '');
    const pass = String(payload.password || '');
    const userOk = safeEqual(user, username);
    const passOk = safeEqual(hashPassword(pass), storedHash);

    // Always spend the same work on both comparisons.
    recordAttempt(key, userOk && passOk);

    if (!userOk || !passOk) {
      return json(401, { ok: false, error: 'bad_credentials' });
    }

    const exp = Date.now() + SESSION_TTL_MS;
    return json(200, {
      ok: true,
      token: sign({ u: username, exp }, secret),
      user: username,
      exp,
    });
  }

  return json(400, { ok: false, error: 'unknown_action' });
};
