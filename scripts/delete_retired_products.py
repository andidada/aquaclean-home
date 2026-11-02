# -*- coding: utf-8 -*-
"""Delete 10 retired product pages (9 locales) + data + images + references. Idempotent."""
import json, os, re, shutil, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
LANGS = ['ar', 'en', 'es', 'fr', 'id', 'ru', 'th', 'vi', 'zh']
DEAD_SLUGS = [
    'handheld-vacuum-gv18', 'handheld-vacuum-v22-2', 'handheld-vacuum-gv22', 'handheld-vacuum-v26',
    'robot-vacuum-v9', 'robot-vacuum-pt40c800', 'robot-vacuum-v9-2',
    'tire-inflator-ymc6667', 'steam-cleaner-ptc-sc-004', 'hands-free-soap-dispenser-sd901',
]
DEAD_IDS = {  # data JSON product id per category
    'handheld-vacuum': ['gv18', 'v22-2', 'gv22', 'v26'],
    'robot-vacuum': ['v9', 'pt40c800', 'v9-2'],
    'tire-inflator': ['ymc6667'],
    'steam-cleaner': ['ptc-sc-004'],
    'hands-free-soap-dispenser': ['sd901'],
}
IMG_DIRS = [
    'handheld-vacuum-gv18', 'handheld-vacuum-v22-2', 'handheld-vacuum-gv22', 'handheld-vacuum-v26',
    'robot-vacuum-v9', 'robot-vacuum-pt40c800', 'robot-vacuum-v9-2',
    'tire-inflator-ymc6667', 'steam-cleaner-ptc-sc-004', 'hands-free-soap-dispenser-sd901',
]
# category count after deletion (for productCount badge, keyed by index dir name)
CAT_COUNT = {'handheld-vacuum': 4, 'robot-vacuum': 6, 'tire-inflator': 2,
             'steam-cleaner': 1, 'hands-free-soap-dispenser': 1}

DEAD_HREFS = ['/%s.html' % s for s in DEAD_SLUGS]
DRY = '--apply' not in sys.argv
stats = {'pages_deleted': 0, 'cards_removed': 0, 'ld_fixed': 0, 'trs_removed': 0,
         'badges': 0, 'sitemap_blocks': 0, 'img_dirs': 0}

def read(p):
    with open(p, encoding='utf-8') as f:
        return f.read()

def write(p, h):
    if not DRY:
        with open(p, 'w', encoding='utf-8', newline='') as f:
            f.write(h)

# ---------- 1. delete product page files ----------
for slug in DEAD_SLUGS:
    for lang in LANGS:
        p = os.path.join(lang, slug + '.html')
        if os.path.exists(p):
            stats['pages_deleted'] += 1
            if not DRY:
                os.remove(p)

# ---------- 2. data JSON: drop products ----------
for cat, ids in DEAD_IDS.items():
    p = os.path.join('data', 'products', cat + '.json')
    d = read(p)
    obj = json.loads(d)
    prods = obj['products'] if isinstance(obj, dict) else obj
    before = len(prods)
    prods[:] = [x for x in prods if x.get('id') not in ids]
    if len(prods) == before:
        stats.setdefault('json', []).append('%s: already clean' % cat)
        continue
    assert len(prods) == before - len(ids), 'JSON drop mismatch for %s' % cat
    out = json.dumps(obj, ensure_ascii=False, indent=2)
    if not d.endswith('\n'):
        out += '\n'
    stats.setdefault('json', []).append('%s: %d->%d' % (cat, before, len(prods)))
    write(p, out)

# ---------- 3. image dirs ----------
for d in IMG_DIRS:
    p = os.path.join('assets', 'images', 'products', d)
    if os.path.isdir(p):
        stats['img_dirs'] += 1
        if not DRY:
            shutil.rmtree(p)

# ---------- 4. HTML cleanup helpers ----------
def remove_dead_cards(html):
    """Remove <div class="product-card">...</a></div></div> blocks containing a dead href.
    Anchored lazy match (every card ends with View Details </a> + 2 closing divs);
    balanced-div scan is unsafe here because index pages have unbalanced card HTML."""
    n = [0]
    def repl(m):
        block = m.group(0)
        if any(x in block for x in DEAD_HREFS):
            n[0] += 1
            return ''
        return block
    out = re.sub(r'<div class="product-card">.*?</a>\s*</div>\s*</div>',
                 repl, html, flags=re.S)
    return out, n[0]

