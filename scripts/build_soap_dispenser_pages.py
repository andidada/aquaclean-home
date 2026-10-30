# -*- coding: utf-8 -*-
"""新增品类 hands-free-soap-dispenser —— 页面层（en / zh，幂等）。

为什么是「克隆模板 + 整块重写」而不是从零渲染：
  品类页/详情页各自带 ~10 KB 手写 CSS 与 nav/footer 骨架，重渲极易引入回归。
  这里只重写「内容块」，骨架（包括语言自己的 chrome 文案）原样保留。

  en 页是 gen_pages.py 的模板源；zh 页由 zh 模板直接派生（zh 没有 i18n 文件，
  gen_pages 不会生成它）。其余 7 个语种交给 gen_pages.py。

用法
    python scripts/build_soap_dispenser_pages.py            # dry-run
    python scripts/build_soap_dispenser_pages.py --apply
"""
from __future__ import annotations
import html as htmlmod
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_CAT = 'portable-espresso-machine'
SRC_ID = 'xyd003'
SLUG = 'hands-free-soap-dispenser'
PID = 'sd901'
VER = '?v=20261030a'
IMGDIR = '%s/%s' % ('/assets/images/products/hands-free-soap-dispenser-sd901', '%s')
CARD_IMG = '/assets/images/products/21-hands-free-soap-dispenser.webp' + VER
TARGET_LANGS = ['en', 'zh']


# ---------------------------------------------------------------------------
def read(p):
    return io.open(p, encoding='utf-8', newline='').read()


def write(p, s):
    io.open(p, 'w', encoding='utf-8', newline='').write(s)


def load(p):
    return json.loads(read(p))


def esc(s, quote=True):
    return htmlmod.escape('' if s is None else str(s), quote=quote)


def pick(d, lang):
    if isinstance(d, dict):
        return d.get(lang) or d.get('en') or ''
    return d or ''


class Ctx(object):
    """每个语言的内容集合。"""

    def __init__(self, lang, prod, src_prod, cats, src_cats):
        self.lang = lang
        self.p = prod
        self.cat_name = pick(next(c['name'] for c in cats if c['slug'] == SLUG), lang)
        self.cat_desc = pick(next(c['description'] for c in cats if c['slug'] == SLUG), lang)
        self.src_cat_name = pick(next(c['name'] for c in src_cats if c['slug'] == SRC_CAT), lang)
        self.src_cat_name_p = self.src_cat_name        # 中文没有复数
        self.name = pick(prod['name'], lang)
        self.tagline = pick(prod['tagline'], lang)
        self.desc = pick(prod['description'], lang)
        self.src_name = pick(src_prod['name'], lang)
        self.src_tagline = pick(src_prod['tagline'], lang)
        self.img = [('/assets/images/products/hands-free-soap-dispenser-sd901/%s' % f) + VER
                    for f in ('01.webp', '02.webp', '03.webp')]
        self.price = prod['price_indicator']
        self.moq = prod['moq']['value']
        self.ladder = prod.get('price_ladder') or []


def sub1(doc, old, new, label):
    n = doc.count(old)
    if n == 0:
        raise SystemExit('MISS[%s]: %r' % (label, old[:90]))
    return doc.replace(old, new), n


def rebuild_block(doc, start_pat, end_pat, new_block, label, expect=1):
    """替换 start_pat 到 end_pat 之间的整段（含 start_pat 匹配的文本）。"""
    pat = re.compile(start_pat + r'(.*?)' + end_pat, re.S)
    hit = pat.search(doc)
    if not hit:
        raise SystemExit('MISS block: %s' % label)
    return doc[:hit.start()] + new_block + doc[hit.end():], 0


