#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
apply_alibaba_images.py — 把阿里国际站采集到的主图 / 详情长图落到站内

为什么这么设计
--------------
1. **主图原地覆盖同名文件**。7 个目标产品的主图本来就都是 6 张、名字都是
   NN.jpg / NN.webp，阿里给的主图也正好 6 张。所以只要用同样的文件名覆盖，
   `data/products/<cat>.json` 的 images 数组和 HTML 里的主图引用**一个字都不用改**。
   （唯一例外：gv18 的第一张叫 01-main.*，脚本会额外再写一份。）

2. **详情长图数量会变**（站内 8~9 张，阿里 9~14 张），所以详情区的 <img> 列表
   必须重写。为了不碰坏页面其它部分，脚本**不从零生成标记**，而是把现有的第一个
   <img> 当模板，只替换其中的序号和文件名，缩进、style、loading 属性全部照抄。

3. **先落暂存区，再删旧的，最后拷进去**。下载和转码全部成功后才动旧文件，
   中途崩了最多是暂存区有垃圾，站上还是原样。

4. 尺寸沿用站内既有约定：主图最宽 1200，详情长图最宽 750（详情页容器就是 750px）。
   阿里原图动辄 2048，直接放上去只会拖慢大陆访问速度。

数据源
------
scraped/alibaba_v3/<productId>.json   （collect_alibaba_v3.js + retry_attrs.js 产出）

用法
----
    python scripts/apply_alibaba_images.py              # dry-run，只打印计划
    python scripts/apply_alibaba_images.py --apply      # 真正落盘
    python scripts/apply_alibaba_images.py --apply --only handheld-vacuum/gv22

落盘后还要跑一步把改动同步到另外 8 个语种：
    python scripts/gen_pages.py
