# -*- coding: utf-8 -*-
"""Validate a locale's hand-authored translation sources.

Checks, for data/i18n/_src/{lang}.json:
  * key set matches data/i18n/_src/_keys_ui.json exactly (no drift, no typos)
  * every {placeholder} in the English source survives in the translation
  * values are non-empty, and flags values that are byte-identical to English

And for data/i18n/products/{lang}.json:
  * same sub-blocks and same key sets as _keys_products.json
  * the *English* keys inside taglines/applications/highlightLabels/
    highlightProse are unchanged (they are lookup keys, not copy)

Usage
    python scripts/check_tr_src.py es
    python scripts/check_tr_src.py            # every _src/*.json except _keys*/_hints
"""
from __future__ import annotations
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'data/i18n/_src')
PH = re.compile(r'\{[a-zA-Z_]+\}')


def phs(s):
    """Placeholders that must survive translation (`{s}` is droppable)."""
    return [p for p in PH.findall(s) if p != '{s}']

# strings whose translation may legitimately equal the English source
SAME_OK = {'MOQ', 'OEM', 'ODM', 'App', 'APP', 'HEPA', 'Yes'}


def load(p):
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def check_lang(lang):
    print('=' * 62)
    print(lang)
    print('=' * 62)
    bad = 0

    keys = load(os.path.join(SRC, '_keys_ui.json'))
    path = os.path.join(SRC, lang + '.json')
    if not os.path.exists(path):
        print('  MISSING  data/i18n/_src/%s.json' % lang)
        return 1
    src = load(path)

    missing = [k for k in keys if k not in src]
    extra = [k for k in src if k not in keys]
    empty = [k for k, v in src.items() if not (v or '').strip()]
    same = [k for k, v in src.items() if k in keys and v == k and k not in SAME_OK]
    ph_bad = [k for k in keys if k in src and phs(src[k]) != phs(k)]

    print(f'  ui strings      : {len(src)} / {len(keys)}')
    # hard failures: the lookup would silently break or fall back to English
    for label, items in (('missing', missing), ('extra', extra),
                         ('empty', empty), ('placeholder', ph_bad)):
        if items:
            bad += len(items)
            print(f'  !! {label:<21}: {len(items)}')
            for x in items[:12]:
                print(f'       {x!r}')
    if missing:
        print('     (a missing key silently falls back to English)')
    # soft warning: legitimate keeps (brand, model codes, contact lines,
    # cognates that are spelled the same in both languages) live here
    if same:
        print(f'  .. identical-to-English : {len(same)} (review only)')
        for x in same[:8]:
            print(f'       {x!r}')

    # ---- product layer ------------------------------------------------------
    kp = load(os.path.join(SRC, '_keys_products.json'))
    ppath = os.path.join(ROOT, 'data/i18n/products', lang + '.json')
    if not os.path.exists(ppath):
        print(f'  MISSING  data/i18n/products/{lang}.json')
        return bad + 1
    P = load(ppath)
    for blk, kobj in kp.items():
        if blk == 'descSuffix':
            if not P.get('descSuffix'):
                print('  !! descSuffix empty'); bad += 1
            continue
        got, want = P.get(blk) or {}, kobj
        miss = [k for k in want if k not in got]
        print(f'  {blk:<16}: {len(got)} / {len(want)}'
              + (f'   !! missing {len(miss)} e.g. {miss[:4]}' if miss else ''))
        bad += len(miss)
        # lookup keys must stay English
        if blk != 'names':
            wrong = [k for k, v in got.items() if isinstance(v, dict)]
            if wrong:
                print(f'  !! {blk}: nested objects where a string is expected: {wrong[:3]}')
                bad += len(wrong)
    print(f'  -> {"OK" if bad == 0 else str(bad) + " problems"}')
    return bad


def main():
    langs = sys.argv[1:]
    if not langs:
        langs = sorted(f[:-5] for f in os.listdir(SRC)
                       if f.endswith('.json')
                       and not f.startswith('_') and '_' not in f)
    total = sum(check_lang(l) for l in langs)
    print(f'\nTOTAL problems: {total}')


if __name__ == '__main__':
    main()
