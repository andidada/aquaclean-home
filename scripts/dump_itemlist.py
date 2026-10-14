#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dump_itemlist.py — 打印某个类目页里 ItemList JSON-LD 的 position/url 顺序。

用来排查 "ItemList 的 position 不连续" 这类断言失败：先看清楚现状到底是
哪里错位，再决定怎么修，别对着报错瞎改。
用法：python scripts/dump_itemlist.py en/handheld-vacuum/index.html
"""
import io, json, re, sys

path = sys.argv[1]
t = io.open(path, encoding='utf-8', newline='').read()

for i, m in enumerate(re.finditer(r'"@type"\s*:\s*"ItemList"', t)):
    start = t.rfind('{', 0, m.start())
    depth = 0
    j = start
    while j < len(t):
        if t[j] in '{[':
            depth += 1
        elif t[j] in '}]':
            depth -= 1
            if depth == 0:
                break
        j += 1
    try:
        obj = json.loads(t[start:j + 1])
    except Exception as e:
        print('第 %d 个 ItemList 解析失败：%s' % (i + 1, e))
        continue
    print('=== ItemList #%d  (%s 项) ===' % (i + 1, obj.get('numberOfItems')))
    for it in obj.get('itemListElement', []):
        print('   position=%-4s %s' % (it.get('position'),
                                       (it.get('url') or '').rsplit('/', 1)[-1]))
