#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
add_product_pg16pro.py — 新增一个产品（PG16PRO）到 data/products/handheld-vacuum.json

做法与 add_product_eg16pro.py 完全一致：只往 products 数组末尾塞一个元素，
其余字节一个不动。原因见那个文件的文件头 —— 这些 JSON 是 2/3/4 空格递进缩进
+ 纯 CRLF，整文件 json.dumps 会把 70%+ 的行重排，diff 没法审。

数据来源
--------
scraped/alibaba_v3/1601780738060.json（阿里国际站 PG16PRO listing）
  gallery 6 张、detail 12 张、英文属性 18 条
属性表里可靠的字段：Model PG16PRO / Power 230W / Suction 110AW /
Battery-less runtime ≤30min / Charging 4-5h / Dust Capacity 0.8L /
Brushless / ≥3kg / Warranty 1 year / No App Control / Nozzle ≤3 /
 OLED 显示屏 / 干湿两用 / 可水洗滤网 / 彩盒+瓦楞纸箱。

⚠️ 术语污染的坑（这次特意躲开了）
------------------------------------
gen_pages.py 的 put() 是 last-write-wins：一个产品里出现的英文 spec 标签，
会成为**全站**这个英文词条的译文来源。所以这里的 spec / quick_specs 标签
**一个都没新造**，全部照抄 add_product_eg16pro.py 里已经核过（0 冲突）的那套
译法。要加新标签请先跑验证：改完所有语言后 diff 必须只有预期那几个文件。

VERIFY_TODO：发布前必须过一遍的四件事
--------------------------------------
1. 价格留空（多数产品也是空的）。listing 没给可引用报价，B2B 页面上的价格
   是商业承诺，不能估。拿到实际报价再补 price_indicator。
2. 吸力口径冲突：标题写 28kPa，属性表写 110AW。这里取属性表的 110AW
   （结构化数据优先）。确认实际口径后要连 specs / highlights / tagline 一起改。
3. 续航取「≤30 min」：属性表 Maximum Runtime 是 "<30分钟"，没有别的续航数据，
   没有像 EG16Pro 那样 25-35 与 30-60 互相打架。
4. 与 EG16Pro 的关系：两者 230W / 110AW / 0.8L / ≥3kg / 4-5h 充电几乎一样，
   看着像同一套平台。**但两个 listing 的主图感知哈希距离 88-121（远大于同一张
   图的 12），是完全不同的产品照片**，且型号不同，所以按不同产品上架。
   若日后确认是同机身换型号名，需要合并。

用法
----
    python scripts/add_product_pg16pro.py           # 预演
    python scripts/add_product_pg16pro.py --apply   # 写入
