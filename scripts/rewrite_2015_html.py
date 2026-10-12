#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
rewrite_2015_html.py — 把预渲染 HTML 里的「2015 年公司创立」改成「2015 年工厂投产」

配套 rewrite_2015_narrative.py（改 data/）。这两个必须一起跑：
公开站的首页 / 关于页是**预渲染**的，文案直接写在 HTML 里，
只改 data 不会生效；只改 HTML 又会和 data 脱节，下次生成就打架。

本脚本做**子串**替换（不是 JSON 引号包裹），因为同一句文案会同时出现在
正文、<title>、meta description、og:、twitter:、JSON-LD 里，
子串匹配能一次覆盖全部位置。

每个替换都报告命中次数；跑完会再扫一遍，确认没有漏网的
「since 2015 / 始于 2015 / 2015 年…创立」。
"""
import io
import glob
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── 页脚品牌描述：各语种完整句 ────────────────────────────────────
FOOTER = [
    # en
    ('Professional manufacturer of smart home cleaning appliances. OEM/ODM '
     'solutions for brands worldwide since 2015.',
     'Manufacturer of smart home cleaning appliances. Our Ningbo plant has '
     'produced for global brands since 2015; Hong Kong-registered company '
     'handling worldwide OEM/ODM.'),
    # zh —— HTML 里有四种标点/空格变体，统一成一句
    ('专业智能家用清洁电器制造商。自2015年起为全球品牌提供OEM/ODM解决方案。',
     '智能家用清洁电器制造商。宁波工厂自 2015 年起为全球品牌生产；'
     '香港注册公司负责全球 OEM/ODM 业务。'),
    ('专业智能家用清洁电器制造商。自 2015 年起为全球品牌提供 OEM/ODM 解决方案。',
     '智能家用清洁电器制造商。宁波工厂自 2015 年起为全球品牌生产；'
     '香港注册公司负责全球 OEM/ODM 业务。'),
    ('专业智能家用清洁电器制造商，自 2015 年起为全球品牌提供 OEM/ODM 解决方案。',
     '智能家用清洁电器制造商。宁波工厂自 2015 年起为全球品牌生产；'
     '香港注册公司负责全球 OEM/ODM 业务。'),
    ('专业制造智能家用清洁电器，自 2015 年起为全球品牌提供 OEM/ODM 解决方案。',
     '智能家用清洁电器制造商。宁波工厂自 2015 年起为全球品牌生产；'
     '香港注册公司负责全球 OEM/ODM 业务。'),
    # es
    ('Fabricante profesional de electrodomésticos inteligentes de limpieza para '
     'el hogar. Soluciones OEM/ODM para marcas globales desde 2015.',
     'Fabricante de electrodomésticos inteligentes de limpieza para el hogar. '
     'Nuestra planta de Ningbo produce para marcas globales desde 2015; empresa '
     'registrada en Hong Kong que gestiona el OEM/ODM mundial.'),
    # fr
    ("Fabricant professionnel d'appareils de nettoyage domestique intelligents. "
     "Solutions OEM/ODM pour des marques du monde entier depuis 2015.",
     "Fabricant d'appareils de nettoyage domestique intelligents. Notre usine de "
     "Ningbo produit pour des marques mondiales depuis 2015 ; société enregistrée "
     "à Hong Kong gérant l'OEM/ODM international."),
    # id
    ('Produsen peralatan kebersihan rumah cerdas profesional. Solusi OEM/ODM '
     'untuk merek global sejak 2015.',
     'Produsen peralatan kebersihan rumah cerdas. Pabrik Ningbo kami memproduksi '
     'untuk merek global sejak 2015; perusahaan terdaftar di Hong Kong yang '
     'menangani OEM/ODM global.'),
    # ru
    ('Профессиональный производитель умной бытовой клининговой техники. OEM/ODM '
     'решения для брендов по всему миру с 2015 года.',
     'Производитель умной бытовой клининговой техники. Наш завод в Нинбо '
     'производит продукцию для мировых брендов с 2015 года; компания '
     'зарегистрирована в Гонконге и ведёт OEM/ODM по всему миру.'),
    # th
    ('ผู้ผลิตอุปกรณ์ทำความสะอาดบ้านอัจฉริยะระดับมืออาชีพ บริการ OEM/ODM '
     'สำหรับแบรนด์ทั่วโลกตั้งแต่ปี 2015',
     'ผู้ผลิตอุปกรณ์ทำความสะอาดบ้านอัจฉริยะ โรงงานหนิงปัวของเราผลิตให้'
     'แบรนด์ระดับโลกตั้งแต่ปี 2015 บริษัทจดทะเบียนในฮ่องกงดูแล OEM/ODM ทั่วโลก'),
    # vi
    ('Nhà sản xuất chuyên nghiệp thiết bị làm sạch nhà thông minh. Giải pháp '
     'OEM/ODM cho các thương hiệu toàn cầu kể từ 2015.',
     'Nhà sản xuất thiết bị làm sạch nhà thông minh. Nhà máy Ninh Ba của chúng '
     'tôi sản xuất cho các thương hiệu toàn cầu từ 2015; công ty đăng ký tại '
     'Hong Kong phụ trách OEM/ODM toàn cầu.'),
    # ar —— 两种措辞（حول العالم / العالمية），统一成一句
    ('شركة تصنيع احترافية لأجهزة تنظيف المنزل الذكية. حلول OEM/ODM للعلامات '
     'التجارية حول العالم منذ 2015.',
     'شركة تصنيع أجهزة تنظيف المنزل الذكية. مصنعنا في نينغبو ينتج للعلامات '
     'التجارية العالمية منذ 2015؛ وشركة مسجلة في هونغ كونغ تتولى خدمات OEM/ODM '
     'عالميًا.'),
    ('شركة تصنيع احترافية لأجهزة تنظيف المنزل الذكية. حلول OEM/ODM للعلامات '
     'التجارية العالمية منذ 2015.',
     'شركة تصنيع أجهزة تنظيف المنزل الذكية. مصنعنا في نينغبو ينتج للعلامات '
     'التجارية العالمية منذ 2015؛ وشركة مسجلة في هونغ كونغ تتولى خدمات OEM/ODM '
     'عالميًا.'),
]

# ── 首页 hero 徽章 ────────────────────────────────────────────────
BADGE = [
    ('\U0001F1E8\U0001F1F3 OEM / ODM Manufacturer · Since 2015',
     '\U0001F1E8\U0001F1F3 OEM / ODM · Manufacturing since 2015'),
    ('\U0001F1E8\U0001F1F3 Fabricante OEM / ODM · Desde 2015',
     '\U0001F1E8\U0001F1F3 OEM / ODM · En producción desde 2015'),
    ('\U0001F1E8\U0001F1F3 Fabricant OEM / ODM · Depuis 2015',
     '\U0001F1E8\U0001F1F3 OEM / ODM · En production depuis 2015'),
    ('\U0001F1E8\U0001F1F3 Produsen OEM / ODM · Sejak 2015',
     '\U0001F1E8\U0001F1F3 OEM / ODM · Berproduksi sejak 2015'),
    ('\U0001F1E8\U0001F1F3 OEM / ODM Производитель · С 2015 года',
     '\U0001F1E8\U0001F1F3 OEM / ODM · Производство с 2015 года'),
    ('\U0001F1E8\U0001F1F3 ผู้ผลิต OEM / ODM · ตั้งแต่ปี 2015',
     '\U0001F1E8\U0001F1F3 OEM / ODM · ผลิตตั้งแต่ปี 2015'),
    ('\U0001F1E8\U0001F1F3 Nhà Sản Xuất OEM / ODM · Kể Từ 2015',
     '\U0001F1E8\U0001F1F3 OEM / ODM · Sản xuất từ 2015'),
    ('\U0001F1E8\U0001F1F3 شركة تصنيع OEM / ODM · منذ 2015',
     '\U0001F1E8\U0001F1F3 OEM / ODM · ننتج منذ 2015'),
    # zh：HTML 里带空格、带 emoji，用不含 emoji 的子串以覆盖所有变体
    ('OEM/ODM 制造商 · 始于 2015 年', 'OEM/ODM 制造商 · 2015 年起投产'),
    ('OEM/ODM制造商 · 始于2015年', 'OEM/ODM制造商 · 2015 年起投产'),
]

# ── 关于页：标题 / meta / 徽章 / 故事 / 里程碑 ────────────────────
ABOUT = [
    ('About AquaClean — Cleaning Appliance Manufacturer Since 2015',
     'About AquaClean — Cleaning Appliance Manufacturer, Ningbo Plant since 2015'),
    ('关于我们 — 清洁电器制造商，始于 2015',
     '关于我们 — 清洁电器制造商，宁波工厂始于 2015'),
    ('AquaClean is a Ningbo-based OEM/ODM manufacturer of smart home cleaning '
     'appliances, serving 200+ B2B partners in 50+ countries since 2015.',
     'AquaClean is an OEM/ODM manufacturer of smart home cleaning appliances. '
     'Our Ningbo plant has produced since 2015; Hong Kong-registered company '
     'serving 200+ B2B partners in 50+ countries.'),
    ('AquaClean 是一家位于宁波的 OEM/ODM 清洁电器制造商，自 2015 年起服务全球 '
     '50 多个国家的 200+ B2B 合作伙伴。',
     'AquaClean 是 OEM/ODM 清洁电器制造商。宁波工厂自 2015 年起生产，'
     '香港注册公司服务全球 50 多个国家的 200+ B2B 合作伙伴。'),
    ('\U0001F3ED Since 2015 · Ningbo, China',
     '\U0001F3ED Ningbo Plant since 2015 · HK-registered 2024'),
    ('\U0001F3ED 始于 2015 · 中国宁波',
     '\U0001F3ED 宁波工厂始于 2015 · 香港公司 2024 年注册'),
    ('Founded in 2015 in Ningbo, Zhejiang, AquaClean began with one goal: make '
     'professional-grade cleaning technology accessible to households '
     'everywhere. What started as a single handheld vacuum line has grown into '
     'a full portfolio of smart cleaning appliances.',
     'Our Ningbo plant has been building cordless vacuums and cleaning '
     'appliances since 2015. In 2024, Hong Kong Damaijia Technology Co., '
     'Limited was established to bring that manufacturing base to B2B partners '
     'worldwide — what started as a single handheld vacuum line is now a full '
     'portfolio of smart cleaning appliances.'),
    ('2015 年，AquaClean 在浙江宁波创立，初衷只有一个：让专业级清洁科技走进千家万户。'
     '从一条手持吸尘器产品线起步，如今已发展成完整的智能清洁电器产品矩阵。',
     '我们的宁波工厂自 2015 年起生产无线吸尘器与清洁电器。2024 年，'
     '香港大迈嘉科技有限公司（Hong Kong Damaijia Technology Co., Limited）成立，'
     '把这套制造能力带给全球 B2B 客户——从一条手持吸尘器产品线起步，'
     '如今已发展成完整的智能清洁电器产品矩阵。'),
    ('Founded in Ningbo', 'Ningbo Plant in Production'),
    ('宁波创立', '宁波工厂投产'),
]

RULES = FOOTER + BADGE + ABOUT


def main():
    files = sorted(glob.glob(os.path.join(ROOT, '**', '*.html'), recursive=True))
    total_files, total_hits = 0, 0
    per_rule = {}

    for p in files:
        s = io.open(p, encoding='utf-8', newline='').read()
        orig = s
        for old, new in RULES:
            n = s.count(old)
            if n:
                s = s.replace(old, new)
                per_rule[old[:52]] = per_rule.get(old[:52], 0) + n
        if s != orig:
            io.open(p, 'w', encoding='utf-8', newline='').write(s)
            total_files += 1

    print('命中规则：')
    for k, v in sorted(per_rule.items(), key=lambda x: -x[1]):
        print('  %5d  %s…' % (v, k))
        total_hits += v
    print('\n已改写 %d 个文件 / %d 处' % (total_files, total_hits))

    # ── 复扫：还有没有旧叙事 ────────────────────────────────────────
    # ⚠️ 不能用 "since 2015" 当标记——新叙事本身就是
    # "Our Ningbo plant has produced ... since 2015"，那样会把自己的成果
    # 报成残留（第一版就误报了 166 处）。要检测的是**旧叙事独有**的措辞。
    left = []
    for p in files:
        s = io.open(p, encoding='utf-8', errors='replace').read()
        for marker in [
            'Founded in 2015',
            'Founded in Ningbo',
            'AquaClean began with one goal',
            'OEM/ODM solutions for brands worldwide since 2015',
            'solutions for brands worldwide since 2015',
            'About AquaClean — Cleaning Appliance Manufacturer Since 2015',
            '关于我们 — 清洁电器制造商，始于 2015',
            'serving 200+ B2B partners in 50+ countries since 2015',
            'Ningbo-based OEM/ODM manufacturer',
            '在浙江宁波创立',
            '宁波创立',
            # 必须是完整旧值：新文案「宁波工厂始于 2015 · 香港公司…」本身
            # 也含「始于 2015 ·」，用短片段会把自己报成残留。
            '\U0001F3ED 始于 2015 · 中国宁波',
            '始于2015年',
        ]:
            if marker in s:
                left.append((os.path.relpath(p, ROOT), marker))
    if left:
        print('\n❌ 仍有 %d 处旧叙事未改：' % len(left))
        for f, m in left[:25]:
            print('   %s  ← %s' % (f, m))
        sys.exit(1)
    print('\n✅ 复扫通过：没有残留的「2015 年创立」叙事')


if __name__ == '__main__':
    main()
