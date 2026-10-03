# -*- coding: utf-8 -*-
"""List the i18n entries that actually need a translation.

Values that are units, model codes, certification names or pure numbers are
identical in every locale, so a language file can omit them and let the
generator fall back to English.  This prints only the entries that carry real
words, per section, in the shape you can paste straight into a language file.

Usage
    python scripts/needstranslating.py                # summary counts
    python scripts/needstranslating.py specValue       # full dump of a section
"""
from __future__ import annotations
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from check_i18n_leftovers import KEEP, has_alpha, UNIT_WORDS, ANSWER_WORDS  # noqa

EN = json.load(open(os.path.join(ROOT, 'data/i18n/en.json'), encoding='utf-8'))

SECTIONS = ['nav', 'footer', 'category', 'detail', 'specLabel', 'quickLabel',
            'specNote', 'specValue', 'chrome', 'guideTitle', 'guideValues']

PH = re.compile(r'\{[a-zA-Z_]+\}')


def needs(v):
    """True if the English string carries real words rather than units/codes.

    Placeholders are blanked out first so templates such as
    ``How to Choose a {name}`` are still recognised as needing a translation.
    UNIT_WORDS lives in check_i18n_leftovers.py so that the skeleton builder
    and the leftover checker can never disagree about what a unit word is.
    """
    if not isinstance(v, str):
        return False
    plain = PH.sub(' ', v).strip()
    if plain.lower() in ANSWER_WORDS:
        return True
    words = re.findall(r'[A-Za-z]{3,}', plain)
    return any(w.lower() not in UNIT_WORDS for w in words)


def main():
    want = sys.argv[1] if len(sys.argv) > 1 else ''
    total = 0
    for sec in SECTIONS:
        d = EN.get(sec, {})
        need = {k: v for k, v in d.items() if needs(k if sec in
                ('chrome', 'guideTitle', 'guideValues') else v)}
        total += len(need)
        print(f'{sec:<14} {len(need):>4} / {len(d):>4}')
        if want == sec:
            print(json.dumps(need, ensure_ascii=False, indent=1))
    print(f'{"TOTAL":<14} {total:>4}')


if __name__ == '__main__':
    main()
