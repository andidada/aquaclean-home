# -*- coding: utf-8 -*-
"""Report leftover English strings on generated non-English pages.

Why a diff-based check
----------------------
The first version of this script flagged any text node containing three or
more Latin letters.  That works for Arabic / Thai, but for every Latin-script
locale (es / fr / id / vi) it flags the *translation* itself -- "Alfombra",
"Aplicación", "Aluminio" are reported as English.  Signal-to-noise was ~1%.

The correct test is a **diff against the English twin page**: a string still
sitting on a localised page that is byte-identical to the string on the
corresponding en/ page is a missed translation -- unless it is a unit, model
code, certification, brand or contact detail that is legitimately shared.

Both sides are HTML-unescaped before comparison, so "&gt; 2 L" and "> 2 L"
compare equal and numeric entities such as "&#8594;" do not create phantom
mismatches.

Usage
    python scripts/check_i18n_leftovers.py es
    python scripts/check_i18n_leftovers.py ar fr id ru th vi --verbose
"""
from __future__ import annotations
import collections
import html as htmlmod
import json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
from gen_pages import CATS, ALL_LANGS, load_json   # noqa

# --------------------------------------------------------------------------
# what may stay identical to English
# --------------------------------------------------------------------------
# Tokens that carry no words: units, certifications, materials, technologies,
# region codes, trade acronyms.  This is the single source of truth -- both
# needs() (which decides what enters the translation skeleton) and the leftover
# checker read it, so the two can never disagree.
UNIT_WORDS = {
    'abs', 'pp', 'pc', 'pcs', 'hepa', 'led', 'uv', 'lcd', 'rpm', 'mah', 'kpa',
    'pa', 'psi', 'bar', 'aw', 'db', 'w', 'v', 'h', 's', 'min', 'mins', 'ml',
    'l', 'kg', 'g', 'cm', 'mm', 'ce', 'fcc', 'rohs', 'reach', 'cb', 'gs', 'emc',
    'lvd', 'pse', 'kc', 'saa', 'etl', 'ul', 'iso', 'msds', 'usb', 'sos', 'oem',
    'odm', 'usd', 'us', 'eu', 'uk', 'au', 'cn', 'gua', 'jia', 'li', 'ion',
    'tuya', 'wifi', 'c', 'hv', 'ac', 'dc', 'ip', 'ipx', 'mmhg', 'r', 'es',
    'en', 'zh',
}
# Tolerated by the leftover checker only -- adding these to UNIT_WORDS would
# shrink the translation skeleton and silently drop real entries.
SHARED_EXTRA = {'lds', 'slam', 'vslam', 'lidar', 'imu', 'oled', 'hrs', 'hr',
                'moq'}
SHARED_WORDS = UNIT_WORDS | SHARED_EXTRA

# real 2-3 letter answer words ("No" vs "Yes")
ANSWER_WORDS = {'no', 'on', 'off', 'yes'}

PH = re.compile(r'\{[a-zA-Z_]+\}')

