# -*- coding: utf-8 -*-
"""Repair the `price_indicator` defect in data/products/*.json.

`price_indicator.min` / `.max` on three Alibaba-sourced records are
`{currency, number}` dicts instead of numbers.  Every consumer that assumed a
number rendered a repr of the dict — the visible symptom was

    US${'currency': 'USD', 'number': 64.5}–{...} / pc

on category comparison tables and detail pages (static HTML, and again at
runtime via product-detail.js buildPriceLadder, which produced NaN prices).

Normalising the three records to plain numbers fixes both paths.

NOTE: category names/descriptions are owned by scripts/fix_categories.py —
this script deliberately does not touch categories.json.

Usage
    python scripts/fix_product_data.py --check
    python scripts/fix_product_data.py
"""
from __future__ import annotations
import argparse, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def num(v):
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return None
    if isinstance(v, dict):
        return num(v.get('number'))
    return None


def fix_prices(dry):
    changed = []
    for name in sorted(os.listdir(os.path.join(ROOT, 'data/products'))):
        if not name.endswith('.json') or name == 'categories.json':
            continue
        p = os.path.join(ROOT, 'data/products', name)
        data = json.load(open(p, encoding='utf-8'))
        dirty = False
        for prod in data.get('products', []):
            pi = prod.get('price_indicator')
            if not isinstance(pi, dict):
                continue
            for k in ('min', 'max'):
                if isinstance(pi.get(k), dict):
                    pi[k] = num(pi[k])
                    dirty = True
        if dirty:
            changed.append(name)
            if not dry:
                with open(p, 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=1)
                    f.write('\n')
    return changed


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()
    ch = fix_prices(args.check)
    print(f'price_indicator repaired in {len(ch)} files: {ch}')
    if args.check:
        print('(dry run — nothing written)')


if __name__ == '__main__':
    main()
