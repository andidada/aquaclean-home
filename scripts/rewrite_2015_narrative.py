#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
rewrite_2015_narrative.py — 把「2015 年公司创立」改写为「2015 年工厂投产」

背景
----
2026-10-08 全站把公司主体换成 Hong Kong Damaijia Technology Co., Limited
（founded 2024 / 总部香港 / 工厂在宁波）。但品牌叙事还停在旧的
「2015 年在浙江宁波创立」，于是出现自相矛盾：
    company.json  founded = 2024
    页面文案      since 2015 / 2015 年创立
客户做尽调时公司注册年份可查，这个矛盾是实打实的信用风险。

用户 2026-10-13 拍板：**2015 改成制造经验年** —— 保留 2015 但把主语从
「公司创立」换成「宁波工厂投产」，并点明香港公司 2024 注册。
这样营销上的「11 年制造经验」保住了，事实也经得起查。

做法
----
只做字符串字面量替换，不整体 json.dumps —— 保持最小 diff，
且这些文件里混着 emoji / 泰文 / 阿拉伯文，重写容易翻车。
每个替换都断言：旧值存在且只出现 1 次、值里没有引号和反斜杠、
替换后 JSON 仍能解析、新值确实到位。
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── 首页 hero 徽章 ────────────────────────────────────────────────
HERO_BADGE = {
    'en': ('\U0001F1E8\U0001F1F3 OEM / ODM Manufacturer · Since 2015',
           '\U0001F1E8\U0001F1F3 OEM / ODM · Manufacturing since 2015'),
    'zh': ('OEM/ODM制造商 · 始于2015年',
           'OEM/ODM制造商 · 2015 年起投产'),
    'es': ('\U0001F1E8\U0001F1F3 Fabricante OEM / ODM · Desde 2015',
           '\U0001F1E8\U0001F1F3 OEM / ODM · En producción desde 2015'),
    'fr': ('\U0001F1E8\U0001F1F3 Fabricant OEM / ODM · Depuis 2015',
           '\U0001F1E8\U0001F1F3 OEM / ODM · En production depuis 2015'),
    'id': ('\U0001F1E8\U0001F1F3 Produsen OEM / ODM · Sejak 2015',
           '\U0001F1E8\U0001F1F3 OEM / ODM · Berproduksi sejak 2015'),
    'ru': ('\U0001F1E8\U0001F1F3 OEM / ODM Производитель · С 2015 года',
           '\U0001F1E8\U0001F1F3 OEM / ODM · Производство с 2015 года'),
    'th': ('\U0001F1E8\U0001F1F3 ผู้ผลิต OEM / ODM · ตั้งแต่ปี 2015',
           '\U0001F1E8\U0001F1F3 OEM / ODM · ผลิตตั้งแต่ปี 2015'),
    'vi': ('\U0001F1E8\U0001F1F3 Nhà Sản Xuất OEM / ODM · Kể Từ 2015',
           '\U0001F1E8\U0001F1F3 OEM / ODM · Sản xuất từ 2015'),
    'ar': ('\U0001F1E8\U0001F1F3 شركة تصنيع OEM / ODM · منذ 2015',
           '\U0001F1E8\U0001F1F3 OEM / ODM · ننتج منذ 2015'),
}

