# -*- coding: utf-8 -*-
"""Patch container/unit terms that were missing from the flat locale sources.

Four groups:

* ``pcs`` / ``/ pc`` -- filtered out of the skeleton by needs() because they are
  bare unit words, yet they are *composed* into strings a reader sees
  ("MOQ 10 pcs", "US$11 / pc").  Without a translation those stayed English on
  every page.
* ``2200mAh Lithium-Ion (removable)`` -- a spec value present in
  data/products/*.json but absent from the specValue dictionary, so
  apply_product_i18n.py propagated the English form into es/ar.
* Hong Kong place names -- the footer contact lines and the supplier
  "location" row were left in English by some locales and localised by others.
  Normalised here so every locale uses its own standard exonym (es / fr / id
  legitimately use "Hong Kong" unchanged).
* Two ``chrome`` entries whose raw key is wordier than the string actually
  rendered in the spec table -- ``after-sales service provided`` is displayed as
  "After-sales service" and ``product net weight`` as "Net Weight".  The other
  20 chrome normalisations differ only in capitalisation / parenthesis style, so
  their existing translations already match the rendered text.

Rewrites each file in `_keys_ui.json` order so a diff between locales stays
readable.  Idempotent.

Usage
    python scripts/patch_locale_terms.py
"""
from __future__ import annotations
import json, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, 'data/i18n/_src')
LANGS = ['ar', 'es', 'fr', 'id', 'ru', 'th', 'vi']

CONTACT_EMOJI = '📍 Hong Kong | 📧 info@aquaclean-home.com | 📱 WhatsApp: +86 177 7919 0118'
CONTACT_PLAIN = 'Hong Kong | info@aquaclean-home.com | WhatsApp: +86 177 7919 0118'

# keys whose raw form is longer than the string rendered in the spec table
DISPLAY = {
    'ar': {'after-sales service provided': 'خدمة ما بعد البيع',
           'product net weight': 'الوزن الصافي'},
    'es': {'after-sales service provided': 'servicio posventa',
           'product net weight': 'peso neto'},
    'fr': {'after-sales service provided': 'service après-vente',
           'product net weight': 'poids net'},
    'id': {'after-sales service provided': 'layanan purnajual',
           'product net weight': 'berat bersih'},
    'ru': {'after-sales service provided': 'послепродажное обслуживание',
           'product net weight': 'вес нетто'},
    'th': {'after-sales service provided': 'บริการหลังการขาย',
           'product net weight': 'น้ำหนักสุทธิ'},
    'vi': {'after-sales service provided': 'dịch vụ sau bán hàng',
           'product net weight': 'trọng lượng tịnh'},
}

