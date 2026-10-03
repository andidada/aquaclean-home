# -*- coding: utf-8 -*-
"""Populate the new `chrome` / `guideTitle` / `guideValues` sections of
data/i18n/en.json and extend `specValue` / `specLabel` with the entries that
the coverage audit (scripts/audit_coverage.py) flagged as missing.

Keyed by the exact English string as it appears in the en/ markup, so the
generator's normalised lookup matches it directly.

Usage: python scripts/patch_en_dict.py
"""
from __future__ import annotations
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
P = os.path.join(ROOT, 'data/i18n/en.json')

# --- static-markup chrome (detail + category templates) --------------------
CHROME = {
    # section headings / labels that were not in the JS UI dictionary
    'More products in this category': 'More products in this category',
    'Packaging & logistics': 'Packaging & logistics',
    'Packaging': 'Packaging',
    'Unit': 'Unit',
    'Written specification table (text-based)': 'Written specification table (text-based)',
    'Key specifications': 'Key specifications',

    # comparison table (category page)
    'Product': 'Product',
    'MOQ': 'MOQ',
    'Key specifications': 'Key specifications',
    'Certifications': 'Certifications',

    # pricing block
    'Order quantity': 'Order quantity',
    'Unit price': 'Unit price',
    'Platform shipping estimate: {amount}': 'Platform shipping estimate: {amount}',
    'Best Price': 'Best Price',

    # packaging block
    'Carton size': 'Carton size',
    'Gross weight': 'Gross weight',
    'Unit size (cm)': 'Unit size (cm)',
    'Unit weight (kg)': 'Unit weight (kg)',
    'Color Box': 'Color Box',
    'Gift Box': 'Gift Box',
    'Corrugated Box': 'Corrugated Box',

    # certifications block
    'Certificate': 'Certificate',
    'Certificate no.': 'Certificate no.',
    'Valid until': 'Valid until',
    'Alibaba verification': 'Alibaba verification',
    'Declaration of Conformity': 'Declaration of Conformity',
    'View': 'View',
    'Certification documents on file — available on request.':
        'Certification documents on file — available on request.',

    # buyer feedback block
    'reply rate': 'reply rate',
    'on Alibaba.com since': 'on Alibaba.com since',
    'Main markets': 'Main markets',
    'Supplier location': 'Supplier location',
    'Source: Alibaba.com store data (store-level, not per-product reviews)':
        'Source: Alibaba.com store data (store-level, not per-product reviews)',

    # order & customisation flow
    'Inquiry & requirements': 'Inquiry & requirements',
    'Sample & confirmation': 'Sample & confirmation',
    'Customisation approval': 'Customisation approval',
    'Mass production': 'Mass production',
    'QC inspection': 'QC inspection',
    'Shipping & documents': 'Shipping & documents',

    # customisation options
    'Custom logo': 'Custom logo',
    'Custom colour': 'Custom colour',
    'Custom packaging': 'Custom packaging',

    # supplier profile
    'Company name': 'Company name',
    'Business type': 'Business type',
    'Established': 'Established',
    'Team size': 'Team size',
    'Location': 'Location',
    'Alibaba.com store opened': 'Alibaba.com store opened',
    'Main products': 'Main products',
    'Export regions': 'Export regions',
    'Platform status': 'Platform status',
    'Certificates on file': 'Certificates on file',
    'Logistics': 'Logistics',
    'Trading company': 'Trading company',
    'Trading company established 2024 · Hong Kong': 'Trading company established 2024 · Hong Kong',
    '51–100 people': '51–100 people',
    'Hong Kong (New Territories)': 'Hong Kong (New Territories)',
    'vacuum cleaners, robot vacuums, car accessories, steam mops, air fryers':
        'vacuum cleaners, robot vacuums, car accessories, steam mops, air fryers',
    'North America · South America · Eastern Europe · Southeast Asia':
        'North America · South America · Eastern Europe · Southeast Asia',
    'Certified (Y) · Verified Supplier (N)': 'Certified (Y) · Verified Supplier (N)',
    'FOB, CIF and DDP shipping to major markets': 'FOB, CIF and DDP shipping to major markets',
    'How is shipping arranged?': 'How is shipping arranged?',
    'We ship FOB, CIF or DDP depending on your preference. Sea, air and express are all '
    'available; transit time and cost are confirmed per order and destination.':
        'We ship FOB, CIF or DDP depending on your preference. Sea, air and express are all '
        'available; transit time and cost are confirmed per order and destination.',
    'Source: Alibaba.com seller profile (authoritative company data for this site)':
        'Source: Alibaba.com seller profile (authoritative company data for this site)',
    'AquaClean Home Appliances Co., Ltd.': 'AquaClean Home Appliances Co., Ltd.',
    'OEM/ODM Manufacturer': 'OEM/ODM Manufacturer',
    'Hong Kong': 'Hong Kong',
    'Supplier': 'Supplier',

    # spec-table values that carry English words
    'Wet & Dry': 'Wet & Dry',
    'Wet and dry': 'Wet and dry',
    'Wet And Dry': 'Wet And Dry',
    'With LED Lights': 'With LED Lights',
    'With Bag': 'With Bag',
    'Button': 'Button',
    'LDS Navigation': 'LDS Navigation',
    'LDS SLAM': 'LDS SLAM',
    'LDS Slam': 'LDS Slam',
    'LDS+SLAM': 'LDS+SLAM',
    'LDS Slam+Vslam': 'LDS Slam+Vslam',
    'Max Pressure': 'Max Pressure',
    'Pressure Range': 'Pressure Range',
    'Plug Type': 'Plug Type',
    'No-Go Zones & Virtual Walls': 'No-Go Zones & Virtual Walls',
    'No-Go Zones': 'No-Go Zones',
    'Virtual Walls': 'Virtual Walls',
    'Brush Motor': 'Brush Motor',
    'High Power Motor': 'High Power Motor',
    'Brushless Motor': 'Brushless Motor',
    'Purple': 'Purple',
    'Black': 'Black',
    'White': 'White',
    'Aluminum': 'Aluminum',
    'digital pressure gauge': 'digital pressure gauge',
    'multiple modes': 'multiple modes',
    'stain cleaning': 'stain cleaning',
    'carpets, upholstery, car seats, windows': 'carpets, upholstery, car seats, windows',
    'wet and dry car vacuum cleaner': 'wet and dry car vacuum cleaner',
    '1 Year': '1 Year',
    'Free Spare Parts': 'Free Spare Parts',
    'Yes': 'Yes',
    'No': 'No',
    'Housing Material': 'Housing Material',
    'Charging Time': 'Charging Time',
    'ChargingTime': 'Charging Time',
    'Coffee Maker Capacity': 'Coffee Maker Capacity',
    'Heating Time': 'Heating Time',
    'Water Tank Capacity': 'Water Tank Capacity',
    'Dust Cup Capacity': 'Dust Cup Capacity',
    'Dust capacity': 'Dust capacity',
    'Battery Capacity': 'Battery Capacity',
    'Motor Power': 'Motor Power',
    'Suction Power': 'Suction Power',
    'Air Power': 'Air Power',
    'Runtime': 'Runtime',
    'maximum runtime': 'Maximum Runtime',
    'Navigation': 'Navigation',
    'Function': 'Function',
    'Voltage': 'Voltage',
    'Weight (KG)': 'Weight (KG)',
    'Weight': 'Weight',
    'private mold': 'Private Mould',
    'product net weight': 'Net Weight',
    'power (w)': 'Power (W)',
    'power source': 'Power Source',
    'filter': 'Filter',
    'pump pressure bars': 'Pump Pressure (bar)',
    'suction power (airwatts)': 'Suction Power (air watts)',
    'dust box capacity (l)': 'Dust Box Capacity (L)',
    'Steam pressure': 'Steam Pressure',
    'Maximum Pressure': 'Maximum Pressure',
    'Model': 'Model',
    'Model number': 'Model number',
    'Place of Origin': 'Place of Origin',
    'after-sales service provided': 'After-sales service',
    'app-controlled': 'App-controlled',
    'application': 'Application',
    'bag or bagless': 'Bag or bagless',
    'brand name': 'Brand name',
    'model number': 'Model number',
    'nozzle number': 'Nozzle number',
    'operating language': 'Operating language',
    'packaging types': 'Packaging types',
    'place of origin': 'Place of origin',
    'warranty': 'Warranty',
    'Overseas Call Centers': 'Overseas Call Centers',
    'Bagless': 'Bagless',
    'Cyclone Technology': 'Cyclone Technology',
    'Easy Cleaning': 'Easy Cleaning',
    'Lightweight': 'Lightweight',
    'Portable': 'Portable',
    'Washable Filter': 'Washable Filter',
    'Smart Touch LED Display': 'Smart Touch LED Display',
    'Removable Battery': 'Removable Battery',
    'Household': 'Household',
    'Hotel': 'Hotel',
    'Dry': 'Dry',
    'Battery': 'Battery',
    'Battery Powered': 'Battery Powered',
    'vacuuming': 'vacuuming',
    'HEPA, lightweight, portable, wet/dry, rechargeable':
        'HEPA, lightweight, portable, wet/dry, rechargeable',
}

