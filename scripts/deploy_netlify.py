#!/usr/bin/env python3
"""Deploy this site to Netlify (including Functions) over the REST API.

Why this exists: the public site is published by GitHub Pages, which cannot
run server-side code, and this repo is not connected to Netlify (the
aquaclean-home.netlify.app site is a stale snapshot that ignores pushes).
So the admin auth Functions have to be uploaded directly.

    set NETLIFY_TOKEN=nfp_...          # Netlify Personal Access Token
    python scripts/deploy_netlify.py            # admin + functions (default)
    python scripts/deploy_netlify.py --full     # every file, incl. 86MB images

Steps, in this order:
  1. find the site
  2. set ADMIN_SESSION_SECRET / ADMIN_PASSWORD_HASH / GITHUB_TOKEN
  3. upload files + function bundles
  4. poll the auth endpoint until it answers configured:true

The environment variables must be set BEFORE the deploy that reads them.
Nothing is written to git.

GITHUB_TOKEN is read from the Windows Credential Manager entry
"git:https://github.com" (the same one admin/gh_token_server.py uses) so the
PAT never has to be typed. Skip with --no-github-token.

Uses urllib + zipfile only - no npm, no CLI.
"""
import argparse
import ctypes
import fnmatch
import hashlib
import io
import json
import os
import secrets
import struct
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile

API = "https://api.netlify.com/api/v1"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

SITE_NAME = "aquaclean-home"
ADMIN_PASSWORD_HASH = "c55d159448b8df02f5242ae3e561b00ae99e6a1befccd0aec7577a775d943f44"
FUNCTIONS_DIR = "netlify/functions"

# What the admin actually needs. The 86MB of assets/images and the nine
# localised page trees live on Pages and are not required here.
INCLUDE = ["admin/**", "data/**", "assets/css/**", "assets/js/**",
           "netlify/functions/**", "*.html", "*.txt", "*.xml", "*.ico", "*.png"]
EXCLUDE = ["**/__pycache__/**", "**/*.pyc", "**/.tmp*", "**/*.log", "shots/**"]

LANG_DIRS = {"en", "zh", "ar", "es", "fr", "id", "ru", "th", "vi", "ca"}


def api(method, path, token, body=None, raw=None, content_type="application/json"):
    if raw is not None:
        data = raw
    elif body is not None:
        data = json.dumps(body).encode()
    else:
        data = None
    r = urllib.request.Request(
        API + path, data=data, method=method,
        headers={"Authorization": "Bearer " + token,
                 "Content-Type": content_type,
                 "User-Agent": "aquaclean-deploy"},
    )
    try:
        with urllib.request.urlopen(r, timeout=120) as resp:
            txt = resp.read().decode()
            try:
                return resp.status, (json.loads(txt) if txt else None)
            except ValueError:
                return resp.status, txt
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:300]