PATCH = {
    'ar': {
        'pcs': 'قطعة', '/ pc': '/ قطعة',
        '2200mAh Lithium-Ion (removable)': '2200mAh ليثيوم أيون (قابل للإزالة)',
        'Hong Kong': 'هونغ كونغ',
        'Hong Kong (New Territories)': 'هونغ كونغ (الأقاليم الجديدة)',
        'HK / New Territories': 'هونغ كونغ / الأقاليم الجديدة',
        CONTACT_EMOJI: '📍 هونغ كونغ | 📧 info@aquaclean-home.com | 📱 WhatsApp: +86 177 7919 0118',
        CONTACT_PLAIN: 'هونغ كونغ | info@aquaclean-home.com | WhatsApp: +86 177 7919 0118',
    },
    'es': {
        'pcs': 'uds.', '/ pc': '/ ud.',
        '2200mAh Lithium-Ion (removable)': '2200mAh litio-ion (extraíble)',
        'Hong Kong': 'Hong Kong',
        'Hong Kong (New Territories)': 'Hong Kong (Nuevos Territorios)',
        'HK / New Territories': 'HK / Nuevos Territorios',
        CONTACT_EMOJI: '📍 Hong Kong | 📧 info@aquaclean-home.com | 📱 WhatsApp: +86 177 7919 0118',
        CONTACT_PLAIN: 'Hong Kong | info@aquaclean-home.com | WhatsApp: +86 177 7919 0118',
    },
    'fr': {
        'pcs': 'pièces', '/ pc': '/ pièce',
        '2200mAh Lithium-Ion (removable)': '2200mAh lithium-ion (amovible)',
        'Hong Kong': 'Hong Kong',
        'Hong Kong (New Territories)': 'Hong Kong (Nouveaux Territoires)',
        'HK / New Territories': 'HK / Nouveaux Territoires',
        CONTACT_EMOJI: '📍 Hong Kong | 📧 info@aquaclean-home.com | 📱 WhatsApp : +86 177 7919 0118',
        CONTACT_PLAIN: 'Hong Kong | info@aquaclean-home.com | WhatsApp : +86 177 7919 0118',
    },
    'id': {
        'pcs': 'pcs', '/ pc': '/ pcs',
        '2200mAh Lithium-Ion (removable)': '2200mAh Lithium-Ion (dapat dilepas)',
        'Hong Kong': 'Hong Kong',
        'Hong Kong (New Territories)': 'Hong Kong (Wilayah Baru)',
        'HK / New Territories': 'HK / Wilayah Baru',
        CONTACT_EMOJI: CONTACT_EMOJI,
        CONTACT_PLAIN: CONTACT_PLAIN,
    },
    'ru': {
        'pcs': 'шт.', '/ pc': '/ шт.',
        '2200mAh Lithium-Ion (removable)': '2200mAh литий-ионный (съёмный)',
        'Hong Kong': 'Гонконг',
        'Hong Kong (New Territories)': 'Гонконг (Новые Территории)',
        'HK / New Territories': 'Гонконг / Новые Территории',
        CONTACT_EMOJI: '📍 Гонконг | 📧 info@aquaclean-home.com | 📱 WhatsApp: +86 177 7919 0118',
        CONTACT_PLAIN: 'Гонконг | info@aquaclean-home.com | WhatsApp: +86 177 7919 0118',
    },
    'th': {
        'pcs': 'ชิ้น', '/ pc': '/ ชิ้น',
        '2200mAh Lithium-Ion (removable)': '2200mAh ลิเธียมไอออน (ถอดได้)',
        'Hong Kong': 'ฮ่องกง',
        'Hong Kong (New Territories)': 'ฮ่องกง (นิวเทร์ริทอรีส์)',
        'HK / New Territories': 'ฮ่องกง / นิวเทอร์ริทอรีส์',
        CONTACT_EMOJI: '📍 ฮ่องกง | 📧 info@aquaclean-home.com | 📱 WhatsApp: +86 177 7919 0118',
        CONTACT_PLAIN: 'ฮ่องกง | info@aquaclean-home.com | WhatsApp: +86 177 7919 0118',
    },
    'vi': {
        'pcs': 'cái', '/ pc': '/ cái',
        '2200mAh Lithium-Ion (removable)': '2200mAh Lithium-Ion (tháo rời)',
        'Hong Kong': 'Hồng Kông',
        'Hong Kong (New Territories)': 'Hồng Kông (Tân Giới)',
        'HK / New Territories': 'Hồng Kông / Tân Giới',
        CONTACT_EMOJI: '📍 Hồng Kông | 📧 info@aquaclean-home.com | 📱 WhatsApp: +86 177 7919 0118',
        CONTACT_PLAIN: 'Hồng Kông | info@aquaclean-home.com | WhatsApp: +86 177 7919 0118',
    },
}


def main():
    order = list(json.load(open(os.path.join(SRC, '_keys_ui.json'), encoding='utf-8')))
    for lang in LANGS:
        p = os.path.join(SRC, lang + '.json')
        d = json.load(open(p, encoding='utf-8'))
        added, changed = 0, 0
        for k, v in {**PATCH[lang], **DISPLAY[lang]}.items():
            assert k in order, f'{lang}: unknown key {k!r}'
            if k not in d:
                added += 1
            elif d[k] != v:
                changed += 1
            d[k] = v
        for k in d:
            assert k in order, f'{lang}: stray key {k!r}'
        d = {k: d[k] for k in order if k in d}
        assert len(d) == len(order), (lang, len(d), len(order))
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
            f.write('\n')
        print(f'{lang}: {len(d)} keys  (+{added} new, {changed} changed)')
    print('done - run build_lang.py next')


if __name__ == '__main__':
    main()
