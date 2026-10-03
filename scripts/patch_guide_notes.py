# -*- coding: utf-8 -*-
"""Add the buying-guide explanatory sentences to every locale.

`en.json.specNote` is keyed by the guide card title ("Suction Power") with the
explanatory sentence as the *value*.  Those values were never collected into
the translation skeleton -- the key was -- so `build_lang.py` filled the
specNote value with the card's *title* translation and every guide card ended
up reading "Current range: 30kPa … . Suction Power" instead of a real
explanation.  The skeleton now collects the values; this script supplies the
seventeen distinct sentences in each locale.

Idempotent.  Run after make_tr_skeleton.py, before build_lang.py.

Usage
    python scripts/patch_guide_notes.py
"""
from __future__ import annotations
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'data/i18n/_src')
LANGS = ['ar', 'es', 'fr', 'id', 'ru', 'th', 'vi']

EN = [
    'Battery capacity in mAh is the main driver of runtime; removable packs extend service life.',
    'USB-C charging removes proprietary docks; check charge time against use per cycle.',
    'Compare this figure across the models listed below before choosing.',
    'A larger cup means fewer empties; a compact body reaches tighter spaces.',
    'Multi-in-1 functions widen the use case; check what is included in the box.',
    'Food-contact and boiler materials should be stainless steel with the relevant certification.',
    'Pressure tells you how deeply steam penetrates grout, seals and seams.',
    'Laser/SLAM mapping builds a real floor plan; gyroscope units wander.',
    'Wattage is input power, not lifting force \u2014 read it together with the suction figure.',
    'Runtime decides how much floor one charge covers \u2014 check whether the battery is removable.',
    'Higher Pa lifts more debris; compare Pa together with motor type (brushed vs brushless).',
    'Tank capacity sets how long a session runs before a refill.',
    'Weight decides whether the tool is actually used for a full room or mattress.',
    'Dust box and water tank size decide mopping area per cycle.',
    'HEPA filtration traps the allergen the machine has just released.',
    'For home espresso, pressure stability during extraction matters more than the peak bar rating.',
    'Air watts (AW) show usable suction after losses \u2014 read it next to the maximum Pa figure.',
]

