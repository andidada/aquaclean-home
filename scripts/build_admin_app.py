#!/usr/bin/env python3
"""Assemble the admin back office into a standalone, publishable app.

Why: GitHub Pages cannot run server-side code, and the cloud auth used for a
real login gate only works on the app's own registered release domain. So the
admin is published as its own small app while the public site stays exactly
where it is.

The product images (85MB) are only used for preview thumbnails in the
dashboard, so instead of shipping them we point those references at the public
site - same pictures, a fraction of the upload.

    python scripts/build_admin_app.py
    -> ../aquaclean-admin-app/   (outside the repo, never committed)
"""
import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.abspath(os.path.join(ROOT, "..", "aquaclean-admin-app"))

PUBLIC_SITE = "https://www.hkdmj.net"

# Small enough to ship: the admin shell plus the data it edits.
COPY_DIRS = ["data", os.path.join("assets", "css"), os.path.join("assets", "js")]
COPY_FILES = ["favicon.ico", "CNAME"]
ADMIN_FILES = ["index.html", "login.html", "dashboard.html", "admin.css",
               "admin-theme.css", "admin.js", "auth-guard.js", "cloud.js"]


def copy_tree(rel):
    src = os.path.join(ROOT, rel)
    dst = os.path.join(OUT, rel)
    if not os.path.isdir(src):
        print("  ! 缺少目录，跳过: %s" % rel)
        return 0
    n = 0
    for dirpath, _dirs, files in os.walk(src):
        for fn in files:
            if fn.endswith(".pyc"):
                continue
            s = os.path.join(dirpath, fn)
            d = os.path.join(dst, os.path.relpath(s, src))
            os.makedirs(os.path.dirname(d), exist_ok=True)
            shutil.copy2(s, d)
            n += 1
    print("  + %s (%d 个文件)" % (rel, n))
    return n


def absolutise_images():
    """Dashboard previews point at the public site instead of local copies."""
    path = os.path.join(OUT, "admin", "dashboard.html")
    if not os.path.exists(path):
        print("  ! dashboard.html 不存在，跳过图片改写")
        return
    with open(path, encoding="utf-8") as f:
        html = f.read()
    before = html
    html = html.replace("../assets/images/", PUBLIC_SITE + "/assets/images/")
    if html != before:
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        hits = len(re.findall(re.escape(PUBLIC_SITE + "/assets/images/"), html))
        print("  + dashboard 图片改为绝对地址（%d 处）" % hits)


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "admin"), exist_ok=True)
    print("构建到 %s" % OUT)

    n = 0
    for f in ADMIN_FILES:
        s = os.path.join(ROOT, "admin", f)
        if os.path.exists(s):
            shutil.copy2(s, os.path.join(OUT, "admin", f))
            n += 1
        else:
            print("  ! 缺少 admin/%s" % f)
    print("  + admin/ (%d 个文件)" % n)

    for d in COPY_DIRS:
        copy_tree(d)
    for f in COPY_FILES:
        s = os.path.join(ROOT, f)
        if os.path.exists(s):
            shutil.copy2(s, os.path.join(OUT, f))

    absolutise_images()

    total = sum(
        os.path.getsize(os.path.join(dp, fn))
        for dp, _d, fns in os.walk(OUT) for fn in fns
    )
    count = sum(len(fns) for _dp, _d, fns in os.walk(OUT) for fn in fns)
    print("\n共 %d 个文件，%.1f MB" % (count, total / 1048576))
    return 0


if __name__ == "__main__":
    sys.exit(main())
