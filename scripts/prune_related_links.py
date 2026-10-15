#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""清掉详情页「More products in this category」里指向已删除产品的 <li>。

为什么需要单独一个脚本
----------------------
相关产品区块是**预渲染**进 HTML 的：
    <section class="section" id="related"> … <ul><li><a href="/en/xxx.html">…</a></li> …
删掉产品后，存活页面的这个区块会指向 404。gen_pages.py 只会**重新贴标签**
（把链接文字换成对应语种），不会删条目，所以死链要自己清。

边界情况
--------
某个品类只剩 1 个产品时，相关产品全部是死链 —— 清完 <ul> 为空，
这时把整个 <section id="related"> 移除，而不是留一个空标题。

用法
    python scripts/prune_related_links.py <cat>:<id> [<cat>:<id> ...] [--apply]
"""
from __future__ import annotations
import io, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALL_LANGS = ['en', 'zh', 'ar', 'es', 'fr', 'id', 'ru', 'th', 'vi']

SEC_RE = re.compile(r'[ \t]*<section[^>]*\bid="related"[^>]*>.*?</section>[ \t]*\r?\n?', re.S)
LI_RE = re.compile(r'<li>.*?</li>', re.S)


def read(p):
    return io.open(p, encoding='utf-8', newline='').read()


def prune(text, dead):
    """返回 (新文本, 删除条目数, 是否整块移除)。"""
    m = SEC_RE.search(text)
    if not m:
        return text, 0, False
    block = m.group(0)
    items = LI_RE.findall(block)
    if not items:
        return text, 0, False
    keep = [li for li in items if not any(d in li for d in dead)]
    if len(keep) == len(items):
        return text, 0, False
    if not keep:
        return text[:m.start()] + text[m.end():], len(items), True
    new = block
    for li in items:
        if li not in keep:
            new = new.replace(li, '', 1)
    return text[:m.start()] + new + text[m.end():], len(items) - len(keep), False


def main():
    argv = [a for a in sys.argv[1:] if a != '--apply']
    apply = '--apply' in sys.argv[1:]
    if not argv:
        sys.exit('用法：python scripts/prune_related_links.py <cat>:<id> ... [--apply]')

    dead = set()
    for item in argv:
        cat, _, pid = item.partition(':')
        assert cat and pid, '参数格式应为 <cat>:<id>，收到 %r' % item
        dead.add('%s-%s.html' % (cat, pid))

    touched = removed_items = removed_secs = 0
    for lang in ALL_LANGS:
        base = os.path.join(ROOT, lang)
        if not os.path.isdir(base):
            continue
        for fn in sorted(os.listdir(base)):
            if not fn.endswith('.html'):
                continue
            p = os.path.join(base, fn)
            text = read(p)
            new, n, whole = prune(text, dead)
            if not n:
                continue
            touched += 1
            removed_items += n
            removed_secs += 1 if whole else 0
            if apply:
                io.open(p, 'w', encoding='utf-8', newline='').write(new)

    print('%s 清理页面 %d 个，删除条目 %d 条，整块移除 section %d 处%s'
          % ('✓' if apply else '·', touched, removed_items, removed_secs,
             '' if apply else '   [预演，未写入]'))

    # 复检
    left = 0
    for lang in ALL_LANGS:
        base = os.path.join(ROOT, lang)
        if not os.path.isdir(base):
            continue
        for fn in os.listdir(base):
            if not fn.endswith('.html'):
                continue
            if any(d in read(os.path.join(base, fn)) for d in dead):
                left += 1
    print('复检：仍含死链的页面 %d 个（应为 0）' % left)
    return 1 if left else 0


if __name__ == '__main__':
    sys.exit(main())
