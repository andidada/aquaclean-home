# -*- coding: utf-8 -*-
"""
修复产品数据里被合并脚本写错的字段（highlights / specs / quick_specs）。

背景
----
commit 7f09acc（"merge: integrate remote product content with local redesign"）
用一次字段错位赋值，把「每个品类文件的第 1 个产品」的三个字段冲掉了：

    highlights   <- 整个 products 数组（本该是 [{icon, text:{9 语言}}]）
    specs        <- 评论数据（本该是 [{label, value}]）
    quick_specs  <- 评论 schema（本该是 [{label, value}]）

后果：详情页 "PRODUCT HIGHLIGHTS" 下面只剩一排对勾，文字全空 ——
因为渲染用的是 pick(h.text, lang)，从产品对象里取 .text 取到 undefined。

正确数据在上一个提交 eeb11bd 里完好无损，本脚本只把那几个被冲掉的字段
搬回来，其它字段一律不动。

为什么是"外科式替换"而不是整文件重新序列化
------------------------------------------
这些 JSON 由不同来源合并而来，缩进虽是 1 空格、行尾以 CRLF 为主，但**存在
行尾混用**。整文件 json.dumps 会重排 70%+ 的行，diff 大到无法审阅。所以这里
用带位置跟踪的扫描器精确定位目标值的字节区间，只替换那一小段。

用法
----
    python scripts/fix_product_highlights.py            # 预演，只报告
    python scripts/fix_product_highlights.py --apply    # 真正写入
"""
import json
import subprocess
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_COMMIT = 'eeb11bd'   # 最后一个 highlights 还完好的提交

# 每个品类文件里被冲掉的那个产品
TARGETS = {
    'car-vacuum': 'yzx-305',
    'coffee-machine': '2604',
    'handheld-vacuum': 'gv18',
    'robot-vacuum': 'gt20',
    'steam-cleaner': 'd09s',
    'tire-inflator': 'ymc6628',
    'upright-steam-mop': 'qst063',
    'uv-mite-remover': 'pc708',
    'window-cleaner-robot': 'gm1-c',
}

# 需要从旧版本搬回来的字段，以及它们的合法形态
FIELDS = {
    'highlights': lambda v: (isinstance(v, list) and v and
                             all(isinstance(x, dict) and 'icon' in x and 'text' in x for x in v)),
    'specs': lambda v: (isinstance(v, list) and v and
                        all(isinstance(x, dict) and 'label' in x and 'value' in x for x in v)),
    'quick_specs': lambda v: (isinstance(v, list) and v and
                              all(isinstance(x, dict) and 'label' in x and 'value' in x for x in v)),
}


# ────────────────────────── 带位置的 JSON 扫描器 ──────────────────────────
WS = ' \t\r\n'


def skip_ws(t, i):
    while i < len(t) and t[i] in WS:
        i += 1
    return i


def read_string(t, i):
    """i 指向起始引号；返回 (解码后的字符串, 结束引号之后的位置)。"""
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
    """跳过任意一个 JSON 值，返回其结束位置。"""
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
    # 字面量
    j = i
    while j < len(t) and t[j] not in ',}] \t\r\n':
        j += 1
    return j


def object_members(t, i):
    """i 指向 '{'；产出 (键, 值起点, 值终点)。"""
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
    """i 指向 '['；产出 (下标, 值起点, 值终点)。"""
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


def root_value_start(t):
    return skip_ws(t, 0)


def find_product_span(t, product_id):
    """在 products 数组里按 id 找到产品对象，返回 (对象起点, 对象终点)。"""
    root = root_value_start(t)
    products_span = None
    for key, vs, ve in object_members(t, root):
        if key == 'products':
            products_span = (vs, ve)
            break
    if not products_span:
        raise SystemExit('找不到 products 数组')
    for _, vs, ve in array_items(t, products_span[0]):
        for key, kvs, kve in object_members(t, vs):
            if key == 'id':
                pid, _ = read_string(t, kvs)
                if pid == product_id:
                    return vs, ve
                break
    raise SystemExit('在 products 里找不到 id=%s' % product_id)


