#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Static audit of every page: do all local assets and links resolve?

Checks, per HTML page under each locale tree:
  * <img src>        -- file must exist (root-relative, page-relative, or data URI)
  * <link href>      -- stylesheets / icons / preconnects
  * <script src>
  * <a href>         -- internal links only (directory -> index.html),
                        anchors / mailto / tel / external are skipped
  * fetch()/DATA_URL targets referenced from inline scripts (e.g.
    /data/products/*.json served to the runtime)

External absolute URLs are reported separately as a count (og:image and
JSON-LD legitimately use them) so a sudden spike is visible.

Usage
    python scripts/audit_links.py            # summary
    python scripts/audit_links.py --verbose  # list every miss
"""
from __future__ import annotations
import argparse, os, re, sys, urllib.parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANGS = ['en', 'zh', 'ar', 'es', 'fr', 'id', 'ru', 'th', 'vi']

ATTR_RE = re.compile(r'<(img|link|script|a|source)\b[^>]*?(?:src|href)\s*=\s*"([^"]*)"', re.I)
# inline JS/CSS builds markup as strings ("' + img + '"), which the attribute
# regex would happily read as a URL -- keep the tags, drop their bodies
INNER_RE = re.compile(r'(<(script|style)\b[^>]*>).*?(</\2>)', re.S | re.I)
SKIP_PREFIX = ('#', 'mailto:', 'tel:', 'javascript:', 'data:', 'sms:', 'whatsapp:')


def exists(path):
    if os.path.isfile(path):
        return True
    # a directory serves its index.html
    if os.path.isdir(path) and os.path.isfile(os.path.join(path, 'index.html')):
        return True
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--verbose', action='store_true')
    args = ap.parse_args()

    misses = []
    external = 0
    checked = 0
    pages = 0
    data_refs = set()

    for lang in LANGS:
        base = os.path.join(ROOT, lang)
        for dirpath, _dirnames, filenames in os.walk(base):
            for name in sorted(filenames):
                if not name.endswith('.html'):
                    continue
                pages += 1
                fp = os.path.join(dirpath, name)
                reldir = os.path.dirname(fp)
                with open(fp, encoding='utf-8') as f:
                    doc = f.read()
                scan_doc = INNER_RE.sub(lambda m: m.group(1) + m.group(3), doc)

                for m in ATTR_RE.finditer(scan_doc):
                    tag, raw = m.group(1).lower(), m.group(2).strip()
                    if not raw or raw.startswith(SKIP_PREFIX):
                        continue
                    if raw.startswith(('http://', 'https://', '//')):
                        if 'hkdmj.net' in raw:
                            # self-URL: fine for canonical/og/jsonld, but an
                            # <img> pointing at the live host is a bug
                            if tag == 'img':
                                misses.append((fp, 'img points at live host', raw))
                            external += 1
                        continue
                    path = raw.split('#')[0].split('?')[0]
                    if path in ('', '/en', '/zh'):     # bare roots handled below
                        pass
                    if path.startswith('/'):
                        target = os.path.join(ROOT, path.lstrip('/').replace('/', os.sep))
                    else:
                        target = os.path.normpath(os.path.join(reldir, path.replace('/', os.sep)))
                    checked += 1
                    if not exists(target):
                        kind = 'dir' if path.endswith('/') else 'file'
                        misses.append((fp, f'{tag} {kind}', raw))
                    if tag == 'script' and 'DATA_URL' in doc:
                        for d in re.findall(r'"/data/[\w/.-]+"', doc):
                            data_refs.add(d.strip('"'))

    # data files the runtime fetches
    for d in sorted(data_refs):
        checked += 1
        if not os.path.isfile(os.path.join(ROOT, d.lstrip('/').replace('/', os.sep))):
            misses.append(('<inline script>', 'data fetch', d))

    # root index
    if not os.path.isfile(os.path.join(ROOT, 'index.html')):
        misses.append(('<site root>', 'missing', 'index.html'))

    print(f'pages scanned : {pages}')
    print(f'local refs    : {checked}')
    print(f'self-host URLs (meta/jsonld): {external}')
    print(f'MISSES        : {len(misses)}')
    bykind = {}
    for fp, kind, raw in misses:
        bykind.setdefault(kind, []).append((fp, raw))
    for kind, items in sorted(bykind.items(), key=lambda x: -len(x[1])):
        print(f'  {kind}: {len(items)}')
        for fp, raw in (items if args.verbose else items[:6]):
            print(f'     {os.path.relpath(fp, ROOT)}  ->  {raw}')
    if misses:
        sys.exit(1)


if __name__ == '__main__':
    main()
