#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dedupe_highlights_from_specs.py — 删掉产品亮点里与规格重复的条目。

问题
----
详情页同一组数字出现两遍（用户截图反馈）：

    顶部 quick_specs 药丸   Suction Power: 40000Pa | Power (W): 35W | ...
    下面 PRODUCT HIGHLIGHTS ✓ Suction Power: 40000Pa
                              ✓ Power (W): 35W
                              ...

36 个产品的 highlights 整个就是规格回音——每条文本都恰好等于某条
quick_specs / specs 的 "{标签}: {值}"。这是早期从阿里巴巴搬数据时
把规格表直接当亮点填进去留下的，不是页面写错了。

留哪一边
--------
**留药丸（quick_specs），删亮点里的重复条目。** 理由：

1. 语义。`highlights` 该写卖点（"LDS SLAM Navigation with Smart
   Mapping"），`quick_specs` 才是专门放紧凑规格的字段。删错的数据，
   不删对的数据。
2. 不丢信息。每条被删的亮点都能在 quick_specs 药丸或下面的
   "Key Attributes" 规格表里找到（规格表渲染全部 specs，一个不漏）。
3. 站点上本来就有 3 个产品（gv18 / gt20 / ymc6628）是"真亮点 + 药丸"
   并存的样子，那才是这个页面的设计意图。这次改动是让另外 36 个
   产品向它对齐，不是发明新布局。

匹配规则
--------
亮点文本（按 en）归一化（压缩空白 + 忽略大小写）后，等于某条规格的
"{label}: {value}" 或 "{label}:{value}"，即判为重复。
只按 en 判定：亮点和规格都是 9 语言齐备的，删整条（含所有语言），
渲染时 pick() 会回退，不会出现半截翻译。

真亮点产品零误伤：gv18 / gt20 / ymc6628 各 4 条，命中 0 条。

为什么是外科式替换
------------------
同 fix_product_highlights.py：这些 JSON 行尾混用（CRLF 为主但有 LF），
整文件 json.dumps 会重排大量行、diff 没法审阅。这里用带位置跟踪的
扫描器只替换 highlights 那一段，保留的元素原文照抄、一个字节不动。

用法
----
    python scripts/dedupe_highlights_from_specs.py            # 预演
    python scripts/dedupe_highlights_from_specs.py --apply    # 写入
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRODUCTS_DIR = os.path.join(ROOT, 'data', 'products')
FILES = ['car-vacuum.json', 'coffee-machine.json', 'handheld-vacuum.json',
         'robot-vacuum.json', 'steam-cleaner.json', 'tire-inflator.json',
         'upright-steam-mop.json', 'uv-mite-remover.json',
         'window-cleaner-robot.json']


# ────────────────────────── 带位置的 JSON 扫描器 ──────────────────────────
WS = ' \t\r\n'


def skip_ws(t, i):
    while i < len(t) and t[i] in WS:
        i += 1
    return i


def read_string(t, i):
    assert t[i] == '"', 'expected string at %d' % i
    j = i + 1
    buf = []
    while True:
        c = t[j]
        if c == '\\':
            esc = t[j + 1]
            if esc == 'u':
                buf.append(chr(int(t[j + 2:j + 6], 16)))
                j += 6
            else:
                buf.append({'n': '\n', 't': '\t', 'r': '\r', 'b': '\b',
                            'f': '\f', '/': '/', '\\': '\\', '"': '"'}[esc])
                j += 2
        elif c == '"':
            return ''.join(buf), j + 1
        else:
            buf.append(c)
            j += 1


def skip_value(t, i):
    i = skip_ws(t, i)
    c = t[i]
    if c == '"':
        return read_string(t, i)[1]
    if c == '{':
        i += 1
        while True:
            i = skip_ws(t, i)
            if t[i] == '}':
                return i + 1
            i = read_string(t, i)[1]
            i = skip_ws(t, i)
            assert t[i] == ':'
            i = skip_value(t, i + 1)
            i = skip_ws(t, i)
            if t[i] == ',':
                i += 1
    if c == '[':
        i += 1
        while True:
            i = skip_ws(t, i)
            if t[i] == ']':
                return i + 1
            i = skip_value(t, i)
            i = skip_ws(t, i)
            if t[i] == ',':
                i += 1
    j = i
    while j < len(t) and t[j] not in ',}] \t\r\n':
        j += 1
    return j


