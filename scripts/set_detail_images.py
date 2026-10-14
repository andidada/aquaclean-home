#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
set_detail_images.py — 给产品数据补上 detail_images 字段

为什么必须有这一步
------------------
assets/js/product-detail.js 的 render() 会**整体重写** #aqc-detail-mount：

    var mount = $('#aqc-detail-mount');
    ...
    var detailImgs = Array.isArray(product.detail_images) ? ... : [];

详情长图的唯一数据来源是 product.detail_images。而 data/products/*.json 里
**39 个产品一个都没有这个字段** —— 所以只要 JS 正常执行，页面上就一张长图都
不显示；静态 HTML 里那段 <section id="detail-images"> 会被运行时渲染整个抹掉，
只有爬虫和禁用 JS 的访客看得到。

也就是说：光换磁盘上的图片文件、光改静态 HTML 都不够，必须把清单写进数据。

为什么是"外科式插入"而不是整文件重新序列化
------------------------------------------
同 fix_product_highlights.py：这些 JSON 是 1 空格递进的缩进、CRLF 行尾，
整文件 json.dumps 会重排大部分行，diff 没法审。这里复用 fix_product_highlights.py
里的位置感知扫描器，只在目标产品对象的末尾插入一个键。

用法
----
    python scripts/set_detail_images.py             # 预演
    python scripts/set_detail_images.py --apply     # 写入
"""
from __future__ import annotations
import io, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fix_product_highlights import (  # noqa: E402  位置感知 JSON 扫描器
    find_product_span, object_members,
)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V3 = os.path.join(ROOT, 'scraped', 'alibaba_v3')
SITE = 'https://www.hkdmj.net'

# 与 scripts/apply_alibaba_images.py 的 MAP 保持一致
MAP = [
    ('1601719491601', 'handheld-vacuum', 'gv22'),
    ('1601812941902', 'handheld-vacuum', 'v26'),
    ('1601887535950', 'handheld-vacuum', 'gv18'),
    ('1601673204576', 'robot-vacuum',    'v2g-sj'),
    # 2026-10-14 纠偏：这条 Model 是 GT20-C800（220ml/230ml/40W），归属 gt20，
    # 原先误贴给 t20-c800。详见 apply_alibaba_images.py 里的注释。
    ('1601781055404', 'robot-vacuum',    'gt20'),
    ('1601957733461', 'robot-vacuum',    'v9'),
    ('1601716189230', 'car-vacuum',      'yzx-309'),
    ('1601820268825', 'handheld-vacuum', 'eg16pro'),   # EG16Pro 洗地机（站内新建产品）
    # ── 第二批（2026-10-14）：这三个产品原先detail_images 是空的 ──────────
    ('1601909117845', 'tire-inflator',   'ymc6667'),    # Model YMC6667
    ('1601905921428', 'steam-cleaner',   'ytc-sc-004'), # Model YTC-SC-004
    ('1601784081376', 'robot-vacuum',    'pt40c800'),   # Model ZT40-C800
    # ── 第三批（2026-10-14）：一律按阿里属性表的 Model 号映射 ──────────────
    ('1601887224510', 'robot-vacuum',    't20-c800'),   # Model T20-C800
    ('1601799709236', 'handheld-vacuum', 'v22-2'),      # Model V22 / 40000Pa / 650W
    ('1601898271900', 'steam-cleaner',   'ptc-sc-004'), # Model PTC-SC-004
    # 1601780738060 (PG16PRO) 不上架：用户确认 = EG16Pro，仅主图不同。
    # 与 apply_alibaba_images.py 保持一致，别再加回来。
]

# 与 apply_alibaba_images.py 的 EXCLUDE 保持一致：
# EG16Pro 的第 9 张详情长图是"Founded in 2016 / 10+ years"的公司自述页，
# 与站内"宁波工厂 2015 年投产、香港公司 2024 年注册"直接冲突，不上站。
# 排除之后图片序号会从 13 变成 12 —— 上游脚本会把剩下的图按 01..N 重排，
# 所以这里的 urls 只需要按同样的排除规则跳过，再重新连续编号。
EXCLUDE = {
    '1601820268825': {9},
}


def dominant_eol(t):
    return '\r\n' if t.count('\r\n') * 2 >= t.count('\n') else '\n'


def member_indent(t, obj_start):
    """取产品对象里第一个成员的缩进量（文件里是 3 空格）。"""
    for key, vs, _ve in object_members(t, obj_start):
        line_start = t.rfind('\n', 0, vs) + 1
        n = 0
        while line_start + n < len(t) and t[line_start + n] == ' ':
            n += 1
        return n
    return 3


def render_array(items, indent, eol):
    pad = ' ' * indent
    inner = ' ' * (indent + 1)
    body = (',' + eol).join(inner + json.dumps(u, ensure_ascii=False) for u in items)
    return '[' + eol + body + eol + pad + ']'


def set_field(t, product_id, key, value_text):
    """在产品对象里设置 key：已存在则替换其值，不存在则作为最后一个成员插入。

    返回 (新文本, 字段原本是否存在)。第二返回值用来区分两种合法情况：
    字段本来就有且值相同 → 长度不变（幂等重跑）；字段原本没有 → 必须变长。
    """
    ps, pe = find_product_span(t, product_id)
    for k, vs, ve in object_members(t, ps):
        if k == key:
            return t[:vs] + value_text + t[ve:], True
    # 插到最后一个成员之后、对象收尾的大括号之前
    j = pe - 1
    while t[j] in ' \t\r\n':
        j -= 1
    assert t[j] == '}', '产品对象结尾不是 } —— 扫描器定位错了'
    eol = dominant_eol(t)
    ind = member_indent(t, ps)
    pad = ' ' * ind
    # 收尾大括号的缩进比成员少一格（文件里成员 3 空格、对象收尾 2 空格）
    close_pad = ' ' * max(0, ind - 1)
    insertion = (',' + eol + pad + json.dumps(key) + ': ' + value_text +
                 eol + close_pad)
    return t[:j] + insertion + t[j:], False


def main():
    apply = '--apply' in sys.argv

    # 按文件分组：同一个 data/products/*.json 要读一次、把所有属于它的产品
    # 依次应用、最后只写一次。早期版本在循环里每次都重读磁盘，导致同一文件里
    # 只有最后一个产品的 new_t 活下来（前面几轮的结果被后一次读取覆盖），
    # 表现出来就是"脚本报告写了 7 个，实际每个文件只有最后 1 个生效"。
    groups = {}
    for pid, cat, sid in MAP:
        groups.setdefault(cat, []).append((pid, sid))

    total = 0
    for cat, items in groups.items():
        path = os.path.join(ROOT, 'data', 'products', cat + '.json')
        t = io.open(path, encoding='utf-8', newline='').read()
        eol = dominant_eol(t)
        before_tree = json.loads(t)

        for pid, sid in items:
            src = os.path.join(V3, pid + '.json')
            rec = json.load(io.open(src, encoding='utf-8'))
            # 排除规则必须与 apply_alibaba_images.py 的 detail_urls() 完全一致，
            # 不然磁盘上的图数会和 data 里的条数对不上（页面上不报错，只是末图不显示）
            skip = EXCLUDE.get(pid, set())
            n = sum(1 for i in range(1, len(rec['detail']) + 1) if i not in skip)
            d = '%s-%s' % (cat, sid)
            urls = ['%s/assets/images/products/%s/detail/%02d.webp' % (SITE, d, i)
                    for i in range(1, n + 1)]

            ps, pe = find_product_span(t, sid)
            ind = member_indent(t, ps)
            new_t, existed = set_field(
                t, sid, 'detail_images', render_array(urls, ind, eol))

            # 先算出结果、断言长度，再谈写盘（绝不 io.open(p,'w').write(...) 一把梭）
            # 字段原本就有且值相同 → 长度可以不变（幂等重跑）；
            # 字段原本没有 → 必须变长，否则说明插入没发生。
            assert len(new_t) >= len(t), '%s/%s 写入后变短了' % (cat, sid)
            if not existed:
                assert len(new_t) > len(t), '%s/%s 插入后没有变长' % (cat, sid)
            obj = json.loads(new_t)
            prod = [p for p in obj['products'] if p['id'] == sid][0]
            assert prod.get('detail_images') == urls, '%s/%s 写回后校验不符' % (cat, sid)
            # 除了新增字段，其它内容必须一字不动
            for p in before_tree['products']:
                p.pop('detail_images', None)
            for p in obj['products']:
                p.pop('detail_images', None)
            assert before_tree == obj, '%s/%s 除 detail_images 外还有别的变化' % (cat, sid)

            t = new_t   # 关键：把结果带进下一个产品
            total += 1
            print('  %-14s/%-9s detail_images %d 条（缩进 %d，行尾 %s）'
                  % (cat, sid, n, ind, 'CRLF' if eol == '\r\n' else 'LF'))

        if apply:
            with io.open(path, 'w', encoding='utf-8', newline='') as f:
                f.write(t)

    if not apply:
        print('\n预演模式，未写入。加 --apply 真正写入。')
        return 0
    print('\n已写入 %d 个产品（%d 个文件）。' % (total, len(groups)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