# ────────────────────────────── 序列化与替换 ──────────────────────────────
def render_value(value, key_indent):
    """
    把一个值渲染成与文件风格一致的文本片段。

    json.dumps(indent=1) 产出的首行顶格、后续行逐级缩进、收尾括号顶格；
    嵌入时只要给除首行外的每一行补上 key 的缩进量即可对齐。
    """
    body = json.dumps(value, ensure_ascii=False, indent=1)
    lines = body.split('\n')
    pad = ' ' * key_indent
    return lines[0] + ''.join('\r\n' + pad + l for l in lines[1:])


def key_indent_of(t, value_start):
    """取该值所在行的缩进量（即其 key 的缩进）。"""
    line_start = t.rfind('\n', 0, value_start) + 1
    n = 0
    while line_start + n < len(t) and t[line_start + n] == ' ':
        n += 1
    return n


def main():
    apply = '--apply' in sys.argv
    total_fixed = 0

    for cat, pid in TARGETS.items():
        rel = 'data/products/%s.json' % cat
        path = os.path.join(ROOT, rel)
        with open(path, 'r', encoding='utf-8', newline='') as fh:
            text = fh.read()

        old_raw = subprocess.run(
            ['git', 'show', '%s:%s' % (BASE_COMMIT, rel)],
            cwd=ROOT, capture_output=True, check=True).stdout.decode('utf-8')
        old_obj = json.loads(old_raw)
        old_prod = [p for p in old_obj['products'] if p.get('id') == pid][0]

        cur_obj = json.loads(text)
        cur_prod = [p for p in cur_obj['products'] if p.get('id') == pid][0]

        obj_start, _ = find_product_span(text, pid)

        edits = []
        for field, is_valid in FIELDS.items():
            cur_v = cur_prod.get(field)
            if is_valid(cur_v):
                continue                       # 本来就好的，不碰
            new_v = old_prod.get(field)
            if not is_valid(new_v):
                print('  !! %s.%s 旧版也不合法，跳过' % (cat, field))
                continue
            # 在文本里定位这个字段的值区间
            span = None
            for key, vs, ve in object_members(text, obj_start):
                if key == field:
                    span = (vs, ve)
                    break
            if span is None:
                print('  !! %s 文本里找不到字段 %s' % (cat, field))
                continue
            edits.append((span[0], span[1], render_value(new_v, key_indent_of(text, span[0]))))
            total_fixed += 1

        if not edits:
            print('%-22s %-9s 无需修复' % (cat, pid))
            continue

        edits.sort(key=lambda e: e[0])
        out = ''
        pos = 0
        for s, e, rep in edits:
            out += text[pos:s] + rep
            pos = e
        out += text[pos:]

        # ── 安全检查：解析必须成功，且除目标字段外内容完全一致 ──
        new_obj = json.loads(out)
        new_prod = [p for p in new_obj['products'] if p.get('id') == pid][0]
        assert json.dumps(new_obj, sort_keys=True, ensure_ascii=False) != json.dumps(
            cur_obj, sort_keys=True, ensure_ascii=False), '内容没变，替换无效'
        for k in set(list(cur_prod.keys()) + list(new_prod.keys())):
            same = json.dumps(cur_prod.get(k), sort_keys=True, ensure_ascii=False) == \
                   json.dumps(new_prod.get(k), sort_keys=True, ensure_ascii=False)
            if not same:
                assert k in FIELDS, '意外改动了字段 %s' % k
                assert FIELDS[k](new_prod.get(k)), '字段 %s 修完仍不合法' % k
        # 其它产品必须一字未动
        for i, p in enumerate(cur_obj['products']):
            if p.get('id') == pid:
                continue
            assert json.dumps(p, sort_keys=True, ensure_ascii=False) == \
                   json.dumps(new_obj['products'][i], sort_keys=True, ensure_ascii=False), \
                   '误改了产品 %s' % p.get('id')
        assert abs(len(out) - len(text)) < len(text), '体积异常'

        fields = ', '.join(sorted(k for k in cur_prod
                                  if json.dumps(cur_prod.get(k), sort_keys=True, ensure_ascii=False) !=
                                  json.dumps(new_prod.get(k), sort_keys=True, ensure_ascii=False)))
        print('%-22s %-9s 修复: %-28s %+d bytes' % (cat, pid, fields, len(out) - len(text)))

        if apply:
            with open(path, 'w', encoding='utf-8', newline='') as fh:
                fh.write(out)

    print('\n共修复字段 %d 处。%s' % (total_fixed, '已写入。' if apply else '（预演模式，未写入）'))


if __name__ == '__main__':
    main()
