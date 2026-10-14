#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""img_fingerprint.py — 感知哈希（16×16 aHash，256 bit）比对图片是否为同一张。

用途：判断某个产品目录下的现有图，和两个阿里 listing 的主图究竟哪个同源。
用法：
  python scripts/img_fingerprint.py URL_OR_LOCAL [更多...]      # 只算指纹
  python scripts/img_fingerprint.py --cmp A B C ...             # 两两比对
判定：汉明距离 <= 12 / 256 视为同一张图。

⚠️ 必须用带 Pillow 的 venv：
   C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe
"""
import io
import sys
import os
import urllib.request

try:
    from PIL import Image
except ImportError:
    sys.exit('✗ 缺 Pillow，请用 venv python：'
             'C:/Users/Administrator/.workbuddy/binaries/python/envs/default/Scripts/python.exe')

PROXY = os.environ.get('https_proxy') or os.environ.get('HTTPS_PROXY')


def load(src):
    if src.startswith('http'):
        req = urllib.request.Request(src, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                          '(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36',
            'Referer': 'https://www.alibaba.com/',
        })
        if PROXY:
            req.set_proxy(PROXY.split('//')[-1], 'https')
        raw = urllib.request.urlopen(req, timeout=40).read()
        im = Image.open(io.BytesIO(raw))
    else:
        im = Image.open(src)
    im = im.convert('L').resize((16, 16), Image.LANCZOS)
    return im


def ahash(src):
    im = load(src)
    px = list(im.getdata())
    avg = sum(px) / 256.0
    bits = [1 if p > avg else 0 for p in px]
    return bits


def ham(a, b):
    return sum(1 for x, y in zip(a, b) if x != y)


def main():
    args = sys.argv[1:]
    mode = '--cmp'
    if args and args[0] == '--cmp':
        args = args[1:]
    items = args
    prints = {}
    for s in items:
        try:
            prints[s] = ahash(s)
        except Exception as e:
            print('✗ %s : %s' % (s, e), file=sys.stderr)

    keys = [k for k in items if k in prints]
    print('%-62s  %s' % ('文件/URL', '最小差异 vs 组内其它'))
    for k in keys:
        ds = [ham(prints[k], prints[o]) for o in keys if o != k]
        print('%-62s  %s' % (k[-62:], min(ds) if ds else '-'))

    print()
    print('两两距离矩阵（<=12 视为同一张图）')
    print('%-30s' % '', end='')
    for j, b in enumerate(keys):
        print('%6d' % j, end='')
    print()
    for i, a in enumerate(keys):
        print('%-6d %-24s' % (i, os.path.basename(a)[-24:]), end='')
        for b in keys:
            print('%6d' % ham(prints[a], prints[b]), end='')
        print()


if __name__ == '__main__':
    main()
