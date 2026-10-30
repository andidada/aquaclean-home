# -*- coding: utf-8 -*-
"""首页新增第 10 张品类卡（hands-free-soap-dispenser）。

首页是 **双份数据**：data/pages/home/<lang>.json 供 JS 用，<lang>/index.html
里还有一份预渲染卡（<!-- P9 --> 注释锚定）供爬虫/禁用 JS 的访客。两边都要加。

幂等：JSON 里已有 p10 / HTML 里已有 <!-- P10 --> 就跳过。
"""
from __future__ import annotations
import html as htmlmod
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLUG = 'hands-free-soap-dispenser'
IMG = '../assets/images/products/21-hands-free-soap-dispenser.webp?v=20261030a'
LANGS = ['en', 'zh', 'ar', 'es', 'fr', 'id', 'ru', 'th', 'vi']

NAME = {
    'en': 'Hands-free Soap Dispenser',
    'zh': '免接触泡沫洗手机',
    'ar': 'موزع صابون أوتوماتيكي',
    'es': 'Dispensador automático de jabón',
    'fr': 'Distributeur automatique de savon',
    'id': 'Dispenser sabun otomatis',
    'ru': 'Автоматический дозатор мыла',
    'th': 'เครื่องจ่ายสบู่อัตโนมัติ',
    'vi': 'Bình đựng xà phòng tự động',
}
DESC = {
    'en': 'Touch-free automatic foam soap dispenser with four output levels (0.25–1.0 s). Infra-red sensor, USB-C rechargeable battery and a 300 ml visible tank.',
    'zh': '免接触自动泡沫洗手机，四档出液（0.25–1.0 秒）。红外感应、USB-C 充电电池、300 ml 可视水箱。',
    'ar': 'موزع صابون رغوي أوتوماتيكي بدون لمس بأربعة مستويات ضخ (٠٫٢٥–١٫٠ ثانية). مستشعر أشعة تحت الحمراء، بطارية قابلة للشحن USB-C وخزان مرئي ٣٠٠ مل.',
    'es': 'Dispensador automático de espuma de jabón sin contacto con cuatro niveles de salida (0,25–1,0 s). Sensor infrarrojo, batería recargable USB-C y depósito visible de 300 ml.',
    'fr': 'Distributeur automatique de mousse de savon sans contact à quatre niveaux de distribution (0,25–1,0 s). Capteur infrarouge, batterie rechargeable USB-C et réservoir visible de 300 ml.',
    'id': 'Dispenser sabun busa otomatis tanpa sentuh dengan empat tingkat keluaran (0,25–1,0 dtk). Sensor inframerah, baterai isi ulang USB-C, dan tangki 300 ml yang terlihat.',
    'ru': 'Бесконтактный автоматический пенный дозатор мыла с четырьмя уровнями подачи (0,25–1,0 с). Инфракрасный датчик, аккумулятор с зарядкой USB-C и видимый бак на 300 мл.',
    'th': 'เครื่องจ่ายสบู่โฟมอัตโนมัติแบบไม่ต้องสัมผัส มีระดับจ่าย 4 ระดับ (0.25–1.0 วินาที) เซ็นเซอร์อินฟราเรด แบตเตอรี่ชาร์จ USB-C และถังใส 300 มล.',
    'vi': 'Bình đựng xà phòng bọt tự động không cần chạm với bốn mức nhả (0,25–1,0 giây). Cảm biến hồng ngoại, pin sạc USB-C và bình chứa 300 ml có cửa quan sát.',
}
TAGS = {
    'en': ['4 Levels', '0.25–1.0s', 'USB-C'],
    'zh': [],
    'ar': ['4 مستويات', '٠٫٢٥–١٫٠ ثانية', 'USB-C'],
    'es': ['4 niveles', '0,25–1,0 s', 'USB-C'],
    'fr': ['4 niveaux', '0,25–1,0 s', 'USB-C'],
    'id': ['4 tingkat', '0,25–1,0 dtk', 'USB-C'],
    'ru': ['4 режима', '0,25–1,0 с', 'USB-C'],
    'th': ['4 ระดับ', '0.25–1.0 วินาที', 'USB-C'],
    'vi': ['4 mức', '0,25–1,0 giây', 'USB-C'],
}


def esc(s):
    return htmlmod.escape(str(s), quote=True)


def read(p):
    return io.open(p, encoding='utf-8', newline='').read()