# ---------------------------------------------------------------------------
# 公共文案替换（head / nav / breadcrumb / 引用）
# ---------------------------------------------------------------------------
def apply_common(doc, c, log):
    pairs = []
    # 1) 长串优先：tagline（head 的 meta description 里就有它）
    pairs.append((esc(c.src_tagline), esc(c.tagline), 'tagline'))
    pairs.append((c.src_tagline, c.tagline, 'tagline-raw'))
    # 2) 完整产品名（escaped / 原文）
    pairs.append((esc(c.src_name), esc(c.name), 'prodname+esc'))
    pairs.append((c.src_name, c.name, 'prodname'))
    pairs.append((esc(c.src_name, quote=False), esc(c.name, quote=False), 'prodname-q'))
    # 2) 品类名（复数在前）
    pairs.append((esc(c.src_cat_name), esc(c.cat_name), 'catname'))
    pairs.append((c.src_cat_name, c.cat_name, 'catname-raw'))
    # 3) URL / id
    pairs.append(('portable-espresso-xyd003', 'hands-free-soap-dispenser-sd901', 'url-imgdir'))
    pairs.append(('%s-%s' % (SRC_CAT, SRC_ID), '%s-%s' % (SLUG, PID), 'url-detail'))
    pairs.append((SRC_CAT, SLUG, 'url-cat'))
    pairs.append((SRC_ID, PID, 'id'))
    pairs.append(('Portable Espresso Machine', 'Hands-free Soap Dispenser', 'catname-en'))
    for old, new, label in pairs:
        if old == new or not old:
            continue
        n = doc.count(old)
        if n:
            doc = doc.replace(old, new)
            log.append('  %-14s x%d' % (label, n))
    return doc


# ---------------------------------------------------------------------------
# 品类页
# ---------------------------------------------------------------------------
CAT_LOADER = """{
  "@context": "https://schema.org",
  "@type": "CollectionPage",
  "name": "%s - OEM Manufacturer | AquaClean Home",
  "description": "Browse %s products. Wholesale/OEM/ODM available. MOQ %d pieces. Global shipping.",
  "url": "https://www.hkdmj.net/%s/%s/",
  "publisher": {
    "@id": "https://www.hkdmj.net/#organization"
  }
}"""


def cat_hero(doc, c, log):
    pat = re.compile(r'(<h1>[^<]*</h1>\s*<p>)(.*?)(</p>)', re.S)
    m = pat.search(doc)
    if not m:
        raise SystemExit('MISS cat hero <p>')
    out = doc[:m.start()] + m.group(1) + esc(c.cat_desc) + m.group(3) + doc[m.end():]
    log.append('  hero-p        x1')
    return out


def cat_card(doc, c, log):
    """静态产品卡片的描述行（quick_specs 前 3 项）。"""
    quick = c.p['quick_specs'][:3]
    line = ' · '.join('%s: %s' % (pick(q['label'], c.lang), pick(q['value'], c.lang))
                      for q in quick)
    pat = re.compile(r'(<div class="product-img-wrap">.*?<h3>[^<]*</h3>\s*<p>)(.*?)(</p>)', re.S)
    m = pat.search(doc)
    if not m:
        raise SystemExit('MISS static card desc')
    out = doc[:m.start()] + m.group(1) + esc(line) + m.group(3) + doc[m.end():]
    # 卡片主图
    # 卡片主图（URL 已被 apply_common 换成新路径，这里只是补缓存戳）
    doc, n = sub1(out, '/assets/images/products/hands-free-soap-dispenser-sd901/01.webp',
                  c.img[0], 'card-img')
    log.append('  card-desc     x1')
    log.append('  card-img      x%d' % n)
    return doc


def cat_price(doc, c, log):
    pat = re.compile(r'(<div class="price-indicator">)(.*?)(</div>)', re.S)
    m = pat.search(doc)
    if not m:
        raise SystemExit('MISS price indicator')
    inside = 'US$%g–%g <span class="moq">/ pc MOQ %d pcs</span>' % (
        c.price['min'], c.price['max'], c.moq)
    return doc[:m.start()] + m.group(1) + inside + m.group(3) + doc[m.end():]


