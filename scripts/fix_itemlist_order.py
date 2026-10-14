#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fix_itemlist_order.py — 把类目页 ItemList JSON-LD 的顺序对齐到「数据 + 静态卡片」的顺序

背景
----
add_to_category.py 当初插新产品时，把 ListItem 塞在数组**开头**、position 却写成
N+1，于是文档里第一条是 position=11（EG16Pro 那次留下的）。静态卡片是追加在
grid 末尾的，所以结构化数据和页面可见顺序正好相反 —— Google 可能判为
"结构化数据与页面内容不符"。

本脚本只做一件事：按 data/products/<cat>.json 的产品顺序重排 ItemList，
position 从 1 连续编号。卡片、表格、文案一个字不动。

用法
----
    python scripts/fix_itemlist_order.py handheld-vacuum           # 预演
    python scripts/fix_itemlist_order.py handheld-vacuum --apply
    python scripts/fix_itemlist_order.py --all --apply             # 所有品类
"""
from __future__ import annotations
import io, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANGS = ['en', 'zh', 'ar', 'es', 'fr', 'id', 'ru', 'th', 'vi']
IL_RE = re.compile(r'<script type="application/ld\+json">\s*\{\s*"@context": "https://schema\.org",\s*'
                   r'"@type": "ItemList".*?</script>', re.S)


def read(p):
    return io.open(p, encoding='utf-8', newline='').read()


def itemlist_order(s):
    """返回 ItemList 里 url 对应的产品 id 序列（按文档顺序）。"""
    m = IL_RE.search(s)
    if not m:
        return None
    ids = []
    for it in re.findall(r'\{[^{}]*"@type": "ListItem"[^{}]*\}', m.group(0), re.S):
        u = re.search(r'"url": "([^"]+)"', it)
        if not u:
            return None
        slug = u.group(1).rsplit('/', 1)[-1][:-len('.html')]
        ids.append(slug)
    return ids


def needs_fix(s, want):
    got = [x for x in (itemlist_order(s) or [])]
    return got != want


def fix(path, want, apply):
    t = read(path)
    crlf = '\r\n' in t
    s = t.replace('\r\n', '\n')
    m = IL_RE.search(s)
    assert m, '%s 找不到 ItemList' % path
    block = m.group(0)

    # ⚠️ 连**前面的缩进空白**一起捕获：只匹配 `\{...\}` 会把每行开头的 4 个
    #    空格吃掉，重排完 ItemList 全部顶格，diff 多出十几行纯排版噪声。
    items = re.findall(r'[ \t]*\{[^{}]*"@type": "ListItem"[^{}]*\}', block, re.S)
    by_id = {}
    for it in items:
        u = re.search(r'"url": "([^"]+)"', it).group(1)
        pid = u.rsplit('/', 1)[-1][:-len('.html')]
        # 统一成"4 空格缩进的 { 开头"，避免第一行带着数组开头的换行
        by_id[pid] = it.lstrip(' \t')
    missing = [x for x in want if x not in by_id]
    extra = [x for x in by_id if x not in want]
    assert not missing, '%s 的 ItemList 缺这些产品：%s' % (path, missing)
    assert not extra, '%s 的 ItemList 多出这些产品：%s' % (path, extra)

    def _num(m0):
        _num.i += 1
        return '"position": %d' % _num.i

    _num.i = 0
    # 进来时已经把 CRLF 归一化成 \n 了，收尾会再换回去，所以这里一律用 \n
    new_items = ['    ' + re.sub(r'"position": \d+', _num, by_id[x]) for x in want]
    newblock = re.sub(r'("itemListElement": \[)(.*?)(\n\s*\])',
                      lambda m0: m0.group(1) + '\n' + ',\n'.join(new_items) + m0.group(3),
                      block, count=1, flags=re.S)
    assert newblock != block, '%s 的 ItemList 没改动（顺序本来就是对的？）' % path

    out = s[:m.start()] + newblock + s[m.end():]
    # 断言
    assert itemlist_order(out) == want, '%s 重排后顺序仍不对' % path
    pos = [int(x) for x in re.findall(r'"position": (\d+)', IL_RE.search(out).group(0))]
    assert pos == list(range(1, len(want) + 1)), '%s position 不连续：%s' % (path, pos)
    for mm in re.finditer(r'<script type="application/ld\+json">(.*?)</script>', out, re.S):
        json.loads(mm.group(1))
    out = out.replace('\n', '\r\n') if crlf else out

    if apply:
        with io.open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(out)
    return True


def main():
    argv = sys.argv[1:]
    apply = '--apply' in argv
    cats = [a for a in argv if not a.startswith('-')]
    if '--all' in argv or not cats:
        cats = sorted(os.path.basename(p)[:-len('.json')]
                      for p in os.listdir(os.path.join(ROOT, 'data', 'products'))
                      if p.endswith('.json'))

    total_fixed = 0
    for cat in cats:
        dpath = os.path.join(ROOT, 'data', 'products', cat + '.json')
        if not os.path.isfile(dpath):
            print('· 跳过 %s（没有数据文件）' % cat)
            continue
        data = json.loads(read(dpath))
        prods = data.get('products') or []
        if not prods:
            continue          # categories.json 之类的非产品文件
        want = ['%s-%s' % (cat, x['id']) for x in prods]
        for lang in LANGS:
            page = os.path.join(ROOT, lang, cat, 'index.html')
            if not os.path.isfile(page):
                continue
            s = read(page)
            if not needs_fix(s, want):
                continue
            print('  %s/%s/index.html  需要重排' % (lang, cat))
            fix(page, want, apply)
            total_fixed += 1
    print('\n%d 个类目页%s' % (total_fixed, '已修复' if apply else '需要修复（预演）'))
    return 0


if __name__ == '__main__':
    sys.exit(main())
