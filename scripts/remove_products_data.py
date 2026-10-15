#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只把一批产品从 data/products/*.json 里摘掉（不动任何 HTML）。

HTML 交给 gen_pages.py 重建 —— 它会按剩下的数据重排卡片网格、
productCount、ItemList、对比表和相关产品链接（实测字节级幂等）。

为什么不再用 remove_product.py 整条链路
--------------------------------------
remove_product.py 的类目页摘除是"外科手术式"的，但它的匹配串写死了
en/zh 口径：
  * "N models in this category" / "共 N 个型号" —— 只有 en/zh 有
  * 对比表 <tr> —— 只有 ar/es/fr/id/ru/th/vi 有，en/zh 根本没有
  * 卡片定位 marker 还重复套了一层 class=，永远匹配不到
逐个语种打补丁不如直接交给已验证幂等的生成器重建。

摘除数组元素时注意"第一个元素"：它前面是 '[' 没有逗号可吃，必须改吃
它**后面**的逗号，否则留下 "[\n , {...}]" 这种非法 JSON。

用法： python scripts/remove_products_data.py <cat>:<id> [<cat>:<id> ...] [--apply]
"""
from __future__ import annotations
import io, json, os, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from remove_product import strip_product_from_data, read

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def strip_chain(dpath, pids, apply):
    """按顺序摘掉多个产品。apply=False 时在临时文件上演练，绝不碰真实文件。"""
    text = read(dpath)
    ids0 = [p['id'] for p in json.loads(text)['products']]

    if not apply:
        tmp = os.path.join(tempfile.gettempdir(), 'aqc_rm_' + os.path.basename(dpath))
        io.open(tmp, 'w', encoding='utf-8', newline='').write(text)
        work = tmp
    else:
        work = dpath

    for pid in pids:
        cur = [p['id'] for p in json.loads(text)['products']]
        if pid not in cur:
            # 幂等：已经摘掉了就跳过（Bash 工具在沙箱升级时会重复执行同一条命令，
            # 第二遍再跑时产品已经不在了，不能报错）
            print('    · %s 已不存在，跳过' % pid)
            continue
        text = strip_product_from_data(work, pid)      # 读文件、返回新文本
        io.open(work, 'w', encoding='utf-8', newline='').write(text)

    ids1 = [p['id'] for p in json.loads(text)['products']]
    want = [i for i in ids0 if i not in pids]
    assert ids1 == want, '删除后清单不对：\n  期望=%s\n  实际=%s' % (want, ids1)
    return text, ids0, ids1


def main():
    argv = [a for a in sys.argv[1:] if a != '--apply']
    apply = '--apply' in sys.argv[1:]
    if not argv:
        sys.exit('用法：python scripts/remove_products_data.py <cat>:<id> ... [--apply]')

    plan = {}
    for item in argv:
        cat, _, pid = item.partition(':')
        assert cat and pid, '参数格式应为 <cat>:<id>，收到 %r' % item
        plan.setdefault(cat, []).append(pid)

    for cat, pids in plan.items():
        dpath = os.path.join(ROOT, 'data', 'products', cat + '.json')
        assert os.path.isfile(dpath), '没有 %s' % dpath
        text, ids0, ids1 = strip_chain(dpath, pids, apply)
        tag = '✓' if apply else '·'
        tail = '' if apply else '   [预演，未写入]'
        print('%s %-20s %d → %d  剩余 %s%s'
              % (tag, cat, len(ids0), len(ids1), ','.join(ids1) or '(空)', tail))
        if apply:
            io.open(dpath, 'w', encoding='utf-8', newline='').write(text)


if __name__ == '__main__':
    main()