def cat_compare(doc, c, log):
    quick = c.p['specs'][1:4]
    key = ' · '.join('%s: %s' % (pick(s['label'], c.lang), pick(s['value'], c.lang))
                     for s in quick)
    row = ('          <tr><td><a href="/%s/%s-%s.html">%s</a></td><td>%s</td><td>%d pcs</td>'
           '<td>US$%g–%g / pc</td><td>%s</td><td>—</td></tr>' % (
               c.lang, SLUG, PID, esc(c.name), PID, c.moq,
               c.price['min'], c.price['max'], esc(key)))
    pat = re.compile(r'(<div class="aqc-ss">\s*<table>\s*<thead>.*?</thead>\s*<tbody>\s*)'
                     r'(.*?)(\s*</tbody>)', re.S)
    m = pat.search(doc)
    if not m:
        raise SystemExit('MISS compare tbody')
    return doc[:m.start()] + m.group(1) + row + m.group(3) + doc[m.end():]


def cat_guide(doc, c, log):
    cards = load(os.path.join(ROOT, 'data/i18n/category-guides.json'))[SLUG]
    items = []
    for i, card in enumerate(cards, 1):
        items.append('<div class="feature-card"><div class="feature-icon">%02d</div>'
                     '<h3>%s</h3><p>%s</p></div>' % (
                         i, esc(card['title']), esc(card['explain'])))
    block = ('<div class="features-grid" style="margin-top:48px;">%s\n\n\n\n\n    </div>'
             % ''.join(items))
    start = doc.index('<div class="features-grid"')
    end = doc.index('<section class="section section-alt" id="oem">')
    return doc[:start] + block + '\n  </div></section>\n\n' + doc[end:]


def cat_count(doc, c, log):
    """「N models in this category …」——新类目只有 1 个型号，模板句尾的 model(s) 保持原样。"""
    return doc


def build_category(c, tpl, out_path, apply_this):
    log = []
    doc = read(tpl)
    doc = apply_common(doc, c, log)
    doc = cat_hero(doc, c, log)
    doc = cat_card(doc, c, log)
    doc = cat_price(doc, c, log)
    doc = cat_compare(doc, c, log)
    doc = cat_guide(doc, c, log)
    # og:image / twitter:image 指向模板里的旧图
    for old in ('https://www.hkdmj.net/assets/images/products/17-12-portable-espresso.webp',
                '/assets/images/products/17-12-portable-espresso.webp',
                '/assets/images/products/12-portable-espresso.webp',
                '/assets/images/products/hands-free-soap-dispenser-sd901/01.webp'):
        if old in doc:
            doc = doc.replace(old, CARD_IMG)
            log.append('  og-image      %s' % old)
    # 残留扫描
    # /{lang}/coffee-machine/ 的「Espresso Coffee Machine / 意式咖啡机」是站内的
    # 另一个品类，属于合法的相关链接与页脚导航，不算残留
    probe = doc.replace('Espresso Coffee Machine', '').replace('意式咖啡机', '')\
                .replace('咖啡机', '').replace('coffee-machine', '')
    leftovers = [w for w in ('espresso', 'Espresso', 'XYD-003', 'xyd003',
                             'portable-espresso') if w in probe]
    # 中文残留
    if c.lang == 'zh':
        leftovers += [w for w in ('咖啡', '浓缩') if w in probe]
    if leftovers:
        for w in leftovers:
            for mm in list(re.finditer(re.escape(w), probe))[:3]:
                snip = probe[max(0, mm.start() - 90):mm.start() + 90].replace('\n', ' ')
                print('    !! %-18s ...%s...' % (w, snip))
    print('--- %s/%s/index.html  leftovers=%s' % (c.lang, SLUG, leftovers or 'none'))
    for line in log:
        print(line)
    if apply_this and not leftovers:
        write(out_path, doc)
        print('  wrote %s' % os.path.relpath(out_path, ROOT))
    elif apply_this:
        print('  !! skipped write because of leftovers')
    return not leftovers