def object_members(t, i):
    assert t[i] == '{'
    i += 1
    while True:
        i = skip_ws(t, i)
        if t[i] == '}':
            return
        key, i = read_string(t, i)
        i = skip_ws(t, i)
        assert t[i] == ':'
        vs = skip_ws(t, i + 1)
        ve = skip_value(t, vs)
        yield key, vs, ve
        i = skip_ws(t, ve)
        if t[i] == ',':
            i += 1


def array_items(t, i):
    assert t[i] == '['
    i += 1
    idx = 0
    while True:
        i = skip_ws(t, i)
        if t[i] == ']':
            return
        ve = skip_value(t, i)
        yield idx, i, ve
        idx += 1
        i = skip_ws(t, ve)
        if t[i] == ',':
            i += 1


# ────────────────────────────── 判定逻辑 ──────────────────────────────
def pick(v, lang='en'):
    if isinstance(v, dict):
        return v.get(lang) or v.get('en') or ''
    return v or ''


def norm(s):
    return re.sub(r'\s+', ' ', str(s)).strip().casefold()


def spec_strings(product):
    """该产品全部规格的 "{label}: {value}" 归一化候选集。"""
    out = set()
    for key in ('quick_specs', 'specs'):
        for sp in product.get(key) or []:
            if not isinstance(sp, dict):
                continue
            lab = str(pick(sp.get('label'))).strip()
            val = str(pick(sp.get('value'))).strip()
            if not lab and not val:
                continue
            out.add(norm('%s: %s' % (lab, val)))
            out.add(norm('%s:%s' % (lab, val)))
    return out


def is_echo(highlight, cands):
    return norm(pick(highlight.get('text'))) in cands


def eol_style(b):
    crlf = b.count(b'\r\n')
    lf = b.count(b'\n') - crlf
    return 'CRLF' if crlf > lf else 'LF'


def write_bytes(p, b):
    # 先算好内容、断言非空，再开写（防 0 字节事故）
    assert isinstance(b, (bytes, bytearray)) and len(b) > 0, '拒绝写入空内容: %s' % p
    with open(p, 'wb') as f:
        f.write(b)


# ────────────────────────────── 主流程 ──────────────────────────────
def plan_file(rel):
    """返回 (原文, 编辑列表[(起,止,新文本)], 删除条数, 保留条数, 明细)。"""
    path = os.path.join(PRODUCTS_DIR, rel)
    raw = open(path, 'rb').read()
    t = raw.decode('utf-8')
    j = json.loads(t)

    # 产品对象 → id 的映射，按数组顺序
    root = skip_ws(t, 0)
    products_span = None
    for key, vs, ve in object_members(t, root):
        if key == 'products':
            products_span = (vs, ve)
            break
    assert products_span, '找不到 products 数组'

    prod_objs = []           # (id, 对象起点, 对象终点)
    for _, vs, ve in array_items(t, products_span[0]):
        pid = None
        for key, kvs, kve in object_members(t, vs):
            if key == 'id':
                pid, _ = read_string(t, kvs)
                break
        prod_objs.append((pid, vs, ve))

    by_id = {p['id']: p for p in j['products']}

    edits = []
    n_rm = 0
    # 保留条数按"文件里原有亮点总数 - 删除数"算：没有重复的产品
    # （比如 gv18 那种真亮点）一条不动，也要算进保留数里。
    n_keep = sum(len(p.get('highlights') or []) for p in j['products'])
    detail = []

    for pid, pvs, pve in prod_objs:
        product = by_id.get(pid)
        if product is None:
            continue
        hl = product.get('highlights')
        if not isinstance(hl, list) or not hl:
            continue

        # 定位这个产品对象里的 highlights 值
        hl_span = None
        for key, vs, ve in object_members(t, pvs):
            if key == 'highlights':
                hl_span = (vs, ve)
                break
        if hl_span is None:
            continue

        cands = spec_strings(product)
        if not cands:
            continue

        spans = list(array_items(t, hl_span[0]))
        elems = [json.loads(t[vs:ve]) for _, vs, ve in spans]
        keep = [k for k, e in enumerate(elems) if not is_echo(e, cands)]
        drop = [k for k, e in enumerate(elems) if is_echo(e, cands)]
        if not drop:
            continue

        n_rm += len(drop)
        n_keep -= len(drop)
        detail.append((pid, len(elems), len(drop), len(elems) - len(drop)))

        # 重建数组文本：保留的元素原文照抄，只丢掉被删的
        if not keep:
            new_text = '[]'
        else:
            head = t[hl_span[0] + 1:spans[0][1]]
            tail = t[spans[-1][2]:hl_span[1] - 1]
            parts = []
            for n, k in enumerate(keep):
                if n > 0:
                    prev = keep[n - 1]
                    # 用原来跟在 prev 后面的那个分隔符
                    sep_end = spans[k][1]
                    sep_start = spans[prev][2]
                    parts.append(t[sep_start:sep_end])
                parts.append(t[spans[k][1]:spans[k][2]])
            new_text = '[' + head + ''.join(parts) + tail + ']'

        edits.append((hl_span[0], hl_span[1], new_text))

    # 从后往前替换，避免位置漂移
    edits.sort(key=lambda e: e[0], reverse=True)
    out = t
    for s, e, rep in edits:
        out = out[:s] + rep + out[e:]

    return raw, out, n_rm, n_keep, detail


