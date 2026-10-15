#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把一批产品从"手工维护"的语种（en / zh）页面上摘掉，并清理详情页与图片。

背景
----
en 是 gen_pages.py 的模板源；zh 是手工维护的（没有 data/i18n/zh.json，
生成器会直接拒绝）。另外 7 个语种（ar/es/fr/id/ru/th/vi）由 gen_pages.py
从 en 模板 + 数据重建，所以**不在这里动** —— 改完 en 跑一次生成器即可。

本脚本做的事
  1. en / zh 类目页：摘掉产品卡片，更新 productCount / "N models" / ItemList
  2. 全部 9 语种：删除该产品详情页
  3. 删除图片目录（9 语种共用，只删一次）

断言用的"每一步剩余顺序"从 git 历史里取删除前的清单还原，
否则 strip_from_category_page 的 "卡片顺序与数据一致" 校验无从比对。

用法
    python scripts/remove_products_html.py <cat>:<id> [<cat>:<id> ...] [--apply]
"""
from __future__ import annotations
import io, json, os, re, shutil, subprocess, sys, tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from remove_product import strip_from_category_page, read

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HAND_LANGS = ['en', 'zh']          # 手工维护、不能用生成器重建的语种
ALL_LANGS = ['en', 'zh', 'ar', 'es', 'fr', 'id', 'ru', 'th', 'vi']


def orig_ids(cat):
    """从 git HEAD 取删除前的产品顺序。"""
    rel = 'data/products/%s.json' % cat
    out = subprocess.run(['git', 'show', 'HEAD:' + rel], cwd=ROOT,
                         capture_output=True)
    if out.returncode != 0:
        raise RuntimeError('git show HEAD:%s 失败：%s' % (rel, out.stderr.decode()[:200]))
    return [p['id'] for p in json.loads(out.stdout.decode('utf-8'))['products']]


def main():
    argv = [a for a in sys.argv[1:] if a != '--apply']
    apply = '--apply' in sys.argv[1:]
    if not argv:
        sys.exit('用法：python scripts/remove_products_html.py <cat>:<id> ... [--apply]')

    plan = {}
    for item in argv:
        cat, _, pid = item.partition(':')
        assert cat and pid, '参数格式应为 <cat>:<id>'
        plan.setdefault(cat, []).append(pid)

    for cat, pids in plan.items():
        dpath = os.path.join(ROOT, 'data', 'products', cat + '.json')
        now_ids = [p['id'] for p in json.loads(read(dpath))['products']]
        before = orig_ids(cat)
        assert set(before) - set(now_ids) == set(pids), \
            '%s：git 里的旧清单与当前清单之差 != 待删清单\n  旧=%s\n  今=%s\n  删=%s' \
            % (cat, before, now_ids, pids)
        assert set(pids) <= set(before), '%s：待删的 %s 不在旧清单里' % (cat, pids)

        # 逐步推进：每一步摘除后的期望剩余顺序
        cur = list(before)
        steps = []
        for pid in pids:
            cur.remove(pid)
            steps.append((pid, [{'id': i, '_cat': cat} for i in cur]))

        # 摘除要连续作用在同一次结果上。apply 时直接改真实文件；
        # 预演时改临时副本，真实文件一个字节都不碰。
        work = {}
        for lang in HAND_LANGS:
            real = os.path.join(ROOT, lang, cat, 'index.html')
            if not os.path.isfile(real):
                continue
            if apply:
                work[lang] = real
            else:
                tmp = os.path.join(tempfile.gettempdir(),
                                   'aqc_rm_%s_%s.html' % (lang, cat))
                io.open(tmp, 'w', encoding='utf-8', newline='').write(read(real))
                work[lang] = tmp

        for pid, expect in steps:
            # 1) en / zh 类目页
            for lang, path in work.items():
                try:
                    new = strip_from_category_page(path, cat, pid, expect, lang)
                except Exception as e:
                    print('  ❌ %s/%s 类目页摘除失败（%s）：%s'
                          % (lang, cat, pid, str(e)[:200]))
                    return 1
                io.open(path, 'w', encoding='utf-8', newline='').write(new)

            # 2) 详情页（全部语种）
            n = 0
            for lang in ALL_LANGS:
                p = os.path.join(ROOT, lang, '%s-%s.html' % (cat, pid))
                if os.path.isfile(p):
                    if apply:
                        os.remove(p)
                    n += 1

            # 3) 图片目录
            imgdir = os.path.join(ROOT, 'assets', 'images', 'products',
                                  '%s-%s' % (cat, pid))
            has_img = os.path.isdir(imgdir)
            if has_img and apply:
                shutil.rmtree(imgdir)

            print('  %s %s/%s  类目页 en+zh 摘除 ✓，详情页 %d 个，图片 %s'
                  % ('✓' if apply else '·', cat, pid, n,
                     '已删' if (has_img and apply) else ('待删' if has_img else '无')))

        # 校验：最终剩余顺序与数据一致
        for lang, cpath in work.items():
            s = read(cpath).replace('\r\n', '\n')
            got = [m.group(1) for m in re.finditer(
                r'<img src="/assets/images/products/%s-([a-z0-9\-]+)/' % cat.replace('-', '\\-'), s)]
            if got != now_ids:
                print('  ❌ %s/%s 卡片顺序与数据不一致：页面=%s 数据=%s'
                      % (lang, cat, got, now_ids))
                return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