# ---------------------------------------------------------------------------
# 详情页
# ---------------------------------------------------------------------------
def detail_product_ld(doc, c, log):
    props = []
    for s in c.p['specs']:
        props.append('    {\n      "@type": "PropertyValue",\n      "name": "%s",'
                     '\n      "value": "%s"\n    }' % (
                         esc(pick(s['label'], c.lang)), esc(pick(s['value'], c.lang))))
    ld = """{
  "@context": "https://schema.org",
  "@type": "Product",
  "@id": "https://www.hkdmj.net/%s/%s-%s.html#product",
  "name": "%s",
  "description": "%s",
  "image": [
%s
  ],
  "url": "https://www.hkdmj.net/%s/%s-%s.html",
  "sku": "%s",
  "mpn": "%s",
  "brand": {
    "@type": "Brand",
    "name": "AquaClean Home"
  },
  "manufacturer": {
    "@id": "https://www.hkdmj.net/about.html#organization",
    "@type": "Organization",
    "name": "Hong Kong Damaijia Technology Co., Limited",
    "url": "https://www.hkdmj.net",
    "address": {
      "@type": "PostalAddress",
      "addressCountry": "HK",
      "addressRegion": "New Territories"
    }
  },
  "category": "%s",
  "additionalProperty": [
%s
  ]
}""" % (
        c.lang, SLUG, PID, esc(c.name), esc(c.desc),
        ',\n'.join('    "https://www.hkdmj.net%s"' % img for img in c.img),
        c.lang, SLUG, PID, PID, PID, esc(c.cat_name), ',\n'.join(props))
    pat = re.compile(r'(<script type="application/ld\+json">\s*\{.*?"@type": "Product".*?</script>)', re.S)
    m = pat.search(doc)
    if not m:
        raise SystemExit('MISS Product JSON-LD')
    new = '<script type="application/ld+json">\n' + ld + '\n</script>'
    log.append('  product-ld    x1')
    return doc[:m.start()] + new + doc[m.end():]


def detail_mount(doc, c, log):
    block = ('<div id="aqc-detail-mount"><div class="section-inner" '
             'style="max-width:1100px;margin:0 auto;padding:24px;">'
             '<h1>%s</h1><h2>%s</h2><p>MOQ %d pcs · US$%g–%g / pc</p>'
             '<p><a href="/%s/%s/">View full specifications and request a quote</a></p>'
             '<p><a href="/%s/oem-vs-odm/">OEM / ODM custom manufacturing '
             '(logo, colour, packaging) →</a></p></div></div>\n' % (
                 esc(c.name), esc(c.tagline), c.moq, c.price['min'], c.price['max'],
                 c.lang, SLUG, c.lang))
    start = doc.index('<div id="aqc-detail-mount">')
    end = doc.index('<section class="section section-alt" id="detail-images">')
    log.append('  mount         x1')
    return doc[:start] + block + doc[end:]


def detail_images(doc, c, log):
    imgs = []
    for i, img in enumerate(c.img, 1):
        imgs.append('      <img src="%s" alt="%s %02d" loading="lazy" '
                    'style="width:100%%;height:auto;display:block;margin:0 auto 14px;'
                    'border-radius:8px;">' % (img, esc(c.name), i))
    block = ('<section class="section section-alt" id="detail-images">\n'
             '  <div class="section-inner">\n'
             '    <div class="text-center"><div class="section-label">Product details</div>'
             '<h2 class="section-title">%s-%s — detail images</h2></div>\n'
             '    <div class="aqc-ss" style="max-width:750px;margin:32px auto 0;">\n'
             '%s\n    </div>\n  </div>\n</section>\n' % (
                 SLUG, PID, '\n'.join(imgs)))
    start = doc.index('<section class="section section-alt" id="detail-images">')
    end = doc.index('<section class="section" id="glance">')
    log.append('  detail-images x1')
    return doc[:start] + block + '\n' + doc[end:]