def read_github_pat():
    """Read the PAT stored by git credential manager (same target the bridge uses)."""
    CredRead = ctypes.windll.advapi32.CredReadW
    CredRead.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_uint32,
                         ctypes.POINTER(ctypes.c_void_p)]
    CredRead.restype = ctypes.c_bool
    CredFree = ctypes.windll.advapi32.CredFree
    CredFree.argtypes = [ctypes.c_void_p]
    p = ctypes.c_void_p()
    if not CredRead("git:https://github.com", 1, 0, ctypes.byref(p)):
        return None
    base = p.value
    size = struct.unpack("<I", ctypes.string_at(base + 32, 4))[0]
    ptr = struct.unpack("<Q", ctypes.string_at(base + 40, 8))[0]
    pat = ctypes.wstring_at(ptr, size // 2).strip()
    CredFree(p.value)
    return pat or None


def find_site(token):
    status, sites = api("GET", "/sites", token)
    if status != 200 or not isinstance(sites, list):
        print("无法列出站点 (HTTP %s): %s" % (status, sites))
        return None
    for s in sites:
        if s.get("name") == SITE_NAME:
            return s
    for s in sites:
        if SITE_NAME in (s.get("url") or "") or SITE_NAME in (s.get("ssl_url") or ""):
            return s
    print("账号里没有 %s，现有站点：" % SITE_NAME)
    for s in sites:
        print("   -", s.get("name"), s.get("url"))
    return None


def set_env(token, site_id, key, value):
    status, out = api("POST", "/sites/%s/env" % site_id, token,
                      [{"key": key, "values": [{"value": value, "context": "all"}]}])
    if status in (200, 201):
        return True
    status2, out2 = api("POST", "/sites/%s/env" % site_id, token, {"key": key, "value": value})
    if status2 in (200, 201):
        return True
    print("   设置 %s 失败: HTTP %s %s | %s" % (key, status, out, out2))
    return False


def collect(full):
    """Return [(url_path, abs_path)] for the files to upload."""
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in (".git", ".github", "__pycache__", "scripts")]
        if not full and os.path.relpath(dirpath, ROOT) in LANG_DIRS:
            dirnames[:] = []
            continue
        for fn in filenames:
            rel = os.path.relpath(os.path.join(dirpath, fn), ROOT).replace("\\", "/")
            if not full:
                if rel.startswith("assets/images/"):
                    continue
                if not any(fnmatch.fnmatch(rel, p) or
                           (p.endswith("/**") and rel.startswith(p[:-3]))
                           for p in INCLUDE):
                    continue
            if any(fnmatch.fnmatch(rel, p) for p in EXCLUDE):
                continue
            out.append(("/" + rel, os.path.join(dirpath, fn)))
    return out


def build_function_zips():
    """Return {name: zip_bytes} - each bundle holds one self-contained file."""
    fdir = os.path.join(ROOT, FUNCTIONS_DIR)
    bundles = {}
    if not os.path.isdir(fdir):
        return bundles
    for fn in sorted(os.listdir(fdir)):
        if not fn.endswith(".js"):
            continue
        src = os.path.join(fdir, fn)
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
            z.write(src, fn)  # entry name must match the function name
        bundles[fn[:-3]] = buf.getvalue()
    return bundles


def upload_files(token, deploy_id, files, required):
    by_sha = {}
    for url_path, abs_path in files:
        with open(abs_path, "rb") as fh:
            blob = fh.read()
        by_sha[hashlib.sha1(blob).hexdigest()] = (url_path, blob)
    todo = required if required else list(by_sha.keys())
    print("   上传 %d 个文件…" % len(todo))
    done = 0
    for sha in todo:
        if sha not in by_sha:
            continue
        url_path, blob = by_sha[sha]
        path = url_path.lstrip("/")
        status, _ = api("PUT", "/deploys/%s/files/%s" % (deploy_id, path),
                        token, raw=blob, content_type="application/octet-stream")
        if status not in (200, 201, 204):
            print("   文件失败 %s (HTTP %s)" % (path, status))
            return False
        done += 1
        if done % 200 == 0:
            print("      …%d/%d" % (done, len(todo)))
    print("   ✓ %d 个文件已上传" % done)
    return True


def upload_functions(token, deploy_id, bundles, required):
    by_sha = {hashlib.sha1(b).hexdigest(): (n, b) for n, b in bundles.items()}
    todo = [s for s in (required or []) if s in by_sha] or list(by_sha.keys())
    print("   上传 %d 个函数…" % len(todo))
    for sha in todo:
        name, blob = by_sha[sha]
        status, out = api("PUT", "/deploys/%s/functions/%s" % (deploy_id, name),
                          token, raw=blob, content_type="application/zip")
        if status not in (200, 201, 204):
            print("   函数 %s 失败 (HTTP %s): %s" % (name, status, out))
            return False
        print("     ✓ %s (%d 字节)" % (name, len(blob)))
    return True


