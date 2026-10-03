# -*- coding: utf-8 -*-
"""Emit the authoritative translation skeleton for every locale.

Two artefacts, both derived from en.json / data/products/*.json so that the
English side can never drift away from what build_lang.py looks up:

  data/i18n/_src/_keys_ui.json        {"English string": ""}      (flat)
  data/i18n/_src/_keys_products.json  {names/taglines/...: {...}} (English)
  data/i18n/_src/_hints.json          {"English string": "section|section"}

A translator copies _keys_ui.json -> data/i18n/_src/{lang}.json, fills the
values, and copies _keys_products.json -> data/i18n/products/{lang}.json.
Strings that stay identical to English (units, model codes, certifications)
may simply be omitted; build_lang.py falls back to the English source.

Usage
    python scripts/make_tr_skeleton.py
"""
from __future__ import annotations
import glob, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from needstranslating import needs  # noqa

EN = json.load(open(os.path.join(ROOT, 'data/i18n/en.json'), encoding='utf-8'))

FLAT = ('specLabel', 'quickLabel', 'specValue', 'chrome',
        'guideTitle', 'guideValues')
VALUED = ('nav', 'footer', 'category', 'detail', 'specNote')
ORDER = VALUED + ('categoryPage',) + FLAT


def ui_strings():
    """-> (ordered {english: ''}, {english: 'section|section'})"""
    skeleton, hints = {}, {}

    def add(s, *sections):
        if not needs(s):
            return
        skeleton.setdefault(s, '')
        h = hints.setdefault(s, [])
        for sec in sections:
            if sec not in h:
                h.append(sec)

    # sections whose *keys* are the English string to translate
    for sec in ('specLabel', 'quickLabel', 'specValue', 'chrome',
                'guideTitle', 'guideValues'):
        for k, v in EN.get(sec, {}).items():
            add(k, sec)

    # sections keyed by an identifier, whose *value* is the English string.
    # specNote belongs here: it is keyed by the buying-guide card title but the
    # translatable text is the explanatory sentence in the value.
    for sec in VALUED + ('specNote',):
        for k, v in EN.get(sec, {}).items():
            add(v, sec)

    for slug, m in EN.get('categoryPage', {}).items():
        for k, v in m.items():
            if isinstance(v, str):
                add(v, 'categoryPage')

    # Unit words are filtered out by needs(), but these two are *composed* into
    # data strings that a reader sees ("MOQ 10 pcs", "US$11 / pc"), so they
    # have to be translatable per locale.
    for s, hint in ((EN.get('moqUnit', ''), 'moqUnit'),
                    (EN.get('category', {}).get('perPiece', ''), 'category')):
        if s:
            skeleton.setdefault(s, '')
            hints.setdefault(s, [hint])

    # keep the canonical section order in the hint strings
    for k, v in hints.items():
        v.sort(key=lambda s: ORDER.index(s) if s in ORDER else 99)
        hints[k] = '|'.join(v)
    return skeleton, hints


def product_sources():
    names, taglines, apps, labels, prose_h = {}, {}, {}, {}, {}
    prose, suffix = {}, None
    suffix = EN['detail'].get('descSuffix', '')

    for f in sorted(glob.glob(os.path.join(ROOT, 'data/products/*.json'))):
        if os.path.basename(f) == 'categories.json':
            continue
        for p in json.load(open(f, encoding='utf-8')).get('products', []):
            pid = p['id']
            nm = p.get('name')
            if isinstance(nm, dict) and nm.get('en'):
                names[pid] = nm['en']
            tg = p.get('tagline')
            # unit-only taglines ("100 W · <30 min · 2000mAh*3") stay English
            if isinstance(tg, dict) and tg.get('en') and needs(tg['en']):
                taglines.setdefault(tg['en'], '')
            ap = p.get('applications')
            if isinstance(ap, dict) and ap.get('en'):
                apps.setdefault(ap['en'], '')
            # only highlight labels are needed here: apply_product_i18n.py
            # resolves spec-table labels from specLabel / quickLabel instead.
            for h in (p.get('highlights') or []):
                t = (h.get('text') or {}).get('en', '')
                if not t:
                    continue
                if ': ' in t:
                    labels.setdefault(t.split(': ', 1)[0], '')
                else:
                    prose_h.setdefault(t, '')

    # the three hand-written long descriptions
    for pid in ('gv18', 'gt20', 'ymc6628'):
        for f in glob.glob(os.path.join(ROOT, 'data/products/*.json')):
            if os.path.basename(f) == 'categories.json':
                continue
            for p in json.load(open(f, encoding='utf-8')).get('products', []):
                if p['id'] == pid:
                    d = p.get('description')
                    prose[pid] = d.get('en', '') if isinstance(d, dict) else (d or '')
    return {
        'descSuffix': suffix,
        'names': names,
        'taglines': taglines,
        'applications': apps,
        'highlightLabels': labels,
        'highlightProse': prose_h,
        'prose': prose,
    }


def dump(path, obj):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
        f.write('\n')
    return path


def main():
    out = os.path.join(ROOT, 'data/i18n/_src')
    os.makedirs(out, exist_ok=True)
    ui, hints = ui_strings()
    dump(os.path.join(out, '_keys_ui.json'), ui)
    dump(os.path.join(out, '_hints.json'), hints)
    prod = product_sources()
    dump(os.path.join(out, '_keys_products.json'), prod)

    print(f'ui keys      : {len(ui)}')
    for k, v in prod.items():
        print(f'  {k:<16} {len(v) if isinstance(v, dict) else 1}')
    missing = [p for p, v in prod['names'].items() if not v]
    if missing:
        print('  !! products without an English name:', missing)
    print('written      : data/i18n/_src/_keys_ui.json, _hints.json, _keys_products.json')


if __name__ == '__main__':
    main()