def fix_itemlist_ld(html):
    """Filter ItemList LD entries pointing to dead pages; renumber position."""
    n = [0]
    def repl(m):
        body = m.group(1)
        if 'itemListElement' not in body:
            return m.group(0)
        try:
            d = json.loads(body)
        except Exception as e:
            raise SystemExit('LD parse fail: %s\n%r' % (e, body[:200]))
        items = d.get('itemListElement')
        if not isinstance(items, list):
            return m.group(0)
        kept = [it for it in items
                if not any(s + '.html' in json.dumps(it, ensure_ascii=False) for s in DEAD_SLUGS)]
        if len(kept) == len(items):
            return m.group(0)
        for pos, it in enumerate(kept, 1):
            if isinstance(it, dict):
                it['position'] = pos
        d['itemListElement'] = kept
        single = '\n' not in body
        s = json.dumps(d, ensure_ascii=False,
                       separators=(',', ':') if single else (',', ': '),
                       indent=None if single else 2)
        n[0] += 1
        return '<script type="application/ld+json">' + s + '</script>'
    return re.sub(r'<script type="application/ld\+json">\s*(.*?)\s*</script>',
                  repl, html, flags=re.S), n[0]

def remove_dead_trs(html):
    n = [0]
    def repl(m):
        seg = m.group(0)
        if any(h in seg for h in DEAD_HREFS):
            n[0] += 1
            return ''
        return seg
    return re.sub(r'<tr\b.*?</tr>', repl, html, flags=re.S), n[0]

def remove_dead_lis(html):
    """Drop <li><a ...dead...</a></li> items (related-products lists)."""
    n = [0]
    def repl(m):
        seg = m.group(0)
        if any(x in seg for x in DEAD_HREFS):
            n[0] += 1
            return ''
        return seg
    return re.sub(r'<li>\s*<a\b[^>]*>.*?</a>\s*</li>', repl, html, flags=re.S), n[0]

def fix_badge(html, count):
    def repl(m):
        return m.group(1) + str(count) + m.group(3)
    new, n = re.subn(r'(<span id="productCount">)(\d+)([^<]*</span>)', repl, html)
    return new, n

# ---------- walk all html in lang dirs ----------
changed_files = 0
for lang in LANGS:
    for dirpath, _dirs, files in os.walk(lang):
        for fn in files:
            if not fn.endswith('.html'):
                continue
            p = os.path.join(dirpath, fn)
            h = read(p)
            orig = h
            h, c1 = remove_dead_cards(h)
            h, c2 = fix_itemlist_ld(h)
            h, c3 = remove_dead_trs(h)
            h, c5 = remove_dead_lis(h)
            c4 = 0
            if 'id="productCount"' in h:
                m = re.search(r'href="/assets/[^"]*|\.\./data/products/([a-z-]+)\.json|data/products/([a-z-]+)\.json', h)
                # determine category from known index paths
                rel = p.replace('\\', '/')
                cat = None
                for c in CAT_COUNT:
                    if '/%s/index.html' % c in rel:
                        cat = c
                        break
                if cat:
                    h, c4 = fix_badge(h, CAT_COUNT[cat])
            if c1 or c2 or c3 or c4 or c5:
                changed_files += 1
                stats['cards_removed'] += c1
                stats['ld_fixed'] += c2
                stats['trs_removed'] += c3
                stats['badges'] += c4
                stats.setdefault('lis_removed', 0)
                stats['lis_removed'] += c5
                if h != orig:
                    write(p, h)

# ---------- 5. sitemap.xml ----------
sm = read('sitemap.xml')
blocks = re.findall(r'  <url>.*?</url>\n', sm, flags=re.S)
kept_blocks = []
for b in blocks:
    if any(s + '.html' in b for s in DEAD_SLUGS):
        stats['sitemap_blocks'] += 1
    else:
        kept_blocks.append(b)
if stats['sitemap_blocks']:
    sm_new = sm
    for b in blocks:
        if any(s + '.html' in b for s in DEAD_SLUGS):
            sm_new = sm_new.replace(b, '', 1)
    write('sitemap.xml', sm_new)

print('DRY RUN' if DRY else 'APPLIED')
print(json.dumps(stats, ensure_ascii=False, indent=1))
print('html files changed:', changed_files)
