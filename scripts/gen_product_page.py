#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gen_product_page.py — 从产品数据生成/重建一个产品详情页的静态预渲染内容

为什么需要它
------------
产品详情页有两套内容：

  1. **运行时**：product-detail.js 的 render() 整体重写 #aqc-detail-mount，
     数据来自 data/products/{cat}.json。
  2. **静态预渲染**：#aqc-detail-mount 里原本就有的那段 HTML。只有爬虫和
     禁用 JS 的访客看得到，但对 SEO 是主要抓手。

只改 1 不改 2，等于新产品的搜索结果页是一片空白。所以新增产品必须把 2 一并生成。

哪些 section 依赖产品数据、哪些是全站通用
----------------------------------------
依赖数据（本脚本重新生成）：
    #detail-images  详情长图列表（图片张数）
    #glance         tagline + quick_specs 药丸 + 主图 02/03/04 缩略
    #customization  SKU 表 + 包装表
    #specifications 完整规格表
    #pricing        价格阶梯
    #certifications 证书表
    #faq            四条问答
全站通用（照抄模板，一个字不动）：
    #related #feedback #flow #company  —— 这些是店铺级数据，跟具体产品无关

以及 head 里的 title / description / og:* / twitter:* / canonical / 9 条 hreflang，
还有页尾的 window.AQC_PRODUCT。

section 的标题文案（"Product details" / "产品细节" 之类）从模板页里原样取，
不重新翻译 —— 各语种的措辞以现有人工维护的页面为准。

用法
----
    python scripts/gen_product_page.py en  handheld-vacuum eg16pro
    python scripts/gen_product_page.py zh  handheld-vacuum eg16pro
