#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Normalize the Open Graph / Twitter block on the hand-maintained pages.

Two page classes are handled differently:

* Generated pages (category hubs + product details in every locale) are the
  output of `gen_pages.py`, which injects a complete, correct block itself.
  Here they are only *skipped* -- except for one targeted upgrade: a page
  whose og:image is still the generic brand image gets the more specific
  image for its path, and the hard-coded 1200x630 dimensions that belonged
  to the brand image are dropped.

* Hand-maintained pages -- the nine locale homes and the eleven editorial
  pages in en + zh -- are NEVER regenerated, and several of them carry
  stale or copy-pasted social blocks (og:url pointing at /robot-vacuum/,
  og:title taken from a different page, duplicate tags left by earlier
  partial injections, bare `zh` where og:locale:alternate wants `zh_CN`).
  For those the whole og:/twitter: block is STRIPPED and re-injected from
  the page's own <title> and meta description, so the preview text always
  matches what the page actually says.

Path conventions (this bit matters):
  LOCALIZED / SRC_ONLY keys are bare site paths with `.html` kept
  ('about.html', 'car-vacuum', ''), while page_url() wants a trailing
  slash for hubs ('export-certifications/').  page_path() returns the
  former; url_path() converts to the latter.  Getting this wrong used to
  emit og:url as `/en/about` (no `.html`) and made avail_langs() report
  all nine locales for en+zh-only pages.

Idempotent: stripping and re-injecting the same page yields the same bytes.

Usage
    python scripts/fix_og_meta.py
    python scripts/fix_og_meta.py --check     # report only
