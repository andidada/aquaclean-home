#!/usr/bin/env python3
"""Deploy this site to Netlify (including Functions) and configure admin auth.

The repo is published by GitHub Pages, which cannot run server-side code, so
the admin auth Functions have to be deployed here directly rather than
waiting for a git-triggered build.

    set NETLIFY_TOKEN=...          # Netlify Personal Access Token
    python scripts/deploy_netlify.py

What it does, in order:
  1. find the site (by name, falling back to a name match on the URL)
  2. set ADMIN_SESSION_SECRET / ADMIN_PASSWORD_HASH / GITHUB_TOKEN
  3. deploy the working tree + netlify/functions via the Netlify CLI
  4. poll the auth endpoint until it reports configured:true

Order matters: environment variables must exist before the deploy that reads
them. Nothing is written to git.

GITHUB_TOKEN is read from the Windows Credential Manager entry
"git:https://github.com" (the same one admin/gh_token_server.py uses), so the
PAT never has to be typed here. Skip it with --no-github-token.
"""
import argparse
import ctypes
import json
import os
import secrets
import struct
import subprocess
import sys
import time
import urllib.error
import urllib.request

API = "https://api.netlify.com/api/v1"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CLI = os.path.join(
    os.path.expanduser("~"),
    ".workbuddy/binaries/node/workspace/node_modules/netlify-cli/bin/run.js",
)
NODE = os.path.join(
    os.path.expanduser("~"),
    ".workbuddy/binaries/node/versions/22.22.2-3/node.exe",
)

SITE_NAME = "aquaclean-home"
ADMIN_PASSWORD_HASH = "c55d159448b8df02f5242ae3e561b00ae99e6a1befccd0aec7577a775d943f44"


def req(method, path, token, body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(
        API + path,
        data=data,
        method=method,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "aquaclean-deploy",
        },
    )
    try:
        with urllib.request.urlopen(r, timeout=60) as resp:
            raw = resp.read().decode()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]


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
    status, sites = req("GET", "/sites", token)
    if status != 200 or not isinstance(sites, list):
        print("无法列出站点 (HTTP %s): %s" % (status, sites))
        return None
    for s in sites:
        if s.get("name") == SITE_NAME:
            return s
    for s in sites:
        if SITE_NAME in (s.get("url") or "") or SITE_NAME in (s.get("ssl_url") or ""):
            return s
    print("未在账号中找到站点 %s。现有站点：" % SITE_NAME)
    for s in sites:
        print("   -", s.get("name"), s.get("url"))
    return None


def set_env(token, site_id, key, value):
    # Newer accounts accept a list of {key, values:[{value, context}]};
    # older ones want a single {key, value}.
    status, out = req("POST", "/sites/%s/env" % site_id, token,
                      [{"key": key, "values": [{"value": value, "context": "all"}]}])
    if status in (200, 201):
        return True
    status2, out2 = req("POST", "/sites/%s/env" % site_id, token, {"key": key, "value": value})
    if status2 in (200, 201):
        return True
    print("   设置 %s 失败: HTTP %s %s / %s" % (key, status, out, out2))
    return False


def deploy(token, site_id):
    if not os.path.exists(CLI):
        print("找不到 Netlify CLI: %s" % CLI)
        return False
    cmd = [
        NODE, CLI, "deploy", "--prod",
        "--site", site_id,
        "--auth", token,
        "--dir", ".",
        "--functions", "netlify/functions",
        "--message", "admin auth functions + latest site content",
    ]
    print("\n[3/4] 部署（含 Functions）…")
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=900)
    print(r.stdout[-4000:] if r.stdout else "")
    if r.returncode != 0:
        print(r.stderr[-2000:] if r.stderr else "")
        print("部署失败 exit=%s" % r.returncode)
        return False
    return True


def verify(site_url, tries=20):
    url = site_url.replace("http://", "https://").rstrip("/")
    endpoint = url + "/.netlify/functions/admin-auth"
    print("\n[4/4] 验证函数端点 %s" % endpoint)
    for i in range(tries):
        try:
            r = urllib.request.urlopen(endpoint, timeout=30)
            body = r.read().decode()[:200]
            if r.status == 200 and '"configured":true' in body.replace(" ", ""):
                print("   ✓ 已生效: %s" % body[:120])
                return True
            print("   …等待 (%ds) HTTP %s %s" % (i * 10, r.status, body[:80]))
        except Exception as e:
            print("   …等待 (%ds) %s" % (i * 10, e))
        time.sleep(10)
    print("   超时：函数仍未生效")
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-github-token", action="store_true",
                    help="不设置 GITHUB_TOKEN（则后台继续用浏览器里的 PAT）")
    args = ap.parse_args()

    token = os.environ.get("NETLIFY_TOKEN", "").strip()
    if not token:
        print("请先设置环境变量 NETLIFY_TOKEN（Netlify Personal Access Token）")
        return 2

    print("[1/4] 查找站点 %s" % SITE_NAME)
    site = find_site(token)
    if not site:
        return 1
    site_id = site["id"]
    site_url = site.get("ssl_url") or site.get("url")
    print("   ✓ %s  (%s)" % (site.get("name"), site_url))

    secret = os.environ.get("ADMIN_SESSION_SECRET", "").strip() or secrets.token_urlsafe(48)
    env = {"ADMIN_SESSION_SECRET": secret, "ADMIN_PASSWORD_HASH": ADMIN_PASSWORD_HASH}
    if not args.no_github_token:
        pat = read_github_pat()
        if pat:
            env["GITHUB_TOKEN"] = pat
        else:
            print("   ! 未能读取本机 GitHub PAT，跳过 GITHUB_TOKEN")

    print("\n[2/4] 设置环境变量")
    ok = True
    for k, v in env.items():
        shown = v if k == "ADMIN_PASSWORD_HASH" else ("%s…(%d 字符)" % (v[:6], len(v)))
        print("   - %s = %s" % (k, shown))
        ok = set_env(token, site_id, k, v) and ok
    if not ok:
        return 1

    print("\n   ADMIN_SESSION_SECRET 完整值（请自行保存，之后不再显示）：")
    print("   " + secret)

    if not deploy(token, site_id):
        return 1
    return 0 if verify(site_url) else 1


if __name__ == "__main__":
    sys.exit(main())
