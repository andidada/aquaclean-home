#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
read_xlsx_stdlib.py — 只用标准库读 .xlsx（不依赖 openpyxl）

为什么要自己解析：这台机器的 pip 源装不上 openpyxl
（ERROR: No matching distribution found）。xlsx 本身就是
zip + XML，用 zipfile + re 就能拿到单元格，够用了。

支持：共享字符串（t="s"）、内联字符串（t="inlineStr"）、数字（默认）。
不支持：公式缓存值之外的计算（这里也用不到）。

用法：
  python scripts/read_xlsx_stdlib.py <xlsx路径> [工作表名]
输出：CSV 到 stdout
"""
import zipfile
import re
import sys
import csv
import io


def col_to_idx(ref):
    """A1 -> (row, col)；ZE12 -> (12, 631)"""
    m = re.match(r'([A-Z]+)(\d+)', ref)
    if not m:
        return None, None
    col_s, row_s = m.group(1), m.group(2)
    col = 0
    for ch in col_s:
        col = col * 26 + (ord(ch) - 64)
    return int(row_s), col - 1


def load(path):
    z = zipfile.ZipFile(path)

    # 1) 共享字符串
    shared = []
    if 'xl/sharedStrings.xml' in z.namelist():
        xml = z.read('xl/sharedStrings.xml').decode('utf-8', 'replace')
        # 每个 <si> 里可能有多个 <t>（富文本），拼起来
        for si in re.findall(r'<si>(.*?)</si>', xml, re.S):
            parts = re.findall(r'<t[^>]*>(.*?)</t>', si, re.S)
            shared.append(''.join(parts))

    # 2) 工作表名
    wb = z.read('xl/workbook.xml').decode('utf-8', 'replace')
    names = re.findall(r'<sheet[^>]*name="([^"]*)"', wb)

    # 3) sheet 文件（按顺序对应 workbook.xml 里的 sheet）
    rels = z.read('xl/_rels/workbook.xml.rels').decode('utf-8', 'replace')
    targets = re.findall(r'Target="([^"]*sheet\d+\.xml)"', rels)
    # rels 里的 Target 是相对 xl/ 的路径，zip 内要拼回 'xl/' 前缀
    targets = [t if t.startswith('xl/') else 'xl/' + t.lstrip('/') for t in targets]
    # 兜底：直接按名字排序
    if not targets:
        targets = sorted(n for n in z.namelist()
                         if re.match(r'xl/worksheets/sheet\d+\.xml$', n))

    return z, shared, names, targets


def read_sheet(z, shared, sheet_file):
    xml = z.read(sheet_file).decode('utf-8', 'replace')
    grid = {}
    max_c = 0
    for cm in re.finditer(r'<c\b([^>]*)>(.*?)</c>|<c\b([^>]*)/>', xml, re.S):
        attrs = cm.group(1) or cm.group(3) or ''
        inner = cm.group(2) or ''
        ref = re.search(r'r="([A-Z]+\d+)"', attrs)
        if not ref:
            continue
        r, c = col_to_idx(ref.group(1))
        if r is None:
            continue
        t = re.search(r't="([^"]+)"', attrs)
        t = t.group(1) if t else 'n'

        if t == 's':                                   # 共享字符串
            v = re.search(r'<v>(.*?)</v>', inner, re.S)
            val = shared[int(v.group(1))] if v and v.group(1).isdigit() else ''
        elif t == 'inlineStr':
            parts = re.findall(r'<t[^>]*>(.*?)</t>', inner, re.S)
            val = ''.join(parts)
        else:                                          # 数字 / 布尔
            v = re.search(r'<v>(.*?)</v>', inner, re.S)
            val = v.group(1) if v else ''

        grid[(r, c)] = val
        max_c = max(max_c, c)

    if not grid:
        return []
    max_r = max(r for r, _ in grid)
    rows = []
    for r in range(1, max_r + 1):
        rows.append([grid.get((r, c), '') for c in range(max_c + 1)])
    return rows


def main():
    path = sys.argv[1]
    want = sys.argv[2] if len(sys.argv) > 2 else None
    z, shared, names, targets = load(path)

    idx = 0
    if want:
        for i, n in enumerate(names):
            if n == want:
                idx = i
                break
    if idx >= len(targets):
        idx = 0

    print('# 工作表: %s  (%d 个: %s)' % (names[idx] if names else '?',
                                       len(names), ', '.join(names)),
          file=sys.stderr)
    rows = read_sheet(z, shared, targets[idx])
    w = csv.writer(sys.stdout)
    for row in rows:
        w.writerow(row)


if __name__ == '__main__':
    main()
