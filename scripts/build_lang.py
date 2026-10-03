# -*- coding: utf-8 -*-
"""Build data/i18n/{lang}.json from a compact flat translation source.

Why
---
A full language file has ~900 keys spread over 13 sections, and the same
English string often appears in several of them ("Suction Power" is a spec
label, a comparison-table column, a buying-guide card title and a chrome
string).  Authoring 7 x 900 sectioned keys by hand invites drift and omissions.

So each locale is authored once as a *flat* map

    data/i18n/_src/{lang}.json   { "English string": "translation", ... }

and this script expands it into the sectioned file that gen_pages.py and
product-detail.js consume:

  * sections keyed by an English string (specLabel / quickLabel / specValue /
    chrome / specNote / guideTitle / guideValues) -> translate the key
  * sections keyed by an identifier with an English value (nav / footer /
    category / detail / categoryPage) -> translate the value

Placeholders (`{name}`, `{moq}`, `{amount}` ...) are validated: a translation
must carry exactly the same set as its English source.

Usage
    python scripts/build_lang.py es
    python scripts/build_lang.py            # every _src/*.json
"""
from __future__ import annotations
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_DIR = os.path.join(ROOT, 'data/i18n/_src')
EN = json.load(open(os.path.join(ROOT, 'data/i18n/en.json'), encoding='utf-8'))

# sections whose keys are the English string itself
FLAT = ('specLabel', 'quickLabel', 'specValue', 'chrome',
        'guideTitle', 'guideValues')
# sections keyed by an identifier, with the English string as the value.
# specNote is keyed by the buying-guide card title ("Suction Power") but the
# text a reader sees -- and therefore the text that needs translating -- is the
# explanatory sentence stored in the value.
VALUED = ('nav', 'footer', 'category', 'detail', 'specNote')

PH = re.compile(r'\{[a-zA-Z_]+\}')


def phs(s):
    """Placeholders that must survive translation.

    `{s}` is a bare English plural suffix («{n} model{s}»).  Languages whose
    plural marking is not an "s" — ru / ar / th / vi / id — may legitimately
    drop it, so it is excluded from the contract.
    """
    return [p for p in PH.findall(s) if p != '{s}']


def expand(lang, src):
    out = {}
    flat_missing, ph_bad = [], []

    for sec in FLAT:
        d = {}
        for k, ev in EN.get(sec, {}).items():
            tv = src.get(k, k)
            if phs(tv) != phs(ev):
                ph_bad.append(f'{sec}.{k}')
            d[k] = tv
            if k not in src:
                flat_missing.append(f'{sec}.{k}')
        out[sec] = d

    for sec in VALUED:
        d = {}
        for k, ev in EN.get(sec, {}).items():
            if not isinstance(ev, str):
                d[k] = ev
                continue
            tv = src.get(ev, ev)
            if phs(tv) != phs(ev):
                ph_bad.append(f'{sec}.{k}')
            d[k] = tv
        out[sec] = d

    cp = {}
    for slug, m in EN.get('categoryPage', {}).items():
        d = {}
        for k, ev in m.items():
            if not isinstance(ev, str):
                d[k] = ev
                continue
            tv = src.get(ev, ev)
            if phs(tv) != phs(ev):
                ph_bad.append(f'categoryPage.{slug}.{k}')
            d[k] = tv
        cp[slug] = d
    out['categoryPage'] = cp

    # a few scalars
    out['moqUnit'] = src.get(EN['moqUnit'], EN['moqUnit'])
    return out, flat_missing, ph_bad


def main():
    langs = sys.argv[1:] or sorted(
        f[:-5] for f in os.listdir(SRC_DIR) if f.endswith('.json'))
    for lang in langs:
        sp = os.path.join(SRC_DIR, lang + '.json')
        if not os.path.exists(sp):
            print(f'{lang}: no {sp}')
            continue
        src = json.load(open(sp, encoding='utf-8'))
        data, missing, ph_bad = expand(lang, src)
        dest = os.path.join(ROOT, 'data/i18n', lang + '.json')
        with open(dest, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write('\n')
        n_keys = sum(len(v) for v in data.values() if isinstance(v, dict))
        print(f'{lang}: {len(src)} source strings -> {dest} ({n_keys} keys)')
        if ph_bad:
            print(f'   !! placeholder mismatch: {len(ph_bad)} -> {ph_bad[:6]}')
        if missing:
            print(f'   .. untranslated (falling back to English): '
                  f'{len(missing)} -> {missing[:8]}')


if __name__ == '__main__':
    main()
