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

3. **先落暂存区，再拷进去，不删文件**。因为每个产品的旧文件名（01~06.jpg/webp、
   detail/01~NN.jpg/webp）在新集合里都有对应项，而且新数量一律 ≥ 旧数量
   （详情长图 8~9 → 9~14），所以**直接覆盖同名文件就等于"删掉旧图"**，
   站上不会留下任何一张旧图，中途崩了也不会出现半删的破图状态。

   ⚠️ 曾经写成"先删后拷"，结果单轮删到 50 个文件被安全机制拦下，
   进程当场中断，v26 的 6 张主图只剩 2 张 —— 详情页直接破图。
   覆盖式写入没有这个失败模式。

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
    """alicdn 允许匿名直取，但偶尔会抽风，给几次重试。

    注意：详情长图的 URL 是协议相对的（//sc04.alicdn.com/kf/...），
    urllib 不认这种写法（unknown url type），必须补上 https:。
    主图那边在采集时已经补过了，两边不一致，所以在这里统一兜底。
    """
    if url.startswith('//'):
        url = 'https:' + url
    elif not re.match(r'^https?://', url):
        raise RuntimeError('不认识的 URL 形式：%s' % url[:90])
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

    # 最后一张图之后到 </div> 之间的空白也要留着，否则新图会贴着 </div> 挤成一行
    last = imgs[-1]
    tail = inner[inner.rindex(last) + len(last):]

    out = []
    for i in range(1, n + 1):
        tag = re.sub(r'detail/\d+\.(jpg|webp)', 'detail/%02d.\\1' % i, tmpl)
        tag = re.sub(r'(\s—\s)\d+"', '\\g<1>%d"' % i, tag)
        out.append(tag)
    return section[:start] + lead + gap.join(out) + tail + section[end:]


# 详情区的文案是语言相关的。zh 页面手工维护、不进 gen_pages.py，
# 所以插入整节时这里得自己给中文措辞（照抄 zh/handheld-vacuum-gv22.html 的写法）。
SECTION_LABEL = {'en': 'Product details', 'zh': '\u4ea7\u54c1\u7ec6\u8282'}
# 小标题：英文是 "{name} — detail images"，中文是 "{name} 细节图"（空格，没有破折号）
HEADING_TMPL = {'en': '{name} \u2014 detail images', 'zh': '{name} \u7ec6\u8282\u56fe'}

