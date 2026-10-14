#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
add_product_eg16pro.py — 新增一个产品（EG16Pro）到 data/products/handheld-vacuum.json

为什么要单独写脚本，而不是整个 json.load → 加一条 → json.dump 覆盖回去
--------------------------------------------------------------------
同 fix_product_highlights.py / set_detail_images.py：这些 JSON 是 2/3/4 空格的
递进缩进 + 纯 CRLF 行尾。整文件 json.dumps 会重排 70%+ 的行，diff 没法审，
而且会把原本"看起来像人手排的"文件变成机器排的。这里只往 products 数组末尾
塞一个元素，其余字节一个不动。

数据来源
--------
scraped/alibaba_v3/1601820268825.json（阿里国际站 EG16Pro listing 的采集结果）
  - gallery 6 张主图、detail 13 张详情长图、attrs 24 条属性
图片由 scripts/apply_alibaba_images.py 下载转码，本脚本只管数据。

⚠️ 两处需要人工确认的地方，写在 VERIFY_TODO 里，发布前必须过一遍
--------------------------------------------------------------------
1. 价格。Alibaba listing 没给出可引用的成交价，82–96 USD 是按"比同类的
   立式吸尘器（54–64）高一档、比洗地机整机低一档"估的，B2B 页面上的价格
   是商业承诺，不能拍脑袋。发布前请换成实际报价。
2. 规格口径。listing 里 Runtime 写 30–60 分钟，Maximum Runtime 又写 30–60
   分钟，两者冲突且详情图里没有规格表可查。这里取了更保守、与 230W/2200mAh
   物理上自洽的 30–60 分钟。如果实际是 60 分钟档，specs 和 quick_specs
   要一起改。

用法
----
    python scripts/add_product_eg16pro.py           # 预演，打印将插入的内容
    python scripts/add_product_eg16pro.py --apply   # 写入
