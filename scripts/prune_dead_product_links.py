#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把页面上指向已删除产品详情页的引用全部清掉（表格行 / 列表项 / JSON-LD）。

删掉产品后，引用会残留在三种地方（prune_related_links.py 只管了第一种）：

  1. 相关产品区块的 <li>（详情页）
  2. 对比表的 <tr><td><a>（品类页，只有 ar/es/fr/id/ru/th/vi 有；
     **OEM 落地页的 "Models available for OEM / ODM" 表格也是这个形态**）
  3. ItemList JSON-LD 的 ListItem 条目（各页）

表格行清完后如果 tbody 空了（只剩 thead），给 <table> 加 display:none，
不留一块只有表头的空表。

幂等：找不到死链就不动（Bash 沙箱升级可能重复执行同一条命令）。

用法
    python scripts/prune_dead_product_links.py <cat>:<id> [<cat>:<id> ...] [--apply]
"""
from __future__ import annotations
import io, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANGS = ['en', 'zh', 'ar', 'es', 'fr', 'id', 'ru', 'th', 'vi']

# 只匹配数据行：thead 的行用 <th>，不会被误伤
TR_RE = re.compile(r'[ \t]*<tr><td>.*?</tr>[ \t]*\r?\n?', re.S)
LI_RE = re.compile(r'[ \t]*<li>.*?</li>[ \t]*\r?\n?', re.S)
IL_BLOCK_RE = re.compile(
    r'(<script type="application/ld\+json">\s*\{\s*"@context": "https://schema\.org",\s*'
    r'"@type": "ItemList".*?</script>)', re.S)
LI_OBJ_RE = re.compile(r'\{[^{}]*"@type": "ListItem"[^{}]*\}', re.S)


def read(p):
    return io.open(p, encoding='utf-8', newline='').read()


def prune_itemlist(text, dead):
    """删掉 ItemList 里指向死链的条目，并把 position 重排为 1..N。"""
    def _fix(m):
        block = m.group(1)
        items = LI_OBJ_RE.findall(block)
        if not items:
            return block
        keep = [x for x in items if not any(d in x for d in dead)]
        if len(keep) == len(items):
            return block
        counter = {'i': 0}

        def _num(_m):
            counter['i'] += 1
            return '"position": %d' % counter['i']

        new_items = [re.sub(r'"position": \d+', _num, x) for x in keep]
        newblock = re.sub(r'("itemListElement": \[)(.*?)(\n\s*\])',
                          lambda mm: mm.group(1) + '\n' + ',\n'.join(new_items) + mm.group(3),
                          block, count=1, flags=re.S)
        if '"numberOfItems"' in newblock:
            newblock = re.sub(r'"numberOfItems": \d+',
                              '"numberOfItems": %d' % len(keep), newblock, count=1)
        return newblock

    return IL_BLOCK_RE.sub(_fix, text)


def hide_empty_tables(text):
    """tbody 里没有数据行的表格，加 display:none（每页可能有多个，都要处理）。

    从后往前改，避免前面的插入让后面的偏移失效。
    """
    spans = []
    for m in re.finditer(r'<table\b[^>]*>', text):
        tag = m.group(0)
        if 'display:none' in tag or 'display: none' in tag:
            continue
        end = text.find('</table>', m.end())
        if end < 0:
            continue
        # ⚠️ 判据必须是"整个表里一个 <td> 都没有"。
        #    不能只认 <tr><td>：很多表是 <tr><th scope="row">…</th><td> 的
        #    键值对结构（OEM / 样品量 / 价格 / 认证 / 公司信息），
        #    行首是 <th>，用 <tr><td> 判断会误判为空而被隐藏（实测踩过）。
        if '<td' in text[m.end():end]:
            continue          # 还有数据，不动
        spans.append((m.start(), m.end(), tag))
    out = text
    for a, b, tag in reversed(spans):
        out = out[:a] + tag[:-1] + ' style="display:none">' + out[b:]
    return out


def main():
    argv = [a for a in sys.argv[1:] if a != '--apply']
    apply = '--apply' in sys.argv[1:]
    if not argv:
        sys.exit('用法：python scripts/prune_dead_product_links.py <cat>:<id> ... [--apply]')

    dead = set()
    for item in argv:
        cat, _, pid = item.partition(':')
        assert cat and pid, '参数格式应为 <cat>:<id>'
        dead.add('%s-%s.html' % (cat, pid))

    def is_dead(seg):
        return any(d in seg for d in dead)

    touched = {'tr': 0, 'li': 0, 'jsonld': 0, 'pages': 0, 'tables': 0}
    for lang in LANGS:
        base = os.path.join(ROOT, lang)
        if not os.path.isdir(base):
            continue
        for dirpath, _dirs, files in os.walk(base):
            for fn in sorted(files):
                if not fn.endswith('.html'):
                    continue
                p = os.path.join(dirpath, fn)
                s = read(p)
                if not is_dead(s):
                    continue
                orig = s

                n_tr = [0]
                n_li = [0]

                def sub_tr(m):
                    if is_dead(m.group(0)):
                        n_tr[0] += 1
                        return ''
                    return m.group(0)

                def sub_li(m):
                    if is_dead(m.group(0)):
                        n_li[0] += 1
                        return ''
                    return m.group(0)

                s = TR_RE.sub(sub_tr, s)
                s = LI_RE.sub(sub_li, s)
                s2 = prune_itemlist(s, dead)
                n_json = (len(LI_OBJ_RE.findall(orig)) -
                          len(LI_OBJ_RE.findall(s2))) if '"@type": "ItemList"' in orig else 0
                s = s2
                before_tbl = s
                s = hide_empty_tables(s)
                hid = 1 if s != before_tbl else 0

                if s == orig:
                    continue
                touched['tr'] += n_tr[0]
                touched['li'] += n_li[0]
                touched['jsonld'] += max(0, n_json)
                touched['tables'] += hid
                touched['pages'] += 1
                if apply:
                    io.open(p, 'w', encoding='utf-8', newline='').write(s)

    print('%s 页面 %d 个：表格行 %d，列表项 %d，JSON-LD 条目 %d，隐藏空表 %d%s'
          % ('✓' if apply else '·', touched['pages'], touched['tr'], touched['li'],
             touched['jsonld'], touched['tables'],
             '' if apply else '   [预演，未写入]'))

    # 复检
    left = 0
    for lang in LANGS:
        base = os.path.join(ROOT, lang)
        if not os.path.isdir(base):
            continue
        for dirpath, _dirs, files in os.walk(base):
            for fn in files:
                if fn.endswith('.html') and is_dead(read(os.path.join(dirpath, fn))):
                    left += 1
    print('复检：仍含死链的页面 %d 个（应为 0）' % left)
    return 1 if left else 0


if __name__ == '__main__':
    sys.exit(main())