KEEP = re.compile(
    r'^(?:'
    r'[\W\d_]*'                                  # punctuation / numbers / symbols
    r'|[A-Za-z]{1,4}\d*[A-Za-z]*'                # short codes: CE, FCC, LDS, USB, ABS, W
    r'|\d[\w./%\u2013\-\u00d7 ]*'                # 400W, 30kPa, 20-65mins, 1.2L, 2\u20133 h
    r'|US\$[\d.,\u2013\u00d7\- ]*'
    r'|[\d.,\u2013\u00d7\- ]*(?:mAh|kPa|Kpa|kpa|Pa|PSI|psi|Bar|bar|AW|dB|W|w|L|l|ml|ML|'
    r'kg|g|V|v|H|h|s|S|min|mins|Mins|%|\u2103|C|pc|pcs|Pcs|PCS|hrs|Hrs|KG|MM|mm|cm|CM|'
    r'RPM|rpm|IPX\d*|IP\d+)\b[\w./\u2013\u00d7\- ]*'
    r'|(?:CE|FCC|RoHS|REACH|CB|GS|EMC|LVD|PSE|KC|SAA|ETL|UL|ISO\d*|MSDS|UN38\.3|'
    r'HEPA|LED|UV|LCD|ABS|PP|PC|TPE|SUS\d*|PCBA|BSCI|SGS|TUV|Tuya|TUYA|WiFi|Wi-Fi|'
    r'Alexa|Google Home|USB|Type-C|USB-C|SOS)'
    r'|OEM|ODM|OEM/ODM|OEM / ODM|OEM&ODM'
    r'|P\s*p\s*s|Pcs|PCS'
    r'|AquaClean.*|HKDMJ.*|D[A-Z]\d+.*'
    r'|Hong Kong(?:, China)?.*'
    r'|info@aquaclean-home\.com.*'
    r'|(?:https?://|/)[\w./#%?=&+\-]*'
    r'|\u00a9.*'
    r'|\d+D\d+M\d+.*'
    r'|[A-Z][A-Za-z]*\d+[A-Za-z0-9\-]*'           # model numbers: PV18, QW3011, YZX-305
    r'|[a-z]{2}_[A-Z]{2}'                         # og:locale codes: ar_AR, zh_CN
    r')$'
)

# "🇬🇧 English" — a language picker lists every language in its own script
LANG_PICKER_RE = re.compile(r'^[\U0001F1E6-\U0001F1FF]{2}')
# ASCII shell of a trade code: no prose characters
CODE_SHAPE_RE = re.compile(r'^[A-Za-z0-9][A-Za-z0-9 \-+;,.()/\u00d7]*$')
# short lowercase model slugs: gt20, v2g-sj, pt20c800, d2-004
SLUG_RE = re.compile(r'^[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*$')

# Attribute values worth checking in addition to text nodes.
ATTRS = ('alt', 'content', 'placeholder', 'aria-label')


def is_shared(s):
    """True when `s` is legitimately byte-identical across locales."""
    if KEEP.match(s):
        return True
    # language pickers are intentionally written in their own language
    if LANG_PICKER_RE.match(s):
        return True
    # contact lines / boilerplate that carries an email, URL or viewport spec
    if ('info@aquaclean-home.com' in s or 'http' in s
            or s == 'summary_large_image' or s.startswith('width=device-width')):
        return True
    # model slugs and trade codes: gt20, v2g-sj, pt20c800, PTC-SC-004
    if (len(s) <= 16 and re.search(r'\d', s) and SLUG_RE.match(s)
            and not re.search(r'[a-z]{4,}', s)):
        return True
    # all-uppercase token strings: CN;GUA, CE RoHS, AU, EU, UK, US, OEM ODM
    if not re.search(r'[a-z]', s):
        toks = re.findall(r'[A-Za-z]+', s)
        if toks and all(len(t) <= 4 for t in toks):
            return True
        if toks and re.search(r'\d', s) and CODE_SHAPE_RE.match(s):
            return True
    # unit-only expressions: "100 W · <30 min · 2000mAh*3", "11*6*20CM"
    words = re.findall(r'[A-Za-z]{2,}', s)
    if words and all(w.lower() in SHARED_WORDS for w in words):
        return True
    return False


def _clean(s):
    return re.sub(r'\s+', ' ', htmlmod.unescape(s)).strip()


def page_strings(path):
    """All user-visible strings of a page: text nodes + translatable attributes."""
    h = open(path, encoding='utf-8').read()
    h = re.sub(r'<style[^>]*>.*?</style>', ' ', h, flags=re.S)
    h = re.sub(r'<script[^>]*>.*?</script>', ' ', h, flags=re.S)
    out = set()
    for i, part in enumerate(re.split(r'(<[^>]*>)', h)):
        if i % 2 == 0:
            t = _clean(part)
            if t:
                out.add(t)
    for a in ATTRS:
        for m in re.finditer(a + r'="([^"]*)"', h):
            v = _clean(m.group(1))
            if v:
                out.add(v)
    return out


