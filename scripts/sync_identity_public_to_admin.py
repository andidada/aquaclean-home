# -*- coding: utf-8 -*-
"""
把公开站的公司主体信息同步到后台仓库。

为什么需要这个
--------------
主体信息（公司名 / 邮箱 / 电话 / WhatsApp）在项目里有多份拷贝，2026-10-08
那次全站切换就漏改了后台那几份，导致后台首页数据里还留着旧号码
（+8617779190118）和旧邮箱（info@aquaclean-home.com）。

这件事的危害不是"看着不一致"这么简单：后台的「🚀 发布到线上」会把它自己
的 data/pages/home/*.json 推上去，也就是说**在后台点一次发布，就会把旧
号码覆盖回线上**。所以公开站和后台必须始终一致。

方向是单向的：**公开站是权威来源**，后台跟着它变。

用法
----
    python scripts/sync_identity_public_to_admin.py            # 预演
    python scripts/sync_identity_public_to_admin.py --apply    # 写入

⚠️ 后台仓库不在 git 版本控制下，--apply 之前请自行备份。
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ADMIN = os.path.join(os.path.dirname(ROOT), 'aquaclean-admin-app')

LANGS = ['en', 'zh', 'ar', 'es', 'fr', 'id', 'ru', 'th', 'vi']

# 需要同步的字段（点号路径）。改了主体信息就往这里加。
FIELDS = [
    ['contact', 'email'],
    ['contact', 'phone'],
    ['contact', 'whatsapp'],
    ['footer', 'phone'],
]


# ────────────────────── 带位置的 JSON 扫描器（同 fix_product_highlights.py） ──────────────────────
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


def find_path_span(t, path):
    """返回 path 指向的值在文本里的 (起, 止)；找不到返回 None。"""
    i = skip_ws(t, 0)
    for step in path:
        if t[i] != '{':
            return None
        hit = None
        for key, vs, ve in object_members(t, i):
            if key == step:
                hit = (vs, ve)
                break
        if hit is None:
            return None
        i = hit[0]
    return hit


def flatten(o, prefix=''):
    out = {}
    if isinstance(o, dict):
        for k, v in o.items():
            out.update(flatten(v, prefix + '/' + k))
    elif isinstance(o, list):
        for idx, v in enumerate(o):
            out.update(flatten(v, prefix + '/%d' % idx))
    else:
        out[prefix] = o
    return out


def main():
    apply = '--apply' in sys.argv
    if not os.path.isdir(ADMIN):
        raise SystemExit('找不到后台仓库: %s' % ADMIN)

    changed = 0
    for lang in LANGS:
        rel = os.path.join('data', 'pages', 'home', '%s.json' % lang)
        src_path = os.path.join(ROOT, rel)
        dst_path = os.path.join(ADMIN, rel)

        with open(src_path, 'r', encoding='utf-8') as fh:
            src = fh.read()
        with open(dst_path, 'r', encoding='utf-8', newline='') as fh:
            dst = fh.read()

        edits = []
        for path in FIELDS:
            span = find_path_span(src, path)
            if span is None:
                print('  !! 公开站 %s 里找不到 %s' % (lang, '.'.join(path)))
                continue
            new_val = json.loads(src[span[0]:span[1]])
            dspan = find_path_span(dst, path)
            if dspan is None:
                print('  !! 后台 %s 里找不到 %s' % (lang, '.'.join(path)))
                continue
            old_raw = dst[dspan[0]:dspan[1]]
            if json.loads(old_raw) == new_val:
                continue
            new_raw = json.dumps(new_val, ensure_ascii=False)
            edits.append((dspan[0], dspan[1], new_raw, '.'.join(path),
                          json.loads(old_raw), new_val))

        if not edits:
            print('%-4s 已一致，无需同步' % lang)
            continue

        edits.sort(key=lambda e: e[0])
        out = ''
        pos = 0
        for s, e, rep, *_ in edits:
            out += dst[pos:s] + rep
            pos = e
        out += dst[pos:]

        # 安全校验：解析后与公开站逐字段比对，必须完全一致
        a, b = flatten(json.loads(out)), flatten(json.loads(src))
        diff = [k for k in set(a) | set(b) if a.get(k) != b.get(k)]
        assert not diff, '同步后仍不一致: %s' % diff[:5]
        assert 0.9 * len(dst) < len(out) < 1.1 * len(dst), '体积异常'

        for _, _, _, name, old, new in edits:
            print('%-4s %-20s %-26s -> %s' % (lang, name, old, new))
        changed += 1

        if apply:
            with open(dst_path, 'w', encoding='utf-8', newline='') as fh:
                fh.write(out)

    print('\n需要同步的语种: %d。%s' % (changed, '已写入。' if apply else '（预演模式，未写入）'))


if __name__ == '__main__':
    main()