def detail_glance(doc, c, log):
    specs = c.p['specs']
    metrics = []
    for idx, sub in ((1, 'Output levels'), (2, 'Tank'), (3, 'Material'), (5, 'Sensor')):
        metrics.append('<div class="metric"><b>%s</b><span>%s</span></div>' % (
            esc(pick(specs[idx]['value'], c.lang)), esc(sub)))
    figs = ''
    for i, img in enumerate(c.img[1:], 2):
        figs += ('          <figure><img src="%s" alt="%s %d" loading="lazy">'
                 '<figcaption>%s</figcaption></figure>\n' % (
                     img, esc(c.name), i, esc(c.name)))
    block = ('<section class="section" id="glance">\n  <div class="section-inner">\n'
             '    <div class="text-center">\n      <h2 class="section-title">At a glance</h2>\n'
             '      <p class="section-sub">%s</p>\n    </div>\n'
             '    <div class="aqc-ss">\n      <div class="metrics">\n        %s\n      </div>\n'
             '      <div class="strip">\n%s      </div>\n    </div>\n  </div>\n</section>\n' % (
                 esc(c.tagline), '\n        '.join(metrics), figs))
    start = doc.index('<section class="section" id="glance">')
    end = doc.index('<section class="section" id="customization">')
    log.append('  glance        x1')
    return doc[:start] + block + '\n' + doc[end:]


def detail_customization(doc, c, log):
    sku = c.p['sku'][0]
    colours = ', '.join(pick(v['name'], c.lang) for v in sku['values'])
    pkg = c.p['packaging']
    rows = [
        ('Colour', colours),
        ('Custom logo', '✓'),
        ('Custom colour', '✓'),
        ('Custom packaging', '✓'),
    ]
    trs = ''.join('          <tr><th scope="row">%s</th><td>%s</td></tr>\n' % (
        esc(a), esc(b)) for a, b in rows)
    pkg_rows = ''.join('        <tr><th scope="row">%s</th><td>%s</td></tr>\n' % (
        esc(a), esc(b)) for a, b in (
            ('Unit', pkg['unit']), ('Carton size', pkg['ctn_size']),
            ('Carton qty', pkg['ctn_qty']), ('Gross weight', pkg['gross_weight'])))
    block = ('<section class="section" id="customization">\n  <div class="section-inner">\n'
             '    <div class="text-center">\n      <h2 class="section-title">Customisation</h2>\n'
             '      <p class="section-sub">OEM / ODM · MOQ %d pcs · sample up to %d pc</p>\n'
             '    </div>\n    <div class="aqc-ss">\n      <table>\n        <tbody>\n%s'
             '        </tbody>\n      </table>\n'
             '      <h3 style="margin:24px 0 8px;font-size:16px;color:#0F172A;">Packaging</h3>\n'
             '      <table><tbody>\n%s      </tbody></table>\n    </div>\n  </div>\n</section>\n' % (
                 c.moq, c.p['sample']['qty'], trs, pkg_rows))
    start = doc.index('<section class="section" id="customization">')
    end = doc.index('<section class="section" id="specifications">')
    log.append('  customization x1')
    return doc[:start] + block + '\n' + doc[end:]


def detail_specs(doc, c, log):
    trs = ''.join('            <tr><th scope="row">%s</th><td>%s</td></tr>\n' % (
        esc(pick(s['label'], c.lang)), esc(pick(s['value'], c.lang)))
        for s in c.p['specs'])
    block = ('<section class="section" id="specifications">\n  <div class="section-inner">\n'
             '    <div class="text-center">\n      <h2 class="section-title">Full specifications</h2>\n'
             '      <p class="section-sub">%s — Model SD-901</p>\n    </div>\n'
             '    <div class="aqc-ss">\n      <table>\n'
             '        <caption style="text-align:left;padding:0 0 10px;color:#64748B;'
             'font-size:13px;">Written specification table (text-based)</caption>\n'
             '        <tbody>\n%s        </tbody>\n      </table>\n    </div>\n'
             '  </div>\n</section>\n' % (esc(c.name), trs))
    start = doc.index('<section class="section" id="specifications">')
    end = doc.index('<section class="section section-alt" id="pricing">')
    log.append('  specifications x1')
    return doc[:start] + block + '\n' + doc[end:]


