#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Run every back-office regression suite in one pass.

Each suite is a standalone jsdom script under scripts/ that boots the *real*
admin/front-end code and asserts one link of the chain:

    verify_product_merge.js        产品表单 27 个字段的落库映射（纯函数）
    verify_admin_publish_button.js 发布按钮 / 草稿≠发布 / Token 来源
    verify_admin_roundtrip.js      上传图文 → 改内容 → 发布 → 前台真实渲染
    verify_category_pages.js       类目页运行时渲染 + 失败时不抹掉静态卡片
    verify_inquiry_relay.js        询盘中继：跨域写入、防 spam、字段裁剪

Usage:
    python scripts/verify_admin_all.py
    python scripts/verify_admin_all.py --node "C:/path/to/node.exe"

Why Python and not a node aggregator: spawning the node binary from inside a
node process fails with EBUSY in this environment (same for git), so the
driver shells out from Python where subprocess works.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)

SUITES = [
    ('verify_product_merge.js',        '产品字段落库映射'),
    ('verify_admin_publish_button.js', '发布按钮 / Token 来源'),
    ('verify_admin_roundtrip.js',      '上传图文 → 发布 → 前台渲染'),
    ('verify_category_pages.js',       '类目页渲染与失败回退'),
    ('verify_inquiry_relay.js',        '询盘中继：跨域写入 / 防 spam / 字段裁剪'),
]

# 这些套件会故意触发 console.error（模拟加载失败），过滤掉免得看起来像报错
NOISE = re.compile(r'^(Failed to load products|ReferenceError: fetch is not defined|\s+at )')


def find_node(explicit: str | None) -> str:
    if explicit:
        return explicit
    env = os.environ.get('WORKBUDDY_NODE')
    if env and os.path.exists(env):
        return env
    for base in (r'C:\Users\Administrator\.workbuddy\binaries\node\versions',):
        if not os.path.isdir(base):
            continue
        for d in sorted(os.listdir(base), reverse=True):
            cand = os.path.join(base, d, 'node.exe')
            if os.path.exists(cand):
                return cand
    return 'node'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--node', help='node 可执行文件路径')
    args = ap.parse_args()
    node = find_node(args.node)
    if not os.path.exists(node) and node != 'node':
        print('找不到 node：', node)
        return 2

    total_pass = total_fail = 0
    broken = []
    for script, desc in SUITES:
        path = os.path.join(HERE, script)
        print('\n── %s（%s）' % (script, desc))
        try:
            proc = subprocess.run([node, path], cwd=ROOT, capture_output=True,
                                  text=True, encoding='utf-8', errors='replace')
            out = proc.stdout or ''
        except Exception as exc:                       # noqa: BLE001
            print('   无法运行：%s' % exc)
            broken.append(script)
            continue

        for line in out.splitlines():
            if NOISE.match(line):
                continue
            print(line)
        m = re.search(r'(\d+) passed, (\d+) failed', out)
        if m:
            total_pass += int(m.group(1))
            total_fail += int(m.group(2))
        if proc.returncode != 0:
            broken.append(script)

    print('\n' + '=' * 46)
    if not broken and total_fail == 0:
        print('✅ 全部通过：%d 项断言（%d 个套件）' % (total_pass, len(SUITES)))
        return 0
    print('❌ 失败套件：%s；断言 %d passed / %d failed'
          % (', '.join(broken) or '-', total_pass, total_fail))
    return 1


if __name__ == '__main__':
    sys.exit(main())
