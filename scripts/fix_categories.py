# -*- coding: utf-8 -*-
"""Rewrite the non-English category names and descriptions.

Why
---
data/products/categories.json is the source for the category-page hero, the
related-product labels and the CollectionPage JSON-LD.  Its non-English values
had been produced by a pipeline that stripped non-ASCII characters:

  es  "Aspiradoras de mano inalambricas ligeras... rapidas ... quimicos"
  fr  "Aspirateurs portatifs sans fil legres ... a la maison ... arret"
  ru  "Legkie i moshhnye besprovodnye rukonnye pylesosy"   (Latin, not Cyrillic)
  vi  "May hut bui cam tay khong day ... khuan khuan khong can hoa chat"
  ar  "روبوت تنظيف الارضيات"                                 (missing hamza)

Several were also translated loosely and lost the tail sentence of the English
copy.  This script installs correct, full-length copy for all seven locales so
the category pages and the homepage agree.

Usage
    python scripts/fix_categories.py --check
    python scripts/fix_categories.py
"""
from __future__ import annotations
import argparse, json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, 'data/products/categories.json')

NAME = {
    'handheld-vacuum': {
        'ar': 'مكنسة يدوية لاسلكية', 'es': 'Aspiradora de Mano', 'fr': 'Aspirateur à main',
        'id': 'Pembersih Vakum Tangan', 'ru': 'Ручной пылесос',
        'th': 'เครื่องดูดฝุ่นมือถือ', 'vi': 'Máy hút bụi cầm tay'},
    'robot-vacuum': {
        'ar': 'روبوت تنظيف الأرضيات', 'es': 'Robot Aspirador', 'fr': 'Robot aspirateur',
        'id': 'Robot Pembersih Vakum', 'ru': 'Робот-пылесос',
        'th': 'หุ่นยนต์ดูดฝุ่น', 'vi': 'Robot hút bụi'},
    'steam-cleaner': {
        'ar': 'منظف بالبخار', 'es': 'Limpiador a Vapor', 'fr': 'Nettoyeur vapeur',
        'id': 'Pembersih Uap', 'ru': 'Пароочиститель',
        'th': 'เครื่องทำความสะอาดด้วยไอน้ำ', 'vi': 'Máy vệ sinh hơi nước'},
    'uv-mite-remover': {
        'ar': 'مزيل عث بالأشعة فوق البنفسجية', 'es': 'Eliminador de Ácaros UV',
        'fr': "Éliminateur d'acariens UV", 'id': 'Pembasmi Tungau UV',
        'ru': 'УФ-удалитель пылевых клещей',
        'th': 'เครื่องกำจัดไรด้วยรังสียูวี', 'vi': 'Máy diệt ve bụi UV'},
    'window-cleaner-robot': {
        'ar': 'روبوت تنظيف النوافذ الذكي', 'es': 'Robot Limpiacristales Inteligente',
        'fr': 'Robot nettoyeur de vitres intelligent', 'id': 'Robot Pembersih Jendela Cerdas',
        'ru': 'Умный робот для мойки окон',
        'th': 'หุ่นยนต์ทำความสะอาดกระจกอัจฉริยะ', 'vi': 'Robot lau kính thông minh'},
    'car-vacuum': {
        'ar': 'مكنسة سيارات', 'es': 'Aspirador para Coche', 'fr': 'Aspirateur voiture',
        'id': 'Penyedot Debu Mobil', 'ru': 'Автомобильный пылесос',
        'th': 'เครื่องดูดฝุ่นในรถ', 'vi': 'Máy hút bụi ô tô'},
    'tire-inflator': {
        'ar': 'مضخة إطارات رقمية', 'es': 'Compresor de Neumáticos Digital',
        'fr': 'Gonfleur de pneus numérique', 'id': 'Pompa Ban Digital',
        'ru': 'Цифровой компрессор для шин',
        'th': 'ปั๊มลมยางดิจิทัล', 'vi': 'Bơm lốp xe kỹ thuật số'},
    'coffee-machine': {
        'ar': 'ماكينة قهوة إسبريسو', 'es': 'Máquina de Café Espresso',
        'fr': 'Machine à café expresso', 'id': 'Mesin Kopi Espresso',
        'ru': 'Кофемашина эспрессо',
        'th': 'เครื่องชงกาแฟเอสเปรสโซ', 'vi': 'Máy pha cà phê espresso'},
    'upright-steam-mop': {
        'ar': 'ممسحة بخار عمودية', 'es': 'Fregona de Vapor Vertical',
        'fr': 'Vadrouille vapeur verticale', 'id': 'Pel Uap Tegak',
        'ru': 'Вертикальная паровая швабра',
        'th': 'ไม้ถูพื้นไอน้ำแบบตั้ง', 'vi': 'Cây lau hơi nước đứng'},
}

