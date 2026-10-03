#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Structural validation of the Open Graph / Twitter block on every page.

Checks, per page:
  * each og:/twitter: tag appears at most once (no duplicates)
  * og:url equals the canonical link (same URL, byte for byte)
  * og:title / twitter:title equal <title>; og:description equals meta description
  * og:image resolves to a file under the site root (or is an absolute CDN URL)
  * og:locale:alternate lists exactly the locales that ship the page

Exit code 1 if any problem is found.  Idempotent / read-only.

Usage
    python scripts/check_og_meta.py
"""
from __future__ import annotations
import html as htmlmod
import os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_pages as G  # noqa: E402

ROOT = G.ROOT
LANGS = G.ALL_LANGS

TITLE_RE = re.compile(r'<title>(.*?)</title>', re.S)
DESC_RE = re.compile(r'<meta name="description" content="([^"]*)"')
OG_RE = re.compile(r'<meta (?:property="og:([^"]*)"|name="twitter:([^"]*)") content="([^"]*)"')
CANON_RE = re.compile(r'<link rel="canonical" href="([^"]*)"')
ALT_RE = re.compile(r'<link rel="alternate" hreflang="([a-z-]+)" href="[^"]*"')


def page_path(rel_file):
    """Site path in the LOCALIZED/SRC_ONLY convention (bare, .html kept)."""
    if rel_file == 'index.html':
        return ''
    if rel_file.endswith('/index.html'):
        return rel_file[: -len('/index.html')]
    return rel_file


def url_path(bare):
    """Site path in the page_url() convention (hub gets a trailing slash)."""
    if bare == '' or bare.endswith('.html'):
        return bare
    return bare + '/'


def main():
    G.EN = G.load_json(os.path.join(ROOT, 'data/i18n/en.json'))
    G.CATS_JSON = G.load_json(os.path.join(ROOT, 'data/products/categories.json'))
    G.build_page_availability()
    G.build_page_image_map()

    problems = {}          # kind -> count
    examples = {}          # kind -> list of (file, detail)

    def flag(kind, fp, detail=''):
        problems[kind] = problems.get(kind, 0) + 1
        examples.setdefault(kind, []).append((fp, detail))

    npages = 0
    for lang in LANGS:
        base = os.path.join(ROOT, lang)
        for dirpath, _dirnames, filenames in os.walk(base):
            for name in sorted(filenames):
                if not name.endswith('.html'):
                    continue
                fp = os.path.join(dirpath, name)
                rel = os.path.relpath(fp, base).replace(os.sep, '/')
                npages += 1
                with open(fp, encoding='utf-8') as f:
                    doc = f.read()
                head_end = doc.find('</head>')
                head = doc[:head_end] if head_end >= 0 else doc

                tags = []       # [(kind, value)] in document order
                for m in OG_RE.finditer(head):
                    kind = ('og:' if m.group(1) is not None else 'twitter:') + (m.group(1) or m.group(2))
                    tags.append((kind, htmlmod.unescape(m.group(3))))

                seen = set()
                for kind, value in tags:
                    # og:locale:alternate is legitimately multi-valued;
                    # every other og:/twitter: tag must appear once
                    if kind in seen and kind != 'og:locale:alternate':
                        flag(kind + ' x2', fp)
                    seen.add(kind)
                vals = dict(reversed(tags))   # last occurrence wins

                mt = TITLE_RE.search(head)
                title = htmlmod.unescape(mt.group(1)).strip() if mt else ''

                if 'og:title' in vals and vals['og:title'] != title:
                    flag('og:title != <title>', fp, f'{vals["og:title"]!r} vs {title!r}')
                if 'og:description' in vals:
                    md = DESC_RE.search(head)
                    if md and vals['og:description'] != htmlmod.unescape(md.group(1)).strip():
                        flag('og:description != meta desc', fp, vals['og:description'][:60])
                if 'twitter:title' in vals and vals['twitter:title'] != title:
                    flag('twitter:title != <title>', fp)

                canon = CANON_RE.search(head)
                if canon and 'og:url' in vals and vals['og:url'] != canon.group(1):
                    flag('og:url != canonical', fp, f'{vals["og:url"]} vs {canon.group(1)}')

                if 'og:image' in vals:
                    img = vals['og:image']
                    if img.startswith(G.SITE):
                        local = os.path.join(ROOT, img[len(G.SITE):].lstrip('/').replace('/', os.sep))
                        if not os.path.exists(local):
                            flag('og:image missing file', fp, img)
                else:
                    flag('og:image absent', fp)

                # hreflang block convention (fix_hreflang.py): every locale
                # that ships the page (self included) plus x-default
                bare = page_path(rel)
                want = set(G.avail_langs(bare)) | {'x-default'}
                got = {m.group(1) for m in ALT_RE.finditer(head)}
                got_og = {t[1] for t in tags if t[0] == 'og:locale:alternate'}
                # hreflang uses bare codes, og:locale uses xx_YY; compare via LANGMETA
                want_og = {G.LANGMETA[l]['locale'] for l in G.avail_langs(bare) if l != lang}
                if got != want:
                    flag('hreflang set mismatch', fp, f'{sorted(got)} vs {sorted(want)}')
                if got_og != want_og:
                    flag('og:locale:alternate mismatch', fp, f'{sorted(got_og)} vs {sorted(want_og)}')

    order = sorted(problems, key=lambda k: -problems[k])
    sys.stderr.write(f'pages: {npages}\n')
    if not problems:
        sys.stderr.write('OG structure: 0 problems\n')
        return
    for k in order:
        sys.stderr.write(f'{k}: {problems[k]}\n')
        for fp, detail in examples[k][:6]:
            sys.stderr.write(f'   {fp}' + (f'  [{detail}]' if detail else '') + '\n')
    sys.exit(1)


if __name__ == '__main__':
    main()