# --- buying-guide card titles (raw spec field name -> display label) --------
GUIDE_TITLE = {
    'Suction Power': 'Suction Power',
    'Runtime': 'Runtime',
    'Battery capacity': 'Battery Capacity',
    'Battery Capacity': 'Battery Capacity',
    'Dust Cup Capacity': 'Dust Cup Capacity',
    'Dust capacity': 'Dust Capacity',
    'ChargingTime': 'Charging Time',
    'Charging Time': 'Charging Time',
    'power (w)': 'Power (W)',
    'Power': 'Power',
    'suction power (airwatts)': 'Suction Power (air watts)',
    'maximum runtime': 'Maximum Runtime',
    'Water Tank Capacity': 'Water Tank Capacity',
    'Water tank capacity': 'Water Tank Capacity',
    'Heating Time': 'Heating Time',
    'Coffee Maker Capacity': 'Coffee Maker Capacity',
    'Housing Material': 'Housing Material',
    'Voltage': 'Voltage',
    'Weight (KG)': 'Weight (KG)',
    'product net weight': 'Net Weight',
    'Maximum Pressure': 'Maximum Pressure',
    'pump pressure bars': 'Pump Pressure (bar)',
    'Steam pressure': 'Steam Pressure',
    'Navigation': 'Navigation',
    'Function': 'Function',
    'function': 'Function',
    'filter': 'Filter',
    'dust box capacity (l)': 'Dust Box Capacity (L)',
    'private mold': 'Private Mould',
}

