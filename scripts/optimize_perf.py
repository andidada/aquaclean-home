#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
optimize_perf.py — 首屏加载性能批量改造

起因：用户反馈"网站加载的速度很慢"。实测定位到的问题，按影响排序：

1) 462 个页面都有
     <link href="https://fonts.googleapis.com/css2?family=Inter...">
   这是**阻塞渲染**的外部样式表。该域名在部分网络不可达时会挂起约 2s，
   浏览器必须等它加载或失败才能绘制。→ 改为自托管（@font-face 并入 style.css）。

2) 大量 <script src> 没有 defer，在文档末尾同步阻塞解析。→ 全部加 defer。

3) 英文站首屏 hero 是 CSS background-image，只能等 CSS 下载完才被发现，
   形成 HTML→CSS→图 的串行链。→ 加 rel=preload（见 patch_en_home.py）。

4) 轮播 7 张 banner（412KB）在 idle 时一次性全部 hydrate。
   → 首屏只加载第 1 帧，第 2 帧等 load 事件，其余按需。

5) home-loader 等 DOMContentLoaded 才发 JSON 请求，又多一个串行往返。
   → 立刻发请求，DOM 就绪后再渲染。

6) CJK/阿拉伯/泰文没有显式兜底字体。→ 补全 font-family 回退链。

安全习惯（踩过坑）：先把新内容算成 out 字符串，断言长度合理后再开写，
绝不做 io.open(p,'w').write(s.replace(...)) —— 那样一旦 replace 抛异常
文件就变成 0 字节。
"""
import io
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP_DIRS = {'admin', 'netlify', '.git', 'scripts', 'shots', 'node_modules'}

# ---------------------------------------------------------------- 字体外链
RE_PRECONNECT_GAPI = re.compile(
    r'[ \t]*<link rel="preconnect" href="https://fonts\.googleapis\.com">\r?\n?')
RE_PRECONNECT_GSTATIC = re.compile(
    r'[ \t]*<link rel="preconnect" href="https://fonts\.gstatic\.com" crossorigin>\r?\n?')
RE_INTER_CSS = re.compile(
    r'[ \t]*<link href="https://fonts\.googleapis\.com/css2\?family=Inter[^>]*>\r?\n?')
# Noto Sans Arabic / Thai：体积太大不适合自托管，改为非阻塞加载
RE_NOTO_CSS = re.compile(
    r'[ \t]*<link href="(https://fonts\.googleapis\.com/css2\?family=Noto\+Sans[^"]*)"[^>]*>\r?\n?')

NOTO_ASYNC_TPL = (
    '  <!-- 非阻塞加载：media="print" 的样式表不阻塞渲染，onload 后切回 all。\n'
    '       这样该域名不可达时首屏照常绘制，可达时仍能拿到正确字体。 -->\n'
    '  <link rel="stylesheet" href="%s" media="print" onload="this.media=\'all\'">\n')

# ---------------------------------------------------------------- 脚本 defer
RE_SCRIPT_SRC = re.compile(r'<script\s+src="([^"]+)"([^>]*)>', re.I)
RE_HAS_DEFER = re.compile(r'<script[^>]*\bdefer\b', re.I)


def add_defer(html):
    """给没有 defer/async/type 的 <script src=...> 加 defer。"""
    def repl(m):
        attrs = m.group(2)
        low = attrs.lower()
        if re.search(r'\bdefer\b', low) or re.search(r'\basync\b', low) or 'type=' in low:
            return m.group(0)
        return '<script src="%s"%s defer>' % (m.group(1), attrs.rstrip())
    return RE_SCRIPT_SRC.sub(repl, html)


def iter_html():
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            if fn.endswith('.html'):
                yield os.path.join(dirpath, fn)


def main():
    font_removed = 0
    noto_async = 0
    defer_before = 0
    defer_after = 0
    css_bumped = 0
    loader_bumped = 0
    changed = []
    suspicious = []

    for path in iter_html():
        with io.open(path, 'r', encoding='utf-8') as f:
            src = f.read()
        if len(src) == 0:
            continue
        out = src

        # 1) 移除 Google Fonts 阻塞外链
        out = RE_PRECONNECT_GAPI.sub('', out)
        out = RE_PRECONNECT_GSTATIC.sub('', out)
        out, n_inter = RE_INTER_CSS.subn('', out)
        if n_inter:
            font_removed += 1

        out, n_noto = RE_NOTO_CSS.subn(lambda m: NOTO_ASYNC_TPL % m.group(1), out)
        noto_async += n_noto

        # 2) 脚本加 defer
        defer_before += len(RE_HAS_DEFER.findall(out))
        out = add_defer(out)
        defer_after += len(RE_HAS_DEFER.findall(out))

        # 3) 只给内容确实变了的资产 bump 版本号（CSS 加了 @font-face，
        #    home-loader 改了请求时机），其余保持原版本号以免白白失效缓存。
        if 'style.css?v=20261005' in out:
            out = out.replace('style.css?v=20261005', 'style.css?v=20261009')
            css_bumped += 1
        if 'home-loader.js?v=20261005' in out:
            out = out.replace('home-loader.js?v=20261005', 'home-loader.js?v=20261009')
            loader_bumped += 1

        if out == src:
            continue

        # 安全断言：不允许体积暴涨或暴跌
        if len(out) < len(src) * 0.9 or len(out) > len(src) * 1.03:
            suspicious.append((path, len(src), len(out)))
            continue
        with io.open(path, 'w', encoding='utf-8', newline='') as f:
            f.write(out)
        changed.append(path)

    print('HTML 改造完成：')
    print('  移除 Google Fonts 外链 : %d 页' % font_removed)
    print('  Noto 改为非阻塞        : %d 处' % noto_async)
    print('  defer 脚本             : %d -> %d 处' % (defer_before, defer_after))
    print('  style.css 版本 bump    : %d 页' % css_bumped)
    print('  home-loader 版本 bump  : %d 页' % loader_bumped)
    print('  实际改动文件           : %d 个' % len(changed))
    if suspicious:
        print('  !! 体积异常未写入:')
        for p, a, b in suspicious:
            print('     %s  %d -> %d' % (p, a, b))
    return changed


if __name__ == '__main__':
    main()