"""
from __future__ import annotations
import io, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.path.join(ROOT, 'data', 'products', 'handheld-vacuum.json')
PID = 'pg16pro'
SITE = 'https://www.hkdmj.net'
DIR = 'handheld-vacuum-pg16pro'

VERIFY_TODO = [
    'price_indicator 留空（同站内多数产品），拿到实际报价再补',
    '吸力取属性表的 110AW（标题写 28kPa，两者不一致，已按结构化数据优先）',
    '续航取 ≤30 min（属性表 Maximum Runtime "<30分钟"，无冲突项）',
    '与 EG16Pro 规格高度重合但主图完全不同（汉明距离 88-121），已按不同产品上架',
]

LANGS = ['en', 'zh', 'es', 'ar', 'fr', 'id', 'ru', 'th', 'vi']


def L(*vals):
    """按 en,zh,es,ar,fr,id,ru,th,vi 的顺序打一个语言字典。"""
    assert len(vals) == 9, '语言数不对：%d' % len(vals)
    return dict(zip(LANGS, vals))


def spec(label, value):
    return {'label': L(*label), 'value': L(*value)}


def quick(label, value):
    return {'label': L(*label), 'value': dict((k, v) for k, v in zip(LANGS, value))}


# ── 以下标签元组全部照抄 add_product_eg16pro.py（已验证不污染全局词典） ──
LB_MODEL = ('Model', '型号', 'Modelo', 'الموديل', 'Modèle', 'Model', 'Модель', 'รุ่น', 'Model')
LB_MOTOR_PWR = ('Motor Power', 'Motor Power', 'Potencia del motor', 'قدرة المحرك',
                'Puissance du moteur', 'Daya Motor', 'Мощность двигателя', 'กำลังมอเตอร์',
                'Công suất động cơ')
LB_MOTOR_TYPE = ('Motor Type', '电机类型', 'Tipo de motor', 'نوع المحرك', 'Type de moteur',
                 'Jenis Motor', 'Тип двигателя', 'ประเภทมอเตอร์', 'Loại động cơ')
LB_SUCTION = ('Suction Power', '吸力', 'Potencia de succión', 'قوة الشفط',
              'Puissance d\'aspiration', 'Daya Hisap', 'Мощность всасывания', 'กำลังดูด',
              'Công suất hút')
LB_RUNTIME = ('Runtime', '续航时间', 'Autonomía', 'مدة التشغيل', 'Autonomie', 'Waktu Pakai',
              'Время работы', 'ระยะเวลาทำงาน', 'Thời gian chạy')
LB_CHARGE = ('Charging Time', '充电时间', 'Tiempo de carga', 'زمن الشحن', 'Temps de charge',
             'Waktu Pengisian', 'Время зарядки', 'เวลาในการชาร์จ', 'Thời gian sạc')
LB_TANK = ('Tank Capacity', '水箱容量', 'Capacidad del depósito', 'سعة الخزان',
           'Capacité du réservoir', 'Kapasitas Tangki', 'Объём баков', 'ความจุถัง', 'Dung tích bình')
LB_FILTER = ('Filter Type', '滤网类型', 'Tipo de filtro', 'نوع الفلتر', 'Type de filtre',
             'Jenis Filter', 'Тип фильтра', 'ประเภทตัวกรอง', 'Loại bộ lọc')
LB_FUNCTION = ('Function', '功能', 'Función', 'الوظيفة', 'Fonction', 'Fungsi', 'Функция',
               'ฟังก์ชัน', 'Chức năng')
LB_NOZZLE = ('Nozzle Set', '吸嘴数量', 'Nº de boquillas', 'عدد الفوهات', 'Nombre de buses',
             'Jumlah Nozel', 'Количество насадок', 'จำนวนหัวดูด', 'Số đầu hút')
LB_WEIGHT = ('Net Weight', '净重', 'Peso neto', 'الوزن الصافي', 'Poids net', 'Berat Bersih',
             'Вес нетто', 'น้ำหนักสุทธิ', 'Trọng lượng tịnh')
LB_PACKING = ('Packaging Type', '包装形式', 'Tipo de embalaje', 'نوع التغليف',
              "Type d'emballage", 'Jenis Kemasan', 'Тип упаковки', 'ประเภทบรรจุภัณฑ์',
              'Loại bao bì')
LB_WARRANTY = ('Warranty', '质保', 'Garantía', 'الضمان', 'Garantie', 'Garansi', 'Гарантия',
               'การรับประกัน', 'Bảo hành')
LB_AFTERSALES = ('After-sales', '售后', 'Posventa', 'خدمة ما بعد البيع',
                 'Service après-vente', 'Purnajual', 'Послепродажное обслуживание',
                 'บริการหลังการขาย', 'Sau bán hàng')
LB_SUCTION_Q = ('Suction', '吸力', 'Succión', 'الشفط', 'Aspiration', 'Daya Hisap',
                'Всасывание', 'แรงดูด', 'Lực hút')
LB_TANK_Q = ('Tank', '水箱', 'Depósito', 'الخزان', 'Réservoir', 'Tangki', 'Баки', 'ถัง', 'Bình')

NAME = L(
    'PG16PRO Cordless Wet & Dry Vacuum Mop · Self-Cleaning Floor Washer',
    'PG16PRO 无线干湿两用吸尘拖把 · 自清洁洗地机',
    'Fregona aspiradora inalámbrica PG16PRO en seco y húmedo · lavadora de suelos autolimpiable',
    'ممسحة مكنسة لاسلكية PG16PRO للجاف والرطب · غسالة أرضيات ذاتية التنظيف',
    'Aspirateur-laveur sans fil PG16PRO sec et humide · laveuse de sols autonettoyante',
    'Pel dan vakum nirkabel PG16PRO kering dan basah · pencuci lantai pembersih otomatis',
    'Беспроводной моющий пылесос PG16PRO для сухой и влажной уборки · поломойка с самоочисткой',
    'เครื่องดูดฝุ่นถูพื้น PG16PRO แบบไร้สาย เปียกและแห้ง · เครื่องล้างพื้นทำความสะอาดตัวเอง',
    'Máy hút bụi lau nhà PG16PRO không dây khô & ướt · máy lau sàn tự làm sạch',
)

TAGLINE = L(
    '230W Brushless Motor · 110AW Suction · 0.8L Tank · Self-Cleaning Brush Roll',
    '230W 无刷电机 · 110AW 吸力 · 0.8L 水箱 · 滚刷自清洁',
    'Motor sin escobillas de 230 W · succión 110 AW · depósito de 0,8 L · rodillo autolimpiable',
    'محرك بدون فرشاة 230 واط · شفط 110AW · خزان 0.8 لتر · فرشاة أسطوانية ذاتية التنظيف',
    'Moteur sans balais 230 W · aspiration 110 AW · réservoir de 0,8 L · brosse autonettoyante',
    'Motor tanpa sikat 230W · daya hisap 110AW · tangki 0.8L · rol sikat pembersih otomatis',
    'Бесщёточный двигатель 230 Вт · всасывание 110 AW · бак 0,8 л · самоочищающаяся щётка',
    'มอเตอร์ไม่มีแปรงถ่าน 230W · แรงดูด 110AW · ถัง 0.8L · แปรงลูกกลิ้งทำความสะอาดตัวเอง',
    'Động cơ không chổi than 230W · lực hút 110AW · bình 0.8L · con lăn tự làm sạch',
)

HIGHLIGHTS = [
    {'icon': 'clean', 'text': L(
        'Self-Cleaning Brush Roll — No Need to Touch the Dirt',
        '滚刷自清洁，双手不用碰脏污',
        'Rodillo autolimpiable: no hace falta tocar la suciedad',
        'فرشاة أسطوانية ذاتية التنظيف: لا حاجة للمس الأوساخ',
        'Brosse autonettoyante : pas besoin de toucher la saleté',
        'Rol sikat pembersih otomatis — tidak perlu menyentuh kotoran',
        'Самоочищающаяся щётка — не нужно касаться грязи',
        'แปรงลูกกลิ้งทำความสะอาดตัวเอง ไม่ต้องสัมผัสคราบสกปรก',
        'Con lăn tự làm sạch — không cần chạm tay vào vết bẩn')},
    {'icon': 'suction', 'text': L(
        'Vacuum and Mop in a Single Pass on Hard Floors',
        '硬地板一遍过：吸尘带拖地同时完成',
        'Aspira y friega en una sola pasada en suelos duros',
        'ينظف بالمكنسة ويمسح في تمريرة واحدة على الأرضيات الصلبة',
        'Aspire et lave en une seule passe sur sols durs',
        'Menyedot dan mengepel dalam satu kali jalan di lantai keras',
        'Пылесосит и моет за один проход на твёрдых полах',
        'ดูดฝุ่นและถูพื้นในรอบเดียวบนพื้นแข็ง',
        'Hút bụi và lau nhà trong một lượt trên sàn cứng')},
    {'icon': 'filter', 'text': L(
        'Washable Filter plus OLED Display for Tank and Power Status',
        '可水洗滤网 + OLED 屏实时显示水量电量',
        'Filtro lavable y pantalla OLED con estado de depósito y batería',
        'فلتر قابل للغسل وشاشة OLED لحالة الخزان والطاقة',
        'Filtre lavable et écran OLED pour l’état du réservoir et de la batterie',
        'Filter yang bisa dicuci plus layar OLED untuk status tangki dan daya',
        'Моющийся фильтр и OLED-дисплей состояния бака и заряда',
        'ตัวกรองล้างได้พร้อมจอ OLED แสดงสถานะถังและแบตเตอรี่',
        'Bộ lọc rửa được cùng màn hình OLED hiển thị trạng thái bình và pin')},
    {'icon': 'battery', 'text': L(
        'Brushless Motor with Bagless 0.8L Tank and LED Headlight',
        '无刷电机 · 0.8L 无尘袋水箱 · 前置 LED 照明灯',
        'Motor sin escobillas con depósito sin bolsa de 0,8 L y luz LED frontal',
        'محرك بدون فرشاة مع خزان بلا كيس سعة 0.8 لتر وإضاءة LED أمامية',
        'Moteur sans balais, réservoir sans sac de 0,8 L et éclairage LED avant',
        'Motor tanpa sikat dengan tangki tanpa kantong 0.8L dan lampu LED depan',
        'Бесщёточный двигатель, бак без мешка 0,8 л и светодиодная подсветка',
        'มอเตอร์ไม่มีแปรงถ่าน ถังไม่ใช้ถุง 0.8L และไฟ LED ด้านหน้า',
        'Động cơ không chổi than, bình không túi 0.8L và đèn LED phía trước')},
]

SPECS = [
    spec(LB_MODEL, ['PG16PRO'] * 9),
    spec(LB_MOTOR_PWR, ['230W'] * 9),
    spec(LB_MOTOR_TYPE, ['Brushless'] * 9),
    spec(LB_SUCTION, ['110AW (101–120AW)'] * 9),
    spec(LB_RUNTIME, ['≤30 min'] * 9),
    spec(LB_CHARGE, ['4–5 hours'] * 9),
    spec(LB_TANK, ['0.8L'] * 9),
    spec(LB_FILTER, ['Washable'] * 9),
    spec(LB_FUNCTION, ['Wet & Dry · Self-Cleaning'] * 9),
    spec(LB_NOZZLE, ['≤3 Attachments'] * 9),
    spec(LB_WEIGHT, ['≥3 kg'] * 9),
    spec(LB_PACKING, ['Color Box'] * 9),
    spec(LB_WARRANTY, ['1 Year'] * 9),
    spec(LB_AFTERSALES, ['Free Spare Parts'] * 9),
]

QUICK_SPECS = [
    quick(LB_MOTOR_PWR, ['230W'] * 9),
    quick(LB_SUCTION_Q, ['110AW'] * 9),
    quick(LB_RUNTIME, ['≤30 min'] * 9),
    quick(LB_TANK_Q, ['0.8L'] * 9),
]

DESCRIPTION = L(
    'The PG16PRO is a cordless wet & dry vacuum mop for hard floors. A 230W '
    'brushless motor produces 110AW of suction, and the roller brush washes and '
    'collects in one pass so you are not sweeping and mopping separately. Dirt '
    'goes into a bagless 0.8L tank with a washable filter, and the brush roll '
    'runs a self-cleaning cycle afterwards, so there is no need to touch the '
    'dirt by hand. An OLED panel shows tank level and remaining power, and a '
    'LED headlight picks up dust under furniture. Runtime is up to 30 minutes '
    'per charge, with a 4–5 hour recharge. OEM/ODM available: custom colour, '
    'plug type and packaging for your market. Certification documents are on '
    'file and available on request.',
    'PG16PRO 是一款面向硬地板的无线干湿两用吸尘拖把。230W 无刷电机提供 110AW '
    '吸力，滚刷一遍就能完成清洗与回收，不必先扫再拖。脏污进入 0.8L 无尘袋水箱，'
    '配可水洗滤网；用完后滚刷执行自清洁程序，双手无需接触脏污。OLED 面板显示水箱'
    '余量与剩余电量，前置 LED 照明灯能把家具底下的灰尘照出来。单次充电最长 30 '
    '分钟，充满需 4–5 小时。支持 OEM/ODM 定制颜色、插头规格与包装，认证资料已备案、'
    '可按需提供。',
    'La PG16PRO es una fregona aspiradora inalámbrica para suelos duros. Su motor '
    'sin escobillas de 230 W ofrece 110 AW de succión y el rodillo lava y recoge '
    'en una sola pasada, sin barrer y fregar por separado. La suciedad va a un '
    'depósito sin bolsa de 0,8 L con filtro lavable y el rodillo ejecuta después '
    'un ciclo de autolimpieza, sin tocar la suciedad con las manos. El panel OLED '
    'muestra el nivel del depósito y la batería, y la luz LED frontal revela el '
    'polvo bajo los muebles. Hasta 30 minutos de autonomía y recarga de 4–5 horas. '
    'Disponible en OEM/ODM con color, enchufe y embalaje personalizados. '
    'Documentos de certificación disponibles bajo solicitud.',
    'الPG16PRO ممسحة مكنسة لاسلكية للأرضيات الصلبة. يولد محرك بدون فرشاة بقدرة 230 '
    'واط شفطاً بقوة 110AW، وتغسل الفرشاة الأسطوانية وتجمع في تمريرة واحدة دون الحاجة '
    'إلى الكنس والمسح بشكل منفصل. تذهب الأوساخ إلى خزان بلا كيس سعة 0.8 لتر مع فلتر '
    'قابل للغسل، وتعمل الفرشاة بدورة تنظيف ذاتي بعد الاستخدام فلا حاجة للمس الأوساخ. '
    'تعرض لوحة OLED مستوى الخزان والطاقة المتبقية، ويكشف ضوء LED الأمامي الغبار تحت '
    'الأثاث. مدة التشغيل تصل إلى 30 دقيقة والشحن 4–5 ساعات. متاحة OEM/ODM مع تخصيص '
    'اللون والقابس والتغليف. وثائق الشهادات متاحة عند الطلب.',
    "La PG16PRO est un aspirateur-laveur sans fil pour sols durs. Son moteur sans "
    "balais de 230 W délivre 110 AW d’aspiration et la brosse lave et récupère en "
    "une seule passe, sans balayer puis laver séparément. Les saletés vont dans un "
    "réservoir sans sac de 0,8 L avec filtre lavable, puis la brosse effectue un "
    "cycle d’autonettoyage : pas besoin de toucher la saleté. Le panneau OLED "
    "affiche le niveau du réservoir et la batterie, et l’éclairage LED avant révèle "
    "la poussière sous les meubles. Jusqu’à 30 minutes d’autonomie pour 4–5 heures "
    "de recharge. Disponible en OEM/ODM avec couleur, prise et emballage "
    "personnalisés. Documents de certification disponibles sur demande.",
    'PG16PRO adalah pel dan vakum nirkabel untuk lantai keras. Motor tanpa sikat '
    '230W menghasilkan daya hisap 110AW, dan rol sikat mencuci sekaligus menyedot '
    'dalam satu kali jalan tanpa perlu menyapu lalu mengepel. Kotoran masuk ke '
    'tangki tanpa kantong 0.8L dengan filter yang bisa dicuci, dan rol sikat '
    'menjalankan siklus pembersihan otomatis sehingga tangan tidak perlu menyentuh '
    'kotoran. Panel OLED menampilkan sisa air dan daya, serta lampu LED depan '
    'menyinari debu di bawah furnitur. Waktu pakai hingga 30 menit dengan pengisian '
    '4–5 jam. Tersedia sebagai OEM/ODM dengan warna, colokan, dan kemasan khusus. '
    'Dokumen sertifikasi tersedia atas permintaan.',
    'PG16PRO — беспроводной моющий пылесос для твёрдых полов. Бесщёточный двигатель '
    '230 Вт обеспечивает всасывание 110 AW: щётка моет и собирает за один проход, '
    'не нужно отдельно подметать и мыть. Грязь попадает в бак объёмом 0,8 л без '
    'мешка с моющимся фильтром, после чего щётка выполняет цикл самоочистки — не '
    'нужно трогать грязь руками. OLED-панель показывает уровень бака и заряд, а '
    'светодиодная подсветка спереди выявляет пыль под мебелью. До 30 минут работы, '
    'зарядка 4–5 часов. Доступен как OEM/ODM с выбором цвета, вилки и упаковки. '
    'Сертификаты предоставляются по запросу.',
    'PG16PRO เครื่องดูดฝุ่นถูพื้นแบบไร้สายสำหรับพื้นแข็ง มอเตอร์ไม่มีแปรงถ่าน 230W '
    'ให้แรงดูด 110AW แปรงลูกกลิ้งล้างและดูดกลับในรอบเดียว ไม่ต้องแยกกวาดแล้วถู '
    'สิ่งสกปรกเข้าถังแบบไม่ใช้ถุง 0.8L พร้อมตัวกรองล้างได้ และแปรงจะเข้าสู่โปรแกรม '
    'ทำความสะอาดตัวเอง ไม่ต้องสัมผัสคราบสกปรก แผง OLED แสดงระดับถังและแบตเตอรี่ '
    'ไฟ LED ด้านหน้าช่วยให้เห็นฝุ่นใต้เฟอร์นิเจอร์ ใช้งานได้นานสุด 30 นาที ชาร์จ 4–5 '
    'ชั่วโมง พร้อมบริการ OEM/ODM ปรับสี หัวปลั๊ก และบรรจุภัณฑ์ เอกสารใบรับรองมีให้ '
    'ตามคำขอ',
    'PG16PRO là máy hút bụi lau nhà không dây cho sàn cứng. Động cơ không chổi than '
    '230W cho lực hút 110AW, con lăn vừa rửa vừa thu gom trong một lượt, không cần '
    'quét rồi lau riêng. Bụi bẩn đi vào bình không túi 0.8L với bộ lọc rửa được, sau '
    'đó con lăn chạy chu trình tự làm sạch nên không cần chạm tay vào vết bẩn. Màn '
    'hình OLED hiển thị mức bình và pin, đèn LED phía trước soi rõ bụi dưới gầm nội '
    'thất. Thời gian chạy tối đa 30 phút, sạc 4–5 giờ. Có sẵn dưới dạng OEM/ODM với '
    'tùy chọn màu sắc, phích cắm và bao bì. Tài liệu chứng nhận cung cấp khi có yêu cầu.',
)

APPLICATIONS = L(
    'Hard Floors, Tiles, Marble & Pet Hair Pickup',
    '硬地板、瓷砖、大理石与宠物毛发清理',
    'Suelos duros, baldosas, mármol y recogida de pelo de mascotas',
    'أرضيات صلبة وبلاط ورخام وجمع شعر الحيوانات الأليفة',
    'Sols durs, carrelage, marbre et poils d’animaux',
    'Lantai keras, keramik, marmer, dan bulu hewan peliharaan',
    'Твёрдые полы, плитка, мрамор и шерсть домашних животных',
    'พื้นแข็ง กระเบื้อง หินอ่อน และการเก็บขนสัตว์เลี้ยง',
    'Sàn cứng, gạch ốp, đá cẩm thạch & lông thú cưng',
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
    # VERIFY_TODO[0]：报价到手前刻意留空，不在 B2B 页面拍脑袋给价格
    'price_indicator': {},
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
    'alibaba_url': ('https://www.alibaba.com/product-detail/'
                    'Cordless-Wet-Dry-Vacuum-Cleaner-PG16PRO-1601780738060.html'),
    '_cat': 'handheld-vacuum',
}


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

    crlf = t.count('\r\n')
    lf = t.count('\n') - crlf
    assert lf == 0, '文件里混了 %d 个裸 LF（CRLF %d），先统一行尾再改' % (lf, crlf)
    eol = '\r\n'

    before = json.loads(t)
    ids = [p['id'] for p in before['products']]
    assert PID not in ids, '%s 已经在了，先手工确认再跑' % PID
    # 词典污染守门：本产品用到的英文标签必须至少有一个既有产品也用过，
    # 否则 gen_pages.py 的 last-write-wins 会把这条译文全站覆盖过去。
    existing_labels = set()
    for p in before['products']:
        for s in (p.get('specs') or []) + (p.get('quick_specs') or []):
            lab = s.get('label')
            if isinstance(lab, dict) and lab.get('en'):
                existing_labels.add(lab['en'])
    new_labels = sorted({s['label']['en'] for s in (SPECS + QUICK_SPECS)} - existing_labels)
    assert not new_labels, '引入了全新标签（会污染全站译文）：%s' % new_labels

    if not apply:
        print('当前 %d 个产品；将追加 %s（第 %d 个）' % (len(ids), PID, len(ids) + 1))

    a, b = array_span(t, 'products')
    k = b - 1
    while t[k] in ' \t\r\n,':
        k -= 1
    assert t[k] == '}', 'products 最后一个元素结尾不是 }'

    body = json.dumps(PRODUCT, ensure_ascii=False, indent=1)
    lines = body.split('\n')
    element = '  ' + lines[0] + eol + eol.join('  ' + ln for ln in lines[1:])

    out = t[:k + 1] + ',' + eol + element + t[k + 1:]

    assert len(out) > len(t), '插入后没有变长'
    after = json.loads(out)
    assert len(after['products']) == len(before['products']) + 1, '产品数不对'
    assert after['products'][-1]['id'] == PID, '新元素不在末尾'
    assert after['products'][:-1] == before['products'], '已有产品被改动了'
    for key in before:
        if key == 'products':
            continue
        assert after[key] == before[key], '顶层字段 %s 被改动了' % key
    assert out.count('\n') - out.count('\r\n') == 0, '写出的文本混了裸 LF'

    p = after['products'][-1]
    for field in ('name', 'tagline', 'description', 'applications'):
        assert set(p[field]) == set(LANGS), '%s 语种不齐：%s' % (field, sorted(p[field]))
    for h in p['highlights']:
        assert set(h['text']) == set(LANGS), 'highlights 语种不齐'
    for s in p['specs']:
        assert set(s['label']) == set(LANGS) and set(s['value']) == set(LANGS), 'specs 语种不齐'
    for s in p['quick_specs']:
        assert set(s['label']) == set(LANGS) and set(s['value']) == set(LANGS), 'quick_specs 语种不齐'
    qtexts = {v for s in p['quick_specs'] for v in s['value'].values()}
    for h in p['highlights']:
        assert h['text']['en'] not in qtexts, '亮点文案与药丸文案重复：%s' % h['text']['en']

    print('新元素 %d 字符，%d 个 highlights / %d 条 specs / %d 个 quick_specs'
          % (len(element), len(p['highlights']), len(p['specs']), len(p['quick_specs'])))
    if not apply:
        print('\n预演模式，未写入。加 --apply 真正写入。')
        return 0

    with io.open(PATH, 'w', encoding='utf-8', newline='') as f:
        f.write(out)
    print('\n已写入 %s。现在需要：' % PID)
    print('  1) scripts/set_detail_images.py --apply            （写 detail_images 字段）')
    print('  2) scripts/apply_alibaba_images.py --apply --only handheld-vacuum/%s' % PID)
    print('  3) scripts/gen_product_page.py 生成 en/zh 详情页')
    print('  4) scripts/add_to_category.py 同步品类页')
    print('  5) scripts/gen_pages.py 生成 ar/es/fr/id/ru/th/vi')
    print()
    print('发布前必须确认：')
    for i, t2 in enumerate(VERIFY_TODO, 1):
        print('  %d) %s' % (i, t2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