"""
from __future__ import annotations
import argparse, html as htmlmod, io, json, os, re, shutil, ssl, sys, time, urllib.request
from PIL import Image

htmlescape = htmlmod.escape

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
V3 = os.path.join(ROOT, 'scraped', 'alibaba_v3')
SITE = 'https://www.hkdmj.net'
STAGING = os.path.join(ROOT, 'scraped', '.staging')

MAIN_MAX_W = 1200
DETAIL_MAX_W = 750
JPG_Q = 88
WEBP_Q = 84

# ── 映射表：阿里 productId → 站内 (品类, 产品 id) ──────────────────────────
# 依据见 scraped/mapping_final.csv
MAP = [
    ('1601719491601', 'handheld-vacuum', 'gv22'),      # Model GV22, 550W
    ('1601812941902', 'handheld-vacuum', 'v26'),       # Model GV26, 1.2L
    ('1601887535950', 'handheld-vacuum', 'gv18'),      # Model GV18, 400W/30kPa/1.2L/20-65min 全对
    ('1601673204576', 'robot-vacuum',    'v2g-sj'),    # Model GV2G-SJ, 3500PA, 91-120min
    ('1601781055404', 'robot-vacuum',    't20-c800'),  # Model GT20-C800, 18000Pa, 120-150min
    ('1601957733461', 'robot-vacuum',    'v9'),        # 60W, 150-180min
    ('1601716189230', 'car-vacuum',      'yzx-309'),   # 15kPa/65W/16-25min 三项全对
]

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def log(msg=''):
    print(msg, flush=True)


def download(url, tries=3):
    """alicdn 允许匿名直取，但偶尔会抽风，给几次重试。"""
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Referer': 'https://www.alibaba.com/',
            })
            r = urllib.request.urlopen(req, timeout=40, context=CTX)
            b = r.read()
            if len(b) < 1024:
                raise ValueError('响应太小 %d 字节，八成不是图' % len(b))
            return b
        except Exception as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError('下载失败 %s —— %s' % (url[:90], last))


def flatten(im):
    """PNG 透明通道直接转 JPEG 会变黑，统一压到白底上。"""
    if im.mode in ('RGBA', 'LA', 'P'):
        im = im.convert('RGBA')
        bg = Image.new('RGBA', im.size, (255, 255, 255, 255))
        bg.alpha_composite(im)
        return bg.convert('RGB')
    if im.mode != 'RGB':
        return im.convert('RGB')
    return im


def cap(im, max_w):
    if im.width <= max_w:
        return im
    h = round(im.height * max_w / im.width)
    return im.resize((max_w, h), Image.LANCZOS)


def write_pair(im, base_no_ext, max_w):
    """写 NN.jpg + NN.webp，返回 (jpg字节数, webp字节数)"""
    im = cap(flatten(im), max_w)
    jp = base_no_ext + '.jpg'
    wp = base_no_ext + '.webp'
    im.save(jp, 'JPEG', quality=JPG_Q, optimize=True, progressive=True)
    im.save(wp, 'WEBP', quality=WEBP_Q, method=6)
    return os.path.getsize(jp), os.path.getsize(wp)


# ── HTML 详情区：把现有第一个 <img> 当模板，只换序号 ──────────────────────
def rebuild_detail_block(section, rel_dir, n):
    m_open = re.search(r'<div class="aqc-ss"[^>]*>', section)
    if not m_open:
        return None
    start = m_open.end()
    end = section.index('</div>', start)
    inner = section[start:end]

    imgs = re.findall(r'<img\b[^>]*>', inner)
    if not imgs:
        return None
    tmpl = imgs[0]
    lead = inner[:inner.index(tmpl)]
    if len(imgs) > 1:
        gap = inner[inner.index(imgs[0]) + len(imgs[0]): inner.index(imgs[1])]
    else:
        gap = '\n      '

    out = []
    for i in range(1, n + 1):
        tag = re.sub(r'detail/\d+\.(jpg|webp)', 'detail/%02d.\\1' % i, tmpl)
        tag = re.sub(r'(\s—\s)\d+"', '\\g<1>%d"' % i, tag)
        out.append(tag)
    return section[:start] + lead + gap.join(out) + section[end:]


DETAIL_SECTION_TMPL = '''<section class="section section-alt" id="detail-images">
  <div class="section-inner">
    <div class="text-center">
      <div class="section-label">Product details</div>
      <h2 class="section-title">{name} \u2014 detail images</h2>
    </div>
    <div class="aqc-ss" style="max-width:750px;margin:32px auto 0;">{imgs}
    </div>
  </div>
</section>

'''

IMG_TMPL = ('<img src="/assets/images/products/{rel}/detail/{nn}.jpg" alt="{name} \u2014 {n}" '
            'loading="lazy" style="width:100%;height:auto;display:block;margin:0 auto 14px;'
            'border-radius:8px;">')


def esc(s):
    # 站内既有页面 alt/h2 里的文本是 HTML 转义过的（例如 "Car Care & Spot"），
    # 新插入的块必须一致。别手写替换表，直接用标准库。
    return htmlescape(s, quote=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='真正写盘（默认只打印计划）')
    ap.add_argument('--only', default='', help='只处理指定的 cat/id，逗号分隔')
    args = ap.parse_args()

    only = set(x.strip() for x in args.only.split(',') if x.strip())

    proddata = {}
    for pid, cat, sid in MAP:
        key = '%s/%s' % (cat, sid)
        if only and key not in only:
            continue
        src = os.path.join(V3, pid + '.json')
        if not os.path.exists(src):
            log('✗ 缺采集结果：%s' % src)
            return 1
        rec = json.load(io.open(src, encoding='utf-8'))
        dpath = os.path.join(ROOT, 'data', 'products', cat + '.json')
        if cat not in proddata:
            proddata[cat] = json.load(io.open(dpath, encoding='utf-8'))
        p = [x for x in proddata[cat]['products'] if x['id'] == sid]
        if not p:
            log('✗ data/products/%s.json 里没有 %s' % (cat, sid))
            return 1
        proddata[pid] = p[0]

    todo = [(pid, cat, sid) for pid, cat, sid in MAP
            if (not only or '%s/%s' % (cat, sid) in only)]

    log('=' * 78)
    log('阿里图片落地计划（%s）' % ('执行' if args.apply else 'DRY-RUN'))
    log('=' * 78)
    for pid, cat, sid in todo:
        rec = json.load(io.open(os.path.join(V3, pid + '.json'), encoding='utf-8'))
        d = '%s-%s' % (cat, sid)
        maindir = os.path.join(ROOT, 'assets', 'images', 'products', d)
        detdir = os.path.join(maindir, 'detail')
        old_det = 0
        if os.path.isdir(detdir):
            old_det = len([f for f in os.listdir(detdir) if f.endswith('.jpg')])
        log('  %-14s/%-9s  主图 %d→%d   详情长图 %d→%d' %
            (cat, sid, len(rec['gallery']), len(rec['gallery']), old_det, len(rec['detail'])))
    log('')

    if not args.apply:
        log('（dry-run 结束，加 --apply 才真正写盘）')
        return 0

    # ── 1. 下载 + 转码到暂存区 ──────────────────────────────────────────
    if os.path.isdir(STAGING):
        shutil.rmtree(STAGING)
    os.makedirs(STAGING, exist_ok=True)

    staged = {}
    for pid, cat, sid in todo:
        rec = json.load(io.open(os.path.join(V3, pid + '.json'), encoding='utf-8'))
        d = '%s-%s' % (cat, sid)
        sdir = os.path.join(STAGING, d)
        os.makedirs(sdir, exist_ok=True)
        os.makedirs(os.path.join(sdir, 'detail'), exist_ok=True)
        log('[%s/%s] 下载并转码…' % (cat, sid))

        sizes = {'main': [], 'detail': []}
        for i, u in enumerate(rec['gallery'], 1):
            im = Image.open(io.BytesIO(download(u)))
            jp, wp = write_pair(im, os.path.join(sdir, '%02d' % i), MAIN_MAX_W)
            sizes['main'].append((jp, wp))
        for i, u in enumerate(rec['detail'], 1):
            im = Image.open(io.BytesIO(download(u)))
            jp, wp = write_pair(im, os.path.join(sdir, 'detail', '%02d' % i), DETAIL_MAX_W)
            sizes['detail'].append((jp, wp))

        # gv18 第一张历史上叫 01-main.*，data 里就是这个名字，多写一份
        extra = []
        if sid == 'gv18':
            for ext in ('.jpg', '.webp'):
                shutil.copyfile(os.path.join(sdir, '01' + ext),
                                os.path.join(sdir, '01-main' + ext))
            extra.append('01-main')

        staged[pid] = {'dir': d, 'sdir': sdir, 'sizes': sizes, 'extra': extra,
                       'n_main': len(rec['gallery']), 'n_detail': len(rec['detail'])}
        log('   主图 %d 张（合计 %.0f KB jpg / %.0f KB webp）' %
            (len(sizes['main']),
             sum(a for a, b in sizes['main']) / 1024.0,
             sum(b for a, b in sizes['main']) / 1024.0))
        log('   长图 %d 张（合计 %.0f KB jpg / %.0f KB webp）' %
            (len(sizes['detail']),
             sum(a for a, b in sizes['detail']) / 1024.0,
             sum(b for a, b in sizes['detail']) / 1024.0))

    # ── 2. 删旧图 + 拷新图 ──────────────────────────────────────────────
    log('\n替换旧图…')
    for pid, cat, sid in todo:
        st = staged[pid]
        d = st['dir']
        maindir = os.path.join(ROOT, 'assets', 'images', 'products', d)
        detdir = os.path.join(maindir, 'detail')
        removed = 0
        if os.path.isdir(maindir):
            for f in os.listdir(maindir):
                fp = os.path.join(maindir, f)
                if os.path.isfile(fp) and f.lower().endswith(('.jpg', '.jpeg', '.webp', '.png')):
                    os.remove(fp); removed += 1
        if os.path.isdir(detdir):
            shutil.rmtree(detdir); removed += 1
        shutil.copytree(st['sdir'], maindir, dirs_exist_ok=True)
        log('  %-14s/%-9s 删 %d 项，拷入 %d 主图 + %d 长图' %
            (cat, sid, removed, st['n_main'], st['n_detail']))

    # ── 3. 改 en 模板的详情区 ───────────────────────────────────────────
    log('\n更新 en/ 模板详情长图列表…')
    for pid, cat, sid in todo:
        st = staged[pid]
        d = st['dir']
        en = os.path.join(ROOT, 'en', '%s-%s.html' % (cat, sid))
        if not os.path.exists(en):
            log('  ✗ 找不到 %s' % en)
            return 1
        pdata = proddata[pid]
        name = esc((pdata['name']['en'] or '').strip())
        s = io.open(en, encoding='utf-8', newline='').read()

        if 'id="detail-images"' in s:
            # 已有一节：只换 <img> 列表
            i = s.index('id="detail-images"')
            j = s.find('</section>', i)
            assert j > i, '详情节没有 </section>'
            section = s[s.rfind('<section', 0, i): j + len('</section>')]
            newsec = rebuild_detail_block(section, d, st['n_detail'])
            if newsec is None:
                log('  ✗ %s 详情节结构认不出来' % en)
                return 1
            out = s.replace(section, newsec, 1)
        else:
            # 没有这一节（v2g-sj）：整节插到 specifications 之前
            anchor = '<section class="section" id="specifications">'
            k = s.find(anchor)
            if k < 0:
                log('  ✗ %s 找不到插入锚点' % en)
                return 1
            imgs = ''.join('\n      ' + IMG_TMPL.format(rel=d, nn='%02d' % i, n=i, name=name)
                           for i in range(1, st['n_detail'] + 1))
            block = DETAIL_SECTION_TMPL.format(name=name, imgs=imgs)
            out = s[:k] + block + s[k:]

        assert len(out) > 1000 and out.count('<section') >= s.count('<section'), '改完结构不对'
        assert '<img src="/assets/images/products/%s/detail/%02d.jpg"' % (d, st['n_detail']) in out, \
            '最后一张长图没写进去'
        io.open(en, 'w', encoding='utf-8', newline='').write(out)
        log('  %-14s/%-9s 详情 %d 张' % (cat, sid, st['n_detail']))

    # ── 4. 校验 ─────────────────────────────────────────────────────────
    log('\n校验…')
    bad = 0
    for pid, cat, sid in todo:
        st = staged[pid]
        d = st['dir']
        base = os.path.join(ROOT, 'assets', 'images', 'products', d)
        pdata = proddata[pid]
        for u in (pdata.get('images') or []):
            rel = u.replace(SITE, '').lstrip('/')
            fp = os.path.join(ROOT, rel)
            if not os.path.isfile(fp) or os.path.getsize(fp) == 0:
                log('  ✗ %s/%s images 引用缺失：%s' % (cat, sid, rel)); bad += 1
        en = os.path.join(ROOT, 'en', '%s-%s.html' % (cat, sid))
        s = io.open(en, encoding='utf-8').read()
        for m in re.finditer(r'src="/(assets/images/products/[^"]+)"', s):
            fp = os.path.join(ROOT, m.group(1))
            if not os.path.isfile(fp) or os.path.getsize(fp) == 0:
                log('  ✗ %s/%s HTML 引用缺失：%s' % (cat, sid, m.group(1))); bad += 1
        zero = [f for f in os.listdir(base) if os.path.isfile(os.path.join(base, f))
                and os.path.getsize(os.path.join(base, f)) == 0]
        if zero:
            log('  ✗ %s/%s 有 0 字节文件：%s' % (cat, sid, zero)); bad += 1
    if bad:
        log('\n✗ 校验没过（%d 处）' % bad)
        return 1

    shutil.rmtree(STAGING, ignore_errors=True)
    log('\n✓ 全部完成。下一步把改动同步到另外 8 个语种：')
    log('    python scripts/gen_pages.py')
    return 0


if __name__ == '__main__':
    sys.exit(main())