# ── 页脚品牌描述（一句话讲清：宁波工厂 2015 起生产 + 香港公司 2024 注册）──
FOOTER_DESC = {
    'en': ('Professional manufacturer of smart home cleaning appliances. '
           'OEM/ODM solutions for brands worldwide since 2015.',
           'Manufacturer of smart home cleaning appliances. Our Ningbo plant '
           'has produced for global brands since 2015; Hong Kong-registered '
           'company handling worldwide OEM/ODM.'),
    'zh': ('专业智能家用清洁电器制造商。自2015年起为全球品牌提供OEM/ODM解决方案。',
           '智能家用清洁电器制造商。宁波工厂自 2015 年起为全球品牌生产；'
           '香港注册公司负责全球 OEM/ODM 业务。'),
    'es': ('Fabricante profesional de electrodomésticos inteligentes de limpieza '
           'para el hogar. Soluciones OEM/ODM para marcas globales desde 2015.',
           'Fabricante de electrodomésticos inteligentes de limpieza para el '
           'hogar. Nuestra planta de Ningbo produce para marcas globales desde '
           '2015; empresa registrada en Hong Kong que gestiona el OEM/ODM mundial.'),
    'fr': ("Fabricant professionnel d'appareils de nettoyage domestique "
           "intelligents. Solutions OEM/ODM pour des marques du monde entier "
           "depuis 2015.",
           "Fabricant d'appareils de nettoyage domestique intelligents. Notre "
           "usine de Ningbo produit pour des marques mondiales depuis 2015 ; "
           "société enregistrée à Hong Kong gérant l'OEM/ODM international."),
    'id': ('Produsen peralatan kebersihan rumah cerdas profesional. Solusi '
           'OEM/ODM untuk merek global sejak 2015.',
           'Produsen peralatan kebersihan rumah cerdas. Pabrik Ningbo kami '
           'memproduksi untuk merek global sejak 2015; perusahaan terdaftar di '
           'Hong Kong yang menangani OEM/ODM global.'),
    'ru': ('Профессиональный производитель умной бытовой клининговой техники. '
           'OEM/ODM решения для брендов по всему миру с 2015 года.',
           'Производитель умной бытовой клининговой техники. Наш завод в Нинбо '
           'производит продукцию для мировых брендов с 2015 года; компания '
           'зарегистрирована в Гонконге и ведёт OEM/ODM по всему миру.'),
    'th': ('ผู้ผลิตอุปกรณ์ทำความสะอาดบ้านอัจฉริยะระดับมืออาชีพ บริการ OEM/ODM '
           'สำหรับแบรนด์ทั่วโลกตั้งแต่ปี 2015',
           'ผู้ผลิตอุปกรณ์ทำความสะอาดบ้านอัจฉริยะ โรงงานหนิงปัวของเราผลิตให้'
           'แบรนด์ระดับโลกตั้งแต่ปี 2015 บริษัทจดทะเบียนในฮ่องกงดูแล OEM/ODM '
           'ทั่วโลก'),
    'vi': ('Nhà sản xuất chuyên nghiệp thiết bị làm sạch nhà thông minh. Giải '
           'pháp OEM/ODM cho các thương hiệu toàn cầu kể từ 2015.',
           'Nhà sản xuất thiết bị làm sạch nhà thông minh. Nhà máy Ninh Ba của '
           'chúng tôi sản xuất cho các thương hiệu toàn cầu từ 2015; công ty '
           'đăng ký tại Hong Kong phụ trách OEM/ODM toàn cầu.'),
    'ar': ('شركة تصنيع احترافية لأجهزة تنظيف المنزل الذكية. حلول OEM/ODM '
           'للعلامات التجارية العالمية منذ 2015.',
           'شركة تصنيع أجهزة تنظيف المنزل الذكية. مصنعنا في نينغبو ينتج '
           'للعلامات التجارية العالمية منذ 2015؛ وشركة مسجلة في هونغ كونغ تتولى '
           'خدمات OEM/ODM عالميًا.'),
}

# i18n/ar.json 的措辞和 home/ar.json 差一个词（حول العالم vs العالمية），
# 旧值必须分开给，但新值一样。
I18N_BRANDDESC_OLD = {
    'ar': 'شركة تصنيع احترافية لأجهزة تنظيف المنزل الذكية. حلول OEM/ODM '
          'للعلامات التجارية حول العالم منذ 2015.',
}

# ── 关于我们 ──────────────────────────────────────────────────────
ABOUT = {
    'en': {
        'badge': ('\U0001F3ED Since 2015 · Ningbo, China',
                  '\U0001F3ED Ningbo Plant since 2015 · HK-registered 2024'),
        'story': ('Founded in 2015 in Ningbo, Zhejiang, AquaClean began with one '
                  'goal: make professional-grade cleaning technology accessible '
                  'to households everywhere. What started as a single handheld '
                  'vacuum line has grown into a full portfolio of smart cleaning '
                  'appliances.',
                  'Our Ningbo plant has been building cordless vacuums and '
                  'cleaning appliances since 2015. In 2024, Hong Kong Damaijia '
                  'Technology Co., Limited was established to bring that '
                  'manufacturing base to B2B partners worldwide — what started '
                  'as a single handheld vacuum line is now a full portfolio of '
                  'smart cleaning appliances.'),
        'mile_h4': ('Founded in Ningbo', 'Ningbo Plant in Production'),
    },
    'zh': {
        'badge': ('\U0001F3ED 始于 2015 · 中国宁波',
                  '\U0001F3ED 宁波工厂始于 2015 · 香港公司 2024 年注册'),
        'story': ('2015 年，AquaClean 在浙江宁波创立，初衷只有一个：让专业级清洁'
                  '科技走进千家万户。从一条手持吸尘器产品线起步，如今已发展成完整'
                  '的智能清洁电器产品矩阵。',
                  '我们的宁波工厂自 2015 年起生产无线吸尘器与清洁电器。2024 年，'
                  '香港大迈嘉科技有限公司（Hong Kong Damaijia Technology Co., '
                  'Limited）成立，把这套制造能力带给全球 B2B 客户——从一条手持'
                  '吸尘器产品线起步，如今已发展成完整的智能清洁电器产品矩阵。'),
        'mile_h4': ('宁波创立', '宁波工厂投产'),
    },
}


