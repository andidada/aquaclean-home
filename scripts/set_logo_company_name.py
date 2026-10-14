#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
把页头 / 页脚的品牌标记 AquaClean 换成公司全称
Hong Kong Damaijia Technology Co., Limited（2026-10-14 用户指定）。

只改 **logo 标记里的那一处** text，不动 <title> / og:title / 正文里的
品牌名 —— 用户圈的是导航栏那个 logo。

logo 标记在两种排版下都存在，正则必须吃得住空白：
  页头（换行）:
      <a href="/en/" class="logo">
        <div class="logo-icon">🏠</div>
        <span>AquaClean</span>
      </a>
  页脚（单行）:
      <a href="/en/" class="logo"><div class="logo-icon">🏠</div><span>AquaClean</span></a>

图标本身不动：.logo-icon 的 background-image 已经是 logo-dmj.webp（大卖家 logo）。
"""
from __future__ import annotations
import argparse, glob, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OLD_TEXT = 'AquaClean'
NEW_TEXT = 'Hong Kong Damaijia Technology Co., Limited'

# <a ... class="...logo..."> [可选 一个图标 div] <span>AquaClean</span>
# 图标 div 有两种写法，不能写死 class="logo-icon"：
#   多数页面：<div class="logo-icon">🏠</div> / AC / &nbsp;
#   19 个 zh 页面的页脚：<div style="width:28px;height:28px;...">AC</div>
PAT = re.compile(
    r'(<a\b[^>]*class="[^"]*\blogo\b[^"]*"[^>]*>\s*'
    r'(?:<div\b[^>]*>.*?</div>\s*)?)'
    r'<span>' + re.escape(OLD_TEXT) + r'</span>',
    re.S)

# 兜底盘点：任何 <span>AquaClean</span> 都要能说清它在哪里
ANY_SPAN = re.compile(r'<span>' + re.escape(OLD_TEXT) + r'</span>')


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--root', default=ROOT)
    args = ap.parse_args()

    files = []
    for lang in ('en', 'zh', 'ar', 'es', 'fr', 'id', 'ru', 'th', 'vi', 'assets'):
        files += glob.glob(os.path.join(args.root, lang, '**', '*.html'), recursive=True)
    files = sorted(set(files))

    total_hit = total_span = 0
    untouched = []          # 有 <span>AquaClean</span> 但没被 logo 正则吃到的文件
    writes = []

    for p in files:
        raw = open(p, 'rb').read()
        txt = raw.decode('utf-8')
        n_any = len(ANY_SPAN.findall(txt))
        if not n_any:
            continue
        n_hit = len(PAT.findall(txt))
        total_hit += n_hit
        total_span += n_any
        if n_hit != n_any:
            untouched.append((os.path.relpath(p, args.root), n_any, n_hit))
        new = PAT.sub(lambda m: m.group(1) + '<span>' + NEW_TEXT + '</span>', txt)
        assert ANY_SPAN.search(new) is not None or n_any == n_hit, p
        writes.append((p, raw, new.encode('utf-8')))

    print('扫描 %d 个 html 文件' % len(files))
    print('logo 标记命中 %d 处 / <span>AquaClean</span> 共 %d 处' % (total_hit, total_span))
    if untouched:
        print('\n⚠️ 有 %d 个文件里存在未被 logo 正则吃到的 span：' % len(untouched))
        for rel, n_any, n_hit in untouched[:15]:
            print('   %-52s span=%d 命中=%d' % (rel, n_any, n_hit))
        print('\n→ 这些位置的上下文需要人工看一眼再加规则，先不写入。')
        return 1
    print('✅ 每一处 span 都落在 logo 标记里，可以安全替换')

    if not args.apply:
        print('（dry-run，未写入。加 --apply 执行）')
        return 0

    for p, raw, out in writes:
        assert len(out) > 0
        with open(p, 'wb') as f:
            f.write(out)
    print('✔ 写入 %d 个文件' % len(writes))
    return 0


if __name__ == '__main__':
    sys.exit(main())
