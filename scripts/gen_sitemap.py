#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rebuild sitemap.xml with per-page hreflang alternates.

The sitemap is derived from the filesystem, so it can never drift from what is
actually deployed.  For every page path it discovers which of the nine locales
ship that page and emits one <url> per locale, each carrying the same
<xhtml:link rel="alternate"> set that the page's own <head> declares.

Layout produced:

    49 paths x 9 locales  = 441   (home, 9 category hubs, 39 product pages)
    11 paths x 2 locales  =  22   (about / faq / OEM landings, en+zh only)
    ----------------------------
                            463   <url> entries

The site root (``/index.html``, a JS landing that canonicalises to ``/en/``) is
kept as a single alternate-less entry so existing crawler state keeps working.

Usage
    python scripts/gen_sitemap.py
    python scripts/gen_sitemap.py --check     # report drift only, write nothing
"""
from __future__ import annotations
import argparse, datetime, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'sitemap.xml')

BASE = 'https://www.hkdmj.net'
LANGS = ['en', 'zh', 'ar', 'es', 'fr', 'id', 'ru', 'th', 'vi']
X_DEFAULT = 'en'


def page_paths(lang: str) -> set[str]:
    """Every HTML page of a locale, as a locale-relative site path.

    ``en/index.html``        -> ''            (the locale home, served at /en/)
    ``en/car-vacuum/index.html`` -> 'car-vacuum'  (a directory-style hub)
    ``en/car-vacuum-k15.html``   -> 'car-vacuum-k15.html'
    """
    base = os.path.join(ROOT, lang)
    if not os.path.isdir(base):
        return set()
    found = set()
    for dirpath, _dirnames, filenames in os.walk(base):
        for name in filenames:
            if not name.endswith('.html'):
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), base)
            rel = rel.replace(os.sep, '/')
            if rel == 'index.html':
                found.add('')
            elif rel.endswith('/index.html'):
                found.add(rel[: -len('/index.html')])
            else:
                found.add(rel)
    return found


def site_url(lang: str, path: str) -> str:
    """Absolute URL of a page.

    ``''`` is the locale home and keeps one trailing slash (``/en/``); a hub
    keeps one trailing slash (``/en/car-vacuum/``); a page keeps its ``.html``.
    """
    if path == '':
        return f'{BASE}/{lang}/'
    if path.endswith('.html'):
        return f'{BASE}/{lang}/{path}'
    return f'{BASE}/{lang}/{path}/'


def discover() -> dict[str, list[str]]:
    """Map every page path to the locales that actually ship it.

    Returned in canonical locale order, so callers can build hreflang sets
    directly: ``{'': ['en', 'zh', ...], 'car-vacuum': [...], ...}``.
    """
    per_lang = {l: page_paths(l) for l in LANGS}
    index: dict[str, list[str]] = {}
    for path in set().union(*per_lang.values()):
        index[path] = [l for l in LANGS if path in per_lang[l]]
    return index


def file_for(lang: str, path: str) -> str:
    """On-disk path of a page.  Hub pages live at ``<hub>/index.html``."""
    if path == '' or not path.endswith('.html'):
        return os.path.join(ROOT, lang, path, 'index.html')
    return os.path.join(ROOT, lang, path)


def lastmod() -> str:
    """Newest mtime among the tracked page directories, as YYYY-MM-DD."""
    newest = 0.0
    for lang in LANGS:
        base = os.path.join(ROOT, lang)
        if not os.path.isdir(base):
            continue
        for dirpath, _d, filenames in os.walk(base):
            for name in filenames:
                if name.endswith('.html'):
                    newest = max(newest, os.path.getmtime(os.path.join(dirpath, name)))
    if not newest:
        newest = os.path.getmtime(OUT) if os.path.exists(OUT) else 0.0
    return datetime.date.fromtimestamp(newest).isoformat()


def build() -> str:
    index = discover()

    def sort_key(p):
        # locale home first, then hubs, then product pages; alphabetical within
        return (0 if p == '' else 1 if '/' not in p and not p.endswith('.html') else 2, p)

    date = lastmod()
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"',
        '        xmlns:xhtml="http://www.w3.org/1999/xhtml">',
        '  <url>',
        f'    <loc>{BASE}/</loc>',
        f'    <lastmod>{date}</lastmod>',
        '  </url>',
    ]

    n_url = 1
    groups = 0
    for path in sorted(index, key=sort_key):
        langs = index[path]
        groups += 1
        for lang in langs:
            lines.append('  <url>')
            lines.append(f'    <loc>{site_url(lang, path)}</loc>')
            lines.append(f'    <lastmod>{date}</lastmod>')
            # x-default first, then every locale that actually has this page
            lines.append(f'    <xhtml:link rel="alternate" hreflang="x-default"'
                         f' href="{site_url(X_DEFAULT, path)}"/>')
            for alt in langs:
                lines.append(f'    <xhtml:link rel="alternate" hreflang="{alt}"'
                             f' href="{site_url(alt, path)}"/>')
            lines.append('  </url>')
            n_url += 1

    lines.append('</urlset>')
    lines.append('')
    sys.stderr.write(f'paths: {groups}   urls: {n_url}   lastmod: {date}\n')
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true',
                    help='report the URL count without writing sitemap.xml')
    args = ap.parse_args()

    xml = build()
    old = ''
    if os.path.exists(OUT):
        with open(OUT, encoding='utf-8') as f:
            old = f.read()

    if args.check:
        sys.stderr.write('drift: ' + ('none (up to date)' if old == xml else 'sitemap.xml is stale')
                         + '\n')
        return

    if old == xml:
        sys.stderr.write('sitemap.xml already up to date\n')
        return
    with open(OUT, 'w', encoding='utf-8', newline='\n') as f:
        f.write(xml)
    sys.stderr.write(f'written: {OUT}\n')


if __name__ == '__main__':
    main()
