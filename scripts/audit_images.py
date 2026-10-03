#!/usr/bin/env python3
"""Rendering-level image audit.

Simulates how a browser resolves every image reference on every page and asserts
each one maps to a real file. This closes the gap that a flat <img src> scan
leaves open:

  * srcset / <source media> candidates inside <picture>
  * CSS url(...) in <style> blocks and inline style="" attributes
  * page-relative (./x, ../x), root-relative (/x) and bare (x) forms
  * pages at different depths (/en/index.html vs /en/faq/index.html)

Exits non-zero if any page would render a broken image.
"""
import glob
import os
import posixpath
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {'.git', 'scripts', 'data', 'shots', 'node_modules', '.tmp_en_backup',
             '.tmp_en_p1', '.tmp_idem_a', '.tmp_idem_es', '.tmp_idem_es2'}

IMG_ATTR = re.compile(
    r'<(?:img|source)\b[^>]*?\b(?:src|data-src|srcset)\s*=\s*"([^"]*)"', re.I)
CSS_URL = re.compile(r'url\(\s*[\'"]?([^\'")]+)[\'"]?\s*\)', re.I)
STYLE_BLOCK = re.compile(r'<style\b[^>]*>(.*?)</style>', re.S | re.I)
STYLE_ATTR = re.compile(r'<[^>]+\bstyle\s*=\s*"([^"]*)"', re.I)

RASTER_EXT = ('.webp', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.avif', '.ico')


def is_external(u):
    return (not u or u.startswith(('http://', 'https://', '//', 'data:', 'mailto:',
                                   '#', 'javascript:', '{', '$', '%')))


def split_srcset(v):
    out = []
    for part in v.split(','):
        cand = part.strip().split()[0] if part.strip() else ''
        if cand:
            out.append(cand)
    return out


def resolve(page_rel, ref):
    """Resolve a reference the way a browser would, from the page's own URL."""
    ref = ref.split('?')[0].split('#')[0]
    if ref.startswith('/'):
        return ref.lstrip('/')
    # a directory URL (…/index.html) keeps its own folder as the base
    base = posixpath.dirname(page_rel)
    return posixpath.normpath(posixpath.join(base, ref))


def pages():
    out = []
    for dp, dn, fn in os.walk(ROOT):
        dn[:] = [d for d in dn if d not in SKIP_DIRS and not d.startswith('.tmp')]
        for f in fn:
            if f.endswith('.html'):
                rel = os.path.relpath(os.path.join(dp, f), ROOT).replace('\\', '/')
                out.append(rel)
    return sorted(out)


def collect(doc, page_rel):
    """Every local image reference a browser would attempt to fetch."""
    refs = set()
    for v in IMG_ATTR.findall(doc):
        for cand in (split_srcset(v) if ',' in v else [v]):
            if not is_external(cand) and cand.lower().endswith(RASTER_EXT):
                refs.add(resolve(page_rel, cand))
    # inline + embedded CSS
    css_blobs = STYLE_BLOCK.findall(doc) + STYLE_ATTR.findall(doc)
    for blob in css_blobs:
        for u in CSS_URL.findall(blob):
            if not is_external(u) and u.lower().split('?')[0].endswith(RASTER_EXT):
                refs.add(resolve(page_rel, u))
    return refs


def main():
    bad = []
    total = 0
    page_count = 0
    for rel in pages():
        with open(os.path.join(ROOT, rel), encoding='utf-8', errors='ignore') as fh:
            doc = fh.read()
        page_count += 1
        for r in collect(doc, rel):
            total += 1
            if not os.path.isfile(os.path.join(ROOT, r)):
                bad.append((rel, r))

    print(f'pages rendered : {page_count}')
    print(f'image refs     : {total}')
    print(f'BROKEN         : {len(bad)}')
    for r, i in bad[:25]:
        print('   ', r, '->', i)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
