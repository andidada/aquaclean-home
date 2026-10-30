# -*- coding: utf-8 -*-
"""新增品类 hands-free-soap-dispenser —— 数据层（幂等）。

产出
  1. data/products/categories.json        surgical 插入品类条目（该文件行尾混杂，
                                          整体 dump 会重排，所以只能用锚点插入）
  2. data/products/hands-free-soap-dispenser.json   新建（9 语种）
  3. data/i18n/{en,ar,es,fr,id,ru,th,vi}.json       增量：categoryPage / guideTitle /
                                          guideValues / specNote
  4. data/i18n/category-guides.json       新 slug 的购买指南卡片

所有英文串都从本文件的 EN_* 常量出发生成，品类页 HTML 也读同一份，
保证 gen_pages.py 的 exact 匹配一定能命中。
"""
from __future__ import annotations
import io
import json
import os
import re
import shutil
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SLUG = 'hands-free-soap-dispenser'
PID = 'sd901'
VER = '?v=20261030a'          # 资源缓存戳
IMGDIR = '/assets/images/products/hands-free-soap-dispenser-sd901'
CARD_IMG = '../assets/images/products/21-hands-free-soap-dispenser.webp' + VER

LANGS = ['en', 'zh', 'ar', 'es', 'fr', 'id', 'ru', 'th', 'vi']
I18N_LANGS = ['en', 'ar', 'es', 'fr', 'id', 'ru', 'th', 'vi']   # zh 手工维护，无 i18n 文件

