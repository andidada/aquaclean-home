#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
remove_product.py — 把一个产品从站点上彻底摘掉（数据 / 详情页 / 类目页 / 图片）

为什么不用 git revert / checkout
--------------------------------
撤产品的那个提交里通常混着别的有用改动（这次 PG16PRO 那条提交同时改了 3 个
脚本、纠了 GT20 归属），整提交回滚会把那些一起赔进去。这里只精确地摘除
这一个产品留下的痕迹。

要处理的 5 处（任何一处漏了，线上就是"点了能进但列表里没有"或"列表有但 404"）
--------------------------------------------------------------------------
  1. data/products/<cat>.json 里的产品元素（位置感知删除，不动其它字节）
  2. 9 个语种的详情页 <lang>/<cat>-<id>.html
  3. 类目页的静态卡片 + productCount + "N models" 文案
  4. 类目页的 ItemList JSON-LD（按品类顺序整体重建，position 重新连续编号）
  5. 类目页底部对比表的行 —— 同样整体重排
另外还有图片目录。

⚠️ 类目页的 3/4/5 不是"把新加的那份删掉"，而是**按剩下的数据重新生成**，
   因为 add_to_category.py 当初插的时候重排过 position 和表格顺序，
   单纯逆向删除会把顺序留下错位。

用法
----
    python scripts/remove_product.py handheld-vacuum pg16pro           # 预演
    python scripts/remove_product.py handheld-vacuum pg16pro --apply