"""
from __future__ import annotations
import argparse, html as htmlmod, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_pages as G  # noqa: E402

ROOT = G.ROOT
LANGS = G.ALL_LANGS

TITLE_RE = re.compile(r'<title>(.*?)</title>', re.S)
TAG_RE = re.compile(r'<[^>]+>')
DESC_RE = re.compile(r'<meta name="description" content="([^"]*)"')
OGTW_RE = re.compile(
    # the optional-newline + optional-indent prefix must be separable, or the
    # indent of every tag whose preceding newline was eaten by the previous
    # match's \n? is orphaned -- 2 spaces per tag, re-accumulated on each run
    r'(?:\n[ \t]*)?[ \t]*<meta (?:property="og:[^"]*"|name="twitter:[^"]*")[^>]*>\n?')
# a bare `zh` (no territory) in og:locale:alternate marks a pre-standardisation
# og block -- e.g. the zh category hubs, which gen_pages cannot rebuild
# (there is no data/i18n/zh.json) and which therefore carry their oldest
# emitted block forever unless it is normalised in place
STALE_ALT_RE = re.compile(r'og:locale:alternate" content="[^"_"]*"')


def page_path(rel_file: str) -> str:
    """Site path in the LOCALIZED/SRC_ONLY convention (`.html` kept)."""
    if rel_file == 'index.html':
        return ''
    if rel_file.endswith('/index.html'):
        return rel_file[: -len('/index.html')]
    return rel_file


def url_path(bare: str) -> str:
    """Site path in the page_url() convention (hub gets a trailing slash)."""
    if bare == '' or bare.endswith('.html'):
        return bare
    return bare + '/'


def init_gen_pages():
    """Give gen_pages the same state main() would have built."""
    G.EN = G.load_json(os.path.join(ROOT, 'data/i18n/en.json'))
    G.CATS_JSON = G.load_json(os.path.join(ROOT, 'data/products/categories.json'))
    G.build_page_availability()
    G.build_page_image_map()


def extract_title_desc(head, fp):
    mt = TITLE_RE.search(head)
    md = DESC_RE.search(head)
    if not mt or not md:
        return None, None
    # the page stores these already HTML-escaped; the injector escapes
    # again, so unescape first or "&amp;" would double up
    title = htmlmod.unescape(TAG_RE.sub('', mt.group(1))).strip()
    desc = htmlmod.unescape(md.group(1)).strip()
    if not title or not desc:
        return None, None
    return title, desc


def normalize_handwritten(doc, lang, rel, fp):
    """Strip every og:/twitter: tag and re-inject one canonical block."""
    head_end = doc.find('</head>')
    if head_end < 0:
        return None
    head = doc[:head_end]
    title, desc = extract_title_desc(head, fp)
    if title is None:
        return None
    bare = page_path(rel)
    stripped = OGTW_RE.sub('', head)
    # a stripped block can orphan whitespace-only lines -- including one glued
    # straight after the canonical `>` when the tag's own leading newline was
    # eaten by the previous match; drop any run of spaces that ends a line
    stripped = re.sub(r'(?<=[>\n])[ \t]+(?=\n)', '', stripped)
    return G.inject_og_meta(
        stripped + doc[head_end:], lang, url_path(bare), title, desc,
        G.og_image_for(bare), G.avail_langs(bare))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()

    init_gen_pages()

    injected, upgraded, skipped, errors = [], [], [], []
    for lang in LANGS:
        base = os.path.join(ROOT, lang)
        for dirpath, _dirnames, filenames in os.walk(base):
            for name in filenames:
                if not name.endswith('.html'):
                    continue
                fp = os.path.join(dirpath, name)
                rel = os.path.relpath(fp, base).replace(os.sep, '/')
                bare = page_path(rel)
                with open(fp, encoding='utf-8') as f:
                    doc = f.read()

                # hand-maintained: locale homes (never emitted by gen_pages)
                # and the editorial pages that ship in en + zh only
                if rel == 'index.html' or bare in G.SRC_ONLY:
                    new = normalize_handwritten(doc, lang, rel, fp)
                    if new is None:
                        errors.append(f'{fp}: no <title>/meta description</head>')
                    elif new == doc:
                        skipped.append(fp)
                    else:
                        injected.append(fp)
                        if not args.check:
                            with open(fp, 'w', encoding='utf-8', newline='\n') as f:
                                f.write(new)
                    continue

                head = doc[: doc.find('</head>')] if '</head>' in doc else ''
                has_block = 'property="og:image"' in head
                if has_block and not STALE_ALT_RE.search(head):
                    # healthy block: only the generic-image upgrade applies
                    img = G.og_image_for(bare)
                    if img == G.OG_IMAGE_FALLBACK or G.OG_IMAGE_FALLBACK not in head:
                        skipped.append(fp)
                        continue
                    title, desc = extract_title_desc(head, fp)
                    if title is None:
                        errors.append(f'{fp}: no <title> or meta description')
                        continue
                    new = G.inject_og_meta(
                        doc, lang, url_path(bare), title, desc,
                        G.og_image_for(bare), G.avail_langs(bare))
                    if new == doc:
                        skipped.append(fp)
                        continue
                    upgraded.append(fp)
                    if not args.check:
                        with open(fp, 'w', encoding='utf-8', newline='\n') as f:
                            f.write(new)
                    continue

                # no block at all, or a stale one: strip + re-inject
                new = normalize_handwritten(doc, lang, rel, fp)
                if new is None:
                    errors.append(f'{fp}: no <title> or meta description</head>')
                elif new == doc:
                    skipped.append(fp)
                else:
                    injected.append(fp)
                    if not args.check:
                        with open(fp, 'w', encoding='utf-8', newline='\n') as f:
                            f.write(new)

    verb = 'would normalize' if args.check else 'normalized'
    sys.stderr.write(f'{verb}: {len(injected)}   image upgraded: {len(upgraded)}   '
                     f'untouched: {len(skipped)}   errors: {len(errors)}\n')
    for fp in injected[:12]:
        sys.stderr.write(f'   + {fp}\n')
    for fp in upgraded[:8]:
        sys.stderr.write(f'   ~ {fp}\n')
    for e in errors[:8]:
        sys.stderr.write(f'   ! {e}\n')
    if errors:
        sys.exit(1)


if __name__ == '__main__':
    main()