def write(p, s):
    io.open(p, 'w', encoding='utf-8', newline='').write(s)


def patch_json(lang, apply_this):
    p = os.path.join(ROOT, 'data/pages/home', lang + '.json')
    raw = read(p)
    d = json.loads(raw)
    if any(x.get('id') == 'p10' for x in d['products']):
        print('  = %s home json already has p10' % lang)
        return
    p9 = [x for x in d['products'] if x.get('id') == 'p9'][0]
    item = {
        'id': 'p10',
        'name': NAME[lang],
        'slug': '',
        'desc': DESC[lang],
        'img': IMG,
        'btn_text': p9['btn_text'],
        'btn_href': '/%s/%s/' % (lang, SLUG),
        'tags': TAGS[lang],
    }
    d['products'].append(item)
    text = json.dumps(d, ensure_ascii=False, indent=2).replace('\n', '\r\n')
    # round-trip 校验：未改的键顺序必须完全一致
    check = json.loads(text)
    assert check == d
    if apply_this:
        write(p, text)
    print('  + %s home json p10 added (%d products)' % (lang, len(d['products'])))


def card_html(lang, tpl):
    doc = tpl
    doc, n1 = re.subn(r'(<h3>)(.*?)(</h3>)',
                      lambda m: m.group(1) + esc(NAME[lang]) + m.group(3), doc, count=1)
    doc, n2 = re.subn(r'(<p>)(.*?)(</p>)',
                      lambda m: m.group(1) + esc(DESC[lang]) + m.group(3), doc, count=1)
    doc, n3 = re.subn(r'(<img src=")[^"]*(" alt=")[^"]*(")',
                      lambda m: m.group(1) + IMG + m.group(2) + esc(NAME[lang]) + m.group(3),
                      doc, count=1)
    doc, n4 = re.subn(r'(<a href=")[^"]*(" class="btn btn-primary")',
                      lambda m: m.group(1) + '/%s/%s/' % (lang, SLUG) + m.group(2),
                      doc, count=1)
    tags = TAGS[lang]
    it = iter(tags)

    def tag_sub(m):
        try:
            v = next(it)
        except StopIteration:
            return m.group(0)
        # group(1)=<span …>、group(2)=旧文本、group(3)=</span>
        return m.group(1) + esc(v) + m.group(3)

    doc, n5 = re.subn(r'(<span class="product-tag">)(.*?)(</span>)', tag_sub, doc)
    if not (n1 and n2 and n3 and n4):
        raise SystemExit('card_html failed: %s n=(%d,%d,%d,%d)' % (lang, n1, n2, n3, n4))
    if bool(tags) and n5 != len(tags):
        raise SystemExit('tags mismatch %s: replaced %d of %d' % (lang, n5, len(tags)))
    return doc


def patch_html(lang, apply_this):
    p = os.path.join(ROOT, lang, 'index.html')
    doc = read(p)
    if '<!-- P10 -->' in doc:
        print('  = %s index.html already has P10' % lang)
        return
    # 取 P9 卡片作为模板（到它闭合的 </div> 为止）
    start = doc.index('<!-- P9 -->')
    # 取 P9 卡片整块作为模板：必须按 <div> 深度配对找闭合，
    # 否则会在 product-body 的 </div> 处提前收尾，把新卡塞进旧卡肚子里
    body_start = doc.index('<div class="product-card">', start)
    pos, depth = body_start, 0
    tok = re.compile(r'<div\b|</div>')
    while True:
        m = tok.search(doc, pos)
        depth += -1 if m.group(0) == '</div>' else 1
        pos = m.end()
        if depth == 0:
            break
    body_end = pos
    tpl = doc[body_start:body_end]
    new_card = card_html(lang, tpl)
    insert = '\n      <!-- P10 -->\n      ' + new_card
    out = doc[:body_end] + insert + doc[body_end:]
    # P9 注释块内的模板注释顺序：P9 注释 -> 卡片；新卡片紧跟其后
    if apply_this:
        write(p, out)
    print('  + %s index.html P10 inserted (tags=%d)' % (lang, len(TAGS[lang])))


def main():
    apply_this = '--apply' in sys.argv
    for lang in LANGS:
        patch_json(lang, apply_this)
        patch_html(lang, apply_this)
    print('done%s' % ('' if apply_this else '  (dry-run)'))


if __name__ == '__main__':
    main()