T = {
    'es': [
        'La capacidad de la batería en mAh determina la autonomía; las baterías extraíbles prolongan la vida útil.',
        'La carga por USB-C elimina las bases propietarias; compare el tiempo de carga con el uso por ciclo.',
        'Compare esta cifra entre los modelos indicados abajo antes de elegir.',
        'Un depósito más grande significa menos vaciados; un cuerpo compacto llega a espacios más estrechos.',
        'Las funciones multi-en-1 amplían el uso; compruebe qué se incluye en la caja.',
        'Los materiales en contacto con alimentos y del calderín deben ser acero inoxidable con la certificación correspondiente.',
        'La presión indica la profundidad con que el vapor penetra en juntas, sellos y ranuras.',
        'El mapeo por láser/SLAM traza un plano real; las unidades con giroscopio se desvían.',
        'La potencia en vatios es la potencia de entrada, no la fuerza de succión — léala junto con la cifra de succión.',
        'La autonomía determina cuánta superficie cubre una carga — compruebe si la batería es extraíble.',
        'Una cifra mayor en Pa levanta más residuos; compare los Pa junto con el tipo de motor (con o sin escobillas).',
        'La capacidad del depósito determina cuánto dura una sesión antes de rellenar.',
        'El peso decide si la herramienta se usa realmente en una habitación completa o en un colchón.',
        'El tamaño del depósito de polvo y del tanque de agua determina la superficie de fregado por ciclo.',
        'La filtración HEPA atrapa el alérgeno que la máquina acaba de liberar.',
        'Para el espresso doméstico, la estabilidad de la presión durante la extracción importa más que el pico de bares.',
        'Los air watts (AW) indican la succión útil tras las pérdidas — léalos junto a la cifra máxima en Pa.',
    ],
    'fr': [
        "La capacité de la batterie en mAh détermine l'autonomie ; les packs amovibles prolongent la durée de vie.",
        "La charge USB-C supprime les socles propriétaires ; comparez le temps de charge à l'usage par cycle.",
        'Comparez ce chiffre entre les modèles listés ci-dessous avant de choisir.',
        'Un bac plus grand signifie moins de vidages ; un corps compact atteint les espaces étroits.',
        'Les fonctions multi-en-1 élargissent les usages ; vérifiez ce qui est inclus dans la boîte.',
        'Les matériaux au contact des aliments et de la chaudière doivent être en inox avec la certification correspondante.',
        'La pression indique la profondeur avec laquelle la vapeur pénètre les joints, les soudures et les rainures.',
        'La cartographie laser/SLAM construit un vrai plan ; les unités à gyroscope dérivent.',
        "La puissance en watts est la puissance d'entrée, pas la force d'aspiration — lisez-la avec la valeur d'aspiration.",
        "L'autonomie détermine la surface couverte par charge — vérifiez si la batterie est amovible.",
        'Un Pa plus élevé soulève plus de débris ; comparez les Pa avec le type de moteur (balais ou sans balais).',
        "La capacité du réservoir détermine la durée d'une session avant remplissage.",
        "Le poids décide si l'appareil est réellement utilisé pour une pièce entière ou un matelas.",
        "La taille du bac à poussière et du réservoir d'eau détermine la surface lavée par cycle.",
        "La filtration HEPA retient l'allergène que la machine vient de libérer.",
        "Pour l'espresso à domicile, la stabilité de la pression pendant l'extraction compte plus que le pic de bars.",
        'Les air watts (AW) indiquent aspiration utile après pertes — lisez-les à côté de la valeur maximale en Pa.',
    ],
    'ru': [
        'Ёмкость аккумулятора в мА·ч определяет время работы; съёмные аккумуляторы продлевают срок службы.',
        'Зарядка USB-C избавляет от фирменных док-станций; сравните время зарядки с расходом за цикл.',
        'Сравните этот показатель между моделями ниже, прежде чем выбирать.',
        'Чем больше контейнер, тем реже его опорожнять; компактный корпус достаёт в узкие места.',
        'Функции «много в одном» расширяют применение; проверьте комплектацию.',
        'Материалы, контактирующие с едой, и бойлер должны быть из нержавеющей стали с соответствующей сертификацией.',
        'Давление показывает, насколько глубоко пар проникает в швы, уплотнения и стыки.',
        'Лазерное/SLAM-картирование строит реальный план; гироскопные модели «блуждают».',
        'Мощность в ваттах — это потребляемая мощность, а не сила всасывания; читайте её вместе с показателем всасывания.',
        'Время работы определяет, какую площадь покрывает один заряд; проверьте, съёмный ли аккумулятор.',
        'Большее значение в Па поднимает больше мусора; сравнивайте Па вместе с типом двигателя (щёточный или бесщёточный).',
        'Объём бака определяет, сколько длится сессия до доливки.',
        'Вес решает, будут ли прибором реально убирать всю комнату или матрас.',
        'Объём пылесборника и бака для воды определяет площадь влажной уборки за цикл.',
        'Фильтрация HEPA задерживает аллерген, который прибор только что поднял.',
        'Для домашнего эспрессо стабильность давления при экстракции важнее пикового значения в барах.',
        'Air watts (AW) показывают полезное всасывание после потерь; читайте их рядом с максимумом в Па.',
    ],
    'ar': [
        'سعة البطارية بالملي أمبير تحدد مدة التشغيل؛ والبطاريات القابلة للإزالة تطيل عمر الخدمة.',
        'الشحن عبر USB-C يلغي استخدام القواعد الخاصة؛ قارن زمن الشحن مع الاستهلاك في كل دورة.',
        'قارن هذا الرقم بين الطُرز المذكورة أدناه قبل الاختيار.',
        'الخزان الأكبر يعني تفريغًا أقل؛ والجسم المدمج يصل إلى الأماكن الضيقة.',
        'الوظائف المتعددة توسّع الاستخدام؛ تحقق مما يشمله الصندوق.',
        'يجب أن تكون المواد الملامسة للطعام وجسم الغلاية من الفولاذ المقاوم للصدأ وبالشهادة المناسبة.',
        'يبيّن الضغط مدى عمق تغلغل البخار في الفواصل والحشوات والشقوق.',
        'رسم الخرائط بالليزر/SLAM يبني مخططًا حقيقيًا للأرضية؛ أما الوحدات بالجيروسكوب فتتوه.',
        'القدرة بالواط هي قدرة الدخل، لا قوة الشفط — اقرأها مع رقم الشفط.',
        'مدة التشغيل تحدد مساحة الأرضية التي تغطيها الشحنة — تحقق مما إذا كانت البطارية قابلة للإزالة.',
        'ارتفاع قيمة الباسكال يعني رفع المزيد من الأوساخ؛ قارن الباسكال مع نوع المحرك (بفرش أم بدون فرش).',
        'سعة الخزان تحدد مدة الجلسة قبل إعادة التعبئة.',
        'الوزن يحدد ما إذا كان الجهاز سيُستخدم فعلًا في غرفة كاملة أو مرتبة.',
        'حجم صندوق الغبار وخزان الماء يحددان مساحة المسح في كل دورة.',
        'فلتر HEPA يحتجز المواد المسببة للحساسية التي أطلقها الجهاز للتو.',
        'للإسبريسو المنزلي، استقرار الضغط أثناء الاستخلاص أهم من ذروة البار.',
        'الـ air watts (AW) تُظهر الشفط الفعلي بعد الفاقد — اقرأها بجانب الحد الأقصى بالباسكال.',
    ],
    'th': [
        'ความจุแบตเตอรี่หน่วย mAh เป็นตัวกำหนดระยะเวลาทำงานเป็นหลัก แบตเตอรี่ถอดได้ช่วยยืดอายุการใช้งาน',
        'การชาร์จ USB-C ตัดอุปกรณ์วางชาร์จเฉพาะรุ่นออกไป ควรเทียบเวลาชาร์จกับการใช้งานต่อรอบ',
        'ควรเทียบตัวเลขนี้ระหว่างรุ่นที่ระบุด้านล่างก่อนตัดสินใจ',
        'ถังที่ใหญ่ขึ้นหมายถึงการทิ้งฝุ่นน้อยครั้งลง ตัวเครื่องกะทัดรัดเข้าถึงพื้นที่แคบกว่า',
        'ฟังก์ชันหลาย-in-1 ต่อยอดการใช้งานได้กว้างขึ้น ควรตรวจสอบว่ากล่องบรรจุอะไรบ้าง',
        'วัสดุที่สัมผัสอาหารและหม้อต้มควรเป็นสแตนเลสพร้อมใบรับรองที่เกี่ยวข้อง',
        'แรงดันบอกว่าไอน้ำซึมลึกแค่ไหนตามรอยยาแนว ซีล และร่องตะเข็บ',
        'การทำแผนที่ด้วยเลเซอร์/SLAM สร้างแผนผังพื้นจริง เครื่องที่ใช้ไจโรสโคปจะคลาดเคลื่อน',
        'กำลังไฟเป็นกำลังขาเข้า ไม่ใช่แรงดูด ควรอ่านคู่กับตัวเลขแรงดูด',
        'ระยะเวลาทำงานกำหนดว่าชาร์จหนึ่งครั้งครอบคลุมพื้นที่เท่าไร ควรดูว่าแบตเตอรี่ถอดได้หรือไม่',
        'ค่า Pa ที่สูงขึ้นยกเศษฝุ่นได้มากกว่า ควรเทียบ Pa กับชนิดมอเตอร์ (มีแปรงถ่าน/ไร้แปรงถ่าน)',
        'ความจุถังกำหนดว่าใช้งานได้นานแค่ไหนก่อนเติมใหม่',
        'น้ำหนักเป็นตัวตัดสินว่าจะได้ใช้งานจริงทั้งห้องหรือทั้งที่นอนหรือไม่',
        'ขนาดถังเก็บฝุ่นและถังน้ำกำหนดพื้นที่ถูต่อรอบ',
        'ฟิลเตอร์ HEPA ดักจับสารก่อภูมิแพ้ที่เครื่องเพิ่งปล่อยออกมา',
        'สำหรับเอสเปรสโซที่บ้าน ความเสถียรของแรงดันระหว่างสกัดสำคัญกว่าค่าสูงสุดเป็นบาร์',
        'ค่า air watts (AW) แสดงแรงดูดที่ใช้งานได้จริงหลังหักการสูญเสีย ควรอ่านคู่กับค่า Pa สูงสุด',
    ],
    'vi': [
        'Dung lượng pin tính theo mAh quyết định thời gian chạy; pin tháo rời kéo dài tuổi thọ.',
        'Sạc USB-C loại bỏ đế sạc riêng; hãy so thời gian sạc với mức dùng mỗi chu kỳ.',
        'Hãy so chỉ số này giữa các model liệt kê bên dưới trước khi chọn.',
        'Khay lớn hơn nghĩa là ít lần đổ hơn; thân máy nhỏ gọn tiếp cận được chỗ hẹp.',
        'Các chức năng đa năng mở rộng phạm vi dùng; hãy kiểm tra hộp có gì.',
        'Vật liệu tiếp xúc thực phẩm và nồi đun nên là thép không gỉ kèm chứng nhận phù hợp.',
        'Áp suất cho biết hơi nước thấm sâu đến đâu vào đường ron, gioăng và khe hở.',
        'Lập bản đồ bằng laser/SLAM tạo sơ đồ mặt sàn thật; máy dùng con quay hồi chuyển dễ lệch.',
        'Công suất W là công suất đầu vào, không phải lực hút — hãy đọc kèm chỉ số lực hút.',
        'Thời gian chạy quyết định một lần sạc phủ được bao nhiêu diện tích — hãy kiểm tra pin có tháo rời được không.',
        'Pa cao hơn hút được nhiều bụi hơn; hãy so Pa cùng loại động cơ (có chổi than hay không chổi than).',
        'Dung tích bình quyết định một phiên dùng được bao lâu trước khi châm thêm.',
        'Khối lượng quyết định thiết bị có thực sự dùng hết cả phòng hay cả đệm không.',
        'Kích thước khay bụi và bình nước quyết định diện tích lau mỗi chu kỳ.',
        'Màng lọc HEPA giữ lại tác nhân gây dị ứng mà máy vừa thổi ra.',
        'Với espresso tại nhà, độ ổn định áp suất khi chiết quan trọng hơn mức bar đỉnh.',
        'Air watts (AW) cho biết lực hút thực dùng sau tổn thất — hãy đọc cạnh mức Pa tối đa.',
    ],
    'id': [
        'Kapasitas baterai dalam mAh adalah penentu utama waktu pakai; baterai yang dapat dilepas memperpanjang umur pakai.',
        'Pengisian USB-C menghilangkan dudukan khusus; bandingkan waktu pengisian dengan pemakaian per siklus.',
        'Bandingkan angka ini antar model yang tercantum di bawah sebelum memilih.',
        'Wadah lebih besar berarti lebih jarang dikosongkan; bodi ringkas menjangkau celah sempit.',
        'Fungsi multi-in-1 memperluas penggunaan; periksa apa saja isi kotaknya.',
        'Bahan yang bersentuhan dengan makanan dan ketel sebaiknya stainless steel dengan sertifikasi yang sesuai.',
        'Tekanan menunjukkan seberapa dalam uap menembus nat, seal, dan celah.',
        'Pemetaan laser/SLAM membentuk denah lantai nyata; unit giroskop mudah melenceng.',
        'Daya dalam watt adalah daya masukan, bukan gaya hisap — bacalah bersama angka daya hisap.',
        'Waktu pakai menentukan seberapa luas lantai yang tercakup per pengisian — periksa apakah baterainya dapat dilepas.',
        'Pa lebih tinggi mengangkat lebih banyak kotoran; bandingkan Pa bersama jenis motor (brush atau brushless).',
        'Kapasitas tangki menentukan berapa lama satu sesi berjalan sebelum diisi ulang.',
        'Berat menentukan apakah alat benar-benar dipakai untuk satu ruangan penuh atau kasur.',
        'Ukuran wadah debu dan tangki air menentukan luas pel per siklus.',
        'Filtrasi HEPA menahan alergen yang baru saja dilepas mesin.',
        'Untuk espresso rumahan, kestabilan tekanan saat ekstraksi lebih penting daripada puncak bar.',
        'Air watts (AW) menunjukkan hisapan terpakai setelah kerugian — bacalah di samping angka Pa maksimum.',
    ],
}


def main():
    order = list(json.load(open(os.path.join(SRC, '_keys_ui.json'), encoding='utf-8')))
    missing = [s for s in EN if s not in order]
    assert not missing, f'skeleton does not carry {len(missing)} of the notes: {missing[:2]}'

    for lang in LANGS:
        p = os.path.join(SRC, lang + '.json')
        d = json.load(open(p, encoding='utf-8'))
        added = changed = 0
        for ev, tv in zip(EN, T[lang]):
            if ev not in d:
                added += 1
            elif d[ev] != tv:
                changed += 1
            d[ev] = tv
        for k in d:
            assert k in order, f'{lang}: stray key {k!r}'
        d = {k: d[k] for k in order if k in d}
        assert len(d) == len(order), (lang, len(d), len(order))
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
            f.write('\n')
        print(f'{lang}: {len(d)} keys  (+{added} new notes, {changed} corrected)')
    print('done - run build_lang.py next')


if __name__ == '__main__':
    main()