"""
from __future__ import annotations
import html as htmlmod
import io, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = 'https://www.hkdmj.net'
ALL_LANGS = ['en', 'zh', 'ar', 'es', 'fr', 'id', 'ru', 'th', 'vi']

# 每个语种拿哪个产品的页当前面模板（en 是其余 7 个语种的源，zh 手工维护）
TEMPLATE = {'en': 'handheld-vacuum-gv18', 'zh': 'handheld-vacuum-gv18'}
TEMPLATE_DIR = 'handheld-vacuum-gv18'   # 模板页的图片目录名，标题里会嵌它
TEMPLATE_PID = 'gv18'                  # 模板产品 id，用来从 data 里取它的名字/型号


def esc(s):
    return htmlmod.escape('' if s is None else str(s), quote=True)


def read(p):
    return io.open(p, encoding='utf-8', newline='').read()


def pick(d, lang, default=None):
    if isinstance(d, dict):
        v = d.get(lang)
        if v:
            return v
        return d.get('en') or default
    return d if d is not None else default


# ── 从模板页抠出各section 的标签文案 ─────────────────────────────────
LABEL_RE = {
    'label': re.compile(r'<div class="section-label">(.*?)</div>'),
    'title': re.compile(r'<h2 class="section-title">(.*?)</h2>'),
    'sub': re.compile(r'<p class="section-sub">(.*?)</p>'),
}


def section_span(t, sid):
    m = re.search(r'<section[^>]*\bid="%s"[^>]*>' % re.escape(sid), t)
    if not m:
        raise RuntimeError('模板页里找不到 section#%s' % sid)
    depth, i = 0, m.start()
    while i < len(t):
        if t.startswith('<section', i):
            depth += 1
        elif t.startswith('</section>', i):
            depth -= 1
            if depth == 0:
                return m.start(), i + len('</section>')
        i += 1
    raise RuntimeError('section#%s 没有收尾' % sid)


def slice_section(t, sid):
    a, b = section_span(t, sid)
    return t[a:b]


def labels_of(sec):
    out = {}
    for k, rx in LABEL_RE.items():
        m = rx.search(sec)
        out[k] = m.group(1) if m else ''
    return out


def faq_questions(sec):
    return re.findall(r'<summary>(.*?)</summary>', sec, re.S)


# ── 各 section 的生成器 ───────────────────────────────────────────────
def sec_detail_images(tpl, name, d, n):
    lab = labels_of(slice_section(tpl, 'detail-images'))
    # 模板页标题里嵌着模板产品的目录名（"handheld-vacuum-gv18 — detail images"），
    # 必须换成新产品的，否则两个产品的详情区标题一模一样
    title = lab['title'].replace(TEMPLATE_DIR, d)
    imgs = '\n'.join(
        '      <img src="/assets/images/products/%s/detail/%02d.jpg" alt="%s %02d" '
        'loading="lazy" style="width:100%%;height:auto;display:block;margin:0 auto 14px;'
        'border-radius:8px;">' % (d, i, esc(name), i)
        for i in range(1, n + 1))
    return '''<section class="section section-alt" id="detail-images">
  <div class="section-inner">
    <div class="text-center"><div class="section-label">%s</div><h2 class="section-title">%s</h2></div>
    <div class="aqc-ss" style="max-width:750px;margin:32px auto 0;">
%s
    </div>
  </div>
</section>''' % (lab['label'], title, imgs)


def sec_glance(tpl, p, lang, name, tagline, d):
    lab = labels_of(slice_section(tpl, 'glance'))
    metrics = '\n'.join(
        '        <div class="metric"><b>%s</b><span>%s</span></div>'
        % (esc(q['value'][lang] if lang in q['value'] else q['value']['en']),
           esc(pick(q['label'], lang)))
        for q in p['quick_specs'])
    figs = '\n'.join(
        '          <figure><img src="/assets/images/products/%s/%02d.jpg" alt="%s %d" '
        'loading="lazy"><figcaption>%s</figcaption></figure>' % (d, i, esc(name), i, esc(name))
        for i in (2, 3, 4))
    return '''<section class="section" id="glance">
  <div class="section-inner">
    <div class="text-center">
      <h2 class="section-title">%s</h2>
      <p class="section-sub">%s</p>
    </div>
    <div class="aqc-ss">
      <div class="metrics">
%s
      </div>
      <div class="strip">
%s
      </div>
    </div>
  </div>
</section>''' % (lab['title'], tagline, metrics, figs)


def sec_customization(tpl, p, lang):
    lab = labels_of(slice_section(tpl, 'customization'))
    cu = p.get('customization') or {}
    rows = []
    for s in p.get('sku') or []:
        vals = ', '.join(v['name'] for v in s['values'])
        rows.append('          <tr><th scope="row">%s</th><td>%s</td></tr>'
                    % (esc(pick(s['name'], lang)), esc(vals)))
    rows.append('          <tr><th scope="row">%s</th><td>%s</td></tr>'
                % (esc({'en': 'Custom logo', 'zh': '定制logo'}[lang]),
                   '✓' if cu.get('logo') else '—'))
    rows.append('          <tr><th scope="row">%s</th><td>%s</td></tr>'
                % (esc({'en': 'Custom colour', 'zh': '定制颜色'}[lang]),
                   '✓' if cu.get('color') else '—'))
    rows.append('          <tr><th scope="row">%s</th><td>%s</td></tr>'
                % (esc({'en': 'Custom packaging', 'zh': '定制包装'}[lang]),
                   '✓' if cu.get('package') else '—'))
    pk = p.get('packaging') or {}
    pk_rows = []
    for key, lbl in (('unit', {'en': 'Unit', 'zh': '单位'}),
                     ('ctn_size', {'en': 'Carton size', 'zh': '外箱尺寸'}),
                     ('ctn_qty', {'en': 'Carton qty', 'zh': '装箱数'}),
                     ('gross_weight', {'en': 'Gross weight', 'zh': '毛重'})):
        if pk.get(key):
            pk_rows.append('        <tr><th scope="row">%s</th><td>%s</td></tr>'
                           % (esc(lbl.get(lang, lbl['en'])), esc(pk[key])))
    pk_table = ('<table><tbody>\n%s\n      </tbody></table>' % '\n'.join(pk_rows)) if pk_rows else ''
    return '''<section class="section" id="customization">
  <div class="section-inner">
    <div class="text-center">
      <h2 class="section-title">%s</h2>
      <p class="section-sub">%s</p>
    </div>
    <div class="aqc-ss">
      <table>
        <tbody>
%s
        </tbody>
      </table>
      <h3 style="margin:24px 0 8px;font-size:16px;color:#0F172A;">%s</h3>
      %s
    </div>
  </div>
</section>''' % (lab['title'], lab['sub'], '\n'.join(rows),
                 esc({'en': 'Packaging', 'zh': '包装'}[lang]), pk_table)


def sec_specifications(tpl, p, lang, name, tpl_name, tpl_model):
    lab = labels_of(slice_section(tpl, 'specifications'))
    rows = '\n'.join(
        '            <tr><th scope="row">%s</th><td>%s</td></tr>'
        % (esc(pick(s['label'], lang)), esc(pick(s['value'], lang)))
        for s in p['specs'])
    caption = {'en': 'Written specification table (text-based)',
               'zh': '文字版规格表（可直接复制到邮件/Excel）'}[lang]
    # 模板副标题是"产品名 — Model 型号"，两个都要换成新产品的
    model = next((pick(s['value'], lang) for s in p['specs']
                  if pick(s['label'], lang) in ('Model', '型号')), '')
    sub = lab['sub'].replace(tpl_name or '\0', name).replace(tpl_model or '\0', model)
    return '''<section class="section" id="specifications">
  <div class="section-inner">
    <div class="text-center">
      <h2 class="section-title">%s</h2>
      <p class="section-sub">%s</p>
    </div>
    <div class="aqc-ss">
      <table>
        <caption style="text-align:left;padding:0 0 10px;color:#64748B;font-size:13px;">%s</caption>
        <tbody>
%s
        </tbody>
      </table>
    </div>
  </div>
</section>''' % (lab['title'], sub, caption, rows)


def sec_pricing(tpl, p, lang):
    lab = labels_of(slice_section(tpl, 'pricing'))
    moq = (p.get('moq') or {}).get('value')
    ladder = p.get('price_ladder') or []
    if ladder:
        rows = '\n'.join(
            '            <tr><td>%s</td><td>US$%s / pc</td></tr>'
            % ('%s–%s pcs' % (r['min'], r['max']) if r.get('max') else '%s–+ pcs' % r['min'],
               r['price'])
            for r in ladder)
        thead = ('<thead><tr><th scope="col">%s</th><th scope="col">%s</th></tr></thead>'
                 % (esc({'en': 'Order quantity', 'zh': '订购数量'}[lang]),
                    esc({'en': 'Unit price', 'zh': '单价'}[lang])))
    else:
        pi = p.get('price_indicator') or {}
        rng = ('US$%s / pc' % pi['min'] if pi.get('min') == pi.get('max')
               else 'US$%s–%s / pc' % (pi.get('min'), pi.get('max')))
        rows = '            <tr><td>%s–999 pcs</td><td>%s</td></tr>' % (moq, rng)
        thead = ('<thead><tr><th scope="col">%s</th><th scope="col">%s</th></tr></thead>'
                 % (esc({'en': 'Order quantity', 'zh': '订购数量'}[lang]),
                    esc({'en': 'Unit price', 'zh': '单价'}[lang])))
    note = ''
    if p.get('shipping_fee_usd'):
        note = ('      <p class="aqc-note">%s US$%s</p>'
                % (esc({'en': 'Platform shipping estimate:',
                        'zh': '平台运费估算：'}[lang]), esc(p['shipping_fee_usd'])))
    return '''<section class="section section-alt" id="pricing">
  <div class="section-inner">
    <div class="text-center">
      <h2 class="section-title">%s</h2>
      <p class="section-sub">%s</p>
    </div>
    <div class="aqc-ss">
      <table>
%s
        <tbody>
%s
        </tbody>
      </table>
%s
    </div>
  </div>
</section>''' % (lab['title'], lab['sub'], thead, rows, note)


def sec_certifications(tpl, p, lang):
    lab = labels_of(slice_section(tpl, 'certifications'))
    certs = p.get('certificates') or []
    if certs:
        rows = '\n'.join(
            '          <tr><td>%s</td><td>%s</td><td>%s</td><td>%s</td><td>%s</td></tr>'
            % (esc(c.get('name')), esc(c.get('certNo')), esc(c.get('expiredDate')),
               esc({'en': 'Alibaba verification', 'zh': '阿里验证'}[lang] if c.get('verified') else '—'),
               ('<a href="%s" target="_blank" rel="noopener">%s</a>'
                % (esc(c['image'].replace('.webp', '.jpg')),
                   esc({'en': 'View', 'zh': '查看'}[lang]))) if c.get('image') else '—')
            for c in certs)
    else:
        rows = ''
    return '''<section class="section section-alt" id="certifications">
  <div class="section-inner">
    <div class="text-center">
      <h2 class="section-title">%s</h2>
    </div>
    <div class="aqc-ss">
      <table>
        <thead><tr><th scope="col">%s</th><th scope="col">%s</th><th scope="col">%s</th><th scope="col">%s</th><th scope="col"></th></tr></thead>
        <tbody>
%s
        </tbody>
      </table>
      <p class="aqc-note">%s</p>
    </div>
  </div>
</section>''' % (lab['title'],
                 esc({'en': 'Certificate', 'zh': '证书'}[lang]),
                 esc({'en': 'Certificate no.', 'zh': '证书编号'}[lang]),
                 esc({'en': 'Valid until', 'zh': '有效期至'}[lang]),
                 esc({'en': 'Alibaba verification', 'zh': '阿里验证'}[lang]),
                 rows,
                 esc(pick(p.get('cert_note'), lang)))


def faq_answers(p, lang):
    """FAQ 四条问答的答案文本。#faq section 和 FAQPage JSON-LD 共用同一份，
    两边各写一遍必然漂移 —— 页面上的答案和结构化数据里的答案不一致，
    Google 会判为结构化数据与页面内容不符。"""
    moq = (p.get('moq') or {}).get('value')
    pi = p.get('price_indicator') or {}
    pr = ('US$%s/pc' % pi['min'] if pi.get('min') == pi.get('max')
          else 'US$%s–%s/pc' % (pi.get('min'), pi.get('max')))
    sample = p.get('sample') or {}
    sn = (sample.get('qty') or 1)
    opts = '; '.join('%s: %s' % (pick(s['name'], lang),
                                 ', '.join(v['name'] for v in s['values']))
                     for s in (p.get('sku') or []))
    return {
        'en': ['MOQ is %s pcs. FOB price is %s depending on quantity. '
               'Samples are available (up to %s pc).' % (moq, pr, sn),
               'Yes — OEM/ODM with these configurable options: %s. '
               'Custom colour orders start at a higher MOQ, confirmed per option.' % opts,
               '%s We can share the test documentation for your market-entry review.'
               % pick(p.get('cert_note'), lang),
               'Yes, samples are supported (up to %s pc) so you can validate quality '
               'before committing to %s pcs.' % (sn, moq)],
        'zh': ['起订量 %s 台，FOB 价格 %s（按数量浮动），可打样（最多 %s 台）。' % (moq, pr, sn),
               '支持 OEM/ODM 定制，可配置项：%s。定制颜色订单起订量更高，按选项确认。' % opts,
               '%s 可按需提供测试文件。' % pick(p.get('cert_note'), lang),
               '支持打样（最多 %s 台），可先验证品质再下%s 台的批量订单。' % (sn, moq)],
    }[lang]


def sec_faq(tpl, p, lang, name, tpl_name):
    qs = faq_questions(slice_section(tpl, 'faq'))
    assert len(qs) == 4, '模板页的 FAQ 不是 4 条（%d），得先对齐模板' % len(qs)
    # 问题句式沿用模板（各语种措辞以现有人工页面为准），
    # 但要把模板产品的名字换掉 —— 否则页面上会出现两个产品的名字。
    qs = [q.replace(tpl_name, name) if tpl_name else q for q in qs]
    T = faq_answers(p, lang)
    body = '\n'.join(
        '        <details>\n          <summary>%s</summary>\n          <p>%s</p>\n        </details>'
        % (esc(q), esc(a)) for q, a in zip(qs, T))
    lab = labels_of(slice_section(tpl, 'faq'))
    return qs, '''<section class="section" id="faq">
  <div class="section-inner">
    <div class="text-center">
      <h2 class="section-title">%s</h2>
    </div>
    <div class="aqc-ss">
%s
    </div>
  </div>
</section>''' % (lab['title'], body)


def rewrite_faq_jsonld(t, questions, answers):
    """重建第二段 ld+json（FAQPage）。

    模板页里其实有**两段** ld+json：Product 和 FAQPage。只改第一段的话，
    FAQ 富媒体结果还会挂着模板产品的问答。
    """
    blocks = list(re.finditer(r'<script type="application/ld\+json">.*?</script>', t, re.S))
    assert len(blocks) == 2, '模板页的 ld+json 块数不是 2（%d）' % len(blocks)
    faq_m = blocks[1]
    assert '"FAQPage"' in faq_m.group(0), '第二段 ld+json 不是 FAQPage'
    ld = {
        '@context': 'https://schema.org',
        '@type': 'FAQPage',
        'mainEntity': [
            {'@type': 'Question', 'name': q,
             'acceptedAnswer': {'@type': 'Answer', 'text': a}}
            for q, a in zip(questions, answers)
        ],
    }
    new = '<script type="application/ld+json">\n%s\n</script>' % json.dumps(
        ld, ensure_ascii=False, indent=2)
    return t[:faq_m.start()] + new + t[faq_m.end():]


# ── head / AQC_PRODUCT ───────────────────────────────────────────────
def rewrite_jsonld(t, p, lang, cat, pid, name, d):
    """重建 <script type="application/ld+json"> 的 Product 结构化数据。

    这是搜索引擎真正读的那份产品数据（富媒体摘要/价格/评分都靠它）。
    忘了改的话，新产品的搜索结果会挂着**模板产品**的图和描述 —— 而且页面本身
    看起来完全正常，只有 Google 富媒体测试会暴露。
    """
    m = re.search(r'<script type="application/ld\+json">.*?</script>', t, re.S)
    assert m, '模板页里没有 ld+json'
    slug = '%s-%s' % (cat, pid)
    url = '%s/%s/%s.html' % (SITE, lang, slug)
    imgs = ['%s/assets/images/products/%s/%02d.jpg' % (SITE, d, i) for i in range(1, 7)]
    pi = p.get('price_indicator') or {}
    cur = pi.get('currency') or 'USD'
    sup = p.get('supplier') or {}
    ld = {
        '@context': 'https://schema.org',
        '@type': 'Product',
        '@id': url + '#product',
        'name': name,
        'description': pick(p.get('description'), lang),
        'image': imgs,
        'url': url,
        'sku': pid,
        'mpn': pid,
        'brand': {'@type': 'Brand', 'name': 'AquaClean Home'},
        'manufacturer': {
            '@id': '%s/about.html#organization' % SITE,
            '@type': 'Organization',
            'name': 'Hong Kong Damaijia Technology Co., Limited',
            'url': SITE,
        },
        'category': pick(p.get('category_name'), lang),
        'additionalProperty': [
            {'@type': 'PropertyValue', 'name': pick(s['label'], lang), 'value': pick(s['value'], lang)}
            for s in (p.get('specs') or [])
        ],
        'offers': {
            '@type': 'AggregateOffer',
            'priceCurrency': cur,
            'lowPrice': pi.get('min'),
            'highPrice': pi.get('max'),
            'offerCount': '1',
            'availability': 'https://schema.org/InStock',
            'seller': {'@type': 'Organization', 'name': 'Hong Kong Damaijia Technology Co., Limited'},
        },
    }
    if p.get('moq'):
        ld['offers']['eligibleQuantity'] = {
            '@type': 'QuantitativeValue',
            'minValue': p['moq'].get('value'),
            'unitCode': 'C62',
        }
    if sup.get('country'):
        ld['manufacturer']['address'] = {
            '@type': 'PostalAddress',
            'addressCountry': 'HK',
            'addressRegion': sup.get('province') or '',
        }
    new = '<script type="application/ld+json">\n%s\n</script>' % json.dumps(
        ld, ensure_ascii=False, indent=2)
    return t[:m.start()] + new + t[m.end():]


def rewrite_head(t, lang, cat, pid, name, tagline, d):
    slug = '%s-%s' % (cat, pid)
    page = '%s/%s.html' % (lang, slug)
    url = '%s/%s' % (SITE, page)
    title = '%s — AquaClean Home' % name
    desc = '%s | AquaClean OEM/ODM manufacturer. Contact us for wholesale pricing.' % tagline

    def sub1(rx, new, s):
        # 用 lambda 返回替换串，避免替换内容里的反斜杠/\\g 被当成反向引用
        out, n = re.compile(rx, re.S).subn(lambda m: new, s, count=1)
        assert n == 1, 'head 里没找到待替换项：%s' % rx
        return out

    t = sub1(r'<title>.*?</title>', '<title>%s</title>' % esc(title), t)
    t = sub1(r'<meta name="description" content=".*?">',
             '<meta name="description" content="%s">' % esc(desc), t)
    # ⚠️ og:* 用 property=，twitter:* 用 name=。模板页两种都有，写错就匹配不到。
    for prop in ('og:title', 'twitter:title'):
        a = 'property' if prop.startswith('og:') else 'name'
        t = sub1(r'<meta %s="%s" content=".*?">' % (a, prop),
                 '<meta %s="%s" content="%s">' % (a, prop, esc(title)), t)
    for prop in ('og:description', 'twitter:description'):
        a = 'property' if prop.startswith('og:') else 'name'
        t = sub1(r'<meta %s="%s" content=".*?">' % (a, prop),
                 '<meta %s="%s" content="%s">' % (a, prop, esc(desc)), t)
    t = sub1(r'<meta property="og:url" content=".*?">',
             '<meta property="og:url" content="%s">' % url, t)
    for prop in ('og:image', 'twitter:image'):
        a = 'property' if prop.startswith('og:') else 'name'
        t = sub1(r'<meta %s="%s" content=".*?">' % (a, prop),
                 '<meta %s="%s" content="%s/assets/images/products/%s/01.webp">'
                 % (a, prop, SITE, d), t)
    t = sub1(r'<link rel="canonical" href=".*?">',
             '<link rel="canonical" href="%s">' % url, t)
    t = sub1(r'<link rel="alternate" hreflang="x-default" href=".*?">',
             '<link rel="alternate" hreflang="x-default" href="%s">' % url, t)
    for lg in ALL_LANGS:
        t = sub1(r'<link rel="alternate" hreflang="%s" href=".*?">' % lg,
                 '<link rel="alternate" hreflang="%s" href="%s/%s/%s.html">' % (lg, SITE, lg, slug), t)
    return t


def rewrite_hero(t, name, tagline, moq, pi, cat):
    a = t.index('<div id="aqc-detail-mount">') + len('<div id="aqc-detail-mount">')
    b = t.index('</div>', a)
    pr = ('US$%s–%s / pc' % (pi.get('min'), pi.get('max')) if pi.get('min') != pi.get('max')
          else 'US$%s / pc' % pi.get('min'))
    hero = ('<div class="section-inner" style="max-width:1100px;margin:0 auto;padding:24px;">'
            '<h1>%s</h1><h2>%s</h2><p>%s</p>'
            '<p><a href="/%s/%s/">%s</a></p>'
            '<p><a href="/%s/oem-cordless-vacuum-manufacturer/">%s</p></div>'
            % (esc(name), tagline, esc('MOQ %s pcs · %s' % (moq, pr)),
               cat, cat,
               esc({'en': 'View full specifications and request a quote',
                    'zh': '查看完整规格并索取报价'}[lang_of(name)]),
               lang_of(name),
               esc({'en': 'OEM / ODM custom manufacturing (logo, colour, packaging) →',
                    'zh': 'OEM / ODM 定制（logo、颜色、包装）→'}[lang_of(name)])))
    return t[:a] + hero + t[b:]


_LANG_OF = {}


def lang_of(_):
    return _LANG_OF.get('cur', 'en')


def rewrite_aqc(t, cat, pid, lang, category_name):
    old = re.search(r'window\.AQC_PRODUCT = \{.*?\};', t, re.S)
    assert old, '找不到 window.AQC_PRODUCT'
    new = ('window.AQC_PRODUCT = {\n  category: %s,\n  id: %s,\n  lang: %s,\n'
           '  categoryName: %s\n};'
           % (json.dumps(cat), json.dumps(pid), json.dumps(lang),
              json.dumps(category_name, ensure_ascii=False)))
    return t[:old.start()] + new + t[old.end():]


def main():
    if len(sys.argv) < 4:
        print(__doc__)
        return 1
    lang, cat, pid = sys.argv[1], sys.argv[2], sys.argv[3]
    _LANG_OF['cur'] = lang
    assert lang in ('en', 'zh'), '只负责 en/zh（其余 7 个语种交给 gen_pages.py）'
    apply = '--apply' in sys.argv

    tpl_id = TEMPLATE.get(lang, 'handheld-vacuum-gv18')
    tpl_path = os.path.join(ROOT, lang, '%s.html' % tpl_id)
    tpl = read(tpl_path)
    # 模板统一成 LF 处理，输出时再按目标文件的行尾风格写回去
    tpl = tpl.replace('\r\n', '\n')

    data = json.loads(read(os.path.join(ROOT, 'data', 'products', cat + '.json')))
    p = [x for x in data['products'] if x['id'] == pid]
    assert p, 'data/products/%s.json 里没有 %s' % (cat, pid)
    p = p[0]

    d = '%s-%s' % (cat, pid)
    name = pick(p['name'], lang)
    tagline = esc(pick(p['tagline'], lang))
    moq = (p.get('moq') or {}).get('value')
    pi = p.get('price_indicator') or {}
    n_detail = len(p.get('detail_images') or [])

    # 模板产品自己的名字和型号：模板的副标题 / FAQ 问题句式里嵌着它们，
    # 不替换的话新页面会同时出现两个产品的名字。
    tdata = json.loads(read(os.path.join(ROOT, 'data', 'products', cat + '.json')))
    tp = [x for x in tdata['products'] if x['id'] == TEMPLATE_PID]
    assert tp, '模板产品 %s 不在 data 里' % TEMPLATE_PID
    tpl_name = pick(tp[0]['name'], lang)
    tpl_model = next((pick(s['value'], lang) for s in (tp[0].get('specs') or [])
                      if pick(s['label'], lang) in ('Model', '型号')), '')

    t = tpl
    t = rewrite_head(t, lang, cat, pid, name, tagline, d)
    t = rewrite_jsonld(t, p, lang, cat, pid, name, d)
    t = rewrite_hero(t, name, tagline, moq, pi, cat)

    for sid, gen in (
        ('detail-images', lambda: sec_detail_images(tpl, name, d, n_detail)),
        ('glance', lambda: sec_glance(tpl, p, lang, name, tagline, d)),
        ('customization', lambda: sec_customization(tpl, p, lang)),
        ('specifications', lambda: sec_specifications(tpl, p, lang, name, tpl_name, tpl_model)),
        ('pricing', lambda: sec_pricing(tpl, p, lang)),
        ('certifications', lambda: sec_certifications(tpl, p, lang)),
        ('faq', None),   # FAQ 要连问答一起拿出来给 JSON-LD 用，单独处理
    ):
        if gen is None:
            continue
        a, b = section_span(t, sid)
        t = t[:a] + gen() + t[b:]

    questions, faq_sec = sec_faq(tpl, p, lang, name, tpl_name)
    a, b = section_span(t, 'faq')
    t = t[:a] + faq_sec + t[b:]
    t = rewrite_faq_jsonld(t, questions, faq_answers(p, lang))

    t = rewrite_aqc(t, cat, pid, lang, p.get('category_name', {}).get(lang)
                    or p.get('category_name', {}).get('en', ''))

    # ── 断言 ─────────────────────────────────────────────────────────
    assert t.count('<section') == tpl.count('<section'), 'section 数量对不上'
    assert d in t, '新页面里没有 %s 的图片路径' % d
    assert 'id: "%s"' % pid in t, 'AQC_PRODUCT 的 id 不对'
    assert 'hreflang="vi" href="%s/%s/%s.html"' % (SITE, 'vi', d) in t, 'hreflang 不全'
    assert name.split()[0] in t, 'h1 名字没进去'
    if n_detail:
        assert ('/assets/images/products/%s/detail/%02d.jpg' % (d, n_detail)) in t, \
            '最后一张长图没写进去'
    # 页面上不能残留模板产品的名字或型号
    for bad in ('gv18', 'GV18', 'V18 Cordless'):
        assert bad not in t, '页面里还残留模板产品痕迹：%s' % bad

    out_path = os.path.join(ROOT, lang, '%s.html' % d)
    # 目标目录里既有页面是什么行尾，就跟着它
    existing = read(out_path) if os.path.exists(out_path) else None
    if existing is not None and '\r\n' not in existing:
        out = t
    else:
        out = t.replace('\n', '\r\n')

    print('生成 %s（%d 字符，%d 张详情长图）' % (os.path.relpath(out_path, ROOT), len(out), n_detail))
    if not apply:
        print('预演模式。加 --apply 写入。')
        return 0
    with io.open(out_path, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    print('已写入 %s' % os.path.relpath(out_path, ROOT))
    return 0


if __name__ == '__main__':
    sys.exit(main())