DETAIL_SECTION_TMPL = '''<section class="section section-alt" id="detail-images">
  <div class="section-inner">
    <div class="text-center">
      <div class="section-label">{label}</div>
      <h2 class="section-title">{heading}</h2>
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
    # 站内既有页面的 alt / h2 里存的是 HTML 转义后的文本（& 会写成实体），
    # 新插入的块必须一致。别手写替换表，直接用标准库。
    return htmlescape(s, quote=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--apply', action='store_true', help='真正写盘（默认只打印计划）')
    ap.add_argument('--only', default='', help='只处理指定的 cat/id，逗号分隔')
    ap.add_argument('--from-staging', action='store_true',
                    help='跳过下载，直接复用 scraped/.staging 里已转好的图')
    ap.add_argument('--delete-orphans', action='store_true',
                    help='拷完后删掉既没被覆盖、也没被任何页面引用的残留文件（默认只报告不删）')
    ap.add_argument('--langs', default='en,zh',
                    help='直接改哪些语种（默认 en,zh：en 是模板，zh 手工维护）。'
                         '其余 7 个语种由 gen_pages.py 生成')
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
    if args.from_staging:
        log('复用已有暂存区（跳过下载）：%s\n' % STAGING)
    else:
        if os.path.isdir(STAGING):
            shutil.rmtree(STAGING)
        os.makedirs(STAGING, exist_ok=True)

    staged = {}
    for pid, cat, sid in todo:
        rec = json.load(io.open(os.path.join(V3, pid + '.json'), encoding='utf-8'))
        d = '%s-%s' % (cat, sid)
        sdir = os.path.join(STAGING, d)

        # gv18 第一张历史上叫 01-main.*，data 里就是这个名字，要多写一份
        extra = ['01-main'] if sid == 'gv18' else []

        if args.from_staging:
            n_main = len(rec['gallery'])
            n_detail = len(rec['detail'])
            have_main = len([f for f in os.listdir(sdir) if f.endswith('.jpg')]) \
                if os.path.isdir(sdir) else 0
            have_det = len([f for f in os.listdir(os.path.join(sdir, 'detail'))
                            if f.endswith('.jpg')]) if os.path.isdir(os.path.join(sdir, 'detail')) else 0
            # gv18 会多写一份 01-main.*，所以期望值要加上 extra
            want_main = n_main + len(extra)
            if not os.path.isdir(sdir) or have_main != want_main or have_det != n_detail:
                log('✗ 暂存区 %s 不完整（主图 %d/%d，长图 %d/%d），去掉 --from-staging 重跑'
                    % (d, have_main, want_main, have_det, n_detail))
                return 1
            sizes = {'main': [], 'detail': []}
            staged[pid] = {'dir': d, 'sdir': sdir, 'sizes': sizes, 'extra': extra,
                           'n_main': n_main, 'n_detail': n_detail}
            log('  %-14s/%-9s 暂存区就绪：主图 %d，长图 %d' % (cat, sid, n_main, n_detail))
            continue

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

        if sid == 'gv18':
            for ext in ('.jpg', '.webp'):
                shutil.copyfile(os.path.join(sdir, '01' + ext),
                                os.path.join(sdir, '01-main' + ext))

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

    # ── 2. 覆盖式拷入（不删文件） ────────────────────────────────────────
    # 旧文件名全部落在新集合里，新数量 ≥ 旧数量，所以覆盖即等于替换。
    # 真要删残留，得显式给 --delete-orphans。
    log('\n覆盖式写入…')
    for pid, cat, sid in todo:
        st = staged[pid]
        d = st['dir']
        maindir = os.path.join(ROOT, 'assets', 'images', 'products', d)
        os.makedirs(maindir, exist_ok=True)
        shutil.copytree(st['sdir'], maindir, dirs_exist_ok=True)
        log('  %-14s/%-9s 写入 %d 主图 + %d 长图' % (cat, sid, st['n_main'], st['n_detail']))

    # ── 3. 改 en / zh 的详情区 ──────────────────────────────────────────
    # 为什么是两个而不是九个：gen_pages.py 默认只生成 ar/es/fr/id/ru/th/vi 七个语种，
    # **zh 是手工维护的**（没有 data/i18n/zh.json，生成器会直接拒绝），所以 zh 必须
    # 在这里单独开刀；en 是那七个语种的模板，也得改。
    lang_list = [x.strip() for x in (args.langs or 'en,zh').split(',') if x.strip()]
    log('\n更新 %s 的详情长图列表…' % '/'.join(lang_list))
    for pid, cat, sid in todo:
        st = staged[pid]
        d = st['dir']
        pdata = proddata[pid]
        for lang in lang_list:
            page = os.path.join(ROOT, lang, '%s-%s.html' % (cat, sid))
            if not os.path.exists(page):
                log('  ✗ 找不到 %s' % page)
                return 1
            # zh 是手写的，产品名称得用 zh 自己的；en 用 data 里的英文名
            nm = pdata['name'].get(lang) or pdata['name']['en']
            name = esc((nm or '').strip())
            s = io.open(page, encoding='utf-8', newline='').read()

            if 'id="detail-images"' in s:
                # 已有一节：只换 <img> 列表
                i = s.index('id="detail-images"')
                j = s.find('</section>', i)
                assert j > i, '详情节没有 </section>'
                section = s[s.rfind('<section', 0, i): j + len('</section>')]
                newsec = rebuild_detail_block(section, d, st['n_detail'])
                if newsec is None:
                    log('  ✗ %s 详情节结构认不出来' % page)
                    return 1
                out = s.replace(section, newsec, 1)
            else:
                # 没有这一节（v2g-sj）：整节插到 specifications 之前
                k = s.find('id="specifications"')
                if k < 0:
                    log('  ✗ %s 找不到插入锚点' % page)
                    return 1
                k = s.rfind('<section', 0, k)
                imgs = ''.join('\n      ' + IMG_TMPL.format(rel=d, nn='%02d' % i, n=i, name=name)
                               for i in range(1, st['n_detail'] + 1))
                heading = HEADING_TMPL.get(lang, HEADING_TMPL['en']).format(name=name)
                block = DETAIL_SECTION_TMPL.format(
                    label=SECTION_LABEL.get(lang, SECTION_LABEL['en']),
                    heading=heading, imgs=imgs)
                out = s[:k] + block + s[k:]

            assert len(out) > 1000 and out.count('<section') >= s.count('<section'), '改完结构不对'
            assert '<img src="/assets/images/products/%s/detail/%02d.jpg"' % (d, st['n_detail']) in out, \
                '最后一张长图没写进去'
            io.open(page, 'w', encoding='utf-8', newline='').write(out)
        log('  %-14s/%-9s 详情 %d 张（%s）' % (cat, sid, st['n_detail'], '/'.join(lang_list)))

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
    # ── 5. 残留文件：既没被覆盖、也没有任何引用 ──────────────────────────
    orphans = []
    for pid, cat, sid in todo:
        st = staged[pid]
        d = st['dir']
        base = os.path.join(ROOT, 'assets', 'images', 'products', d)
        covered = set()
        for root, _, files in os.walk(st['sdir']):
            for f in files:
                covered.add(os.path.relpath(os.path.join(root, f), st['sdir']).lower())
        referenced = set()
        for u in (proddata[pid].get('images') or []):
            rel = u.replace(SITE, '').lstrip('/')
            if rel.startswith('assets/images/products/' + d + '/'):
                referenced.add(os.path.relpath(rel, 'assets/images/products/' + d).lower())
        en = os.path.join(ROOT, 'en', '%s-%s.html' % (cat, sid))
        if os.path.exists(en):
            es = io.open(en, encoding='utf-8').read()
            for m in re.finditer(r'src="/assets/images/products/[^"]+"', es):
                rel = m.group(0)[6:-1]
                if rel.startswith('assets/images/products/' + d + '/'):
                    referenced.add(os.path.relpath(rel, 'assets/images/products/' + d).lower())
        for root, _, files in os.walk(base):
            for f in files:
                rel = os.path.relpath(os.path.join(root, f), base).lower()
                if rel not in covered and rel not in referenced:
                    orphans.append(os.path.join('assets/images/products', d, rel))

    if orphans:
        log('\n残留文件 %d 个（未被覆盖、也无任何引用）：' % len(orphans))
        for o in orphans[:20]:
            log('   ' + o)
        if len(orphans) > 20:
            log('   …以及另外 %d 个' % (len(orphans) - 20))
        if args.delete_orphans:
            for o in orphans:
                os.remove(os.path.join(ROOT, o))
            log('   已删除 %d 个' % len(orphans))
        else:
            log('   （默认不删。确认无误后加 --delete-orphans 再跑一次即可清掉）')
    else:
        log('\n无残留文件 —— 旧图已被同名新图全部覆盖。')

    if bad:
        log('\n✗ 校验没过（%d 处）' % bad)
        return 1

    if not args.from_staging:
        shutil.rmtree(STAGING, ignore_errors=True)
    log('\n✓ 全部完成。下一步把改动同步到另外 8 个语种：')
    log('    python scripts/gen_pages.py')
    return 0


if __name__ == '__main__':
    sys.exit(main())