def has_alpha(s):
    return bool(re.search(r'[A-Za-z]{2,}', s))


def page_strings_ctx(path):
    """page_strings() but keyed to a short DOM context label.

    The label is the nearest preceding heading (h1/h2/h3) or <section id=..>,
    so a leftover can be traced to the block that produced it.
    """
    h = open(path, encoding='utf-8').read()
    h = re.sub(r'<style[^>]*>.*?</style>', ' ', h, flags=re.S)
    h = re.sub(r'<script[^>]*>.*?</script>', ' ', h, flags=re.S)
    out = {}
    ctx = '(head)'
    parts = re.split(r'(<[^>]+>)', h)
    pending_heading = False
    for i, part in enumerate(parts):
        if i % 2 == 1:                                   # a tag
            if re.match(r'<h[123]\b', part):
                pending_heading = True
            m = re.search(r'<section[^>]*\bid="([^"]+)"', part)
            if m:
                ctx = '#' + m.group(1)
                pending_heading = False
            continue
        t = _clean(part)
        if pending_heading:
            if t:
                ctx = t[:48]
            pending_heading = False
        if t:
            out.setdefault(t, ctx)
    for a in ATTRS:
        for m in re.finditer(a + r'="([^"]*)"', h):
            v = _clean(m.group(1))
            if v:
                out.setdefault(v, f'@{a}')
    return out


def pairs_for(cat):
    """Yield the detail-page file names of one category."""
    d = load_json(os.path.join(ROOT, 'data/products', cat + '.json'))
    for p in d['products']:
        yield f'{cat}-{p["id"]}.html'


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith('-')]
    verbose = '-v' in sys.argv or '--verbose' in sys.argv
    langs = argv or ALL_LANGS[2:]

    # cache the English page strings once
    en_cache = {}
    grand_where = {}

    def en_strings(rel):
        if rel not in en_cache:
            fp = os.path.join(ROOT, 'en', rel)
            en_cache[rel] = set(page_strings(fp)) if os.path.exists(fp) else set()
        return en_cache[rel]

    grand = {}
    for lang in langs:
        hits = collections.Counter()
        where = {}
        pages = 0
        for cat in CATS:
            targets = [f'{cat}/index.html'] + list(pairs_for(cat))
            for rel in targets:
                fp = os.path.join(ROOT, lang, rel)
                if not os.path.exists(fp):
                    continue
                pages += 1
                ctxs = page_strings_ctx(fp)
                for s in ctxs:
                    if len(s) < 3 or not has_alpha(s) or is_shared(s):
                        continue
                    if s in en_strings(rel):
                        hits[s] += 1
                        where.setdefault(s, (rel, ctxs[s]))
        grand[lang] = hits
        grand_where[lang] = where
        total = sum(hits.values())
        print(f'{lang}: {pages} pages, {len(hits)} distinct / {total} total leftover strings')

    union = collections.Counter()
    for lang in langs:
        for k, v in grand[lang].items():
            union[k] = max(union[k], v)
    print(f'\n### union of English leftovers: {len(union)} distinct\n')
    first = langs[0]
    show = sorted(union) if verbose else sorted(union)[:400]
    for k in show:
        who = ','.join(l for l in langs if grand[l].get(k))
        n = max(grand[l].get(k, 0) for l in langs)
        loc = grand_where.get(first, {}).get(k)
        tag = f'  <- {loc[0]} :: {loc[1]}' if loc else ''
        print(f'  [{n:>3}x {who}] {k!r}{tag}')

    out = os.path.join(ROOT, '.tmp_leftovers.json')
    json.dump({l: dict(grand[l]) for l in langs}, open(out, 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print(f'\nreport -> {out}')


if __name__ == '__main__':
    main()
