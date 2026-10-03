#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Expand the per-language `product` block of data/i18n/{lang}.json into
concrete translations and merge them into data/products/*.json.

Why this exists
---------------
36 of the 39 products are Alibaba-sourced records whose public copy is
*formulaic*:

    description = "{tagline}. OEM/ODM available; specifications from the
                   supplier listing."
    highlights  = ["{SpecLabel}: {value}", ...]

Only three products (gv18, gt20, ymc6628) carry hand-written prose. So instead
of transcribing 39 near-identical descriptions per language, each language file
supplies the reusable parts once and this script expands them.

`data/i18n/{lang}.json -> product` schema
    descSuffix      : the trailing sentence of every formulaic description
    names           : { product_id: localised product name }        (required)
    taglines        : { english_tagline: localised }
    applications    : { english_applications: localised }
    highlightLabels : { english_label: localised }
    highlightProse  : { english_highlight: localised }   (the 12 no-colon ones)
    prose           : { product_id: full localised description }    (3 products)

Usage
    python scripts/apply_product_i18n.py --langs es
    python scripts/apply_product_i18n.py --check      # report only
    python scripts/apply_product_i18n.py --restore    # drop generated keys
"""
from __future__ import annotations
import argparse, glob, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def save(p, data):
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write('\n')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--langs', default='')
    ap.add_argument('--check', action='store_true')
    ap.add_argument('--restore', action='store_true')
    args = ap.parse_args()

    if args.langs:
        langs = [l for l in args.langs.split(',') if l]
    else:
        langs = sorted(os.path.basename(p)[:-5] for p in
                       glob.glob(os.path.join(ROOT, 'data/i18n/products/*.json')))

    EN = load(os.path.join(ROOT, 'data/i18n/en.json'))
    cj = load(os.path.join(ROOT, 'data/products/categories.json'))
    cat_name = {c['slug']: c['name'] for c in cj['categories']}

    prod_files = sorted(f for f in glob.glob(os.path.join(ROOT, 'data/products/*.json'))
                        if os.path.basename(f) != 'categories.json')

    problems = []
    stats = {}
    for lang in langs:
        lp = os.path.join(ROOT, 'data/i18n', lang + '.json')
        if not os.path.exists(lp):
            problems.append(f'{lang}: no data/i18n/{lang}.json')
            continue
        L = load(lp)
        pp = os.path.join(ROOT, 'data/i18n/products', lang + '.json')
        if not os.path.exists(pp):
            problems.append(f'{lang}: no data/i18n/products/{lang}.json')
            continue
        P = load(pp)
        names = P.get('names') or {}
        taglines = P.get('taglines') or {}
        apps = P.get('applications') or {}
        hl_labels = P.get('highlightLabels') or {}
        hl_prose = P.get('highlightProse') or {}
        prose = P.get('prose') or {}
        desc_suffix = P.get('descSuffix') or EN['detail'].get('descSuffix', '')
        specvalue = L.get('specValue') or {}
        n_prod = 0

        for cat_file in prod_files:
            data = load(cat_file)
            cat = os.path.basename(cat_file)[:-5]
            changed = False
            for p in data.get('products', []):
                pid = p['id']
                n_prod += 1
                if args.restore:
                    for fld in ('name', 'tagline', 'applications', 'description'):
                        if isinstance(p.get(fld), dict):
                            p[fld].pop(lang, None)
                    for h in (p.get('highlights') or []):
                        if isinstance(h.get('text'), dict):
                            h['text'].pop(lang, None)
                    for arr in ('specs', 'quick_specs'):
                        for s in (p.get(arr) or []):
                            for fld in ('label', 'value'):
                                o = s.get(fld)
                                if isinstance(o, dict) and lang in o:
                                    if set(o.keys()) == {'en', lang}:
                                        s[fld] = o['en']
                                    else:
                                        o.pop(lang, None)
                    changed = True
                    continue

                # --- name ---------------------------------------------------
                nm = names.get(pid)
                if not nm:
                    problems.append(f'{lang}: no name for product {pid}')
                    continue
                p.setdefault('name', {})[lang] = nm

                # --- tagline (numeric-only taglines stay as-is) -------------
                tg_en = p.get('tagline', {}).get('en', '')
                p.setdefault('tagline', {})[lang] = taglines.get(tg_en, tg_en)

                # --- applications -------------------------------------------
                ap_en = p.get('applications', {}).get('en', '')
                if ap_en:
                    p.setdefault('applications', {})[lang] = apps.get(ap_en, ap_en)

                # --- description --------------------------------------------
                if pid in prose:
                    p.setdefault('description', {})[lang] = prose[pid]
                else:
                    p.setdefault('description', {})[lang] = \
                        f"{p['tagline'][lang]}. {desc_suffix}"

                # --- highlights ---------------------------------------------
                for h in (p.get('highlights') or []):
                    t_en = h.get('text', {}).get('en', '')
                    if not t_en:
                        continue
                    if ': ' in t_en:
                        lab, val = t_en.split(': ', 1)
                        lab_t = hl_labels.get(lab) or L.get('specLabel', {}).get(lab) or lab
                        val_t = specvalue.get(val, val)
                        h.setdefault('text', {})[lang] = f'{lab_t}: {val_t}'
                    else:
                        h.setdefault('text', {})[lang] = hl_prose.get(t_en, t_en)

                # --- spec table labels + values ------------------------------
                # Values become language-keyed too: the static HTML gets them
                # from the page-level dictionary, but product-detail.js renders
                # data/products/*.json directly, so both paths must agree.
                spec_label = L.get('specLabel') or {}
                quick_label = L.get('quickLabel') or spec_label
                for arr, lab_map in (('specs', spec_label), ('quick_specs', quick_label)):
                    for s in (p.get(arr) or []):
                        lab = s.get('label')
                        if isinstance(lab, dict):
                            lab_en = lab.get('en', '')
                            if lab_en:
                                lab[lang] = lab_map.get(lab_en, lab_en)
                        elif isinstance(lab, str) and lab:
                            s['label'] = {'en': lab, lang: lab_map.get(lab, lab)}
                        val = s.get('value')
                        if isinstance(val, str) and val:
                            s['value'] = {'en': val, lang: specvalue.get(val, val)}
                        elif isinstance(val, dict):
                            val[lang] = specvalue.get(val.get('en', ''), val.get('en', ''))

                # --- category_name (from categories.json) -------------------
                p.setdefault('category_name', {})
                if not p['category_name'].get(lang):
                    p['category_name'][lang] = cat_name.get(cat, {}).get(lang, '')
                changed = True
            if changed and not args.check:
                save(cat_file, data)
        stats[lang] = n_prod

    print('langs   :', langs)
    print('applied :', stats)
    if not args.check and not args.restore:
        print('written : data/products/*.json')
    print('problems:', len(problems))
    for x in problems[:40]:
        print('  !', x)


if __name__ == '__main__':
    main()