def detail_pricing(doc, c, log):
    rows = ''
    for step in c.ladder:
        if step['max'] >= 99999:
            qty = '%d+ pcs' % step['min']
        else:
            qty = '%d–%d pcs' % (step['min'], step['max'])
        rows += '            <tr><td>%s</td><td>US$%g / pc</td></tr>\n' % (qty, step['price'])
    block = ('<section class="section section-alt" id="pricing">\n  <div class="section-inner">\n'
             '    <div class="text-center">\n      <h2 class="section-title">Pricing & MOQ</h2>\n'
             '      <p class="section-sub">MOQ %d pcs</p>\n    </div>\n'
             '    <div class="aqc-ss">\n      <table>\n'
             '<thead><tr><th scope="col">Order quantity</th>'
             '<th scope="col">Unit price</th></tr></thead>\n'
             '        <tbody>\n%s        </tbody>\n      </table>\n'
             '      <p class="aqc-note">Platform shipping estimate: US$0</p>\n'
             '    </div>\n  </div>\n</section>\n' % (c.moq, rows))
    start = doc.index('<section class="section section-alt" id="pricing">')
    end = doc.index('<section class="section section-alt" id="related">')
    log.append('  pricing       x1')
    return doc[:start] + block + '\n' + doc[end:]


def detail_inline(doc, c, log):
    data = {
        'category_name': {c.lang: c.cat_name},
        'products': [{
            'id': PID,
            'name': {c.lang: c.name},
            'tagline': {c.lang: c.tagline},
            'images': ['https://www.hkdmj.net%s' % i for i in c.img],
            'video_url': '',
            'moq': c.p['moq'],
            'certifications': [],
            'cert_note': {c.lang: 'Certification documents on file — available on request.'},
            'highlights': [{'icon': h['icon'], 'text': {c.lang: pick(h['text'], c.lang)}}
                           for h in c.p['highlights']],
            'specs': [{'label': {c.lang: pick(s['label'], c.lang)},
                       'value': {c.lang: pick(s['value'], c.lang)}} for s in c.p['specs']],
            'quick_specs': [{'label': {c.lang: pick(s['label'], c.lang)},
                             'value': {c.lang: pick(s['value'], c.lang)}}
                            for s in c.p['quick_specs']],
            'packaging': c.p['packaging'],
            'customization': c.p['customization'],
            'applications': {c.lang: pick(c.p['applications'], c.lang)},
            'price_indicator': c.price,
            'sku': [{'name': {c.lang: pick(c.p['sku'][0]['name'], c.lang)},
                     'values': [{'name': {c.lang: pick(v['name'], c.lang)}}
                                for v in c.p['sku'][0]['values']]}],
            'description': {c.lang: c.desc},
            'supplier_rating': c.p['supplier_rating'],
            'ship_from': {c.lang: pick(c.p['ship_from'], c.lang)},
            'sample': c.p['sample'],
            'category_name': {c.lang: c.cat_name},
            'certificates': [],
            'supplier': c.p['supplier'],
            'store_rating': c.p['store_rating'],
            'shipping_fee_usd': 0,
            'alibaba_url': '',
            '_cat': SLUG,
            'detail_images': ['https://www.hkdmj.net%s' % i for i in c.img],
        }],
    }
    block = ('<script>/*aqc-product-data*/window.AQC_PRODUCT_DATA=%s;</script>'
             % json.dumps(data, ensure_ascii=False, separators=(',', ':')))
    start = doc.index('<script>/*aqc-product-data*/')
    end = doc.index('</script>', start) + len('</script>')
    log.append('  inline-data   x1')
    return doc[:start] + block + doc[end:]


