#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
add_to_category.py — 把新产品登记进类目页（en / zh）

类目页有 **5 处** 会因为产品数量变化而需要同步，只改其中一两处就会出现
"页面上能点进详情页，但列表数字没变" 这类不一致：

  1. #productsGrid里的静态产品卡片（爬虫 / 禁用 JS 才看得到）
  2. <span id="productCount">N Products</span>
  3. "N models in this category right now" / "该类目当前共 N 个型号"
  4. ItemList JSON-LD（position 从 1 连续编号）
  5. 底部对比表格的 <tr>（型号 / 起订量 / 价格 / 关键规格 / 认证）

⚠️ 其余 7 个语种不用管：gen_pages.py 会把 en 页的 #productsGrid 整块复制过去，
所以改完 en + zh 之后跑一次 gen_pages.py 即可。

用法
----
    python scripts/add_to_category.py en zh --only handheld-vacuum/eg16pro --apply
"""
from __future__ import annotations
import html as htmlmod
import io, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://www.hkdmj.net'


def esc(s):
    return htmlmod.escape('' if s is None else str(s), quote=True)


def read(p):
    return io.open(p, encoding='utf-8', newline='').read()


def pick(d, lang, default=None):
    if isinstance(d, dict):
        v = d.get(lang)
        return v if v else (d.get('en') or default)
    return d if d is not None else default


GRID_RE = re.compile(
    r'(<div id="productsGrid" class="products-grid">)(.*?)(\n\s*</div>\s*</div>\s*</section>)', re.S)


def card_html(p, lang):
    """静态产品卡片。

    注意：这里跟着**既有静态卡片**的写法（描述行取 quick_specs 前 3 项），
    而不是 JS 渲染时用的 tagline —— JS 会用 tagline 整块重写这个 grid，
    静态卡片只对爬虫和禁用 JS 的访客可见。两套写法本来就不一致（既有 10 张
    卡片都是 quick_specs），这里选择跟邻居保持一致，而不是只让新卡片显得特殊。
    """
    name = pick(p['name'], lang)
    d = '%s-%s' % (p['_cat'], p['id'])
    quick = p.get('quick_specs') or []
    desc = ' · '.join('%s: %s' % (pick(q['label'], lang), pick(q['value'], lang))
                      for q in quick[:3])
    pi = p.get('price_indicator') or {}
    moq = (p.get('moq') or {}).get('value')
    unit = {'en': 'MOQ', 'zh': '起订量'}[lang]
    btn = {'en': 'View Details', 'zh': '查看详情'}[lang]
    price = ''
    if pi.get('min') is not None and pi.get('max') is not None:
        price = ('      \n          <div style="margin-bottom:12px;"><div class="price-indicator">'
                 '$%s-$%s <span class="moq">/ pc %s %s pcs</span></div></div>'
                 % (esc(pi['min']), esc(pi['max']), unit, moq))
    return ('      <div class="product-card">\n'
            '        <div class="product-img-wrap">\n'
            '          <img src="/assets/images/products/%s/01.jpg" alt="%s" loading="lazy">\n'
            '        </div>\n'
            '        <div class="product-body">\n'
            '          <h3>%s</h3>\n'
            '          <p>%s</p>\n'
            '          \n'
            '%s'
            '          <a href="%s/%s/%s.html" class="btn btn-primary" '
            'style="width:100%%;justify-content:center;text-decoration:none;">%s &#8594;</a>\n'
            '        </div>\n'
            '      </div>' % (d, esc(name), esc(name), esc(desc),
                           price, SITE, lang, d, btn))


def row_html(p, lang):
    name = pick(p['name'], lang)
    d = '%s-%s' % (p['_cat'], p['id'])
    pi = p.get('price_indicator') or {}
    moq = (p.get('moq') or {}).get('value')
    price = ('US$%s–%s / pc' % (pi['min'], pi['max'])
             if pi.get('min') is not None and pi.get('max') is not None else '—')
    specs = ' · '.join('%s: %s' % (pick(q['label'], lang), pick(q['value'], lang))
                       for q in (p.get('quick_specs') or []))
    certs = '、'.join(p.get('certifications') or []) or '—'
    return ('          <tr><td><a href="/%s/%s.html">%s</a></td><td>%s</td>'
            '<td>%s pcs</td><td>%s</td><td>%s</td><td>%s</td></tr>'
            % (lang, d, esc(name), esc(p['id']), esc(moq), esc(price), esc(specs), esc(certs)))


def patch(path, p, lang):
    t = read(path)
    crlf = '\r\n' in t
    s = t.replace('\r\n', '\n')

    d = '%s-%s' % (p['_cat'], p['id'])
    assert ('%s/%s.html' % (lang, d)) not in s, '%s 已经在 %s 里了' % (p['id'], path)

    # 1. grid 静态卡片
    m = GRID_RE.search(s)
    assert m, '找不到 #productsGrid 块'
    s = s[:m.end(2)] + '\n' + card_html(p, lang) + s[m.end(2):]

    # 2. productCount
    s, n = re.subn(r'(<span id="productCount">)\s*\d+(\s*[^<]*</span>)',
                   r'\g<1>%d\g<2>' % len(p['_all_ids']), s, count=1)
    assert n == 1, '找不到 #productCount'

    # 3. "N models in this category" / "该类目当前共 N 个型号"
    total = len(p['_all_ids'])
    s, n = re.subn(r'\b\d+\s+models in this category', '%d models in this category' % total, s)
    s, m2 = re.subn(r'共 \d+ 个型号', '共 %d 个型号' % total, s)
    assert n == 1 or m2 == 1, '找不到"N models in this category"/"共 N 个型号"'

    # 4. ItemList JSON-LD ——追加到最后，position 接着排
    il = re.search(r'(<script type="application/ld\+json">\s*\{\s*"@context": "https://schema\.org",\s*'
                   r'"@type": "ItemList".*?</script>)', s, re.S)
    assert il, '找不到 ItemList JSON-LD'
    block = il.group(1)
    positions = [int(x) for x in re.findall(r'"position": (\d+)', block)]
    assert positions == list(range(1, len(positions) + 1)), \
        'ItemList 的 position 不连续（%s），先修好再插' % positions
    item = ('    {\n      "@type": "ListItem",\n      "position": %d,\n'
            '      "name": %s,\n      "url": "%s/%s/%s.html"\n    }'
            % (len(positions) + 1, json.dumps(pick(p['name'], lang), ensure_ascii=False),
               SITE, lang, d))
    newblock = block.replace('"itemListElement": [', '"itemListElement": [\n' + item + ',', 1)
    assert newblock != block, 'ItemList 插入失败'
    s = s[:il.start(1)] + newblock + s[il.end(1):]

    # 5. 对比表格追加一行
    tb = re.search(r'<tbody>\n(.*?)\n(\s*)</tbody>', s[il.end(1):], re.S)
    assert tb, '找不到对比表格 tbody'
    at = il.end(1) + tb.start(1)
    s = s[:at] + '\n' + row_html(p, lang) + s[at:]

    # ── 断言 ─────────────────────────────────────────────────────────
    cards = len(re.findall(r'<div class="product-card">\s*<div class="product-img-wrap">'
                           r'\s*<img src="/assets/images/products/handheld-vacuum',
                           s))
    assert cards == total, '静态卡片数 %d != 产品数 %d' % (cards, total)
    # 只在 ItemList 块内数：面包屑 BreadcrumbList 里也有 ListItem，
    # 全页 grep 会多算 2 条，断言永远不成立
    il2 = re.search(r'<script type="application/ld\+json">\s*\{\s*"@context": "https://schema\.org",\s*'
                    r'"@type": "ItemList".*?</script>', s, re.S)
    assert il2, '找不到 ItemList JSON-LD'
    assert len(re.findall(r'"@type": "ListItem"', il2.group(0))) == total, 'ItemList 条目数不对'
    assert ('%s/%s.html' % (lang, d)) in s, '详情页链接没进去'
    assert s.count('<section') == t.replace('\r\n', '\n').count('<section'), 'section 数变了'

    return s.replace('\n', '\r\n') if crlf else s


def main():
    argv = sys.argv[1:]
    apply = '--apply' in argv
    langs = [a for a in argv if a in ('en', 'zh')] or ['en', 'zh']
    only = argv[argv.index('--only') + 1] if '--only' in argv else ''
    cat, pid = only.split('/') if only else (None, None)

    data = json.loads(read(os.path.join(ROOT, 'data', 'products', cat + '.json')))
    p = [x for x in data['products'] if x['id'] == pid]
    assert p, 'data/products/%s.json 里没有 %s' % (cat, pid)
    p = p[0]
    p['_cat'] = cat
    p['_all_ids'] = [x['id'] for x in data['products']]

    for lang in langs:
        path = os.path.join(ROOT, lang, cat, 'index.html')
        out = patch(path, p, lang)
        print('%s：静态卡片 %d 张、ItemList %d 条、对比表 %d 行'
              % (os.path.relpath(path, ROOT), len(p['_all_ids']),
                 len(p['_all_ids']), len(p['_all_ids'])))
        if apply:
            with io.open(path, 'w', encoding='utf-8', newline='') as f:
                f.write(out)
            print('  已写入 %s' % os.path.relpath(path, ROOT))
        else:
            print('  预演模式（%d → %d 字符）' % (len(read(path)), len(out)))

    if apply:
        print('\n下一步：python scripts/gen_pages.py   # 把 en 的 grid 复制到其余 7 个语种')
    return 0


if __name__ == '__main__':
    sys.exit(main())