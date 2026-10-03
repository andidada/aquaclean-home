# -*- coding: utf-8 -*-
"""Audit i18n coverage of the en/ source pages.

For every text node and translatable attribute on an en/ page, report the ones
that have **no entry** in the i18n dictionaries (and are not obviously
language-neutral like units, model codes or certification names).  The output
is the definitive "what keys are still missing" list, grouped by page section.

Usage
    python scripts/audit_coverage.py                 # all en pages, summary
    python scripts/audit_coverage.py --cat handheld-vacuum
    python scripts/audit_coverage.py --rich          # only the 3 rich templates
"""
from __future__ import annotations
import argparse, html as htmlmod, json, os, re, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from gen_pages import CATS, load_json, pick                     # noqa
from check_i18n_leftovers import KEEP, has_alpha                # noqa

SECTIONS = ('nav', 'footer', 'category', 'detail')
DICTS = ('specLabel', 'quickLabel', 'specValue', 'specNote')
# keyed by the English string itself
FLAT_SECTIONS = ('chrome', 'guideTitle', 'guideValues')


def translatable_set(lang='en'):
    """Every string that a language file *could* translate."""
    EN = load_json(os.path.join(ROOT, 'data/i18n/en.json'))
    known = set()

    def add(v):
        if isinstance(v, str) and v.strip():
            known.add(htmlmod.unescape(v).strip())

    for sec in SECTIONS:
        for v in EN.get(sec, {}).values():
            add(v)
            # templates such as "Why Choose Our {name}?" also appear expanded
            if isinstance(v, str) and '{' in v:
                known.add(re.sub(r'\{[a-z]+\}', '', v).strip())
    for sec in DICTS:
        for k, v in EN.get(sec, {}).items():
            add(k)
            add(v)
    for sec in FLAT_SECTIONS:
        for k, v in EN.get(sec, {}).items():
            add(k)
            add(v)
    for slug, m in EN.get('categoryPage', {}).items():
        for v in m.values():
            add(v)

    cj = load_json(os.path.join(ROOT, 'data/products/categories.json'))
    for c in cj['categories']:
        add(pick(c.get('name'), lang))
        add(pick(c.get('description'), lang))

    for cat in CATS:
        d = load_json(os.path.join(ROOT, 'data/products', cat + '.json'))
        for p in d.get('products', []):
            for fld in ('name', 'tagline', 'applications', 'description', 'category_name'):
                add(pick(p.get(fld), lang))
            for h in (p.get('highlights') or []):
                add(pick(h.get('text'), lang))
                if isinstance(h.get('text'), dict):
                    add(h['text'].get('en'))
            for arr in ('specs', 'quick_specs'):
                for s in (p.get(arr) or []):
                    add(pick(s.get('label'), lang))
                    add(pick(s.get('value'), lang))
    return known


KNOWN = None


def split_ctx(path):
    h = open(path, encoding='utf-8').read()
    h = re.sub(r'<style[^>]*>.*?</style>', ' ', h, flags=re.S)
    h = re.sub(r'<script[^>]*>.*?</script>', ' ', h, flags=re.S)
    out = []
    ctx = '(head)'
    pending = False
    for i, part in enumerate(re.split(r'(<[^>]+>)', h)):
        if i % 2 == 1:
            if re.match(r'<h[123]\b', part):
                pending = True
            m = re.search(r'<section[^>]*\bid="([^"]+)"', part)
            if m:
                ctx = '#' + m.group(1)
                pending = False
            continue
        t = re.sub(r'\s+', ' ', part).strip()
        if pending:
            if t:
                ctx = t[:44]
            pending = False
        if t:
            out.append((t, ctx))
    return out


def main():
    global KNOWN
    ap = argparse.ArgumentParser()
    ap.add_argument('--cat', default='')
    ap.add_argument('--rich', action='store_true')
    args = ap.parse_args()

    KNOWN = translatable_set('en')
    print(f'# known translatable strings: {len(KNOWN)}\n')

    rich = {'handheld-vacuum-gv18', 'robot-vacuum-gt20', 'tire-inflator-ymc6628'}
    cats = [args.cat] if args.cat else CATS

    by_ctx = collections.defaultdict(set)
    pages = 0
    for cat in cats:
        srcs = [f'{cat}/index.html']
        d = load_json(os.path.join(ROOT, 'data/products', cat + '.json'))
        srcs += [f'{cat}-{p["id"]}.html' for p in d['products']]
        for rel in srcs:
            if args.rich and rel[:-5] not in rich:
                continue
            fp = os.path.join(ROOT, 'en', rel)
            if not os.path.exists(fp):
                continue
            pages += 1
            for t, ctx in split_ctx(fp):
                if len(t) < 3 or KEEP.match(t) or not has_alpha(t):
                    continue
                if htmlmod.unescape(t).strip() in KNOWN:
                    continue
                by_ctx[ctx].add(t)

    print(f'# scanned {pages} en/ pages\n')
    total = sum(len(v) for v in by_ctx.values())
    print(f'# UNCOVERED strings: {total} distinct across {len(by_ctx)} sections\n')
    for ctx, items in sorted(by_ctx.items(), key=lambda kv: -len(kv[1])):
        print(f'--- {ctx}  [{len(items)}]')
        for s in sorted(items):
            print(f'      {s}')
    print()


if __name__ == '__main__':
    main()