def build_detail(c, tpl, out_path, apply_this):
    log = []
    doc = read(tpl)
    doc = apply_common(doc, c, log)
    doc = detail_product_ld(doc, c, log)
    doc = detail_mount(doc, c, log)
    doc = detail_images(doc, c, log)
    doc = detail_glance(doc, c, log)
    doc = detail_customization(doc, c, log)
    doc = detail_specs(doc, c, log)
    doc = detail_pricing(doc, c, log)
    doc = detail_inline(doc, c, log)
    for old in ('https://www.hkdmj.net/assets/images/products/17-12-portable-espresso.webp',
                '/assets/images/products/17-12-portable-espresso.webp',
                '/assets/images/products/12-portable-espresso.webp',
                '/assets/images/products/hands-free-soap-dispenser-sd901/01.webp'):
        if old in doc:
            doc = doc.replace(old, CARD_IMG)
            log.append('  og-image      %s' % old)
    # /{lang}/coffee-machine/ 的「Espresso Coffee Machine / 意式咖啡机」是站内的
    # 另一个品类，属于合法的相关链接与页脚导航，不算残留
    probe = doc.replace('Espresso Coffee Machine', '').replace('意式咖啡机', '')\
                .replace('咖啡机', '').replace('coffee-machine', '')
    leftovers = [w for w in ('espresso', 'Espresso', 'XYD-003', 'xyd003',
                             'portable-espresso') if w in probe]
    if c.lang == 'zh':
        leftovers += [w for w in ('咖啡', '浓缩') if w in probe]
    if leftovers:
        for w in leftovers:
            for mm in list(re.finditer(re.escape(w), doc))[:3]:
                snip = doc[max(0, mm.start() - 90):mm.start() + 90].replace('\n', ' ')
                print('    !! %-18s ...%s...' % (w, snip))
    print('--- %s/%s-%s.html  leftovers=%s' % (c.lang, SLUG, PID, leftovers or 'none'))
    for line in log:
        print(line)
    if apply_this and not leftovers:
        write(out_path, doc)
        print('  wrote %s' % os.path.relpath(out_path, ROOT))
    elif apply_this:
        print('  !! skipped write because of leftovers')
    return not leftovers


def main():
    apply_this = '--apply' in sys.argv
    prod = load(os.path.join(ROOT, 'data/products', SLUG + '.json'))['products'][0]
    src_prod = load(os.path.join(ROOT, 'data/products', SRC_CAT + '.json'))['products'][0]
    cats = load(os.path.join(ROOT, 'data/products/categories.json'))['categories']
    # 页面上残留的旧品类翻译依据：旧的 categories.json 已被覆盖，改从 src 数据取名
    src_cats_src = json.loads(read(os.path.join(ROOT, 'data/products/categories.json')))
    src_cats = src_cats_src['categories']
    # 旧品类的名字已经不在 categories.json 里（仍在，未被删）—— 直接遍历找
    ok = True
    for lang in TARGET_LANGS:
        c = Ctx(lang, prod, src_prod, cats, src_cats)
        tpl_cat = os.path.join(ROOT, lang, SRC_CAT, 'index.html')
        out_dir = os.path.join(ROOT, lang, SLUG)
        if not os.path.isdir(out_dir):
            os.makedirs(out_dir)
        out_cat = os.path.join(out_dir, 'index.html')
        tpl_detail = os.path.join(ROOT, lang, '%s-%s.html' % (SRC_CAT, SRC_ID))
        out_detail = os.path.join(ROOT, lang, '%s-%s.html' % (SLUG, PID))
        print('=== %s ===' % lang)
        ok &= build_category(c, tpl_cat, out_cat, apply_this)
        ok &= build_detail(c, tpl_detail, out_detail, apply_this)
    print('OK' if ok else 'LEFTOVERS FOUND')
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
