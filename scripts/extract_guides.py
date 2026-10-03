# -*- coding: utf-8 -*-
"""Extract the per-category "Buying Guide" cards from the en/ category pages.

Each en/ category page carries a `#guide` block with five `feature-card`s whose
markup is

    <div class="feature-card"><div class="feature-icon">01</div>
      <h3>Suction Power</h3>
      <p>Current range: 30kPa · 37000Pa · 40000Pa.  Higher Pa lifts more
         debris; compare Pa together with motor type (brushed vs brushless).</p>
    </div>

The `<p>` is a *composed* string (prefix + live values + a stable explanation),
so no dictionary can ever match it as a whole.  Splitting it once here lets the
page generator rebuild it per language as

    {currentRange} {values}. {specNote[title]}

Output: data/i18n/category-guides.json
"""
from __future__ import annotations
import json, os, re, sys, collections

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from gen_pages import CATS, load_json                          # noqa

CARD_RE = re.compile(
    r'<div class="feature-card">.*?<h3>(.*?)</h3>\s*<p>Current range:\s*(.*?)\.\s+(.*?)</p>',
    re.S)


def main():
    out = {}
    titles = collections.Counter()
    explains = {}
    for cat in CATS:
        fp = os.path.join(ROOT, 'en', cat, 'index.html')
        if not os.path.exists(fp):
            print('!! missing', fp)
            continue
        h = open(fp, encoding='utf-8').read()
        cards = []
        for m in CARD_RE.finditer(h):
            title = m.group(1).strip()
            values = re.sub(r'\s+', ' ', m.group(2)).strip()
            explain = re.sub(r'\s+', ' ', m.group(3)).strip()
            cards.append({'title': title, 'values': values, 'explain': explain})
            titles[title] += 1
            explains[explain] = title
        out[cat] = cards
        print(f'{cat}: {len(cards)} cards')

    dest = os.path.join(ROOT, 'data/i18n/category-guides.json')
    with open(dest, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print('\nwrote', dest)

    print(f'\n# distinct card titles ({len(titles)}):')
    for t, n in titles.most_common():
        print(f'   {n:>2}x  {t}')
    print(f'\n# distinct explanations ({len(explains)}):')
    for e, t in explains.items():
        print(f'   [{t}] {e}')


if __name__ == '__main__':
    main()
