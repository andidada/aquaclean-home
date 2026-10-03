#!/usr/bin/env python3
"""Verify every product image referenced by the two data sources exists on disk.

Two independent data files feed images into the site:
  data/products/<cat>.json  -- category + detail pages (gen_pages.py). Fields: images[] (absolute URLs)
  data/products.json        -- admin dashboard.                          Fields: img     (bare filename)

A static <img src> scan cannot see either of them, so they need their own check.
"""
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ok = True


def to_rel(url_or_name):
    """Reduce an image reference (absolute URL or bare name) to a repo-relative path."""
    u = url_or_name.split('?')[0].split('#')[0]
    m = re.search(r'/(assets/images/.*)$', u)
    if m:
        return m.group(1)
    return 'assets/images/products/' + u.split('/')[-1]


def report(label, refs):
    global ok
    miss = sorted({r for r in refs if not os.path.isfile(os.path.join(ROOT, to_rel(r)))})
    stale = sorted({r for r in refs if re.search(r'\.png$', to_rel(r)) and 'og-image' not in r})
    print(f'{"OK  " if not miss and not stale else "FAIL"} {label}: {len(refs)} refs')
    if miss:
        ok = False
        for m in miss[:10]:
            print('       missing:', m)
    if stale:
        ok = False
        for s in stale[:10]:
            print('       stale raster (should be .webp):', s)


# --- data/products/<cat>.json ------------------------------------------------
cat_refs = []
per_file = []
for f in sorted(glob.glob(os.path.join(ROOT, 'data/products/*.json'))):
    if os.path.basename(f) == 'categories.json':
        continue
    with open(f, encoding='utf-8') as fh:
        d = json.load(fh)
    n = 0
    for p in d.get('products', []):
        for u in (p.get('images') or []):
            cat_refs.append(u)
            n += 1
    per_file.append((os.path.basename(f), n))
report('data/products/<cat>.json images[]', cat_refs)

# --- data/products.json ------------------------------------------------------
pj = os.path.join(ROOT, 'data/products.json')
with open(pj, encoding='utf-8') as fh:
    d = json.load(fh)
admin_refs = []
for p in (list(d.get('products', {}).values()) if isinstance(d.get('products'), dict)
          else d.get('products', [])):
    if isinstance(p, dict) and isinstance(p.get('img'), str):
        admin_refs.append(p['img'])
report('data/products.json img', admin_refs)

# --- assets/js/langpicker.v1.js ---------------------------------------------
js = open(os.path.join(ROOT, 'assets/js/langpicker.v1.js'), encoding='utf-8').read()
picker = re.findall(r"img:\s*'([^']+)'", js)
rel = sorted({u for u in picker if not u.startswith('/')})
if rel:
    ok = False
    print('[FAIL] langpicker non-absolute paths:', rel[:5])
report('langpicker.v1.js img', picker)

print()
print('coverage per category file:', ', '.join(f'{k}={v}' for k, v in per_file))
print('RESULT:', 'all product image refs resolve' if ok else 'PROBLEMS FOUND')
sys.exit(0 if ok else 1)