DESC = {
    'handheld-vacuum': {
        'ar': 'مكنسات يدوية لاسلكية خفيفة وقوية. مثالية للتنظيف السريع في المنزل والسيارة والمكتب. شحن USB-C، مدة تشغيل تصل إلى 25 دقيقة، وإمكانية التنظيف الجاف والرطب.',
        'es': 'Aspiradoras de mano inalámbricas ligeras y potentes. Perfectas para limpiezas rápidas en el hogar, el coche y la oficina. Carga USB-C, hasta 25 minutos de autonomía y función de aspiración en seco y húmedo.',
        'fr': "Aspirateurs à main sans fil légers et puissants. Parfaits pour un nettoyage rapide à la maison, en voiture et au bureau. Charge USB-C, jusqu'à 25 minutes d'autonomie et aspiration à sec et humide.",
        'id': 'Penyedot debu tangan nirkabel yang ringan dan kuat. Sempurna untuk pembersihan cepat di rumah, mobil, dan kantor. Pengisian USB-C, daya tahan hingga 25 menit, serta kemampuan kering dan basah.',
        'ru': 'Лёгкие и мощные беспроводные ручные пылесосы. Идеальны для быстрой уборки дома, в машине и офисе. Зарядка USB-C, до 25 минут работы и режим сухой и влажной уборки.',
        'th': 'เครื่องดูดฝุ่นมือถือไร้สายน้ำหนักเบาและทรงพลัง เหมาะสำหรับการทำความสะอาดอย่างรวดเร็วที่บ้าน รถยนต์ และสำนักงาน ชาร์จ USB-C ใช้งานได้นานสูงสุด 25 นาที และดูดได้ทั้งแบบแห้งและเปียก',
        'vi': 'Máy hút bụi cầm tay không dây nhẹ và mạnh mẽ. Hoàn hảo cho việc dọn dẹp nhanh tại nhà, trên xe hơi và văn phòng. Sạc USB-C, thời gian hoạt động lên đến 25 phút và hút được cả khô lẫn ướt.'},
    'robot-vacuum': {
        'ar': 'روبوتات تنظيف ذكية مع ملاحة ليزر LDS وتحكم عبر التطبيق ووظيفة المسح. شحن تلقائي، ورسم خرائط متعدد الطوابق، وتوافق مع Alexa وGoogle Home.',
        'es': 'Robots aspiradores inteligentes con navegación láser LDS, control por aplicación y función de fregado. Recarga automática, mapeo de varias plantas y compatibilidad con Alexa y Google Home.',
        'fr': "Robots aspirateurs intelligents avec navigation laser LDS, contrôle par application et fonction de lavage. Recharge automatique, cartographie multi-étages et compatibilité Alexa / Google Home.",
        'id': 'Robot penyedot debu cerdas dengan navigasi laser LDS, kontrol aplikasi, dan fungsi mengepel. Pengisian otomatis, pemetaan banyak lantai, serta kompatibel dengan Alexa dan Google Home.',
        'ru': 'Умные роботы-пылесосы с лазерной навигацией LDS, управлением через приложение и функцией влажной уборки. Автоматическая зарядка, карта нескольких этажей и поддержка Alexa и Google Home.',
        'th': 'หุ่นยนต์ดูดฝุ่นอัจฉริยะพร้อมการนำทางด้วยเลเซอร์ LDS ควบคุมผ่านแอป และฟังก์ชันถูพื้น ชาร์จอัตโนมัติ ทำแผนที่หลายชั้น และรองรับ Alexa / Google Home',
        'vi': 'Robot hút bụi thông minh với điều hướng laser LDS, điều khiển qua ứng dụng và chức năng lau nhà. Tự động sạc, lập bản đồ nhiều tầng và tương thích Alexa / Google Home.'},
    'steam-cleaner': {
        'ar': 'منظفات بخار عالية الحرارة تطهر دون مواد كيميائية. قوة 1500 واط، بخار بدرجة 105 مئوية، وملحقات متعددة للأرضيات والبلاط والحمامات والمطابخ والنوافذ.',
        'es': 'Limpiadores de vapor de alta temperatura que desinfectan sin productos químicos. Potencia de 1500 W, vapor a 105 °C y múltiples accesorios para suelos, azulejos, baños, cocinas y ventanas.',
        'fr': "Nettoyeurs vapeur haute température qui assainissent sans produits chimiques. Puissance 1500 W, vapeur à 105 °C et accessoires multiples pour sols, carrelage, salles de bain, cuisines et vitres.",
        'id': 'Pembersih uap suhu tinggi yang mensterilkan tanpa bahan kimia. Daya 1500 W, uap 105 °C, dan berbagai aksesori untuk lantai, ubin, kamar mandi, dapur, dan jendela.',
        'ru': 'Пароочистители с высокой температурой пара, обеззараживающие без химии. Мощность 1500 Вт, пар 105 °C и множество насадок для полов, плитки, ванных, кухонь и окон.',
        'th': 'เครื่องทำความสะอาดด้วยไอน้ำอุณหภูมิสูงที่ฆ่าเชื้อโรคโดยไม่ต้องใช้สารเคมี กำลัง 1500W ไอน้ำ 105 องศา พร้อมอุปกรณ์เสริมหลายแบบสำหรับพื้น กระเบื้อง ห้องน้ำ ห้องครัว และกระจก',
        'vi': 'Máy vệ sinh bằng hơi nước nhiệt độ cao, khử trùng mà không cần hóa chất. Công suất 1500W, hơi nước 105°C và nhiều phụ kiện cho sàn nhà, gạch, phòng tắm, nhà bếp và cửa kính.'},
    'uv-mite-remover': {
        'ar': 'أجهزة إزالة العث بالأشعة فوق البنفسجية UV-C مع تجفيف بالهواء الساخن بدرجة 55 مئوية. ترشيح HEPA يحتجز 99.97% من مسببات الحساسية. ضرورية لنظافة المراتب والأرائك والمفروشات.',
        'es': 'Eliminadores de ácaros con luz UV-C y secado por aire caliente a 55 °C. La filtración HEPA atrapa el 99,97% de los alérgenos. Imprescindibles para la higiene de colchones, sofás y ropa de cama.',
        'fr': "Éliminateurs d'acariens à lumière UV-C avec séchage à l'air chaud à 55 °C. La filtration HEPA retient 99,97 % des allergènes. Indispensables pour l'hygiène des matelas, canapés et literies.",
        'id': 'Pembasmi tungau dengan sinar UV-C dan pengeringan udara panas 55 °C. Filtrasi HEPA menangkap 99,97% alergen. Wajib untuk kebersihan kasur, sofa, dan perlengkapan tidur.',
        'ru': 'УФ-удалители пылевых клещей с сушкой горячим воздухом 55 °C. HEPA-фильтрация задерживает 99,97% аллергенов. Необходимы для гигиены матрасов, диванов и постельного белья.',
        'th': 'เครื่องกำจัดไรด้วยแสง UV-C พร้อมทำให้แห้งด้วยลมร้อน 55 องศา การกรอง HEPA กักเก็บสารก่อภูมิแพ้ได้ 99.97% จำเป็นสำหรับความสะอาดของที่นอน โซฟา และเครื่องนอน',
        'vi': 'Máy diệt ve bụi bằng tia UV-C kèm sấy khô bằng khí nóng 55°C. Bộ lọc HEPA giữ lại 99,97% tác nhân gây dị ứng. Thiết yếu cho vệ sinh nệm, sofa và chăn ga gối đệm.'},
    'window-cleaner-robot': {
        'ar': 'روبوتات تنظيف نوافذ تلقائية مع ملاحة بالذكاء الاصطناعي ومستشعرات أمان. تنظف الزجاج والبلاط والمرايا. بطارية احتياطية UPS تمنع السقوط. سرعة تنظيف 4 دقائق لكل متر مربع.',
        'es': 'Robots limpiacristales automáticos con navegación por IA y sensores de seguridad. Limpian cristales, azulejos y espejos. La batería de respaldo UPS evita caídas. Velocidad de limpieza de 4 min/m².',
        'fr': "Robots nettoyeurs de vitres automatiques avec navigation par IA et capteurs de sécurité. Nettoient vitres, carrelage et miroirs. Batterie de secours UPS anti-chute. Vitesse de nettoyage de 4 min/m².",
        'id': 'Robot pembersih jendela otomatis dengan navigasi AI dan sensor keamanan. Membersihkan kaca, ubin, dan cermin. Baterai cadangan UPS mencegah jatuh. Kecepatan pembersihan 4 menit/m².',
        'ru': 'Автоматические роботы для мойки окон с ИИ-навигацией и датчиками безопасности. Моют стекло, плитку и зеркала. Резервная батарея UPS предотвращает падение. Скорость мойки 4 мин/м².',
        'th': 'หุ่นยนต์ทำความสะอาดกระจกอัตโนมัติพร้อมการนำทางด้วย AI และเซนเซอร์ความปลอดภัย ทำความสะอาดกระจก กระเบื้อง และกระจกเงา แบตเตอรี่สำรอง UPS ป้องกันการตก ความเร็วในการทำความสะอาด 4 นาที/ตร.ม.',
        'vi': 'Robot lau kính tự động với điều hướng AI và cảm biến an toàn. Làm sạch kính, gạch và gương. Pin dự phòng UPS chống rơi. Tốc độ làm sạch 4 phút/m².'},
    'car-vacuum': {
        'ar': 'مكنسات سيارات محمولة بخيارات طاقة 12 فولت أو USB. تصميم مدمج للمساحات الضيقة. شفط قوي للفتات وشعر الحيوانات والغبار داخل مقصورة السيارة.',
        'es': 'Aspiradores de coche portátiles con opciones de alimentación de 12 V o USB. Diseño compacto para espacios reducidos. Succión potente para migas, pelo de mascotas y polvo en el interior del vehículo.',
        'fr': "Aspirateurs voiture portables avec alimentation 12 V ou USB. Conception compacte pour les espaces étroits. Aspiration puissante des miettes, poils d'animaux et poussières à l'intérieur du véhicule.",
        'id': 'Penyedot debu mobil portabel dengan pilihan daya 12 V atau USB. Desain ringkas untuk ruang sempit. Daya hisap kuat untuk remah, bulu hewan peliharaan, dan debu di dalam kabin.',
        'ru': 'Портативные автомобильные пылесосы с питанием 12 В или USB. Компактный дизайн для узких пространств. Мощное всасывание крошек, шерсти животных и пыли в салоне.',
        'th': 'เครื่องดูดฝุ่นรถยนต์แบบพกพา พร้อมตัวเลือกพลังงาน 12V หรือ USB ดีไซน์กะทัดรัดสำหรับพื้นที่แคบ กำลังดูดแรงสำหรับเศษอาหาร ขนสัตว์เลี้ยง และฝุ่นภายในห้องโดยสาร',
        'vi': 'Máy hút bụi ô tô di động với tùy chọn nguồn 12V hoặc USB. Thiết kế nhỏ gọn cho không gian chật hẹp. Lực hút mạnh cho vụn bánh, lông thú cưng và bụi trong khoang xe.'},
    'tire-inflator': {
        'ar': 'مضخات إطارات رقمية مع شاشة LCD وإيقاف تلقائي. أوضاع ضغط معدة مسبقاً للسيارة والدراجة والدراجة النارية. بحد أقصى 150 PSI. تعمل بتيار 12 فولت أو بالتيار المنزلي.',
        'es': 'Compresores de neumáticos digitales con pantalla LCD y apagado automático. Modos de presión predefinidos para coche, bicicleta y moto. Máximo 150 PSI. Uso con 12 V CC o corriente doméstica.',
        'fr': "Gonfleurs de pneus numériques avec écran LCD et arrêt automatique. Modes de pression prédéfinis pour voiture, vélo et moto. Maximum 150 PSI. Alimentation 12 V CC ou secteur.",
        'id': 'Pompa ban digital dengan layar LCD dan mati otomatis. Mode tekanan preset untuk mobil, sepeda, dan sepeda motor. Maksimal 150 PSI. Dapat digunakan dengan 12 V DC atau listrik rumah.',
        'ru': 'Цифровые компрессоры для шин с ЖК-дисплеем и автоотключением. Предустановленные режимы давления для автомобиля, велосипеда и мотоцикла. Максимум 150 PSI. Питание 12 В или от сети.',
        'th': 'ปั๊มลมยางดิจิทัลพร้อมหน้าจอ LCD และปิดอัตโนมัติ โหมดความดันตั้งค่าไว้ล่วงหน้าสำหรับรถยนต์ จักรยาน และมอเตอร์ไซค์ สูงสุด 150 PSI ใช้ไฟ 12V DC หรือไฟบ้าน',
        'vi': 'Bơm lốp kỹ thuật số với màn hình LCD và tự động ngắt. Chế độ áp suất cài sẵn cho ô tô, xe đạp và xe máy. Tối đa 150 PSI. Dùng nguồn 12V DC hoặc điện gia đình.'},
    'coffee-machine': {
        'ar': 'ماكينات قهوة إسبريسو احترافية بضغط مضخة 15 بار ورغوة حليب وإعدادات قابلة للبرمجة. تُعد الإسبريسو والكابتشينو واللاتيه في المنزل أو المكتب.',
        'es': 'Máquinas de café espresso profesionales con presión de bomba de 15 bares, espumador de leche y ajustes programables. Preparan espresso, capuchino y latte en casa o en la oficina.',
        'fr': "Machines à café expresso professionnelles avec pression de pompe 15 bars, mousseur à lait et réglages programmables. Préparent espresso, cappuccino et latte à la maison ou au bureau.",
        'id': 'Mesin kopi espresso profesional dengan tekanan pompa 15 bar, pengocok susu, dan pengaturan yang dapat diprogram. Menyajikan espresso, cappuccino, dan latte di rumah atau kantor.',
        'ru': 'Профессиональные кофемашины эспрессо с давлением помпы 15 бар, капучинатором и программируемыми настройками. Готовят эспрессо, капучино и латте дома или в офисе.',
        'th': 'เครื่องชงกาแฟเอสเปรสโซระดับมืออาชีพ ความดันปั๊ม 15 บาร์ มีหัวทำฟองนม และตั้งค่าโปรแกรมได้ ชงเอสเปรสโซ คาปูชิโน และลาเต้ได้ที่บ้านหรือที่ทำงาน',
        'vi': 'Máy pha cà phê espresso chuyên nghiệp với áp suất bơm 15 bar, vòi đánh sữa và cài đặt lập trình được. Pha espresso, cappuccino và latte tại nhà hoặc văn phòng.'},
    'upright-steam-mop': {
        'ar': 'ممسحات بخار عمودية لتنظيف الأرضيات دون مواد كيميائية. قوة 1500 واط، بخار بدرجة 100 مئوية، وخزان مياه 500 مل. تطهر الأرضيات الصلبة والسجاد دون منظفات.',
        'es': 'Fregonas de vapor verticales para limpiar suelos sin productos químicos. 1500 W, vapor a 100 °C y depósito de 500 ml. Desinfectan suelos duros y alfombras sin detergentes.',
        'fr': "Vadrouilles vapeur verticales pour un nettoyage des sols sans produits chimiques. 1500 W, vapeur à 100 °C et réservoir de 500 ml. Assainissent sols durs et moquettes sans détergent.",
        'id': 'Pel uap tegak untuk membersihkan lantai tanpa bahan kimia. 1500 W, uap 100 °C, dan tangki air 500 ml. Mensterilkan lantai keras dan karpet tanpa deterjen.',
        'ru': 'Вертикальные паровые швабры для уборки полов без химии. 1500 Вт, пар 100 °C и бак 500 мл. Обеззараживают твёрдые полы и ковры без моющих средств.',
        'th': 'ไม้ถูพื้นไอน้ำแบบตั้งสำหรับทำความสะอาดพื้นโดยไม่ต้องใช้สารเคมี 1500W ไอน้ำ 100 องศา และถังน้ำ 500 มล. ฆ่าเชื้อพื้นแข็งและพรมโดยไม่ต้องใช้น้ำยาซักฟอก',
        'vi': 'Cây lau hơi nước đứng giúp làm sạch sàn mà không cần hóa chất. 1500W, hơi nước 100°C và bình chứa 500 ml. Khử trùng sàn cứng và thảm mà không cần chất tẩy.'},
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true')
    args = ap.parse_args()

    data = json.load(open(P, encoding='utf-8'))
    n_name = n_desc = 0
    for cat in data['categories']:
        slug = cat['slug']
        for lang, val in NAME.get(slug, {}).items():
            if cat['name'].get(lang) != val:
                n_name += 1
                cat['name'][lang] = val
        for lang, val in DESC.get(slug, {}).items():
            if cat['description'].get(lang) != val:
                n_desc += 1
                cat['description'][lang] = val

    print(f'names updated      : {n_name}')
    print(f'descriptions updated: {n_desc}')
    if args.check:
        print('(dry run — nothing written)')
        return
    with open(P, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print('wrote', P)


if __name__ == '__main__':
    main()