def wait_ready(token, deploy_id, tries=60):
    for i in range(tries):
        status, d = api("GET", "/deploys/%s" % deploy_id, token)
        if status == 200 and isinstance(d, dict):
            state = d.get("state")
            if state in ("ready", "current"):
                print("   ✓ 部署状态: %s" % state)
                return True
            if state == "error":
                print("   ✗ 部署失败: %s" % (d.get("error_message") or d))
                return False
            if i % 3 == 0:
                print("     …%s" % state)
        time.sleep(5)
    print("   等待部署就绪超时")
    return False


def verify(site_url, tries=15):
    base = site_url.replace("http://", "https://").rstrip("/")
    ep = base + "/.netlify/functions/admin-auth"
    print("\n[4/4] 验证 %s" % ep)
    for i in range(tries):
        try:
            r = urllib.request.urlopen(ep, timeout=30)
            body = r.read().decode()[:200]
            if r.status == 200 and '"configured":true' in body.replace(" ", ""):
                print("   ✓ 服务端鉴权已生效: %s" % body[:120])
                return True
            print("   …(%ds) HTTP %s %s" % (i * 8, r.status, body[:80]))
        except Exception as e:
            print("   …(%ds) %s" % (i * 8, e))
        time.sleep(8)
    print("   超时：函数未生效")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="上传全部文件（含 86MB 图片）")
    ap.add_argument("--no-github-token", action="store_true")
    args = ap.parse_args()

    token = os.environ.get("NETLIFY_TOKEN", "").strip()
    if not token:
        print("请先设置环境变量 NETLIFY_TOKEN（Netlify Personal Access Token）")
        return 2

    print("[1/4] 查找站点 %s" % SITE_NAME)
    site = find_site(token)
    if not site:
        return 1
    site_id, site_url = site["id"], site.get("ssl_url") or site.get("url")
    print("   ✓ %s (%s)" % (site.get("name"), site_url))

    secret = os.environ.get("ADMIN_SESSION_SECRET", "").strip() or secrets.token_urlsafe(48)
    env = {"ADMIN_SESSION_SECRET": secret, "ADMIN_PASSWORD_HASH": ADMIN_PASSWORD_HASH}
    if not args.no_github_token:
        pat = read_github_pat()
        if pat:
            env["GITHUB_TOKEN"] = pat
        else:
            print("   ! 未读到本机 GitHub PAT，跳过 GITHUB_TOKEN")

    print("\n[2/4] 设置环境变量")
    for k, v in env.items():
        shown = v if k == "ADMIN_PASSWORD_HASH" else "%s…(%d 字符)" % (v[:6], len(v))
        print("   - %s = %s" % (k, shown))
        if not set_env(token, site_id, k, v):
            return 1
    print("\n   ADMIN_SESSION_SECRET（请自行保存，之后不再显示）：\n   " + secret)

    print("\n[3/4] 上传部署")
    files = collect(args.full)
    bundles = build_function_zips()
    print("   %d 个文件, %d 个函数: %s" % (len(files), len(bundles), ", ".join(bundles) or "无"))

    file_shas, by_path = {}, {}
    for url_path, abs_path in files:
        with open(abs_path, "rb") as fh:
            blob = fh.read()
        file_shas[url_path] = hashlib.sha1(blob).hexdigest()
        by_path[url_path] = abs_path
    func_shas = {n: hashlib.sha1(b).hexdigest() for n, b in bundles.items()}

    status, d = api("POST", "/sites/%s/deploys" % site_id, token, {
        "files": file_shas,
        "functions": func_shas,
        "framework": None,
        "async": False,
    })
    if status not in (200, 201) or not isinstance(d, dict) or not d.get("id"):
        print("   创建部署失败 (HTTP %s): %s" % (status, d))
        return 1
    deploy_id = d["id"]
    print("   ✓ 部署 %s 已创建" % deploy_id)

    if not upload_files(token, deploy_id, files, d.get("required")):
        return 1
    if bundles and not upload_functions(token, deploy_id, bundles, d.get("required_functions")):
        return 1
    if not wait_ready(token, deploy_id):
        return 1

    return 0 if verify(site_url) else 1


if __name__ == "__main__":
    sys.exit(main())
