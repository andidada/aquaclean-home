#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EG16Pro 续航：25–35 min → 30–60 min（用户 2026-10-14 确认值）

为什么不能简单全文替换 "25–35" → "30–60"：
  分类页和 ar 详情页里同时存在**交期** "25–35 days / 25–35 天 /
  25–35 يومًا …"，盲替换会把交期也改成 30–60，属于数据污染。
  所以这里只替换**后面跟着续航单位**的那一些。

为什么不做 json.dumps 重写：
  data/products/handheld-vacuum.json 的缩进/换行不统一，整文件重排
  会让 70%+ 的行出现在 diff 里，无法审阅。这里是纯字节级替换。

为什么连 9 个语种的 HTML 也一起改：
  站点是**预渲染**的，详情页与分类页的 tagline / 药丸 / 规格表 /
  描述 / JSON-LD 都写死在 HTML 里，只改 data 不会体现在页面上。
"""
from __future__ import annotations
import argparse, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

OLD, NEW = '25–35', '30–60'

# 只认"续航单位"。交期单位（days / 天 / días / jours / hari / дней /
# วัน / ngày / يومًا）刻意不在此列 —— 命中不了就是对的。
UNITS = r'min\b|minutes\b|minutos\b|минут\b|мин\b|分钟|دقيقة|menit\b|นาที|phút\b'
PAT = re.compile(re.escape(OLD) + r'(?=[ \t]*(?:' + UNITS + r'))')

LANGS = ['en', 'zh', 'es', 'ar', 'fr', 'id', 'ru', 'th', 'vi']

TARGETS = [('data/products/handheld-vacuum.json', 45)]
for L in LANGS:
    TARGETS.append(('%s/handheld-vacuum-eg16pro.html' % L, 9))
for L in LANGS:
    TARGETS.append(('%s/handheld-vacuum/index.html' % L, 2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='真正写入（默认只报告）')
    ap.add_argument('--extra', nargs='*', default=[], help='额外要改的文件（不校验条数）')
    args = ap.parse_args()

    ok = True
    plan = []
    for rel, want in TARGETS:
        p = os.path.join(ROOT, rel)
        raw = open(p, 'rb').read()
        txt = raw.decode('utf-8')
        n = len(PAT.findall(txt))
        total_old = txt.count(OLD)
        flag = 'OK ' if n == want else 'BAD'
        if n != want:
            ok = False
        plan.append((rel, n, want, total_old, PAT.sub(NEW, txt).encode('utf-8')))
        print('%s %-46s 续航命中 %2d / 期望 %2d   （文件内 25–35 共 %2d）'
              % (flag, rel, n, want, total_old))

    for rel in args.extra:
        p = os.path.join(ROOT, rel)
        txt = open(p, 'rb').read().decode('utf-8')
        n = len(PAT.findall(txt))
        print('EXTRA %-45s 续航命中 %2d   （文件内 25–35 共 %2d）' % (rel, n, txt.count(OLD)))
        plan.append((rel, n, n, txt.count(OLD), PAT.sub(NEW, txt).encode('utf-8')))

    if not ok:
        print('\n❌ 命中数与期望不符，未写入任何文件。')
        return 1
    if not args.apply:
        print('\n（dry-run，未写入。加 --apply 执行）')
        return 0

    # 先全部算完再开写：Python 先求值 open 会先清空文件，
    # 中途抛异常就会留下 0 字节文件。
    for rel, n, want, _t, out in plan:
        p = os.path.join(ROOT, rel)
        before = os.path.getsize(p)
        assert len(out) > 0, rel
        # 长度只会因 25–35→30–60 保持不变（同长度），故断言相等
        assert len(out) == before, '%s 字节数变了（%d→%d）' % (rel, before, len(out))
        with open(p, 'wb') as f:
            f.write(out)
        print('✔ 写入 %s' % rel)
    return 0


if __name__ == '__main__':
    sys.exit(main())
