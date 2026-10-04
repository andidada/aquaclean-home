/**
 * Server-side proxy for GitHub Contents API writes.
 *
 * The real crown jewels of this back office are not the pages - it is the
 * GitHub token. Without this proxy the PAT sits in the browser's
 * localStorage, readable by any script on the page and by anyone at the
 * keyboard, and it carries Contents: Read & Write on the repo.
 *
 * With it, the token lives only in the GITHUB_TOKEN environment variable.
 * The browser sends its short-lived admin session token instead, and this
 * function decides whether to forward the call.
 *
 * Optional: if GITHUB_TOKEN is not set the function answers 501 and the
 * admin UI keeps talking to GitHub directly with its stored PAT, so turning
 * this on is a one-variable change with no lockout risk.
 *
 * Required environment variables:
 *   GITHUB_TOKEN          - PAT with Contents: Read & Write
 *   ADMIN_SESSION_SECRET  - same value as admin-auth, used to check sessions
 * Optional:
 *   GITHUB_REPO           - defaults to "andidada/aquaclean-home"
 *   GITHUB_BRANCH         - defaults to "main"
 */
const crypto = require('crypto');

const DEFAULT_REPO = 'andidada/aquaclean-home';
const DEFAULT_BRANCH = 'main';

const ALLOWED_METHODS = new Set(['GET', 'PUT', 'DELETE', 'PATCH']);

function b64url(buf) {
  return Buffer.from(buf).toString('base64url');
}

function safeEqual(a, b) {
  const ba = Buffer.from(String(a || ''), 'utf8');
  const bb = Buffer.from(String(b || ''), 'utf8');
  if (ba.length !== bb.length) return false;
  return crypto.timingSafeEqual(ba, bb);
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

function sessionFrom(event) {
  const raw = (event.headers || {}).authorization || (event.headers || {}).Authorization || '';
  const m = /^Bearer\s+(.+)$/i.exec(raw.trim());
  return m ? m[1].trim() : '';
}

exports.handler = async function (event) {
  const secret = process.env.ADMIN_SESSION_SECRET;
  const githubToken = (process.env.GITHUB_TOKEN || '').trim();
  const repo = (process.env.GITHUB_REPO || DEFAULT_REPO).trim();
  const branch = (process.env.GITHUB_BRANCH || DEFAULT_BRANCH).trim();

  if (!secret || !githubToken) {
    return json(501, { ok: false, configured: false, reason: 'proxy_not_configured' });
  }

  if (!secret) return json(500, { ok: false, error: 'no_session_secret' });

  const session = verify(sessionFrom(event), secret);
  if (!session) return json(401, { ok: false, error: 'invalid_session' });

  // Health check used by the admin UI to decide whether to route through us.
  if (event.httpMethod === 'GET' && !(event.queryStringParameters || {}).path) {
    return json(200, { ok: true, configured: true, repo, branch });
  }

  const qs = event.queryStringParameters || {};
  const path = String(qs.path || '');
  if (!path) return json(400, { ok: false, error: 'missing_path' });

  // Only ever talk to our own repo, and only to the contents API.
  const url =
    'https://api.github.com/repos/' +
    repo +
    '/contents/' +
    path
      .split('/')
      .filter((seg) => seg.length && seg !== '.' && seg !== '..')
      .map(encodeURIComponent)
      .join('/') +
    '?ref=' +
    encodeURIComponent(branch);

  const method = (qs.method || (event.httpMethod === 'GET' ? 'GET' : 'PUT')).toUpperCase();
  if (!ALLOWED_METHODS.has(method)) {
    return json(405, { ok: false, error: 'method_not_allowed' });
  }

  const headers = {
    Authorization: 'Bearer ' + githubToken,
    Accept: 'application/vnd.github+json',
    'User-Agent': 'aquaclean-admin-proxy',
    'X-GitHub-Api-Version': '2022-11-28',
  };
  const init = { method, headers };
  if (method !== 'GET' && method !== 'DELETE') {
    headers['Content-Type'] = 'application/json';
    init.body = event.body || '{}';
  }

  try {
    const upstream = await fetch(url, init);
    const text = await upstream.text();
    return {
      statusCode: upstream.status,
      headers: {
        'Content-Type': upstream.headers.get('content-type') || 'application/json; charset=utf-8',
        'Cache-Control': 'no-store',
      },
      body: text,
    };
  } catch (e) {
    return json(502, { ok: false, error: 'upstream_failed', detail: String(e && e.message) });
  }
};