# --- guide range values that contain English words -------------------------
GUIDE_VALUES = {
    'Up to 4 cups': 'Up to 4 cups',
    'Aluminum': 'Aluminum',
    'Hot Water System · Programmable · Self-Cleaning · Single Service':
        'Hot Water System · Programmable · Self-Cleaning · Single Service',
    'LDS SLAM · LDS+SLAM · LDS Navigation': 'LDS SLAM · LDS+SLAM · LDS Navigation',
    '4-5hours': '4-5 hours',
    '1-3H': '1-3 h',
    '2min · 20S': '2 min · 20 s',
    'Emergency Light · Power Indicator · Tire Pressure Monitor · Tire Inflation':
        'Emergency Light · Power Indicator · Tire Pressure Monitor · Tire Inflation',
    'HEPA Filter': 'HEPA Filter',
    'No': 'No',
}

# --- detail.dict additions -------------------------------------------------
DETAIL = {
    'modelLabel': 'Model',
    'moqLine': 'MOQ {moq} {unit}',
    'customSub': 'OEM / ODM · MOQ {moq} {unit} · sample up to {sample} {unit}',
    'faqQ4': 'What are the packaging dimensions?',
    'faqA4': 'Unit size {size} cm, unit weight {weight} kg, packed in {pack}.',
    'compareColProduct': 'Product',
    'compareColModel': 'Model',
    'compareColMoq': 'MOQ',
    'compareColPrice': 'Price',
    'compareColSpecs': 'Key specifications',
    'compareColCerts': 'Certifications',
    'dash': '—',
    'sampleQuantity': 'Sample quantity',
    'cartonSizeShort': 'Carton size',
    'grossWeightShort': 'Gross weight',
    'reviewsCount': '{n} reviews',
}

CATEGORY = {
    'guideSubRest': 'things to compare before you place a wholesale order.',
}

SPEC_LABEL = {
    'Unit size (cm)': 'Unit size (cm)',
    'Unit weight (kg)': 'Unit weight (kg)',
    'Key specifications': 'Key specifications',
    'Carton size': 'Carton size',
    'Gross weight': 'Gross weight',
    'Certificate': 'Certificate',
    'Certificate no.': 'Certificate no.',
    'Valid until': 'Valid until',
    'Order quantity': 'Order quantity',
    'Unit price': 'Unit price',
    'Unit': 'Unit',
}

SPEC_VALUE = {}


def main():
    en = json.load(open(P, encoding='utf-8'))

    for sec, data in (('chrome', CHROME), ('guideTitle', GUIDE_TITLE),
                      ('guideValues', GUIDE_VALUES)):
        cur = en.setdefault(sec, {})
        added = 0
        for k, v in data.items():
            if k not in cur:
                added += 1
            cur[k] = v
        print(f'{sec}: +{added} / {len(cur)}')

    for sec, data in (('detail', DETAIL), ('category', CATEGORY),
                      ('specLabel', SPEC_LABEL), ('specValue', SPEC_VALUE)):
        cur = en.setdefault(sec, {})
        added = 0
        for k, v in data.items():
            if k not in cur:
                added += 1
            cur[k] = v
        print(f'{sec}: +{added} / {len(cur)}')

    with open(P, 'w', encoding='utf-8') as f:
        json.dump(en, f, ensure_ascii=False, indent=1)
        f.write('\n')
    print('\nwrote', P)


if __name__ == '__main__':
    main()