# ---------------------------------------------------------------------------
# 品类级文案（同时写入 categories.json 与 en 页hero，必须逐字一致）
# ---------------------------------------------------------------------------
CAT_NAME = {
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
CAT_DESC = {
    'en': 'Touch-free automatic foam soap dispensers with four output levels (0.25–1.0 s). Infra-red sensor, USB-C rechargeable battery, 300 ml visible tank and an IPX4 splash-proof body — for bathrooms, kitchens, hotels, clinics and offices.',
    'zh': '免接触自动泡沫洗手机，四档出液（0.25–1.0 秒）。红外感应、USB-C 充电电池、300 ml 可视水箱与 IPX4 防溅机身，适用于卫浴、厨房、酒店、诊所与办公室。',
    'ar': 'موزعات صابون رغوية أوتوماتيكية بدون لمس بأربعة مستويات ضخ (٠٫٢٥–١٫٠ ثانية). مستشعر أشعة تحت الحمراء وبطارية قابلة للشحن عبر USB-C وخزان مرئي ٣٠٠ مل وجسم مقاوم لرذاذ الماء IPX4 — للحمامات والمطابخ والفنادق والعيادات والمكاتب.',
    'es': 'Dispensadores automáticos de espuma de jabón sin contacto con cuatro niveles de salida (0,25–1,0 s). Sensor infrarrojo, batería recargable USB-C, depósito visible de 300 ml y cuerpo resistente a salpicaduras IPX4 — para baños, cocinas, hoteles, clínicas y oficinas.',
    'fr': 'Distributeurs automatiques de mousse de savon sans contact avec quatre niveaux de distribution (0,25–1,0 s). Capteur infrarouge, batterie rechargeable USB-C, réservoir visible de 300 ml et corps anti-éclaboussures IPX4 — pour salles de bain, cuisines, hôtels, cliniques et bureaux.',
    'id': 'Dispenser sabun busa otomatis tanpa sentuh dengan empat tingkat keluaran (0,25–1,0 dtk). Sensor inframerah, baterai isi ulang USB-C, tangki terlihat 300 ml, dan bodi tahan cipratan IPX4 — untuk kamar mandi, dapur, hotel, klinik, dan kantor.',
    'ru': 'Бесконтактные автоматические пенные дозаторы мыла с четырьмя уровнями подачи (0,25–1,0 с). Инфракрасный датчик, аккумулятор с зарядкой USB-C, видимый бак на 300 мл и влагозащищённый корпус IPX4 — для ванных, кухонь, отелей, клиник и офисов.',
    'th': 'เครื่องจ่ายสบู่โฟมอัตโนมัติแบบไม่ต้องสัมผัส มีระดับจ่าย 4 ระดับ (0.25–1.0 วินาที) เซ็นเซอร์อินฟราเรด แบตเตอรี่ชาร์จได้ USB-C ถังมองเห็นได้ 300 มล. และตัวเครื่องกันน้ำกระเซ็น IPX4 — สำหรับห้องน้ำ ห้องครัว โรงแรม คลินิก และออฟฟิศ',
    'vi': 'Bình đựng xà phòng bọt tự động không cần chạm với bốn mức nhả (0,25–1,0 giây). Cảm biến hồng ngoại, pin sạc USB-C, bình chứa 300 ml có cửa sổ quan sát và thân chống tạt nước IPX4 — cho phòng tắm, bếp, khách sạn, phòng khám và văn phòng.',
}

WHY_TITLE = {
    'en': 'Why Choose Our Hands-free Soap Dispensers?',
    'zh': '为什么选择我们的免接触泡沫洗手机？',
    'ar': 'لماذا تختار موزعات الصابون الأوتوماتيكية منّا؟',
    'es': '¿Por qué elegir nuestros dispensadores automáticos de jabón?',
    'fr': 'Pourquoi choisir nos distributeurs automatiques de savon ?',
    'id': 'Mengapa memilih dispenser sabun otomatis kami?',
    'ru': 'Почему выбирают наши автоматические дозаторы мыла?',
    'th': 'ทำไมต้องเลือกเครื่องจ่ายสบู่อัตโนมัติของเรา?',
    'vi': 'Vì sao chọn bình đựng xà phòng tự động của chúng tôi?',
}
GUIDE_TITLE = {
    'en': 'How to Choose a Hands-free Soap Dispenser',
    'zh': '如何挑选免接触泡沫洗手机',
    'ar': 'كيف تختار موزع صابون أوتوماتيكي',
    'es': 'Cómo elegir un dispensador automático de jabón',
    'fr': 'Comment choisir un distributeur automatique de savon',
    'id': 'Cara memilih dispenser sabun otomatis',
    'ru': 'Как выбрать автоматический дозатор мыла',
    'th': 'วิธีเลือกเครื่องจ่ายสบู่อัตโนมัติ',
    'vi': 'Cách chọn bình đựng xà phòng tự động',
}
OEM_TITLE = {
    'en': 'Need OEM / ODM for Hands-free Soap Dispensers?',
    'zh': '需要免接触泡沫洗手机的 OEM / ODM？',
    'ar': 'تحتاج OEM / ODM لموزعات الصابون الأوتوماتيكية؟',
    'es': '¿Necesita OEM / ODM para dispensadores automáticos de jabón?',
    'fr': 'Besoin d\'OEM / ODM pour distributeurs automatiques de savon ?',
    'id': 'Butuh OEM / ODM untuk dispenser sabun otomatis?',
    'ru': 'Нужен OEM / ODM для автоматических дозаторов мыла?',
    'th': 'ต้องการ OEM / ODM สำหรับเครื่องจ่ายสบู่อัตโนมัติ?',
    'vi': 'Cần OEM / ODM cho bình đựng xà phòng tự động?',
}
OEM_SUB = {
    'en': 'Custom logo, colour and packaging · samples 7–14 days · production 25–35 days',
    'zh': '定制logo、颜色与包装 · 样品 7–14 天 · 量产 25–35 天',
    'ar': 'شعار ولون وتغليف مخصص · عينات ٧–١٤ يوماً · إنتاج ٢٥–٣٥ يوماً',
    'es': 'Logotipo, color y embalaje personalizados · muestras 7–14 días · producción 25–35 días',
    'fr': 'Logo, couleur et emballage personnalisés · échantillons 7–14 jours · production 25–35 jours',
    'id': 'Logo, warna, dan kemasan khusus · sampel 7–14 hari · produksi 25–35 hari',
    'ru': 'Свой логотип, цвет и упаковка · образцы 7–14 дней · производство 25–35 дней',
    'th': 'ปรับโลโก้ สี และบรรจุภัณฑ์ได้ · ตัวอย่าง 7–14 วัน · ผลิต 25–35 วัน',
    'vi': 'Tùy chỉnh logo, màu sắc và bao bì · mẫu 7–14 ngày · sản xuất 25–35 ngày',
}
COUNT_SUB = {
    'en': '1 model in this category right now — see the table below for MOQ, indicative FOB price and key specifications.',
    'zh': '该类目当前共 1 个型号 — 起订量、参考 FOB 价格与关键规格见下表。',
    'ar': 'يوجد موديل واحد في هذا التصنيف حالياً — راجع الجدول أدناه لمعرفة الحد الأدنى للطلب وسعر FOB الاسترشادي وأهم المواصفات.',
    'es': '1 modelo en esta categoría actualmente — consulte la tabla siguiente para el MOQ, el precio FOB orientativo y las especificaciones clave.',
    'fr': '1 modèle dans cette catégorie actuellement — consultez le tableau ci-dessous pour le MOQ, le prix FOB indicatif et les spécifications clés.',
    'id': 'Saat ini ada 1 model dalam kategori ini — lihat tabel di bawah untuk MOQ, harga FOB indikatif, dan spesifikasi utama.',
    'ru': 'Сейчас в этой категории 1 модель — см. таблицу ниже с MOQ, ориентировочной ценой FOB и ключевыми характеристиками.',
    'th': 'ปัจจุบันมี 1 รุ่นในหมวดนี้ — ดู MOQ ราคา FOB โดยประมาณ และสเปกสำคัญได้ในตารางด้านล่าง',
    'vi': 'Hiện có 1 mẫu trong danh mục này — xem MOQ, giá FOB tham khảo và thông số chính ở bảng dưới.',
}

# ---------------------------------------------------------------------------
# 购买指南卡片（5 张）
# ---------------------------------------------------------------------------
GUIDE_CARDS = [
    {
        'title': {
            'en': 'Output Levels', 'zh': '出液档位',
            'ar': 'مستويات الضخ', 'es': 'Niveles de salida',
            'fr': 'Niveaux de distribution', 'id': 'Tingkat keluaran',
            'ru': 'Режимы подачи', 'th': 'ระดับการจ่าย', 'vi': 'Mức nhả',
        },
        'values': {
            'en': '0.25–1.0 s', 'zh': '0.25–1.0 秒',
            'ar': '٠٫٢٥–١٫٠ ثانية', 'es': '0,25–1,0 s',
            'fr': '0,25–1,0 s', 'id': '0,25–1,0 dtk',
            'ru': '0,25–1,0 с', 'th': '0.25–1.0 วินาที', 'vi': '0,25–1,0 giây',
        },
        'explain': {
            'en': 'Four dispensing times cover everything from a quick rinse to a full wash — the difference between waste and good value on a hotel floor.',
            'zh': '四档出液覆盖从快速冲洗到彻底洗净的全部场景，直接决定酒店场景下的耗材成本。',
            'ar': 'أربعة أوقات ضخ تغطي كل شيء من الشطف السريع إلى الغسل الكامل — الفرق بين الهدر والقيمة الجيدة في فندق.',
            'es': 'Cuatro tiempos de dosificación cubren desde un aclarado rápido hasta un lavado completo: la diferencia entre desperdicio y buen rendimiento en un hotel.',
            'fr': 'Quatre durées de distribution couvrent tout, du rinçage rapide au lavage complet : la différence entre gaspillage et bon rendement à l\'hôtel.',
            'id': 'Empat durasi keluaran mencakup semuanya dari bilas cepat hingga cuci penuh — beda antara pemborosan dan nilai baik di lantai hotel.',
            'ru': 'Четыре времени подачи перекрывают всё — от быстрого ополаскивания до полного мытья; именно здесь кроется разница между расходом и экономией в отеле.',
            'th': 'เวลาจ่าย 4 ระดับครอบคลุมตั้งแต่ล้างเร็วไปจนถึงล้างเต็มรูปแบบ — ต่างกันระหว่างการสิ้นเปลืองกับความคุ้มค่าในโรงแรม',
            'vi': 'Bốn thời gian nhả bao phủ từ xả nhanh đến rửa kỹ — khác biệt giữa lãng phí và hiệu quả tại khách sạn.',
        },
    },
    {
        'title': {
            'en': 'Soap Tank Capacity', 'zh': '皂液容量',
            'ar': 'سعة خزان الصابون', 'es': 'Capacidad del depósito',
            'fr': 'Capacité du réservoir', 'id': 'Kapasitas tangki sabun',
            'ru': 'Объём бака для мыла', 'th': 'ความจุถังสบู่', 'vi': 'Dung tích bình xà phòng',
        },
        'values': {
            'en': '300 ml', 'zh': '300 ml', 'ar': '٣٠٠ مل', 'es': '300 ml',
            'fr': '300 ml', 'id': '300 ml', 'ru': '300 мл', 'th': '300 มล.', 'vi': '300 ml',
        },
        'explain': {
            'en': 'A 300 ml tank runs for weeks in a family bathroom and refills tool-free through the top panel.',
            'zh': '300 ml 水箱在家庭卫浴可用数周，从顶部面板徒手补液，无需工具。',
            'ar': 'خزان ٣٠٠ مل يكفي لأسابيع في حمام عائلي ويمكن إعادة تعبئته من الأعلى دون أدوات.',
            'es': 'Un depósito de 300 ml dura semanas en un baño familiar y se rellena desde la tapa superior sin herramientas.',
            'fr': 'Un réservoir de 300 ml dure plusieurs semaines dans une salle de bain familiale et se remplit par le dessus sans outil.',
            'id': 'Tangki 300 ml bertahan berminggu-minggu di kamar mandi keluarga dan diisi ulang dari atas tanpa alat.',
            'ru': 'Бак на 300 мл работает неделями в семейной ванной и пополняется сверху без инструментов.',
            'th': 'ถัง 300 มล. ใช้ได้หลายสัปดาห์ในห้องน้ำครอบครัว และเติมจากด้านบนได้โดยไม่ต้องใช้เครื่องมือ',
            'vi': 'Bình 300 ml dùng nhiều tuần trong phòng tắm gia đình và châm lại từ nắp trên không cần dụng cụ.',
        },
    },
    {
        'title': {
            'en': 'Sensing Distance', 'zh': '感应距离',
            'ar': 'مسافة الاستشعار', 'es': 'Distancia de detección',
            'fr': 'Distance de détection', 'id': 'Jarak sensor',
            'ru': 'Дальность срабатывания', 'th': 'ระยะตรวจจับ', 'vi': 'Khoảng cách cảm biến',
        },
        'values': {
            'en': '0–7 cm', 'zh': '0–7 厘米', 'ar': '٠–٧ سم', 'es': '0–7 cm',
            'fr': '0–7 cm', 'id': '0–7 cm', 'ru': '0–7 см', 'th': '0–7 ซม.', 'vi': '0–7 cm',
        },
        'explain': {
            'en': 'Infra-red sensing triggers inside 7 cm and stops the instant hands leave — no drips, no pumps running dry.',
            'zh': '红外感应在 7 厘米内触发，手一离开立即停止，不滴漏、泵体不会空转。',
            'ar': 'الاستشعار بالأشعة تحت الحمراء يعمل خلال ٧ سم ويتوقف لحظة سحب اليدين — لا تنقيط ولا مضخة تعمل بلا سوائل.',
            'es': 'El sensor infrarrojo se activa dentro de 7 cm y se detiene en cuanto las manos se retiran: sin goteos ni bomba en vacío.',
            'fr': 'Le capteur infrarouge se déclenche à moins de 7 cm et s\'arrête dès que les mains s\'éloignent : pas de gouttes, pas de pompe à vide.',
            'id': 'Sensor inframerah aktif dalam 7 cm dan berhenti segera saat tangan menjauh — tidak menetes, pompa tidak berjalan kosong.',
            'ru': 'Инфракрасный датчик срабатывает в пределах 7 см и мгновенно останавливается, когда убрали руки: ни капель, ни работы всухую.',
            'th': 'เซ็นเซอร์อินฟราเรดทำงานภายใน 7 ซม. และหยุดทันทีเมื่อมือออก ไม่หยด ปั๊มไม่รันเปล่า',
            'vi': 'Cảm biến hồng ngoại kích hoạt trong 7 cm và dừng ngay khi rút tay — không nhỏ giọt, bơm không chạy khan.',
        },
    },
    {
        'title': {
            'en': 'Waterproof Rating', 'zh': '防水等级',
            'ar': 'تصنيف مقاومة الماء', 'es': 'Índice de impermeabilidad',
            'fr': 'Indice d\'étanchéité', 'id': 'Tingkat kedap air',
            'ru': 'Степень влагозащиты', 'th': 'ระดับกันน้ำ', 'vi': 'Mức chống nước',
        },
        'values': {
            'en': 'IPX4', 'zh': 'IPX4', 'ar': 'IPX4', 'es': 'IPX4',
            'fr': 'IPX4', 'id': 'IPX4', 'ru': 'IPX4', 'th': 'IPX4', 'vi': 'IPX4',
        },
        'explain': {
            'en': 'IPX4 splash-proof construction survives the taps, sinks and constant wiping a washroom countertop gets.',
            'zh': 'IPX4 防溅结构足以应对洗手台上的水龙头溅水与频繁擦拭。',
            'ar': 'هيكل IPX4 المقاوم للرذاذ يتحمل رذاذ الصنبور والمسح المتكرر على سطح الحمام.',
            'es': 'La construcción IPX4 resistente a salpicaduras soporta grifos, lavabos y la limpieza constante del mostrador.',
            'fr': 'La construction anti-éclaboussures IPX4 supporte robinets, lavabos et nettoyage fréquent du plan vasque.',
            'id': 'Konstruksi tahan cipratan IPX4 tahan terhadap keran, wastafel, dan seringnya mengelap meja wastafel.',
            'ru': 'Конструкция IPX4 держит брызги от крана, раковины и постоянную протирку столешницы.',
            'th': 'โครงสร้างกันละอองน้ำ IPX4 ทนก๊อกน้ำ อ่างล้างหน้า และการเช็ดถูตลอดเวลาของเคาน์เตอร์',
            'vi': 'Kết cấu chống tạt IPX4 chịu được vòi nước, chậu rửa và việc lau chùi liên tục trên mặt bàn.',
        },
    },
    {
        'title': {
            'en': 'Battery & Charging', 'zh': '电池与充电',
            'ar': 'البطارية والشحن', 'es': 'Batería y carga',
            'fr': 'Batterie et recharge', 'id': 'Baterai & pengisian',
            'ru': 'Аккумулятор и зарядка', 'th': 'แบตเตอรี่และการชาร์จ', 'vi': 'Pin và sạc',
        },
        'values': {
            'en': 'USB-C', 'zh': 'USB-C', 'ar': 'USB-C', 'es': 'USB-C',
            'fr': 'USB-C', 'id': 'USB-C', 'ru': 'USB-C', 'th': 'USB-C', 'vi': 'USB-C',
        },
        'explain': {
            'en': 'USB-C recharging shares one cable with your phone — one charge covers weeks of normal family use.',
            'zh': 'USB-C 充电可与手机共用一根线，一次充电可满足普通家庭数周使用。',
            'ar': 'الشحن عبر USB-C يشارك كابلاً واحداً مع هاتفك — شحنة واحدة تكفي أسابيع من الاستخدام العائلي.',
            'es': 'La recarga USB-C comparte un solo cable con el móvil: una carga cubre semanas de uso familiar normal.',
            'fr': 'La recharge USB-C partage le même câble que le téléphone : une charge couvre plusieurs semaines d\'usage familial.',
            'id': 'Pengisian USB-C berbagi satu kabel dengan ponsel Anda — satu kali cas cukup untuk berminggu-minggu pemakaian keluarga.',
            'ru': 'Зарядка USB-C использует тот же кабель, что и телефон; одной зарядки хватает на недели обычного домашнего использования.',
            'th': 'ชาร์จ USB-C ใช้สายเดียวกับมือถือได้ — ชาร์จครั้งเดียวใช้ได้หลายสัปดาห์สำหรับครอบครัว',
            'vi': 'Sạc USB-C dùng chung cáp với điện thoại — một lần sạc dùng được nhiều tuần cho gia đình.',
        },
    },
]

# ---------------------------------------------------------------------------
# 产品 SD-901
# ---------------------------------------------------------------------------
P_NAME = {
    'en': 'SD-901 Automatic Foam Soap Dispenser · 4-Level Smart Output',
    'zh': 'SD-901 自动泡沫洗手机 · 四档智能出液',
    'ar': 'موزع صابون رغوي أوتوماتيكي SD-901 · 4 مستويات ذكية',
    'es': 'Dispensador automático de espuma de jabón SD-901 · 4 niveles inteligentes',
    'fr': 'Distributeur automatique de mousse de savon SD-901 · 4 niveaux intelligents',
    'id': 'Dispenser sabun busa otomatis SD-901 · keluaran pintar 4 tingkat',
    'ru': 'Автоматический пенный дозатор мыла SD-901 · 4 умных режима',
    'th': 'เครื่องจ่ายสบู่โฟมอัตโนมัติ SD-901 · จ่าย 4 ระดับอัจฉริยะ',
    'vi': 'Bình đựng xà phòng bọt tự động SD-901 · 4 mức nhả thông minh',
}
P_TAGLINE = {
    'en': '4 Output Levels · 0.25–1.0s · Touch Switch · USB-C Rechargeable',
    'zh': '四档出液 · 0.25–1.0 秒 · 触摸开关 · USB-C 充电',
    'ar': '4 مستويات ضخ · ٠٫٢٥–١٫٠ ثانية · مفتاح لمس · شحن USB-C',
    'es': '4 niveles de salida · 0,25–1,0 s · interruptor táctil · recargable USB-C',
    'fr': '4 niveaux de distribution · 0,25–1,0 s · commande tactile · rechargeable USB-C',
    'id': '4 tingkat keluaran · 0,25–1,0 dtk · tombol sentuh · isi ulang USB-C',
    'ru': '4 режима подачи · 0,25–1,0 с · сенсорная кнопка · зарядка USB-C',
    'th': 'จ่าย 4 ระดับ · 0.25–1.0 วินาที · สวิตช์สัมผัส · ชาร์จ USB-C ได้',
    'vi': '4 mức nhả · 0,25–1,0 giây · nút cảm ứng · sạc USB-C',
}
P_HIGHLIGHTS = [
    {   # power
        'en': 'Four output levels — 0.25 / 0.5 / 0.75 / 1.0 s — cover every handwashing habit in the family',
        'zh': '四档出液 0.25 / 0.5 / 0.75 / 1.0 秒，满足全家不同的洗手习惯',
        'ar': 'أربعة مستويات ضخ — ٠٫٢٥ / ٠٫٥ / ٠٫٧٥ / ١٫٠ ثانية — تغطي كل عادات غسل اليدين في الأسرة',
        'es': 'Cuatro niveles de salida — 0,25 / 0,5 / 0,75 / 1,0 s — cubren todos los hábitos de lavado de la familia',
        'fr': 'Quatre niveaux de distribution — 0,25 / 0,5 / 0,75 / 1,0 s — couvrent toutes les habitudes de la famille',
        'id': 'Empat tingkat keluaran — 0,25 / 0,5 / 0,75 / 1,0 dtk — mencakup semua kebiasaan cuci tangan keluarga',
        'ru': 'Четыре уровня подачи — 0,25 / 0,5 / 0,75 / 1,0 с — покрывают любые привычки мытья рук в семье',
        'th': 'ระดับจ่าย 4 ระดับ — 0.25 / 0.5 / 0.75 / 1.0 วินาที — ครอบคลุมทุกพฤติกรรมการล้างมือในครอบครัว',
        'vi': 'Bốn mức nhả — 0,25 / 0,5 / 0,75 / 1,0 giây — đáp ứng mọi thói quen rửa tay của gia đình',
    },
    {   # battery
        'en': 'Touch switch on the slanted top panel with three LED indicators showing the selected level',
        'zh': '斜面顶部面板触摸开关，三颗 LED 指示灯显示当前档位',
        'ar': 'مفتاح لمس على اللوحة العلوية المائلة مع ثلاثة مؤشرات LED توضح المستوى المحدد',
        'es': 'Interruptor táctil en el panel superior inclinado con tres indicadores LED del nivel seleccionado',
        'fr': 'Commande tactile sur le panneau supérieur incliné avec trois témoins LED du niveau sélectionné',
        'id': 'Tombol sentuh di panel atas miring dengan tiga indikator LED untuk tingkat yang dipilih',
        'ru': 'Сенсорная кнопка на наклонной верхней панели и три светодиода, показывающие выбранный уровень',
        'th': 'สวิตช์สัมผัสบนแผงบนเอียง พร้อมไฟ LED 3 ดวงแสดงระดับที่เลือก',
        'vi': 'Nút cảm ứng trên mặt nghiêng phía trên cùng ba đèn LED hiển thị mức đang chọn',
    },
    {   # filter
        'en': 'Short drip-free nozzle above the sensor keeps both the spout and the countertop clean',
        'zh': '感应区上方的短喷嘴防滴漏，出液口与台面都保持洁净',
        'ar': 'فوهة قصيرة لا تقطر أعلى المستشعر تحافظ على نظافة الفوهة وسطح العمل',
        'es': 'Boquilla corta antigoteo sobre el sensor: limpia la salida y el mostrador',
        'fr': 'Bec court anti-goutte au-dessus du capteur : la sortie et le plan de travail restent propres',
        'id': 'Nozel pendek bebas tetes di atas sensor menjaga mulut dan meja tetap bersih',
        'ru': 'Короткий носик без подтекания над датчиком сохраняет чистоту и носика, и столешницы',
        'th': 'หัวจ่ายสั้นกันหยดอยู่เหนือเซ็นเซอร์ ช่วยให้ทั้งหัวจ่ายและเคาน์เตอร์สะอาด',
        'vi': 'Đầu nhả ngắn không nhỏ giọt phía trên cảm biến giữ cả miệng bình và mặt bàn sạch',
    },
    {   # check
        'en': '300 ml tank read through a clear window, with USB-C recharging and quiet operation below 60 dB',
        'zh': '300 ml 水箱配透明视窗，USB-C 充电，运行噪音低于 60 分贝',
        'ar': 'خزان ٣٠٠ مل مع نافذة شفافة للمراقبة وشحن USB-C وتشغيل هادئ أقل من ٦٠ ديسيبل',
        'es': 'Depósito de 300 ml con ventana transparente, recarga USB-C y funcionamiento silencioso por debajo de 60 dB',
        'fr': 'Réservoir de 300 ml avec fenêtre transparente, recharge USB-C et fonctionnement silencieux sous 60 dB',
        'id': 'Tangki 300 ml dengan jendela bening, isi ulang USB-C, dan operasi senyap di bawah 60 dB',
        'ru': 'Бак 300 мл с прозрачным окном, зарядка USB-C и тихая работа ниже 60 дБ',
        'th': 'ถัง 300 มล. มีหน้าต่างใบสมองเห็นระดับ ชาร์จ USB-C และทำงานเงียบต่ำกว่า 60 เดซิเบล',
        'vi': 'Bình 300 ml có cửa sổ trong để xem mức, sạc USB-C và vận hành êm dưới 60 dB',
    },
]

P_SPECS = [
    ('Model', '型号', 'Modelo', 'Modèle', 'Model', 'Модель', 'รุ่น', 'Model', 'الموديل',
     {'en': 'SD-901', 'zh': 'SD-901', 'es': 'SD-901', 'fr': 'SD-901', 'id': 'SD-901',
      'ru': 'SD-901', 'th': 'SD-901', 'vi': 'SD-901', 'ar': 'SD-901'}),
    ('Output Levels', '出液档位', 'Niveles de salida', 'Niveaux de distribution',
     'Tingkat keluaran', 'Режимы подачи', 'ระดับการจ่าย', 'Mức nhả', 'مستويات الضخ',
     {'en': '4 levels (0.25 / 0.5 / 0.75 / 1.0 s)',
      'zh': '4 档（0.25 / 0.5 / 0.75 / 1.0 秒）',
      'es': '4 niveles (0,25 / 0,5 / 0,75 / 1,0 s)',
      'fr': '4 niveaux (0,25 / 0,5 / 0,75 / 1,0 s)',
      'id': '4 tingkat (0,25 / 0,5 / 0,75 / 1,0 dtk)',
      'ru': '4 режима (0,25 / 0,5 / 0,75 / 1,0 с)',
      'th': '4 ระดับ (0.25 / 0.5 / 0.75 / 1.0 วินาที)',
      'vi': '4 mức (0,25 / 0,5 / 0,75 / 1,0 giây)',
      'ar': '4 مستويات (٠٫٢٥ / ٠٫٥ / ٠٫٧٥ / ١٫٠ ثانية)'}),
    ('Soap Tank Capacity', '皂液容量', 'Capacidad del depósito', 'Capacité du réservoir',
     'Kapasitas tangki sabun', 'Объём бака для мыла', 'ความจุถังสบู่', 'Dung tích bình xà phòng',
     'سعة خزان الصابون',
     {'en': '300 ml', 'zh': '300 ml', 'es': '300 ml', 'fr': '300 ml', 'id': '300 ml',
      'ru': '300 мл', 'th': '300 มล.', 'vi': '300 ml', 'ar': '٣٠٠ مل'}),
    ('Material', '材质', 'Material', 'Matériau', 'Material', 'Материал', 'วัสดุ',
     'Chất liệu', 'المادة',
     {'en': 'ABS + PP', 'zh': 'ABS + PP', 'es': 'ABS + PP', 'fr': 'ABS + PP', 'id': 'ABS + PP',
      'ru': 'ABS + PP', 'th': 'ABS + PP', 'vi': 'ABS + PP', 'ar': 'ABS + PP'}),
    ('Power Source', '电源方式', 'Fuente de alimentación', "Source d'alimentation",
     'Sumber daya', 'Источник питания', 'แหล่งจ่ายไฟ', 'Nguồn điện', 'مصدر الطاقة',
     {'en': 'Battery, USB', 'zh': '电池 + USB', 'es': 'Batería, USB', 'fr': 'Batterie, USB',
      'id': 'Baterai, USB', 'ru': 'Аккумулятор, USB', 'th': 'แบตเตอรี่, USB',
      'vi': 'Pin, USB', 'ar': 'بطارية، USB'}),
    ('Sensing Distance', '感应距离', 'Distancia de detección', 'Distance de détection',
     'Jarak sensor', 'Дальность срабатывания', 'ระยะตรวจจับ', 'Khoảng cách cảm biến',
     'مسافة الاستشعار',
     {'en': '0–7 cm', 'zh': '0–7 厘米', 'es': '0–7 cm', 'fr': '0–7 cm', 'id': '0–7 cm',
      'ru': '0–7 см', 'th': '0–7 ซม.', 'vi': '0–7 cm', 'ar': '٠–٧ سم'}),
    ('Waterproof Rating', '防水等级', 'Índice de impermeabilidad', "Indice d'étanchéité",
     'Tingkat kedap air', 'Степень влагозащиты', 'ระดับกันน้ำ', 'Mức chống nước',
     'تصنيف مقاومة الماء',
     {'en': 'IPX4', 'zh': 'IPX4', 'es': 'IPX4', 'fr': 'IPX4', 'id': 'IPX4', 'ru': 'IPX4',
      'th': 'IPX4', 'vi': 'IPX4', 'ar': 'IPX4'}),
    ('Noise Level', '噪音水平', 'Nivel de ruido', 'Niveau sonore', 'Tingkat kebisingan',
     'Уровень шума', 'ระดับเสียง', 'Độ ồn', 'مستوى الضجيج',
     {'en': '< 60 dB', 'zh': '< 60 分贝', 'es': '< 60 dB', 'fr': '< 60 dB', 'id': '< 60 dB',
      'ru': '< 60 дБ', 'th': '< 60 เดซิเบล', 'vi': '< 60 dB', 'ar': '< 60 ديسيبل'}),
    ('Packaging Type', '包装类型', 'Tipo de embalaje', "Type d'emballage", 'Jenis kemasan',
     'Тип упаковки', 'ประเภทบรรจุภัณฑ์', 'Loại bao bì', 'نوع التغليف',
     {'en': 'Corrugated Box, Color Box', 'zh': '瓦楞纸箱、彩盒', 'es': 'Caja de cartón, caja de color',
      'fr': 'Carton ondulé, boîte couleur', 'id': 'Karton bergelombang, kotak warna',
      'ru': 'Гофрокоробка, цветная коробка', 'th': 'กล่องลูกฟูก กล่องสี',
      'vi': 'Thùng carton, hộp màu', 'ar': 'علبة كرتون، علبة ملونة'}),
    ('Private Mould', '私模', 'Molde privado', 'Moule privé', 'Cetakan pribadi',
     'Собственная пресс-форма', 'แม่พิมพ์ส่วนตัว', 'Khuôn riêng', 'قالب خاص',
     {'en': 'Yes', 'zh': '是', 'es': 'Sí', 'fr': 'Oui', 'id': 'Ya', 'ru': 'Да', 'th': 'มี',
      'vi': 'Có', 'ar': 'نعم'}),
    ('Place of Origin', '产地', 'País de origen', "Pays d'origine", 'Negara asal',
     'Страна производства', 'แหล่งผลิต', 'Xuất xứ', 'بلد المنشأ',
     {'en': 'Guangdong, China', 'zh': '中国广东', 'es': 'Guangdong, China',
      'fr': 'Guangdong, Chine', 'id': 'Guangdong, Tiongkok', 'ru': 'Гуандун, Китай',
      'th': 'กว่างตง จีน', 'vi': 'Quảng Đông, Trung Quốc', 'ar': 'قوانغدونغ، الصين'}),
]

QUICK_IDX = (1, 2, 3, 5)      # specs 中进入 quick_specs 的行号

P_APPLICATIONS = {
    'en': 'Home bathroom, kitchen, hotel washroom, restaurant, clinic, office & public washrooms',
    'zh': '家庭卫浴、厨房、酒店洗手间、餐厅、诊所、办公室及公共洗手间',
    'ar': 'حمام المنزل والمطبخ ودورات مياه الفنادق والمطاعم والعيادات والمكاتب والمرافق العامة',
    'es': 'Baño del hogar, cocina, aseos de hotel, restaurante, clínica, oficina y aseos públicos',
    'fr': 'Salle de bain, cuisine, sanitaires d\'hôtel, restaurant, clinique, bureau et sanitaires publics',
    'id': 'Kamar mandi rumah, dapur, toilet hotel, restoran, klinik, kantor, dan toilet umum',
    'ru': 'Домашняя ванная, кухня, санузлы отелей, рестораны, клиники, офисы и общественные туалеты',
    'th': 'ห้องน้ำบ้าน ห้องครัว ห้องน้ำโรงแรม ร้านอาหาร คลินิก ออฟฟิศ และห้องน้ำสาธารณะ',
    'vi': 'Phòng tắm gia đình, nhà bếp, nhà vệ sinh khách sạn, nhà hàng, phòng khám, văn phòng và nhà vệ sinh công cộng',
}
P_DESCRIPTION = {
    'en': 'The SD-901 is a touch-free automatic foam soap dispenser built around a four-step output dial: 0.25, 0.5, 0.75 and 1.0 seconds of foam per trigger. A capacitive touch switch on the slanted top panel selects the level and three LED indicators confirm it. The short nozzle sits above the sensing zone, so hands never touch the unit, and the 300 ml tank is read through a clear window on the front. USB-C recharging, an IPX4 splash-proof ABS body and a sub-60 dB pump make it suitable for bathrooms, kitchens, hotels, clinics and offices. OEM / ODM customization available for logo, colour and packaging.',
    'zh': 'SD-901 是一台免接触自动泡沫洗手机，核心是四段出液调节：单次出泡 0.25 / 0.5 / 0.75 / 1.0 秒。斜面顶部的电容式触摸键切换档位，三颗 LED 指示灯确认当前档位。短喷嘴位于感应区上方，双手全程无需接触机身；300 ml 水箱的余量通过正面透明视窗随时查看。USB-C 充电、IPX4 防溅 ABS 机身与低于 60 分贝的水泵，使其适合卫浴、厨房、酒店、诊所与办公室。支持 logo、颜色、包装的 OEM / ODM 定制。',
    'ar': 'SD-901 موزع صابون رغوي أوتوماتيكي بدون لمس يعتمد على قرص إخراج بأربع خطوات: ٠٫٢٥ و٠٫٥ و٠٫٧٥ و١٫٠ ثانية من الرغوة لكل تشغيل. مفتاح لمس سعوي في اللوحة العلوية المائلة يختار المستوى وتؤكده ثلاثة مؤشرات LED. الفوهة القصيرة فوق منطقة الاستشعار فلا تلمس اليدان الجهاز أبداً، ويمكن قراءة خزان ٣٠٠ مل عبر نافذة شفافة في الأمام. الشحن USB-C والجسم ABS المقاوم للرذاذ IPX4 ومضخة دون ٦٠ ديسيبل تجعله مناسباً للحمامات والمطابخ والفنادق والعيادات والمكاتب. يتوفر التخصيص OEM / ODM للشعار واللون والتغليف.',
    'es': 'El SD-901 es un dispensador automático de espuma de jabón sin contacto construido en torno a un selector de cuatro tiempos: 0,25; 0,5; 0,75 y 1,0 segundo de espuma por activación. Un interruptor táctil capacitivo en el panel superior inclinado selecciona el nivel y tres indicadores LED lo confirman. La boquilla corta queda por encima de la zona de detección, así que las manos nunca tocan el equipo, y el depósito de 300 ml se lee a través de una ventana transparente frontal. Recarga USB-C, cuerpo ABS resistente a salpicaduras IPX4 y bomba por debajo de 60 dB: apto para baños, cocinas, hoteles, clínicas y oficinas. Personalización OEM / ODM de logotipo, color y embalaje disponible.',
    'fr': 'Le SD-901 est un distributeur automatique de mousse de savon sans contact construit autour d\'un sélecteur à quatre temps : 0,25 ; 0,5 ; 0,75 et 1,0 seconde de mousse par déclenchement. Une commande tactile capacitive sur le panneau supérieur incliné choisit le niveau et trois témoins LED le confirment. Le bec court se trouve au-dessus de la zone de détection : les mains ne touchent jamais l\'appareil, et le réservoir de 300 ml se lit à travers une fenêtre transparente en façade. Recharge USB-C, corps ABS anti-éclaboussures IPX4 et pompe sous 60 dB : adapté aux salles de bain, cuisines, hôtels, cliniques et bureaux. Personnalisation OEM / ODM du logo, de la couleur et de l\'emballage disponible.',
    'id': 'SD-901 adalah dispenser sabun busa otomatis tanpa sentuh dengan pengaturan empat langkah: 0,25; 0,5; 0,75 dan 1,0 detik busa setiap pemicu. Tombol sentuh kapasitif di panel atas yang miring memilih tingkat, dan tiga indikator LED mengonfirmasinya. Nozel pendek berada di atas zona sensor sehingga tangan tidak pernah menyentuh unit, dan tangki 300 ml dapat dipantau lewat jendela bening di depan. Pengisian USB-C, bodi ABS tahan cipratan IPX4, dan pompa di bawah 60 dB membuatnya cocok untuk kamar mandi, dapur, hotel, klinik, dan kantor. Kustomisasi OEM / ODM untuk logo, warna, dan kemasan tersedia.',
    'ru': 'SD-901 — бесконтактный автоматический пенный дозатор мыла с четырьмя режимами подачи: 0,25; 0,5; 0,75 и 1,0 секунды пены за срабатывание. Ёмкостная сенсорная кнопка на наклонной верхней панели выбирает уровень, а три светодиода подтверждают его. Короткий носик расположен над зоной датчика, поэтому руки никогда не касаются прибора, а остаток в баке на 300 мл видно через прозрачное окно спереди. Зарядка USB-C, влагозащищённый корпус из ABS по стандарту IPX4 и помпа ниже 60 дБ — подходит для ванных, кухонь, отелей, клиник и офисов. Доступна кастомизация OEM / ODM: логотип, цвет и упаковка.',
    'th': 'SD-901 คือเครื่องจ่ายสบู่โฟมอัตโนมัติแบบไม่ต้องสัมผัส มาพร้อมการปรับระดับจ่าย 4 ระดับ: 0.25, 0.5, 0.75 และ 1.0 วินาทีต่อครั้ง สวิตช์สัมผัสแบบคาปาซิทีฟบนแผงบนเอียงใช้เลือกระดับ และไฟ LED 3 ดวงยืนยันระดับที่เลือก หัวจ่ายสั้นอยู่เหนือโซนเซ็นเซอร์ มือจึงไม่ต้องสัมผัสตัวเครื่อง และตรวจสอบระดับสบู่ในถัง 300 มล. ได้จากหน้าต่างใสด้านหน้า ชาร์จ USB-C ตัวเครื่อง ABS กันน้ำกระเซ็น IPX4 และปั๊มที่ทำงานต่ำกว่า 60 เดซิเบล เหมาะกับห้องน้ำ ห้องครัว โรงแรม คลินิก และออฟฟิศ รองรับการปรับแต่ง OEM / ODM ทั้งโลโก้ สี และบรรจุภัณฑ์',
    'vi': 'SD-901 là bình đựng xà phòng bọt tự động không cần chạm, với bốn mức nhả: 0,25; 0,5; 0,75 và 1,0 giây mỗi lần kích hoạt. Nút cảm ứng điện dung trên mặt nghiêng phía trên dùng chọn mức, ba đèn LED xác nhận lựa chọn. Đầu nhả ngắn nằm phía trên vùng cảm biến nên tay không bao giờ chạm thân máy, và lượng dung dịch trong bình 300 ml được theo dõi qua cửa sổ trong suốt phía trước. Sạc USB-C, thân ABS chống tạt nước IPX4 và bơm dưới 60 dB, phù hợp cho phòng tắm, bếp, khách sạn, phòng khám và văn phòng. Có tùy biến OEM / ODM cho logo, màu sắc và bao bì.',
}
P_CERT_NOTE = {
    'en': 'Certification documents on file — available on request.',
    'zh': '认证资料已备案，可按需提供。',
}
P_SHIP_FROM = {
    'en': 'China', 'zh': '中国', 'es': 'China', 'fr': 'Chine', 'id': 'Tiongkok',
    'ru': 'Китай', 'th': 'จีน', 'vi': 'Trung Quốc', 'ar': 'الصين',
}
P_SAMPLE_NOTE = {
    'en': 'Sample available (max 1 pc)',
    'zh': '可提供样品（最多 1 台）',
    'es': 'Muestra disponible (máx. 1 ud)',
    'fr': 'Échantillon disponible (max. 1 pièce)',
    'id': 'Sampel tersedia (maks. 1 unit)',
    'ru': 'Образец доступен (макс. 1 шт.)',
    'th': 'มีตัวอย่างให้ (สูงสุด 1 เครื่อง)',
    'vi': 'Có mẫu (tối đa 1 chiếc)',
    'ar': 'عينة متاحة (بحد أقصى قطعة واحدة)',
}
SKU_COLOURS = [
    {'en': 'White', 'zh': '白色', 'es': 'Blanco', 'fr': 'Blanc', 'id': 'Putih', 'ru': 'Белый',
     'th': 'สีขาว', 'vi': 'Trắng', 'ar': 'أبيض'},
    {'en': 'Grey', 'zh': '灰色', 'es': 'Gris', 'fr': 'Gris', 'id': 'Abu-abu', 'ru': 'Серый',
     'th': 'สีเทา', 'vi': 'Xám', 'ar': 'رمادي'},
    {'en': 'Green', 'zh': '绿色', 'es': 'Verde', 'fr': 'Vert', 'id': 'Hijau', 'ru': 'Зелёный',
     'th': 'สีเขียว', 'vi': 'Xanh lá', 'ar': 'أخضر'},
    {'en': 'Pink', 'zh': '粉色', 'es': 'Rosa', 'fr': 'Rose', 'id': 'Merah muda', 'ru': 'Розовый',
     'th': 'สีชมพู', 'vi': 'Hồng', 'ar': 'وردي'},
]

IMG_FILES = ['01.webp', '02.webp', '03.webp']


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def read_json(path):
    return json.loads(io.open(path, encoding='utf-8', newline='').read())


def dump_crlf(obj, indent=1):
    """既有的 i18n / category-guides 都是 CRLF + indent=1 且末尾有 CRLF。"""
    return json.dumps(obj, ensure_ascii=False, indent=indent).replace('\n', '\r\n') + '\r\n'


def write_if_changed(path, text):
    old = io.open(path, encoding='utf-8', newline='').read() if os.path.exists(path) else None
    if old == text:
        print('  = unchanged %s' % os.path.relpath(path, ROOT))
        return False
    if old is not None and os.path.exists(path):
        shutil.copyfile(path, path + '.bak')
    io.open(path, 'w', encoding='utf-8', newline='').write(text)
    print('  + wrote     %s (%d chars)' % (os.path.relpath(path, ROOT), len(text)))
    return True


def lang_dict(d):
    """把 {'en': .., 'zh': ..} 转成 9 key 的 dict（顺序统一）。"""
    return {l: d.get(l) or d['en'] for l in LANGS}


# ---------------------------------------------------------------------------
# 1. categories.json —— surgical 插入（不动其它行）
# ---------------------------------------------------------------------------
def patch_categories():
    p = os.path.join(ROOT, 'data/products/categories.json')
    raw = io.open(p, encoding='utf-8', newline='').read()
    if '"%s"' % SLUG in raw:
        print('  = categories.json already has %s' % SLUG)
        return
    # 文件行尾混杂（正文 CRLF，数组结尾 LF），所以两端都要容错
    m = re.search(r'\n(\s*)\}[ \t]*\r?\n[ \t]*(\s*)\][ \t]*\r?\n\}[ \t]*\r?\n?[ \t]*$', raw)
    if not m:
        raise SystemExit('categories.json: cannot find the categories array tail')
    order = max(c['order'] for c in read_json(p)['categories']) + 1
    entry = {
        'slug': SLUG,
        'name': lang_dict(CAT_NAME),
        'description': lang_dict(CAT_DESC),
        'banner_image': 'https://www.hkdmj.net/assets/images/products/21-hands-free-soap-dispenser.webp' + VER,
        'order': order,
    }
    # 正则已经把 "] }" 尾巴整段吃掉，所以 insert 必须把它补回来
    ind, bracket_ind = m.group(1), m.group(2)
    body = json.dumps(entry, ensure_ascii=False, indent=1).replace('\n', '\n' + ind)
    insert = '\n%s},\n%s%s\n%s]\n}\n' % (ind, ind, body, bracket_ind)
    out = raw[:m.start()] + insert + raw[m.end():]
    assert out.count('"%s"' % SLUG) == 1
    write_if_changed(p, out)
    # sanity: still parseable and in sync
    cats = read_json(p)['categories']
    assert any(c['slug'] == SLUG for c in cats), 'categories.json lost the new entry'


# ---------------------------------------------------------------------------
# 2. data/products/<slug>.json
# ---------------------------------------------------------------------------
def build_product():
    images = ['https://www.hkdmj.net%s/%s%s' % (IMGDIR, f, VER) for f in IMG_FILES]
    detail_images = images[:]
    specs = []
    for tup in P_SPECS:
        labels = dict(zip(LANGS, tup[:9]))
        values = tup[9]
        specs.append({
            'label': lang_dict(labels),
            'value': lang_dict(values),
        })
    product = {
        'id': PID,
        'name': lang_dict(P_NAME),
        'tagline': lang_dict(P_TAGLINE),
        'images': images,
        'video_url': '',
        'moq': {'value': 100, 'unit': 'pieces'},
        'certifications': [],
        'cert_note': dict(P_CERT_NOTE),
        'highlights': [
            {'icon': icon, 'text': lang_dict(h)}
            for icon, h in zip(['power', 'battery', 'filter', 'check'], P_HIGHLIGHTS)
        ],
        'specs': specs,
        'quick_specs': [
            {'label': specs[i]['label'], 'value': specs[i]['value']} for i in QUICK_IDX
        ],
        'packaging': {'unit': 'Color Box', 'ctn_size': '—', 'ctn_qty': '—', 'gross_weight': '—'},
        'customization': {
            'oem': True, 'odm': True, 'logo': True, 'color': True, 'package': True,
            'sample_lead': '7–14 days', 'production_lead': '25–35 days',
        },
        'applications': lang_dict(P_APPLICATIONS),
        'price_indicator': {'min': 7.5, 'max': 10.5, 'currency': 'USD'},
        'price_ladder': [
            {'min': 100, 'max': 499, 'price': 10.5},
            {'min': 500, 'max': 4999, 'price': 9.2},
            {'min': 5000, 'max': 99999, 'price': 7.5},
        ],
        'sku': [{'name': lang_dict({
            'en': 'Colour', 'zh': '颜色', 'es': 'Color', 'fr': 'Couleur', 'id': 'Warna',
            'ru': 'Цвет', 'th': 'สี', 'vi': 'Màu sắc', 'ar': 'اللون'}),
            'values': [{'name': lang_dict(c)} for c in SKU_COLOURS]}],
        'description': lang_dict(P_DESCRIPTION),
        'supplier_rating': '4.81',
        'response_time': '—',
        'transactions': '—',
        'years': '—',
        'ship_from': lang_dict(P_SHIP_FROM),
        'sample': {'enabled': True, 'qty': 1, 'note': lang_dict(P_SAMPLE_NOTE)},
        'category_name': lang_dict(CAT_NAME),
        'certificates': [],
        'supplier': {
            'country': 'HK', 'province': 'New Territories', 'established': 2024,
            'reply_rate': 0.9987, 'verified': False,
            'main_markets': ['North America', 'South America', 'Eastern Europe', 'Southeast Asia'],
        },
        'store_rating': {'score': 4.81, 'reviews': 7, 'scope': 'store'},
        'shipping_fee_usd': 0,
        'alibaba_url': '',
        '_cat': SLUG,
        'detail_images': detail_images,
    }
    data = {
        'category': SLUG,
        'products': [product],
        'reviews': [],
    }
    p = os.path.join(ROOT, 'data/products', SLUG + '.json')
    text = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    write_if_changed(p, text)


# ---------------------------------------------------------------------------
# 3. i18n 增量
# ---------------------------------------------------------------------------
def patch_i18n():
    for lang in I18N_LANGS:
        p = os.path.join(ROOT, 'data/i18n', lang + '.json')
        d = read_json(p)
        # categoryPage
        d.setdefault('categoryPage', {})[SLUG] = {
            'heroTitle': CAT_NAME[lang],
            'whyTitle': WHY_TITLE[lang],
            'guideTitle': GUIDE_TITLE[lang],
            'oemTitle': OEM_TITLE[lang],
            'oemSub': OEM_SUB[lang],
            'countSub': COUNT_SUB[lang],
            'heroP': '',
            'hasRelated': True,
        }
        for card in GUIDE_CARDS:
            d.setdefault('guideTitle', {})[card['title']['en']] = card['title'][lang]
            d.setdefault('guideValues', {})[card['values']['en']] = card['values'][lang]
            d.setdefault('specNote', {})[card['title']['en']] = card['explain'][lang]
        # 品类描述由 categories.json 提供，但 i18n 里也补一份 description 兜底
        write_if_changed(p, dump_crlf(d, 1))


# ---------------------------------------------------------------------------
# 4. category-guides.json
# ---------------------------------------------------------------------------
def patch_guides():
    p = os.path.join(ROOT, 'data/i18n/category-guides.json')
    g = read_json(p)
    g[SLUG] = [
        {'title': c['title']['en'], 'values': c['values']['en'], 'explain': c['explain']['en']}
        for c in GUIDE_CARDS
    ]
    write_if_changed(p, dump_crlf(g, 1))


def main():
    print('data phase: %s' % SLUG)
    patch_categories()
    build_product()
    patch_i18n()
    patch_guides()
    print('done.')


if __name__ == '__main__':
    sys.exit(main())