"""
from __future__ import annotations
import io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, 'data', 'products', 'handheld-vacuum.json')
PID = 'eg16pro'
SITE = 'https://www.hkdmj.net'
DIR = 'handheld-vacuum-eg16pro'

VERIFY_TODO = [
    '价格 82–96 USD 是估算值，发布前换成实际报价',
    'Runtime 取 30–60 min（listing 的 Maximum Runtime 30–60 min 与之冲突）',
    'listing 标题写「手持式」，但详情图是双水箱滚刷洗地机形态；已按洗地机口径写文案',
    '详情长图里有一张「Founded in 2016 / 10+ years」的公司介绍页，'
    '与站内「宁波工厂 2015 年投产、香港公司 2024 年注册」冲突，已排除不上站',
]

LANGS = ['en', 'zh', 'es', 'ar', 'fr', 'id', 'ru', 'th', 'vi']


def L(*vals):
    """按 en,zh,es,ar,fr,id,ru,th,vi 的顺序打一个语言字典。"""
    assert len(vals) == 9, '语言数不对：%d' % len(vals)
    return dict(zip(LANGS, vals))


def spec(label, value):
    return {'label': L(*label), 'value': L(*value)}


def quick(label, value):
    """quick_specs 的值大多是数字/单位，9 个语种共用同一个字符串即可。"""
    return {'label': L(*label), 'value': dict((k, v) for k, v in zip(LANGS, value))}


NAME = L(
    'EG16Pro Cordless Wet & Dry Floor Washer · 5-in-1 Cleaning System',
    'EG16Pro 无线干湿两用洗地机 · 五合一清洁系统',
    'Friegasuelos inalámbrico EG16Pro seco y húmedo · sistema de limpieza 5 en 1',
    'EG16Pro مكنسة أرضيات لاسلكية جافة ورطبة · نظام تنظيف 5 في 1',
    'Laveur de sol sans fil EG16Pro sec et humide · système de nettoyage 5 en 1',
    'Pel lantai nirkabel EG16Pro kering dan basah · sistem pembersihan 5 dalam 1',
    'EG16Pro Беспроводный моющий пылесос для сухой и влажной уборки · 5 в 1',
    'เครื่องดูดฝุ่นล้างพื้น EG16Pro แบบไร้สาย เปียกและแห้ง · ระบบทำความสะอาด 5 ใน 1',
    'Máy hút bụi lau sàn EG16Pro không dây · hệ thống vệ sinh 5 trong 1',
)

TAGLINE = L(
    '230W Brushless Motor · 110AW Suction · Dual Tank · 30–60 min',
    '230W 无刷电机 · 110AW 吸力 · 双水箱 · 30–60 分钟',
    'Motor sin escobillas de 230 W · succión 110 AW · tanque doble · 30–60 min',
    'محرك بدون فرشاة 230 واط · شفط 110AW · خزان مزدوج · 30–60 دقيقة',
    'Moteur sans balais 230 W · aspiration 110 AW · double réservoir · 30–60 min',
    'Motor tanpa sikat 230W · daya hisap 110AW · tangki ganda · 30–60 menit',
    'Бесщёточный двигатель 230 Вт · всасывание 110 AW · два бака · 30–60 мин',
    'มอเตอร์ไม่มีแปรงถ่าน 230W · แรงดูด 110AW · ถังคู่ · 30–60 นาที',
    'Động cơ không chổi than 230W · lực hút 110AW · bình kép · 30–60 phút',
)

HIGHLIGHTS = [
    {'icon': 'power', 'text': L(
        '230W Brushless Motor delivering 110AW Suction',
        '230W 无刷电机，110AW 强吸力',
        'Motor sin escobillas de 230 W con succión de 110 AW',
        'محرك بدون فرشاة 230 واط بقوة شفط 110AW',
        'Moteur sans balais de 230 W avec aspiration de 110 AW',
        'Motor tanpa sikat 230W dengan daya hisap 110AW',
        'Бесщёточный двигатель 230 Вт с всасыванием 110 AW',
        'มอเตอร์ไม่มีแปรงถ่าน 230W แรงดูด 110AW',
        'Động cơ không chổi than 230W với lực hút 110AW')},
    {'icon': 'suction', 'text': L(
        'Dual-Tank Wet & Dry Cleaning — No Residue Left Behind',
        '双水箱干湿两用，清洁污水不残留',
        'Limpización en seco y húmedo con dos tanques: sin residuos',
        'تنظيف جاف ورطب بخزانين — دون بقايا',
        'Nettoyage sec et humide à double réservoir : sans résidu',
        'Pembersihan kering & basah dengan tangki ganda — tanpa sisa',
        'Сухая и влажная уборка с двумя баками — без остатков',
        'ทำความสะอาดเปียกและแห้งด้วยถังคู่ ไม่เหลือคราบ',
        'Làm sạch khô & ướt bằng bình kép — không còn vết bẩn')},
    {'icon': 'filter', 'text': L(
        'Washable HEPA Filter with Self-Cleaning Cycle',
        'HEPA 可水洗滤网，自清洁程序',
        'Filtro HEPA lavable con ciclo de autolimpieza',
        'فلتر HEPA قابل للغسل مع دورة تنظيف ذاتي',
        'Filtre HEPA lavable avec cycle d’autonettoyage',
        'Filter HEPA yang bisa dicuci dengan siklus pembersihan otomatis',
        'Моющийся фильтр HEPA с циклом самоочистки',
        'ตัวกรอง HEPA ล้างได้ พร้อมโปรแกรมทำความสะอาดตัวเอง',
        'Bộ lọc HEPA rửa được với chu trình tự làm sạch')},
    {'icon': 'battery', 'text': L(
        '2200mAh Battery · 30–60 min Runtime · HD LED Display',
        '2200mAh 电池 · 30–60 分钟续航 · 高清 LED 显示屏',
        'Batería de 2200 mAh · autonomía de 30–60 min · pantalla LED HD',
        'بطارية 2200mAh · تشغيل 30–60 دقيقة · شاشة LED عالية الوضوح',
        'Batterie 2200 mAh · autonomie 30–60 min · écran LED HD',
        'Baterai 2200mAh · waktu pakai 30–60 menit · layar LED HD',
        'Аккумулятор 2200 мАч · время работы 30–60 мин · HD LED-дисплей',
        'แบตเตอรี่ 2200mAh · ใช้งาน 30–60 นาที · จอ LED ความละเอียดสูง',
        'Pin 2200mAh · thời gian chạy 30–60 phút · màn hình LED HD')},
]

SPECS = [
    spec(('Model', '型号', 'Modelo', 'الموديل', 'Modèle', 'Model', 'Модель', 'รุ่น', 'Model'),
         ['EG16Pro'] * 9),
    spec(('Motor Power', 'Motor Power', 'Potencia del motor', 'قدرة المحرك', 'Puissance du moteur',
          'Daya Motor', 'Мощность двигателя', 'กำลังมอเตอร์', 'Công suất động cơ'),
         ['230W'] * 9),
    spec(('Motor Type', '电机类型', 'Tipo de motor', 'نوع المحرك', 'Type de moteur',
          'Jenis Motor', 'Тип двигателя', 'ประเภทมอเตอร์', 'Loại động cơ'),
         ['Brushless'] * 9),
    spec(('Suction Power', '吸力', 'Potencia de succión', 'قوة الشفط', 'Puissance d\'aspiration',
          'Daya Hisap', 'Мощность всасывания', 'กำลังดูด', 'Công suất hút'),
         ['110AW (101–120AW)'] * 9),
    spec(('Runtime', '续航时间', 'Autonomía', 'مدة التشغيل', 'Autonomie', 'Waktu Pakai',
          'Время работы', 'ระยะเวลาทำงาน', 'Thời gian chạy'),
         ['30–60 min'] * 9),
    spec(('Charging Time', '充电时间', 'Tiempo de carga', 'زمن الشحن', 'Temps de charge',
          'Waktu Pengisian', 'Время зарядки', 'เวลาในการชาร์จ', 'Thời gian sạc'),
         ['4–5 hours'] * 9),
    spec(('Battery', 'Battery', 'Batería', 'البطارية', 'Batterie', 'Baterai', 'Аккумулятор',
          'แบตเตอรี่', 'Pin'),
         ['2200mAh Lithium-Ion'] * 9),
    spec(('Tank Capacity', '水箱容量', 'Capacidad del depósito', 'سعة الخزان',
          'Capacité du réservoir', 'Kapasitas Tangki', 'Объём баков',
          'ความจุถัง', 'Dung tích bình'),
         ['0.8L (dual tank)'] * 9),
    spec(('Filter Type', '滤网类型', 'Tipo de filtro', 'نوع الفلتر', 'Type de filtre',
          'Jenis Filter', 'Тип фильтра', 'ประเภทตัวกรอง', 'Loại bộ lọc'),
         ['HEPA (washable)'] * 9),
    spec(('Function', '功能', 'Función', 'الوظيفة', 'Fonction', 'Fungsi', 'Функция',
          'ฟังก์ชัน', 'Chức năng'),
         ['Wet & Dry · 5-in-1'] * 9),
    spec(('Nozzle Set', '吸嘴数量', 'Nº de boquillas', 'عدد الفوهات', 'Nombre de buses',
          'Jumlah Nozel', 'Количество насадок', 'จำนวนหัวดูด', 'Số đầu hút'),
         ['4–6 Attachments'] * 9),
    spec(('Noise', '噪音', 'Ruido', 'الضجيج', 'Bruit', 'Kebisingan', 'Шум', 'เสียงรบกวน',
          'Độ ồn'),
         ['68dB'] * 9),
    spec(('Net Weight', '净重', 'Peso neto', 'الوزن الصافي', 'Poids net', 'Berat Bersih',
          'Вес нетто', 'น้ำหนักสุทธิ', 'Trọng lượng tịnh'),
         ['≥3 kg'] * 9),
    spec(('Packaging Type', '包装形式', 'Tipo de embalaje', 'نوع التغليف', "Type d'emballage",
          'Jenis Kemasan', 'Тип упаковки', 'ประเภทบรรจุภัณฑ์', 'Loại bao bì'),
         ['Color Box'] * 9),
    spec(('Warranty', '质保', 'Garantía', 'الضمان', 'Garantie', 'Garansi', 'Гарантия',
          'การรับประกัน', 'Bảo hành'),
         ['1 Year'] * 9),
    spec(('After-sales', '售后', 'Posventa', 'خدمة ما بعد البيع', 'Service après-vente',
          'Purnajual', 'Послепродажное обслуживание', 'บริการหลังการขาย',
          'Sau bán hàng'),
         ['Free Spare Parts'] * 9),
]

QUICK_SPECS = [
    quick(('Motor Power', 'Motor Power', 'Potencia del motor', 'قدرة المحرك', 'Puissance du moteur',
           'Daya Motor', 'Мощность двигателя', 'กำลังมอเตอร์', 'Công suất động cơ'),
          ['230W'] * 9),
    quick(('Suction', '吸力', 'Succión', 'الشفط', 'Aspiration', 'Daya Hisap', 'Всасывание',
           'แรงดูด', 'Lực hút'),
          ['110AW'] * 9),
    quick(('Runtime', '续航时间', 'Autonomía', 'مدة التشغيل', 'Autonomie', 'Waktu Pakai',
           'Время работы', 'ระยะเวลาทำงาน', 'Thời gian chạy'),
          ['30–60 min'] * 9),
    quick(('Tank', '水箱', 'Depósito', 'الخزان', 'Réservoir', 'Tangki', 'Баки', 'ถัง', 'Bình'),
          ['0.8L'] * 9),
]

DESCRIPTION = L(
    'The EG16Pro is a cordless wet & dry floor washer built around a 230W brushless '
    'motor with 110AW of suction. A dual-tank system keeps clean water and dirty '
    'water separate, so the roller brush can wash and pick up in one pass without '
    'wiping the floor a second time. The washable HEPA filter runs a self-cleaning '
    'cycle, and the HD LED display shows suction and tank levels at a glance. A '
    '2200mAh battery gives 30–60 minutes per charge. Available as OEM/ODM with '
    'custom colour, plug type and packaging for your market. Certification documents '
    'are on file and available on request.',
    'EG16Pro 是一款无线干湿两用洗地机，搭载 230W 无刷电机，吸力达 110AW。双水箱设计'
    '把清水与污水分开存放，滚刷一遍即可完成「洗 + 吸」，不必回头再拖一次地。配可水洗 '
    'HEPA 滤网与自清洁程序，HD LED 显示屏实时显示吸力与水箱余量。2200mAh 电池单次'
    '充电续航 30–60 分钟。支持 OEM/ODM 定制颜色、插头规格与包装，认证资料已备案、'
    '可按需提供。',
    'El EG16Pro es un friegasuelos inalámbrico seco y húmedo con motor sin escobillas '
    'de 230 W y 110 AW de succión. El sistema de doble tanque separa el agua limpia '
    'de la sucia, de modo que el rodillo lava y aspira en una sola pasada. Filtro HEPA '
    'lavable con ciclo de autolimpieza, pantalla LED HD y batería de 2200 mAh para '
    '30–60 minutos de autonomía. Disponible como OEM/ODM con color, enchufe y '
    'envase personalizados. Documentos de certificación disponibles bajo solicitud.',
    'الEG16Pro جهاز غسل أرضيات لاسلكي للجاف والرطب بمحرك بدون فرشاة بقدرة 230 واط '
    'وشفط 110AW. يفصل نظام الخزانين الماء النظيف عن المتسخ، sehingga performs '
    'الفرشاة الغسلة والشف في تمريرة واحدة. مع فلتر HEPA قابل للغسل بدورة تنظيف ذاتي '
    'وشاشة LED عالية الوضوح وبطارية 2200mAh تمنح 30–60 دقيقة من التشغيل. متاح OEM/ODM '
    'مع تخصيص اللون والقابس والتغليف. وثائق الشهادات متاحة عند الطلب.',
    "L’EG16Pro est un laveur de sol sans fil sec et humide équipé d’un moteur sans balais "
    "de 230 W pour 110 AW d’aspiration. Le double réservoir sépare l’eau propre de "
    "l’eau sale : la brosse lava et aspire en une seule passe. Filtre HEPA lavable avec "
    "cycle d’autonettoyage, écran LED HD et batterie de 2200 mAh pour 30–60 minutes "
    "d’autonomie. Disponible en OEM/ODM avec couleur, prise et emballage personnalisés. "
    "Documents de certification disponibles sur demande.",
    'EG16Pro adalah pel lantai nirkabel untuk pembersihan kering dan basah dengan motor '
    'tanpa sikat 230W dan daya hisap 110AW. Sistem tangki ganda memisahkan air bersih '
    'dan air kotor sehingga rol sikat dapat mencuci dan menyedot dalam satu kali jalan. '
    'Filter HEPA yang dapat dicuci dengan siklus pembersihan otomatis, layar LED HD, dan '
    'baterai 2200mAh untuk 30–60 menit. Tersedia sebagai OEM/ODM dengan pilihan warna, '
    'colokan, dan kemasan khusus. Dokumen sertifikasi tersedia atas permintaan.',
    'EG16Pro — беспроводный моющий пылесос для сухой и влажной уборки с бесщёточным '
    'двигателем 230 Вт и всасыванием 110 AW. Двойной бак разделяет чистую и грязную '
    'воду, поэтому щётка моет и собирает мусор за один проход. Моющийся фильтр HEPA с '
    'циклом самоочистки, HD LED-дисплей и аккумулятор 2200 мАч на 30–60 минут. '
    'Доступен как OEM/ODM с выбором цвета, вилки и упаковки. Сертификаты предоставляются '
    'по запросу.',
    'EG16Pro เครื่องดูดฝุ่นล้างพื้นแบบไร้สายสำหรับดูดเปียกและแห้ง มอเตอร์ไม่มีแปรงถ่าน '
    '230W แรงดูด 110AW ระบบถังคู่แยกน้ำสะอาดออกจากน้ำสกปรก จึงล้างและดูดพร้อมกันใน '
    'รอบเดียว ตัวกรอง HEPA ล้างได้พร้อมโปรแกรมทำความสะอาดตัวเอง จอ LED ความละเอียดสูง '
    'และแบตเตอรี่ 2200mAh ใช้งาน 30–60 นาที พร้อมบริการ OEM/ODM ปรับสี หัวปลั๊ก และบรรจุภัณฑ์ '
    'เอกสารใบรับรองมีให้ตามคำขอ',
    'EG16Pro là máy hút bụi lau sàn không dây cho vệ sinh khô và ướt với động cơ không '
    'chổi than 230W và lực hút 110AW. Hệ thống bình kép tách nước sạch khỏi nước bẩn, '
    'nhờ đó con lăn có thể rửa và hút trong một lượt. Bộ lọc HEPA rửa được kèm chu trình '
    'tự làm sạch, màn hình LED HD và pin 2200mAh cho 30–60 phút. Có sẵn dưới dạng OEM/ODM '
    'với tùy chọn màu sắc, phích cắm và bao bì. Tài liệu chứng nhận cung cấp khi có yêu cầu.',
)

APPLICATIONS = L(
    'Hard Floors, Carpet, Tiles & Whole-House Cleaning',
    '硬地板、地毯、瓷砖与全屋清洁',
    'Suelos rígidos, moquetas, baldosas y limpieza de toda la casa',
    'أرضيات صلبة وسجاد وبلاط وتنظيف المنزل بالكامل',
    'Sols durs, moquettes, carrelage et nettoyage de toute la maison',
    'Lantai keras, karpet, keramik, dan pembersihan seluruh rumah',
    'Твёрдые полы, ковры, плитка и уборка всего дома',
    'พื้นแข็ง พรม กระเบื้อง และการทำความสะอาดทั้งบ้าน',
    'Sàn cứng, thảm, gạch ốp & vệ sinh toàn nhà',
)

CATEGORY_NAME = L(
    'Handheld & Stick Vacuums',
    '手持与立式吸尘器',
    'Aspiradora de Mano',
    'مكنسة يدوية لاسلكية',
    'Aspirateur à main',
    'Pembersih Vakum Tangan',
    'Ручной пылесос',
    'เครื่องดูดฝุ่นมือถือ',
    'Máy hút bụi cầm tay',
)

PRODUCT = {
    'id': PID,
    'name': NAME,
    'tagline': TAGLINE,
    'images': ['%s/assets/images/products/%s/%02d.webp' % (SITE, DIR, i) for i in range(1, 7)],
    'video_url': '',
    'moq': {'value': 2, 'unit': 'pieces'},
    'certifications': [],
    'cert_note': {
        'en': 'Certification documents on file — available on request.',
        'zh': '认证资料已备案，可按需提供。',
    },
    'highlights': HIGHLIGHTS,
    'specs': SPECS,
    'quick_specs': QUICK_SPECS,
    'packaging': {'unit': 'Color Box', 'ctn_size': '—', 'ctn_qty': '—', 'gross_weight': '—'},
    'customization': {
        'oem': True, 'odm': True, 'logo': None, 'color': True, 'package': None,
        'sample_lead': 'on request', 'production_lead': 'on request',
    },
    'applications': APPLICATIONS,
    # TODO(发布前确认)：见文件头 VERIFY_TODO
    'price_indicator': {'min': 82, 'max': 96, 'currency': 'USD'},
    'sku': [
        {'name': {'en': 'Voltage', 'zh': '电压'}, 'values': [{'name': '110-240V'}]},
        {'name': {'en': 'Plug Type', 'zh': '插头'},
         'values': [{'name': 'AU'}, {'name': 'EU'}, {'name': 'UK'}, {'name': 'US'}]},
        {'name': {'en': 'Colour', 'zh': '颜色'}, 'values': [{'name': 'Silver'}]},
    ],
    'description': DESCRIPTION,
    'supplier_rating': '4.81',
    'response_time': '—',
    'transactions': '—',
    'years': '—',
    'ship_from': {'en': 'China', 'zh': '中国'},
    'sample': {'enabled': True, 'qty': 1,
               'note': {'en': 'Sample available (max 1 pc)', 'zh': '支持打样（最多 1 台）'}},
    'category_name': CATEGORY_NAME,
    'certificates': [],
    'supplier': {
        'country': 'HK', 'province': 'New Territories', 'established': 2024,
        'reply_rate': 0.9987, 'verified': False,
        'main_markets': ['North America', 'South America', 'Eastern Europe', 'Southeast Asia'],
    },
    'store_rating': {'score': 4.81, 'reviews': 7, 'scope': 'store'},
    'shipping_fee_usd': 17.02,
    'alibaba_url': 'https://www.alibaba.com/product-detail/OEM-EG16Pro-Hand-Held-Cordless-Wet_1601820268825.html',
    '_cat': 'handheld-vacuum',
}


# ── 位置感知：找到 "products" 数组的收尾 ] ────────────────────────────
def array_span(t, key):
    """返回 (数组 [ 的下标, 数组 ] 的下标)。跳过字符串里的括号。"""
    k = t.index('"%s"' % key)
    i = t.index('[', k)
    depth = 0
    j = i
    while j < len(t):
        c = t[j]
        if c == '"':                      # 跳过整个字符串（含转义）
            j += 1
            while t[j] != '"':
                j += 2 if t[j] == '\\' else 1
        elif c in '[{':
            depth += 1
        elif c in ']}':
            depth -= 1
            if depth == 0:
                return i, j
        j += 1
    raise RuntimeError('"%s" 数组没有收尾' % key)


def main():
    apply = '--apply' in sys.argv
    t = io.open(PATH, encoding='utf-8', newline='').read()

    # 这个仓的 JSON 是纯 CRLF；一旦发现混进裸 LF 就停下来，别把两种行尾搅在一起
    crlf = t.count('\r\n')
    lf = t.count('\n') - crlf
    assert lf == 0, '文件里混了 %d 个裸 LF（CRLF %d），先统一行尾再改' % (lf, crlf)
    eol = '\r\n'

    before = json.loads(t)
    ids = [p['id'] for p in before['products']]
    assert PID not in ids, '%s 已经在了，先手工确认再跑' % PID
    if not apply:
        print('当前 %d 个产品；将追加 %s（第 %d 个）' % (len(ids), PID, len(ids) + 1))

    a, b = array_span(t, 'products')
    # b 是 ] 的下标；往前退到最后一个元素结尾（跳过逗号和空白）
    k = b - 1
    while t[k] in ' \t\r\n,':
        k -= 1
    assert t[k] == '}', 'products 最后一个元素结尾不是 }'

    # 单空格递进 + 整体右移 3 格 → 元素的 { 落在 3 空格、成员落在 4 空格，
    # 与文件里既有元素（{ 在 2 空格、成员在 3 空格）差一格，
    # 所以这里右移 2 而不是 3。
    body = json.dumps(PRODUCT, ensure_ascii=False, indent=1)
    lines = body.split('\n')
    element = '  ' + lines[0] + eol + eol.join('  ' + ln for ln in lines[1:])

    out = t[:k + 1] + ',' + eol + element + t[k + 1:]

    # ── 断言链 ────────────────────────────────────────────────────────
    assert len(out) > len(t), '插入后没有变长'
    after = json.loads(out)
    assert len(after['products']) == len(before['products']) + 1, '产品数不对'
    assert after['products'][-1]['id'] == PID, '新元素不在末尾'
    # 除了多出来的这个产品，其余一切必须完全一致
    assert after['products'][:-1] == before['products'], '已有产品被改动了'
    for key in before:
        if key == 'products':
            continue
        assert after[key] == before[key], '顶层字段 %s 被改动了' % key
    assert out.count('\n') - out.count('\r\n') == 0, '写出的文本混了裸 LF'
    # 每个语言字段都要 9 语种齐
    p = after['products'][-1]
    for field in ('name', 'tagline', 'description', 'applications'):
        assert set(p[field]) == set(LANGS), '%s 语种不齐：%s' % (field, sorted(p[field]))
    for h in p['highlights']:
        assert set(h['text']) == set(LANGS), 'highlights 语种不齐'
    for s in p['specs']:
        assert set(s['label']) == set(LANGS) and set(s['value']) == set(LANGS), 'specs 语种不齐'
    for s in p['quick_specs']:
        assert set(s['label']) == set(LANGS) and set(s['value']) == set(LANGS), 'quick_specs 语种不齐'

    print('新元素 %d 字符，%d 个 highlights / %d 条 specs / %d 个 quick_specs'
          % (len(element), len(p['highlights']), len(p['specs']), len(p['quick_specs'])))
    if not apply:
        print('\n预演模式，未写入。加 --apply 真正写入。')
        return 0

    with io.open(PATH, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    print('\n已写入 %s。现在需要：' % PID)
    print('  1) scripts/apply_alibaba_images.py --apply --only handheld-vacuum/%s' % PID)
    print('     （下 6 张主图 + 详情长图，并把 en/zh 的长图列表写进 HTML）')
    print('  2) 建 en/handheld-vacuum-%s.html（en 是其余 7 个语种的模板）' % PID)
    print('  3) en/handheld-vacuum/index.html 的类目列表里加上它')
    print('  4) scripts/gen_pages.py 生成 ar/es/fr/id/ru/th/vi')
    print('  5) scripts/verify_new_product_images.js handheld-vacuum-%s' % PID)
    print()
    print('发布前必须确认：')
    for i, t2 in enumerate(VERIFY_TODO, 1):
        print('  %d) %s' % (i, t2))
    return 0


if __name__ == '__main__':
    sys.exit(main())