def safe(s):
    """值里不能有引号或反斜杠，否则 '"'+v+'"' 这种朴素替换会写出坏 JSON。"""
    return '"' not in s and '\\' not in s


def sub_once(text, old, new, where):
    assert safe(old) and safe(new), '%s: 值含引号或反斜杠，不能用朴素替换' % where
    cnt = text.count('"%s"' % old)
    if cnt == 0:
        # 退一步：值可能被写成 \\uXXXX 转义形式
        import codecs
        esc = json.dumps(old, ensure_ascii=False)
        if esc != '"%s"' % old and text.count(esc):
            return text.replace(esc, json.dumps(new, ensure_ascii=False)), 1
        raise AssertionError('%s: 未找到旧值\n  %r' % (where, old[:90]))
    assert cnt == 1, '%s: 旧值出现 %d 次，预期 1 次' % (where, cnt)
    return text.replace('"%s"' % old, '"%s"' % new), 1


def main():
    jobs = []  # (路径, 旧值, 新值, 说明)

    for lang, (old, new) in HERO_BADGE.items():
        jobs.append(('data/pages/home/%s.json' % lang, old, new,
                     'home/%s hero.badge' % lang))
    for lang, (old, new) in FOOTER_DESC.items():
        jobs.append(('data/pages/home/%s.json' % lang, old, new,
                     'home/%s footer.description' % lang))
    # 注意：data/i18n/ 下没有 zh.json —— 中文的 UI 文案不走这条链，
    # 中文页面是预渲染的，文案直接写在 HTML 里（见下一段 HTML 替换）。
    for lang, (old, new) in FOOTER_DESC.items():
        if not os.path.exists(os.path.join(ROOT, 'data/i18n/%s.json' % lang)):
            print('  · 跳过 i18n/%s（文件不存在）' % lang)
            continue
        o = I18N_BRANDDESC_OLD.get(lang, old)
        jobs.append(('data/i18n/%s.json' % lang, o, new,
                     'i18n/%s footer.brandDesc' % lang))
    for lang, spec in ABOUT.items():
        jobs.append(('data/pages/about/%s.json' % lang, spec['badge'][0],
                     spec['badge'][1], 'about/%s hero.badge' % lang))
        jobs.append(('data/pages/about/%s.json' % lang, spec['story'][0],
                     spec['story'][1], 'about/%s story.p0' % lang))
        jobs.append(('data/pages/about/%s.json' % lang, spec['mile_h4'][0],
                     spec['mile_h4'][1], 'about/%s milestones[0].h4' % lang))

    # ⚠️ 必须按文件分组、在同一个文本上累积替换。
    # 第一版是每个 job 各自从原始文件读一遍再写回，结果同一文件的多个
    # 替换互相覆盖——最后写入的那个 job 会把前面 job 的改动全抹掉
    # （表现：badge 改了但落盘后还是旧值，只有最后处理的字段生效）。
    by_file = {}
    for rel, old, new, label in jobs:
        by_file.setdefault(rel, []).append((old, new, label))

    outs = []
    for rel, items in by_file.items():
        p = os.path.join(ROOT, rel)
        s = io.open(p, encoding='utf-8', newline='').read()
        for old, new, label in items:
            s, _n = sub_once(s, old, new, label)
        json.loads(s)  # 结构必须仍然合法
        outs.append((p, s, [lb for _o, _n, lb in items]))

    for p, out, labels in outs:
        io.open(p, 'w', encoding='utf-8', newline='').write(out)
        for lb in labels:
            print('  ✓ %s' % lb)

    print('\n已改写 %d 处（%d 个文件）'
          % (sum(len(l) for _p, _o, l in outs), len(outs)))


if __name__ == '__main__':
    main()