"""
from __future__ import annotations
import io, json, os, re, shutil, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fix_product_highlights import find_product_span          # noqa: E402
import add_to_category as ac                                  # noqa: E402

ROOT = ac.ROOT
SITE = ac.SITE
LANGS = ['en', 'zh', 'ar', 'es', 'fr', 'id', 'ru', 'th', 'vi']


def read(p):
    return io.open(p, encoding='utf-8', newline='').read()


def strip_product_from_data(path, pid):
    """把 products 数组里的某个元素整块摘掉，其余字节一字不动。"""
    t = read(path)
    before = json.loads(t)
    ids = [x['id'] for x in before['products']]
    assert pid in ids, '%s 里没有 %s' % (path, pid)

    ps, pe = find_product_span(t, pid)

    # 判断是不是数组里的第一个元素：往回跳过空白，看是不是 '['
    j = ps
    while j > 0 and t[j - 1] in ' \t\r\n':
        j -= 1
    is_first = (t[j - 1] == '[')

    if is_first:
        # 第一个元素前面没有逗号可吃（前面是 '['），必须改吃它**后面**那个逗号，
        # 否则留下 "[\n    , {...}]" 这种非法 JSON。
        # （删 yzx-305 / 2604 / d09s / ymc6628 / qst063 时全踩这个。）
        k = pe
        while k < len(t) and t[k] in ' \t\r\n':
            k += 1
        if t[k:k + 1] == ',':
            k += 1
        out = t[:j] + t[k:]
    else:
        # 往前吃掉分隔符里的逗号（保留元素前的缩进空白，否则换行会塌一行）
        i = ps
        while i > 0 and t[i - 1] in ' \t\r\n':
            i -= 1
        if t[i - 1] == ',':
            i -= 1
        out = t[:i] + t[pe:]

    after = json.loads(out)
    assert [x['id'] for x in after['products']] == [x for x in ids if x != pid], \
        '删除后产品清单不对'
    return out


def div_content_span(s, open_tag_start):
    """给定一个开始标签的位置，返回它内部内容的区间 (start, end)。

    靠 <div …> / </div> 计数找匹配的收尾标签。形如 <div>xxx</div> 的容器、
    里面还嵌套 <div class="product-card">…</div> 的情况都能处理。
    """
    gt = s.index('>', open_tag_start)
    i = gt + 1
    depth = 1
    while depth > 0:
        nx_open = s.find('<div', i)
        nx_close = s.find('</div>', i)
        assert nx_close > 0, '没找到匹配的 </div>'
        if nx_open > 0 and nx_open < nx_close:
            depth += 1
            i = nx_open + 4
        else:
            depth -= 1
            i = nx_close + 6
            if depth == 0:
                return gt + 1, nx_close
    raise RuntimeError('div_content_span 走到不该到的地方')


def find_block_containing(s, class_marker, needle):
    """在所有 class="…" 的 div 里，找出内部文本含 needle 的那一块，
    返回 (块起点, 块终点含收尾 </div>)。找不到返回 None。"""
    for m in re.finditer(r'<div class="%s">' % re.escape(class_marker), s):
        a = m.start()
        c0, c1 = div_content_span(s, a)
        if needle in s[c0:c1]:
            # 收尾 </div> 的结束位置：从 c0 重新开始数一次更稳
            _, _ = c0, c1
            b = s.index('</div>', c1) + len('</div>')
            return a, b
    return None


def strip_from_category_page(path, cat, pid, products, lang):
    """把某个产品的痕迹从类目页里摘掉：**只动它自己那几处**。

    ⚠️ 为什么不是"按剩下的数据重建全部卡片"：其它语种的卡片是本地化的，
    而且带各产品自己的细节（gv18 用 01-main.webp、还有 decoding="async"），
    add_to_category.card_html 只按 en/zh 口径渲染，整块重建会把另外 11 张
    卡片一起改坏（图片路径、属性都可能变）。所以这里只精确摘除这一份。
    """
    t = read(path)
    crlf = '\r\n' in t
    s = t.replace('\r\n', '\n')

    total = len(products)
    d = '%s-%s' % (cat, pid)

    # 1. 静态卡片：定位包含该产品链接的那张卡片整块删掉
    # ⚠️ marker 只传类名：find_block_containing 内部会再套一层 `<div class="...">`，
    #    传 'class="product-card"' 会拼出 <div class="class="product-card"">，永远匹配不到。
    card = find_block_containing(s, 'product-card', '/%s/%s.html' % (lang, d))
    assert card, '%s 里找不到 %s 的卡片' % (path, d)
    a, b = card
    # 连同卡片后面的空行一起吃掉，别留下连续空行
    j = b
    while j < len(s) and s[j] in ' \t':
        j += 1
    if s[j:j + 1] == '\n':
        j += 1
    s = s[:a] + s[j:]

    # 2. productCount
    s, n = re.subn(r'(<span id="productCount">)\s*\d+(\s*[^<]*</span>)',
                   r'\g<1>%d\g<2>' % total, s, count=1)
    assert n == 1, '找不到 #productCount'

    # 3. "N models in this category" / "该类目当前共 N 个型号"
    s, n = re.subn(r'\b\d+\s+models in this category', '%d models in this category' % total, s)
    s, m2 = re.subn(r'共 \d+ 个型号', '共 %d 个型号' % total, s)
    # ⚠️ 只有 en / zh 有这句文案。另外 7 个语种是 gen_pages.py 从 en 模板克隆后
    #    替换语言串生成的，这句没被翻译过去。所以"有则改、无则跳过"，不能 assert。
    if n == 0 and m2 == 0:
        print('     · %s 无"N models/共 N 个型号"文案，跳过' % path)

    # 4. ItemList：删掉这一条，然后按文档顺序把剩下的重排成 1..N
    il = re.search(r'(<script type="application/ld\+json">\s*\{\s*"@context": "https://schema\.org",\s*'
                   r'"@type": "ItemList".*?</script>)', s, re.S)
    assert il, '找不到 ItemList JSON-LD'
    block = il.group(1)
    # ListItem 是扁平对象（没有嵌套 {}），可以用"下一个 { 到匹配的 }"逐个取
    items = re.findall(r'\{[^{}]*"@type": "ListItem"[^{}]*\}', block, re.S)
    assert items, 'ItemList 里一条都没有'
    keep = [x for x in items if '/%s/%s.html' % (lang, d) not in x]
    assert len(keep) == len(items) - 1, 'ItemList 里没有 %s（或不止一条）' % d

    def _num(m0):
        _num.i += 1
        return '"position": %d' % _num.i

    _num.i = 0
    new_items = [re.sub(r'"position": \d+', _num, x) for x in keep]
    newblock = re.sub(r'("itemListElement": \[)(.*?)(\n\s*\])',
                      lambda m0: m0.group(1) + '\n' + ',\n'.join(new_items) + m0.group(3),
                      block, count=1, flags=re.S)
    assert newblock != block, 'ItemList 没改动'
    if '"numberOfItems"' in newblock:
        newblock = re.sub(r'"numberOfItems": \d+', '"numberOfItems": %d' % total,
                          newblock, count=1)
    s = s[:il.start(1)] + newblock + s[il.end(1):]

    # 5. 对比表：删掉这一行
    # ⚠️ 对比表只存在于 ar/es/fr/id/ru/th/vi 这 7 个语种的品类页上，
    #    en / zh 的品类页根本没有 <table>（实测 <tr> 数为 0）。有则删，无则跳过。
    has_table = '<tr><td><a href="/%s/%s-' % (lang, cat) in s
    if has_table:
        row = re.search(r'[ \t]*<tr>[^\n]*?/%s/%s\.html.*?</tr>' % (lang, d), s, re.S)
        assert row, '对比表里找不到 %s 的行' % d
        r2 = row.group(0)
        s = s.replace(r2, '', 1)
        s = re.sub(r'(</tr>)\n\n+', r'\1\n', s, count=1)

    # ── 断言 ──────────────────────────────────────────────────────
    assert '/%s/%s.html' % (lang, d) not in s, '页面里还有 %s 的链接' % d
    cards_n = len(re.findall(r'<div class="product-card">\s*<div class="product-img-wrap">\s*'
                             r'<img src="/assets/images/products/%s' % re.escape(cat), s))
    assert cards_n == total, '静态卡片数 %d != 产品数 %d' % (cards_n, total)
    il3 = re.search(r'<script type="application/ld\+json">\s*\{\s*"@context": "https://schema\.org",\s*'
                    r'"@type": "ItemList".*?</script>', s, re.S)
    pos = [int(x) for x in re.findall(r'"position": (\d+)', il3.group(0))]
    assert pos == list(range(1, total + 1)), 'ItemList position 不连续：%s' % pos
    # 只数数据行：<thead> 的 <tr> 也要算进去的话会永远多 1
    # 只数数据行：<thead> 的 <tr> 也要算进去的话会永远多 1
    # （en / zh 没有对比表，只在表存在时才校验行数）
    if has_table:
        row_n = len(re.findall(r'<tr><td><a href="/%s/%s-' % (re.escape(lang), re.escape(cat)), s))
        assert row_n == total, '对比表数据行数 %d != 产品数 %d' % (row_n, total)
    assert s.count('<section') == t.replace('\r\n', '\n').count('<section'), 'section 数变了'
    # JSON-LD 必须还能解析
    for mm in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', s, re.S):
        json.loads(mm.group(1))
    # 剩下的卡片顺序必须和数据一致（防止摘错位置导致顺序漂移）
    got = [m0.group(1) for m0 in re.finditer(
        r'<img src="/assets/images/products/%s-([a-z0-9\-]+)/' % re.escape(cat), s)]
    want = [x['id'] for x in products]
    assert got == want, '卡片顺序与数据不一致：\n  页面=%s\n  数据=%s' % (got, want)

    return s.replace('\n', '\r\n') if crlf else s


def main():
    argv = sys.argv[1:]
    if len(argv) < 2:
        sys.exit('用法：python scripts/remove_product.py <cat> <id> [--apply]')
    cat, pid = argv[0], argv[1]
    apply = '--apply' in argv

    dpath = os.path.join(ROOT, 'data', 'products', cat + '.json')
    data = json.loads(read(dpath))
    ids_all = [x['id'] for x in data['products']]
    rest = [x for x in data['products'] if x['id'] != pid]
    # 幂等：已经摘过就当作 0 个要摘（脚本中途失败后可以直接重跑）
    if pid not in ids_all:
        print('· data 里已经没有 %s，直接进入类目页重建' % pid)
    assert len(rest) in (len(data['products']) - 1, len(data['products'])), '数据异常'
    for x in rest:
        x['_cat'] = cat

    print('=== 计划（%s）===' % ('执行' if apply else '预演'))
    print('  data/products/%s.json：产品 %d → %d 个' % (cat, len(data['products']), len(rest)))

    d = '%s-%s' % (cat, pid)
    pages = [os.path.join(lang, d + '.html') for lang in LANGS]
    exist_pages = [p for p in pages if os.path.isfile(os.path.join(ROOT, p))]
    print('  详情页：删除 %d 个（%s）' % (len(exist_pages), ', '.join(sorted({p.split(os.sep)[0] for p in exist_pages}))))

    catpaths = [os.path.join(lang, cat, 'index.html') for lang in LANGS]
    exist_cat = [p for p in catpaths if os.path.isfile(os.path.join(ROOT, p))]
    print('  类目页：重建 %d 个' % len(exist_cat))

    imgdir = os.path.join(ROOT, 'assets', 'images', 'products', d)
    if os.path.isdir(imgdir):
        n = sum(len(fs) for _, _, fs in os.walk(imgdir))
        ndir = sum(len(ds) for _, ds, _ in os.walk(imgdir))
        print('  图片目录：assets/images/products/%s（%d 个文件）' % (d, n))
        del ndir

    # 是否还有别的地方引用（防止删出死链）
    print('\n  残留引用扫描：')
    leftovers = []
    for lang in LANGS:
        base = os.path.join(ROOT, lang)
        if not os.path.isdir(base):
            continue
        for fn in os.listdir(base):
            if not fn.endswith('.html'):
                continue
            p = os.path.join(base, fn)
            s = read(p)
            if pid in s and not fn.startswith(d):
                leftovers.append(os.path.join(lang, fn))
    for p in sorted(set(leftovers)):
        print('     ⚠ %s 仍提到 %s' % (p, pid))
    if not leftovers:
        print('     除详情页与类目页外无其它引用 ✅')

    if not apply:
        print('\n预演结束，加 --apply 真正删除。')
        return 0

    # 1. data（幂等：已经摘过就跳过，方便脚本中途失败后直接重跑）
    ids_now = [x['id'] for x in json.loads(read(dpath))['products']]
    if pid in ids_now:
        out = strip_product_from_data(dpath, pid)
        with io.open(dpath, 'w', encoding='utf-8', newline='') as f:
            f.write(out)
        print('\n✓ data 已摘除')
    else:
        print('\n· data 里已经没有 %s，跳过' % pid)

    # 2. 详情页
    done = 0
    for p in exist_pages:
        fp = os.path.join(ROOT, p)
        if os.path.isfile(fp):
            os.remove(fp)
            done += 1
    print('✓ 删除详情页 %d 个' % done)

    # 3. 类目页
    for p in exist_cat:
        new = strip_from_category_page(os.path.join(ROOT, p), cat, pid, rest,
                                       p.split(os.sep)[0])
        with io.open(os.path.join(ROOT, p), 'w', encoding='utf-8', newline='') as f:
            f.write(new)
    print('✓ 重建类目页 %d 个' % len(exist_cat))

    # 4. 图片
    if os.path.isdir(imgdir):
        shutil.rmtree(imgdir)
        print('✓ 删除图片目录')

    print('\n下一步：')
    print('   python scripts/gen_pages.py          # 确认其余语种没有再生成回来')
    print('   同步后台数据；查询 %s 确保无残留' % pid)
    return 0


if __name__ == '__main__':
    sys.exit(main())
