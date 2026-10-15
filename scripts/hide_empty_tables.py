#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""给「一个产品都不剩」的品类页里的空对比表加上 display:none。

品类页的对比表是**静态**的（只有 ar/es/fr/id/ru/th/vi 有，en/zh 没有）。
产品全删光后表只剩 <thead>，看起来像一块坏掉的空白。空的网格由页面自带的
运行时 JS 处理（会渲染 .empty-state），但表格没人管，所以要自己藏。

幂等：已经带 display:none 的会跳过（Bash 沙箱升级可能重复执行同一条命令）。

用法
    python scripts/hide_empty_tables.py [--apply]
"""
from __future__ import annotations
import io, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LANGS = ['en', 'zh', 'ar', 'es', 'fr', 'id', 'ru', 'th', 'vi']


def read(p):
    return io.open(p, encoding='utf-8', newline='').read()


def main():
    apply = '--apply' in sys.argv[1:]

    empties = []
    for f in sorted(os.listdir(os.path.join(ROOT, 'data', 'products'))):
        if not f.endswith('.json'):
            continue
        cat = f[:-5]
        try:
            ps = json.loads(read(os.path.join(ROOT, 'data', 'products', f)))['products']
        except Exception:
            continue
        if not ps:
            empties.append(cat)
    print('空品类：%s' % (', '.join(empties) or '(无)'))

    n = 0
    for cat in empties:
        for lang in LANGS:
            p = os.path.join(ROOT, lang, cat, 'index.html')
            if not os.path.isfile(p):
                continue
            s = read(p)
            if '<table' not in s:
                continue
            # 有数据行的不动
            if re.search(r'<tr><td><a href="/%s/%s-' % (lang, cat), s):
                continue
            m = re.search(r'<table\b[^>]*>', s)
            if not m:
                continue
            tag = m.group(0)
            if 'display:none' in tag or 'display: none' in tag:
                continue
            new_tag = tag[:-1] + ' style="display:none">'
            s = s[:m.start()] + new_tag + s[m.end():]
            if apply:
                io.open(p, 'w', encoding='utf-8', newline='').write(s)
            n += 1
            print('  %s %s/%s  空表格已隐藏' % ('✓' if apply else '·', lang, cat))

    print('%s 共处理 %d 个页面%s' % ('✓' if apply else '·', n,
                                     '' if apply else '   [预演，未写入]'))


if __name__ == '__main__':
    main()
