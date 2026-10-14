#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""dump_grid.py — 按文档顺序列出类目页 #productsGrid 里的静态产品卡片 href。

静态卡片只有爬虫和禁用 JS 的访客看得到，但它和 ItemList JSON-LD 必须同序 ——
两边顺序不一致时，add_to_category.py 的 position 连续性断言就会炸。
用法：python scripts/dump_grid.py en/handheld-vacuum/index.html
"""
import io, re, sys

path = sys.argv[1]
t = io.open(path, encoding='utf-8', newline='').read()

k = t.find('id="productsGrid"')
if k < 0:
    sys.exit('找不到 #productsGrid')
# 取到 grid 容器的收尾 div 为止（用下一个 <section 或 </main 兜底）
end = t.find('</div>\n', k)
nxt = min([x for x in (t.find('<section', k), t.find('</main', k), t.find('</body', k))
           if x > 0] or [len(t)])
blk = t[k:nxt]

for i, m in enumerate(re.finditer(r'href="(/[a-z]{2}/[a-z0-9\-]+-[a-z0-9\-]+\.html)"', blk), 1):
    print('%3d  %s' % (i, m.group(1).rsplit('/', 1)[-1]))