def main():
    apply = '--apply' in sys.argv

    grand_rm = grand_keep = 0
    changed_files = 0

    for rel in FILES:
        raw, out, n_rm, n_keep, detail = plan_file(rel)
        if n_rm == 0:
            print('%-26s 无重复，跳过' % rel)
            continue

        changed_files += 1
        grand_rm += n_rm
        grand_keep += n_keep

        # ── 安全校验 ──
        old_j = json.loads(raw.decode('utf-8'))
        new_j = json.loads(out)
        # 1) 除了 highlights，其它必须一模一样
        def strip_hl(j):
            c = json.loads(json.dumps(j))
            for p in c['products']:
                p.pop('highlights', None)
            return c
        assert strip_hl(old_j) == strip_hl(new_j), \
            '%s: highlights 之外的字段被改动了' % rel
        # 2) 保留的亮点条目必须原文还在（按内容比对）
        old_hl = [h for p in old_j['products'] for h in (p.get('highlights') or [])]
        new_hl = [h for p in new_j['products'] for h in (p.get('highlights') or [])]
        assert len(new_hl) == n_keep, '%s: 保留条数对不上' % rel
        for h in new_hl:
            assert h in old_hl, '%s: 出现了原本不存在的亮点条目' % rel
        # 3) 换行风格不能变
        assert eol_style(raw) == eol_style(out.encode('utf-8')), \
            '%s: 换行风格被改变' % rel
        # 4) 体积量级合理
        assert 0.5 * len(raw) < len(out.encode('utf-8')) < 1.05 * len(raw), \
            '%s: 体积异常 %d -> %d' % (rel, len(raw), len(out.encode('utf-8')))

        print('%-26s 删 %d 条 / 留 %d 条   %s' % (
            rel, n_rm, n_keep,
            '；'.join('%s %d→%d' % (p, a, b) for p, a, _x, b in detail)))

        if apply:
            write_bytes(os.path.join(PRODUCTS_DIR, rel), out.encode('utf-8'))

    print()
    print('合计：%d 个文件，删除 %d 条规格回音亮点，保留 %d 条真亮点'
          % (changed_files, grand_rm, grand_keep))
    if not apply:
        print('（预演模式，未写任何文件。加 --apply 才会真正写入。）')
    else:
        print('已写入。')

        # 写完后整体复核
        print('\n复核 ...')
        bad = 0
        for rel in FILES:
            p = os.path.join(PRODUCTS_DIR, rel)
            b = open(p, 'rb').read()
            if len(b) == 0:
                print('  ❌ 0 字节文件: %s' % rel)
                bad += 1
                continue
            j = json.loads(b.decode('utf-8'))
            for prod in j['products']:
                hl = prod.get('highlights') or []
                cands = spec_strings(prod)
                for h in hl:
                    if is_echo(h, cands):
                        print('  ❌ %s / %s 仍有重复亮点: %s'
                              % (rel, prod.get('id'), pick(h.get('text'))))
                        bad += 1
        if bad:
            print('❌ 复核发现 %d 处问题' % bad)
            return 2
        left = sum(len(p.get('highlights') or [])
                   for rel in FILES
                   for p in json.loads(open(os.path.join(PRODUCTS_DIR, rel),
                                            encoding='utf-8').read())['products'])
        print('✅ 全部通过，站点上还剩 %d 条亮点（都属于 3 个有真亮点的产品）' % left)
    return 0


if __name__ == '__main__':
    sys.exit(main())
