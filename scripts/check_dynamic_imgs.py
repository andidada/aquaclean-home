#!/usr/bin/env python3
"""Verify dynamically-injected image assets exist on disk.

Covers the two data-driven image sources that a static <img src> scan misses:
  1. assets/js/langpicker.v1.js  -- 11 product-modal thumbnails
  2. data/products.json          -- product gallery / detail images
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ok = True


def check(label, base_dir, refs):
    global ok
    miss = [
        u for u in refs
        if not os.path.isfile(os.path.join(ROOT, base_dir, os.path.normpath(u)))
    ]
    flag = 'OK ' if not miss else 'FAIL'
    if miss:
        ok = False
    print(f'[{flag}] {label}: {len(refs)} refs, {len(miss)} missing')
    for m in miss[:10]:
        print('        -', m)


# --- 1. langpicker modal thumbnails -----------------------------------------
js_path = os.path.join(ROOT, 'assets/js/langpicker.v1.js')
with open(js_path, encoding='utf-8') as fh:
    js = fh.read()
picker_refs = re.findall(r"img:\s*'([^']+)'", js)
# The picker is loaded by pages at different depths (/en/index.html vs
# /en/about.html), so store-absolute '/' paths are the only form that resolves
# everywhere. Flag anything still written relative.
bad_rel = sorted({u for u in picker_refs if not u.startswith('/')})
if bad_rel:
    ok = False
    print('[FAIL] langpicker uses non-absolute paths:', bad_rel[:5])
check('langpicker product modals', '.', [u.lstrip('/') for u in picker_refs])

# non-webp leftovers in the picker
non_webp = sorted({u for u in picker_refs if not u.split('?')[0].endswith('.webp')})
if non_webp:
    ok = False
    print('[FAIL] langpicker non-webp refs:', non_webp)

# --- 2. products.json images -------------------------------------------------
pj = os.path.join(ROOT, 'data/products.json')
with open(pj, encoding='utf-8') as fh:
    data = json.load(fh)
products = data.get('products', {})
if isinstance(products, dict):
    items = list(products.values())
else:
    items = products

prod_refs = []
for p in items:
    if not isinstance(p, dict):
        continue
    # products.json uses singular 'img'; tolerate a list form via 'images' too
    raw = []
    if isinstance(p.get('img'), str):
        raw.append(p['img'])
    for key in ('images', 'gallery'):
        if isinstance(p.get(key), list):
            raw.extend(u for u in p[key] if isinstance(u, str))
    for u in raw:
        prod_refs.append(u.split('/')[-1].split('?')[0])
check('products.json gallery', 'assets/images/products', prod_refs)

# flag any product image still pointing at a raster format we migrated away from
stale = sorted({u for u in prod_refs if u.endswith('.png')})
if stale:
    ok = False
    print('[FAIL] products.json still references .png:', stale[:10])

print()
print('RESULT:', 'all dynamic image refs resolve' if ok else 'MISSING ASSETS FOUND')
sys.exit(0 if ok else 1)
