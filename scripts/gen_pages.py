#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AquaClean Home - multi-language page generator.

Generates product-category pages and product-detail pages for the 7
non-English locales (ar, es, fr, id, ru, th, vi) by localising the
already-validated `en/` page templates.

Why "localise a template" instead of "render from scratch":
  the en/ pages carry ~30 KB of hand-tuned CSS/SVG/JSON-LD per page.
  Re-emitting them from a new template risks silent regressions on the
  money pages. Cloning the validated markup and swapping only the
  language-bearing strings keeps structure byte-stable.

Inputs
  data/i18n/en.json            canonical English source strings
  data/i18n/{lang}.json        per-language overrides (partial is fine)
  data/products/categories.json
  data/products/{cat}.json
  en/{cat}/index.html          category template
  en/{cat}-{id}.html           detail template

Outputs
  {lang}/{cat}/index.html
  {lang}/{cat}-{id}.html
"""
from __future__ import annotations
import argparse, html as htmlmod, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = 'en'

CATS = ['car-vacuum', 'coffee-machine', 'handheld-vacuum', 'robot-vacuum', 'steam-cleaner',
        'tire-inflator', 'upright-steam-mop', 'uv-mite-remover', 'window-cleaner-robot']

LANGMETA = {
    'en': {'flag': '\U0001F1EC\U0001F1E7', 'label': 'English',          'locale': 'en_US'},
    'zh': {'flag': '\U0001F1E8\U0001F1F3', 'label': '\u4e2d\u6587',     'locale': 'zh_CN'},
    'ar': {'flag': '\U0001F1F8\U0001F1E6', 'label': '\u0627\u0644\u0639\u0631\u0628\u064a\u0629', 'locale': 'ar_AR', 'rtl': True},
    'es': {'flag': '\U0001F1EA\U0001F1F8', 'label': 'Espa\u00f1ol',     'locale': 'es_ES'},
    'fr': {'flag': '\U0001F1EB\U0001F1F7', 'label': 'Fran\u00e7ais',    'locale': 'fr_FR'},
    'id': {'flag': '\U0001F1EE\U0001F1E9', 'label': 'Bahasa Indonesia',  'locale': 'id_ID'},
    'ru': {'flag': '\U0001F1F7\U0001F1FA', 'label': '\u0420\u0443\u0441\u0441\u043a\u0438\u0439', 'locale': 'ru_RU'},
    'th': {'flag': '\U0001F1F9\U0001F1ED', 'label': '\u0e20\u0e32\u0e29\u0e32\u0e44\u0e17\u0e22', 'locale': 'th_TH'},
    'vi': {'flag': '\U0001F1FB\U0001F1F3', 'label': 'Ti\u1ebfng Vi\u1ec7t', 'locale': 'vi_VN'},
}
ALL_LANGS = ['en', 'zh', 'ar', 'es', 'fr', 'id', 'ru', 'th', 'vi']
SITE = 'https://www.hkdmj.net'


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def pick(obj, lang):
    """Language-keyed value with en fallback (mirrors product-detail.js pick())."""
    if obj is None:
        return ''
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        v = obj.get(lang)
        if v:
            return v
        return obj.get('en') or obj.get('value') or ''
    return ''


def deep_merge(base, over):
    out = dict(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_merge(out[k], v)
        else:
            out[k] = v
    return out


def num_price(v):
    """price_indicator min/max may be a number, a numeric string, or a malformed
    {'currency':..,'number':..} dict (data bug found on gv22 / pv18)."""
    if isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        try:
            return float(v)
        except ValueError:
            return None
    if isinstance(v, dict):
        return num_price(v.get('number'))
    return None


def fmt_num(v):
    if v is None:
        return ''
    f = float(v)
    return str(int(f)) if f == int(f) else ('%g' % f)


def esc(s):
    return htmlmod.escape(str(s), quote=True)


# --------------------------------------------------------------------------
# i18n
# --------------------------------------------------------------------------
EN = None
CATS_JSON = None


def get_i18n(lang):
    p = os.path.join(ROOT, 'data/i18n', lang + '.json')
    if os.path.exists(p):
        return deep_merge(EN, load_json(p))
    return EN


def _norm(s):
    """Canonical form for dictionary matching: unescaped, whitespace-trimmed.

    Everything in the i18n tables is stored in this form, and every node read
    off a page is converted to it before lookup.  That makes the `&amp;` /
    `&copy;` / `&mdash;` entity variants (which previously defeated whole-node
    matching for any string containing "&") a non-issue instead of a special
    case.
    """
    return htmlmod.unescape(str(s)).strip()


def build_maps(lang, i18n, cat_meta):
    """Return (EXACT, FRAG, PREFIX) tables: english -> translated.

    EXACT  : applied to a whole text node / attribute value   (keys normalised)
    FRAG   : substring replacement, for a small, explicit phrase allow-list only
    PREFIX : product names that may appear followed by " — ..." in a longer value
    """
    exact, frag, prefixes = {}, {}, {}

    def put(ev, tv):
        ev, tv = _norm(ev), _norm(tv)
        if ev and tv and ev != tv:
            exact[ev] = tv

    # --- chrome sections -------------------------------------------------
    for sec in ('nav', 'footer', 'category', 'detail'):
        e_sec, t_sec = EN.get(sec, {}), i18n.get(sec, {})
        for k, ev in e_sec.items():
            tv = t_sec.get(k, ev)
            if isinstance(ev, str) and isinstance(tv, str):
                put(ev, tv)

    # --- plain key->key dictionaries -------------------------------------
    # specLabel / quickLabel are keyed by the label itself, so both the key and
    # the value map to the translation.
    for sec in ('specLabel', 'quickLabel'):
        for k, ev in EN.get(sec, {}).items():
            tv = i18n.get(sec, {}).get(k, k if k == ev else ev)
            if isinstance(ev, str):
                put(ev, tv)
                put(k, tv)

    # specNote is keyed by the same buying-guide card titles, but its VALUES are
    # explanatory prose.  Registering the *title* from here would overwrite the
    # real label with a whole sentence (it made the guide <h3> read "Higher Pa
    # lifts more debris..."), so only the prose is registered.  The card titles
    # are translated through the guideTitle / specLabel tables instead.
    for k, ev in EN.get('specNote', {}).items():
        tv = i18n.get('specNote', {}).get(k, ev)
        if isinstance(ev, str):
            put(ev, tv)

    # --- spec values (whole table cells) ---------------------------------
    # Keys absent from a language file fall back to English automatically,
    # so codes such as "ABS" / model numbers need no explicit identity entry.
    for k, ev in EN.get('specValue', {}).items():
        tv = i18n.get('specValue', {}).get(k, ev)
        put(ev, tv)

    # --- flat chrome table ------------------------------------------------
    # Static markup on the detail/category templates that is not part of the
    # JS UI dictionary: keyed by the exact English string.
    #
    # `chrome` is *not* a plain identity table: it carries ~22 "raw -> display"
    # normalisations whose KEY is the lowercase label taken from the supplier
    # listing and whose VALUE is the casing that is actually rendered, e.g.
    #   'after-sales service provided' -> 'After-sales service'
    #   'private mold'                 -> 'Private Mould'
    #   'power (w)'                    -> 'Power (W)'
    # The rendered spec-table `<th>` holds the VALUE, so registering only the
    # key left those 14 rows in English on every localised detail page. Both
    # sides are registered here; they resolve to the same translation.
    for sec in ('chrome', 'guideTitle', 'guideValues'):
        for k, ev in EN.get(sec, {}).items():
            tv = i18n.get(sec, {}).get(k, ev)
            if isinstance(ev, str):
                put(k, tv)
                put(ev, tv)

    # --- per-category page chrome ---------------------------------------
    cp_en = EN.get('categoryPage', {})
    cp_t = i18n.get('categoryPage', {})
    for slug, ev_map in cp_en.items():
        tv_map = cp_t.get(slug, {})
        for k, ev in ev_map.items():
            if k == 'heroP' or not isinstance(ev, str):
                continue
            put(ev, tv_map.get(k, ev))

    # --- products --------------------------------------------------------
    for cat in CATS:
        d = load_json(os.path.join(ROOT, 'data/products', cat + '.json'))
        for p in d.get('products', []):
            for fld in ('name', 'tagline', 'category_name', 'applications', 'description'):
                ev, tv = pick(p.get(fld), 'en'), pick(p.get(fld), lang)
                if ev and tv:
                    put(ev, tv)
            for h in (p.get('highlights') or []):
                ev, tv = pick(h.get('text'), 'en'), pick(h.get('text'), lang)
                if ev and tv:
                    put(ev, tv)
            for arr in ('specs', 'quick_specs'):
                for s in (p.get(arr) or []):
                    for fld in ('label', 'value'):
                        ev, tv = pick(s.get(fld), 'en'), pick(s.get(fld), lang)
                        if ev and tv:
                            put(ev, tv)
            # short product identity strings may appear as a *prefix* of a
            # longer node ("{name} — 1", "{name} — detail images")
            ev, tv = pick(p.get('name'), 'en'), pick(p.get('name'), lang)
            if ev and tv and ev != tv:
                prefixes[_norm(ev)] = _norm(tv)
    # --- category names & descriptions -----------------------------------
    # NOTE: deliberately NOT added to `frag`. A category name such as
    # "Car Vacuum Cleaner" is a substring of longer product names, and blind
    # substring substitution corrupts them. They only ever appear as whole
    # text nodes / attribute values, which `exact` already covers.
    for c in CATS_JSON['categories']:
        put(pick(c.get('name'), 'en'), pick(c.get('name'), lang))
        put(pick(c.get('description'), 'en'), pick(c.get('description'), lang))
    # hero paragraphs come from categories.json descriptions
    for slug, ev_map in cp_en.items():
        slug_name = next((c for c in CATS_JSON['categories'] if c['slug'] == slug), None)
        if slug_name is None:
            continue
        put(ev_map.get('heroP', ''), pick(slug_name.get('description'), lang))

    # --- explicit phrase fragments ---------------------------------------
    # Strings that appear *inside* a larger text node and therefore need
    # substring substitution rather than whole-node matching.
    for k in ('detailImagesSuffix',):
        ev = EN['detail'].get(k, '')
        tv = i18n['detail'].get(k, ev)
        if ev and tv and tv != ev:
            frag['\u2014 ' + _norm(ev)] = '\u2014 ' + _norm(tv)
    for k in ('oemLinkText', 'contactForQuote', 'viewFullSpecs'):
        ev = EN['detail'].get(k, '')
        tv = i18n['detail'].get(k, ev)
        if ev and tv and tv != ev:
            frag[_norm(ev)] = _norm(tv)
    # unit words that appear inside composed data strings ("2–199 pcs")
    for k, phrase in (('moqUnit', ' pcs'), ('perPiece', ' / pc')):
        tv = i18n.get(k) if k == 'moqUnit' else i18n.get('category', {}).get(k)
        ev = EN.get(k) if k == 'moqUnit' else EN.get('category', {}).get(k)
        if tv and ev and tv != ev:
            frag[phrase] = ' ' + _norm(tv)

    # longest-first for safe fragment substitution
    frag_items = sorted(frag.items(), key=lambda kv: -len(kv[0]))
    # NOTE: `prefixes` must stay a dict — it is probed with a key lookup.
    # (It was previously a sorted list of tuples and the membership test
    #  `group in prefixes` compared a string against tuples, so the whole
    #  "{name} — …" / "{name} 1" path was dead code.)
    return exact, frag_items, prefixes


# --------------------------------------------------------------------------
# text-node aware substitution
# --------------------------------------------------------------------------
SPLIT_RE = re.compile(r'(<[^>]+>)')


ATTR_RE = re.compile(r'\b(alt|content|placeholder|aria-label)="([^"]*)"')
FRAG_ATTRS = ('alt', 'content', 'placeholder', 'aria-label')
# "{name} — 1" / "{name} — detail images" (product names embedded in a longer value)
PREFIX_TAIL_RE = re.compile(r'^(\s*)(.*?)(\s*\u2014\s.*)$', re.S)
# "{name} 2" / "{name} 01" (gallery strip alt/caption built as "{name} {n}")
PREFIX_NUM_RE = re.compile(r'^(.*?)(\s+\d{1,2})$', re.S)


def _translate(u, exact, frag, prefixes):
    """Translate an already-normalised (unescaped, stripped) string.

    `prefixes` maps a full English product name to its localised form, for
    nodes where the name is followed by a suffix ("{name} — 1", "{name} 01").

    Returns None when nothing matched, so untouched nodes can be left alone.
    """
    if u in exact:
        return exact[u]
    m = PREFIX_TAIL_RE.match(u)
    if m and m.group(2) in prefixes:
        return m.group(1) + prefixes[m.group(2)] + m.group(3)
    m = PREFIX_NUM_RE.match(u)
    if m and m.group(1) in prefixes:
        return prefixes[m.group(1)] + m.group(2)
    out, hit = u, False
    for k, v in frag:
        if k in out:
            out = out.replace(k, v)
            hit = True
    return out if hit else None


def _apply(raw, exact, frag, prefixes, quote):
    """Translate one raw (possibly entity-escaped) node value in place."""
    u = _norm(raw)
    if not u:
        return raw
    out = _translate(u, exact, frag, prefixes)
    if out is None:
        return raw
    lead = raw[:len(raw) - len(raw.lstrip())]
    trail = raw[len(raw.rstrip()):]
    return lead + htmlmod.escape(out, quote=quote) + trail


def swap_nodes(doc, exact, frag, prefixes):
    """Translate text nodes and translatable attributes.

    Raw-text elements (`<script>`, `<style>`) are skipped: their bodies are JS
    / CSS / JSON, not prose, and running the fragment allow-list over a JSON-LD
    body could rewrite structured data by accident.
    """
    parts = SPLIT_RE.split(doc)
    raw_tag = None
    for i in range(len(parts)):
        if i % 2 == 1:
            tag = parts[i]
            if raw_tag is None:
                m = re.match(r'<\s*(script|style|textarea)\b', tag, re.I)
                if m and not tag.rstrip().endswith('/>'):
                    raw_tag = m.group(1).lower()
            elif re.match(r'<\s*/\s*' + raw_tag + r'\b', tag, re.I):
                raw_tag = None
            # --- tag: localise translatable attribute values ---
            if any(a in tag for a in FRAG_ATTRS):
                parts[i] = ATTR_RE.sub(
                    lambda m: f'{m.group(1)}="{_apply(m.group(2), exact, frag, prefixes, True)}"',
                    tag)
            continue
        if raw_tag or not parts[i].strip():
            continue
        parts[i] = _apply(parts[i], exact, frag, prefixes, False)
    return ''.join(parts)


# --------------------------------------------------------------------------
# head
# --------------------------------------------------------------------------
HREFLANG_RE = re.compile(r'[ \t]*<link rel="alternate" hreflang="[^"]+" href="[^"]*">\s*')
# `>?` is optional on purpose: a past bug emitted alternate tags without the
# closing `>`; the tolerant form also sweeps those up instead of letting them
# accumulate one set per generation
OGLOCALE_ALT_RE = re.compile(r'[ \t]*<meta property="og:locale:alternate" [^>\n]*>?[ \t]*\n?')


def page_url(lang, rel_path):
    """rel_path like 'uv-mite-remover/' or 'uv-mite-remover-pc708.html'"""
    return f'{SITE}/{lang}/{rel_path}'


# --------------------------------------------------------------------------
# which pages exist in which locale
# --------------------------------------------------------------------------
# This script emits the locale home, the nine category hubs and the 39 product
# pages for *every* locale.  A handful of editorial pages (about, FAQ, the OEM
# landings, ...) are maintained by hand and ship in the source locales only.
# Both sets are computed in main() from the data and from what en/ actually
# contains, so the rewrite below can tell a real translation from a 404.
#
#   LOCALIZED: site paths emitted for every locale ('' == the locale home)
#   SRC_ONLY : site paths that exist in en/ and zh/ but nowhere else
LOCALIZED = None
SRC_ONLY = set()

# `"/en/about.html"`, `https://www.hkdmj.net/en/about.html` -- both the relative
# and the absolute form, so JSON-LD URLs get the same treatment as <a href>.
LOCALIZE_RE = re.compile(
    r'(?P<pre>' + re.escape(SITE) + r'|")/' + SRC + r'/(?P<path>[^"\s?#]*)')


def locale_link(lang, path=''):
    """Href for `path` inside `lang`, falling back to the source locale.

    The eleven editorial pages ship in en + zh only, so pointing a translated
    page straight at /ar/about.html produced a 404 in the navbar of every
    generated page for the seven added locales.
    """
    bare = path.rstrip('/')
    if LOCALIZED is not None and bare in SRC_ONLY and lang not in (SRC, 'zh'):
        lang = SRC
    if path == '':
        return f'/{lang}/'
    return f'/{lang}/{path}'


def build_page_availability():
    """Populate LOCALIZED and SRC_ONLY from the data and from en/ on disk."""
    global LOCALIZED, SRC_ONLY
    # Every locale gets the home, the category hubs and the product pages.
    LOCALIZED = {''} | set(CATS)
    for cat in CATS:
        cdata = load_json(os.path.join(ROOT, 'data/products', cat + '.json'))
        for p in cdata.get('products', []):
            LOCALIZED.add(f'{cat}-{p["id"]}.html')
    # Anything else found in en/ is an editorial page shipped in en + zh only.
    SRC_ONLY = set()
    src_root = os.path.join(ROOT, SRC)
    for dirpath, _dirnames, filenames in os.walk(src_root):
        for name in filenames:
            if not name.endswith('.html'):
                continue
            rel = os.path.relpath(os.path.join(dirpath, name), src_root).replace(os.sep, '/')
            if rel == 'index.html':
                rel = ''
            elif rel.endswith('/index.html'):
                rel = rel[: -len('/index.html')]
            if rel not in LOCALIZED:
                SRC_ONLY.add(rel)


def avail_langs(path):
    """Locales that actually ship `path`, in canonical order."""
    if path in SRC_ONLY:
        return [l for l in ALL_LANGS if l in (SRC, 'zh')]
    return list(ALL_LANGS)


# --------------------------------------------------------------------------
# Open Graph / Twitter metadata
# --------------------------------------------------------------------------
# The generated templates ship with no social metadata at all, and
# rebuild_head() only *rewrote* og/twitter tags it assumed were already there
# -- so 384 generated pages had none, which breaks every share preview.
OG_IMAGE_FALLBACK = f'{SITE}/assets/images/og-image.png'
PAGE_IMAGE = None


def build_page_image_map():
    """Map each site path to the most specific og:image available."""
    global PAGE_IMAGE
    m = {'': OG_IMAGE_FALLBACK}
    for c in CATS_JSON['categories']:
        if c.get('banner_image'):
            m[c['slug']] = c['banner_image']
    for cat in CATS:
        data = load_json(os.path.join(ROOT, 'data/products', cat + '.json'))
        for p in data.get('products', []):
            imgs = p.get('images') or []
            m[f'{cat}-{p["id"]}.html'] = imgs[0] if imgs else OG_IMAGE_FALLBACK
    PAGE_IMAGE = m


def og_image_for(path):
    if PAGE_IMAGE is None:
        return OG_IMAGE_FALLBACK
    return PAGE_IMAGE.get(path) or PAGE_IMAGE.get(path.rstrip('/')) or OG_IMAGE_FALLBACK


def rel_img(url):
    """Root-relative src for <img> tags.

    The product data stores absolute URLs (they double as og:image values,
    which MUST be absolute), but pointing <img> at the production host made
    every category-hub product card load -- and 404 -- across the wire, and
    broke them entirely wherever the site is served from another origin.
    """
    return url[len(SITE):] if url.startswith(SITE) else url


def inject_og_meta(doc, lang, path, title, desc, image, avail):
    """Add the Open Graph / Twitter block to a page that has none.

    Idempotent: a page that already carries a curated block (the hand-written
    homes, about, FAQ, the OEM landings) is left untouched, so re-running the
    pipeline never duplicates or overwrites hand-tuned metadata.  One exception
    is made below: those hand-written pages hard-code the generic brand image
    plus fixed 1200x630 dimensions, so a page that *does* have a more specific
    image gets it swapped in and the now-wrong dimensions dropped.
    """
    head_end = doc.find('</head>')
    if head_end < 0:
        return doc
    head = doc[:head_end]
    rest = doc[head_end:]

    if 'property="og:image"' in head:
        if image == OG_IMAGE_FALLBACK or OG_IMAGE_FALLBACK not in head:
            return doc
        swap = lambda m: m.group(1) + image + m.group(2)  # noqa: E731
        head = re.sub(r'(<meta property="og:image" content=")'
                      + re.escape(OG_IMAGE_FALLBACK) + r'(")', swap, head)
        head = re.sub(r'(<meta name="twitter:image" content=")'
                      + re.escape(OG_IMAGE_FALLBACK) + r'(")', swap, head)
        # the dimensions belonged to the brand image, not to this one
        head = re.sub(r'[ \t]*<meta property="og:image:width" content="[^"]*">\n?', '', head)
        head = re.sub(r'[ \t]*<meta property="og:image:height" content="[^"]*">\n?', '', head)
        return head + rest

    # product pages are the only "product" objects; hubs and editorial pages
    # are plain websites
    is_product = path.endswith('.html') and path not in SRC_ONLY
    url = page_url(lang, path)
    alternates = ''.join(
        f'\n    <meta property="og:locale:alternate" content="{LANGMETA[l]["locale"]}">'
        for l in avail if l != lang)
    block = (
        f'  <meta property="og:title" content="{esc(title)}">\n'
        f'  <meta property="og:description" content="{esc(desc)}">\n'
        f'  <meta property="og:type" content="{"product" if is_product else "website"}">\n'
        f'  <meta property="og:url" content="{url}">\n'
        f'  <meta property="og:image" content="{image}">\n'
        f'  <meta property="og:locale" content="{LANGMETA[lang]["locale"]}">{alternates}\n'
        f'  <meta name="twitter:card" content="summary_large_image">\n'
        f'  <meta name="twitter:title" content="{esc(title)}">\n'
        f'  <meta name="twitter:description" content="{esc(desc)}">\n'
        f'  <meta name="twitter:image" content="{image}">\n'
    )
    # sit the social block right under the canonical link, where the
    # hand-written pages already keep theirs
    m = re.search(r'<link rel="canonical" href="[^"]*">', head)
    idx = m.end() if m else head_end
    return doc[:idx] + '\n' + block + doc[idx:]


def _relocalize(m, lang):
    """Point a source-locale URL at `lang`, falling back to en when needed.

    Rewriting blindly turned `/en/about.html` into `/ar/about.html` -- a 404,
    because the about page was never built for the seven added locales.
    """
    path = m.group('path')
    pre = m.group('pre')
    target = lang
    if LOCALIZED is not None and path.rstrip('/') in SRC_ONLY and lang not in (SRC, 'zh'):
        target = SRC
    return f'{pre}/{target}/{path}'


def rebuild_head(doc, lang, rel_path, title, desc, og_locale, detail_url=None):
    # 0) <html lang="..">
    doc = re.sub(r'<html lang="[^"]*"', f'<html lang="{lang}"', doc, count=1)

    # 1) drop the existing hreflang + og:locale:alternate blocks
    doc = HREFLANG_RE.sub('', doc)
    doc = OGLOCALE_ALT_RE.sub('', doc)

    # 2) rewrite the page's own language prefix everywhere -- but leave links
    #    pointing at a translation that was never generated alone (see above)
    doc = LOCALIZE_RE.sub(lambda m: _relocalize(m, lang), doc)

    # 3) canonical + og:url
    doc = re.sub(r'(<link rel="canonical" href=")[^"]*(")',
                 lambda m: m.group(1) + page_url(lang, rel_path) + m.group(2), doc, count=1)
    doc = re.sub(r'(<meta property="og:url" content=")[^"]*(")',
                 lambda m: m.group(1) + page_url(lang, rel_path) + m.group(2), doc, count=1)

    # 4) titles / descriptions
    doc = re.sub(r'<title>.*?</title>', '<title>' + esc(title) + '</title>', doc, count=1, flags=re.S)
    doc = re.sub(r'(<meta property="og:title" content=")[^"]*(")',
                 lambda m: m.group(1) + esc(title) + m.group(2), doc, count=1)
    doc = re.sub(r'(<meta name="twitter:title" content=")[^"]*(")',
                 lambda m: m.group(1) + esc(title) + m.group(2), doc, count=1)
    for pat in (r'(<meta name="description" content=")[^"]*(")',
                r'(<meta property="og:description" content=")[^"]*(")',
                r'(<meta name="twitter:description" content=")[^"]*(")'):
        doc = re.sub(pat, lambda m: m.group(1) + esc(desc) + m.group(2), doc, count=1)

    # 5) og:locale + alternates + hreflang block
    alt = ''.join(f'\n    <meta property="og:locale:alternate" content="{LANGMETA[l]["locale"]}">'
                  for l in ALL_LANGS if l != lang)
    hreflang = ''.join(f'\n  <link rel="alternate" hreflang="{l}" href="{page_url(l, rel_path)}">'
                       for l in ALL_LANGS)
    hreflang = (f'\n  <link rel="alternate" hreflang="x-default" href="{page_url(SRC, rel_path)}">'
                + hreflang)
    doc = doc.replace('<meta property="og:locale" content="en_US">',
                      f'<meta property="og:locale" content="{og_locale}">{alt}', 1)
    if 'og:locale' not in doc:
        doc = doc.replace('<meta property="og:type" content="website">',
                          f'<meta property="og:type" content="website">\n    <meta property="og:locale" content="{og_locale}">{alt}', 1)
    doc = re.sub(r'(<link rel="canonical" href="[^"]*">)',
                 lambda m: m.group(1) + hreflang, doc, count=1)

    # 6) social metadata: the templates carry none, so inject a complete
    #    block (no-op for pages that already have one)
    doc = inject_og_meta(doc, lang, rel_path, title, desc,
                         og_image_for(rel_path), avail_langs(rel_path))
    return doc


# --------------------------------------------------------------------------
# shared chrome: language picker + navbar
# --------------------------------------------------------------------------
def lang_menu_html(lang):
    items = []
    for l in ALL_LANGS:
        m = LANGMETA[l]
        cls = ' class="active"' if l == lang else ''
        items.append(f'        <li><a href="/{l}/"{cls}>{m["flag"]} {m["label"]}</a></li>')
    return '\n'.join(items)


def lang_picker_html(lang):
    m = LANGMETA[lang]
    return f'''    <div class="lang-picker" id="langPicker">
      <button class="lang-current" type="button" aria-haspopup="true" aria-expanded="false">
        <span class="lang-flag">{m["flag"]}</span>
        <span class="lang-label">{m["label"]}</span>
        <span class="lang-caret">&#9662;</span>
      </button>
      <ul class="lang-menu">
{lang_menu_html(lang)}
      </ul>
    </div>'''


NAV_SIMPLE_RE = re.compile(r'<nav class="navbar">.*?</nav>', re.S)


def rebuild_navbar(doc, lang, i18n):
    """Normalise the navbar: same links + language picker on every page type."""
    n = i18n['nav']
    has_picker = 'id="langPicker"' in doc
    if has_picker:
        # detail-style navbar: replace the caret+label + the lang menu contents
        doc = re.sub(r'<span class="lang-flag">[^<]*</span>',
                     f'<span class="lang-flag">{LANGMETA[lang]["flag"]}</span>', doc, count=1)
        doc = re.sub(r'<span class="lang-label">[^<]*</span>',
                     f'<span class="lang-label">{LANGMETA[lang]["label"]}</span>', doc, count=1)
        doc = re.sub(r'<ul class="lang-menu">.*?</ul>',
                     '<ul class="lang-menu">\n' + lang_menu_html(lang) + '\n      </ul>', doc, count=1, flags=re.S)
        return doc

    # category-style navbar (no picker) -> rebuild it entirely
    links = [
        (locale_link(lang, '#products'), n['products']),
        (locale_link(lang, 'about.html'), n['about']),
        (locale_link(lang, '#why-us'), n['whyUs']),
        (locale_link(lang, '#testimonials'), n['reviews']),
        (locale_link(lang, '#contact'), n['contact']),
    ]
    li = '\n'.join(f'      <li><a href="{href}">{label}</a></li>' for href, label in links)
    nav = f'''<nav class="navbar">
  <div class="navbar-inner">
    <a href="{locale_link(lang)}" class="logo">
      <div class="logo-icon">\U0001F3E0</div>
      <span>{esc(n['brand'])}</span>
    </a>
    <ul class="nav-links">
{li}
      <li><a href="{locale_link(lang, '#contact')}" class="nav-cta">{esc(n['getQuote'])}</a></li>
    </ul>
{lang_picker_html(lang)}
  </div>
</nav>'''
    return NAV_SIMPLE_RE.sub(lambda m: nav, doc, count=1)


# --------------------------------------------------------------------------
# inline category-page script (replaces the legacy one)
# --------------------------------------------------------------------------
ICONS_RE = re.compile(r'(\s*var ICONS = \{.*?\n  \};)', re.S)


def build_cat_script(cat, lang, i18n, icons_block):
    c = i18n['category']
    js_ui = json.dumps({
        'viewDetails': c['viewDetails'],
        'products': c['productsWord'],
        'product': c['productWord'],
        'noProducts': c['noProducts'],
        'checkBack': c['checkBack'],
        'loadFailed': c['loadFailed'],
        'tryAgain': c['tryAgain'],
        'error': c['error'],
        'perPiece': c['perPiece'],
        'moqPrefix': c['moqPrefix'],
        'moqUnit': i18n.get('moqUnit', 'pieces'),
    }, ensure_ascii=False)
    return f'''<script>
(function() {{
  var LANG = "{lang}";
  var SLUG = "{cat}";
  var DATA_URL = "/data/products/{cat}.json";
  var UI = {js_ui};

{icons_block}

  function getIcon(name) {{ return ICONS[name] || ICONS['power']; }}

  function t(obj) {{
    if (typeof obj === 'string') return obj;
    if (!obj) return '';
    return obj[LANG] || obj['en'] || '';
  }}

  function detailUrl(id) {{ return '/' + LANG + '/' + SLUG + '-' + id + '.html'; }}

  function priceRange(p) {{
    var pi = p.price_indicator || {{}};
    function n(v) {{
      if (typeof v === 'number') return v;
      if (typeof v === 'string' && v !== '' && !isNaN(v)) return parseFloat(v);
      if (v && typeof v === 'object') return n(v.number);
      return null;
    }}
    var lo = n(pi.min), hi = n(pi.max);
    if (lo === null || hi === null) return '';
    return '$' + lo + ' - $' + hi;
  }}

  function renderProducts(products) {{
    var grid = document.getElementById('productsGrid');
    var countEl = document.getElementById('productCount');
    if (!grid) return;

    if (!products || products.length === 0) {{
      grid.innerHTML = '<div class="empty-state"><div class="empty-state-icon">...</div><h3>' + UI.noProducts + '</h3><p>' + UI.checkBack + '</p></div>';
      if (countEl) countEl.textContent = '0 ' + UI.products;
      return;
    }}
    if (countEl) countEl.textContent = products.length + ' ' + (products.length === 1 ? UI.product : UI.products);

    var html = '';
    products.forEach(function(p) {{
      var name = t(p.name);
      var tagline = t(p.tagline);
      var img = (p.images && p.images[0]) ? p.images[0].split('{SITE}').join('') : '';
      var certs = p.certifications || [];
      var range = priceRange(p);
      var moqTxt = p.moq && p.moq.value ? (p.moq.value + ' ' + UI.moqUnit) : '';

      html += '<div class="product-card">';
      html += '  <div class="product-img-wrap">';
      html += '    <img src="' + img + '" alt="' + name + '" loading="lazy" decoding="async">';
      html += '  </div>';
      html += '  <div class="product-body">';
      html += '    <h3>' + name + '</h3>';
      html += '    <p>' + tagline + '</p>';
      if (certs.length > 0) {{
        html += '    <div class="cert-badges">';
        certs.slice(0, 4).forEach(function(c) {{ html += '<span class="cert-badge">' + c + '</span>'; }});
        html += '    </div>';
      }}
      if (range) {{
        html += '    <div style="margin-bottom:12px;"><div class="price-indicator">' + range + ' <span class="moq">' + UI.perPiece + ' ' + UI.moqPrefix + ' ' + moqTxt + '</span></div></div>';
      }}
      html += '    <a href="' + detailUrl(p.id) + '" class="btn btn-primary" style="width:100%;justify-content:center;text-decoration:none;">' + UI.viewDetails + ' &#8594;</a>';
      html += '  </div>';
      html += '</div>';
    }});
    grid.innerHTML = html;
  }}

  function init() {{
    fetch(DATA_URL)
      .then(function(res) {{ return res.json(); }})
      .then(function(data) {{ renderProducts(data.products || []); }})
      .catch(function(err) {{
        console.error('Failed to load products:', err);
        var grid = document.getElementById('productsGrid');
        if (grid) grid.innerHTML = '<div class="empty-state"><div class="empty-state-icon">!</div><h3>' + UI.loadFailed + '</h3><p>' + UI.tryAgain + '</p></div>';
        var countEl = document.getElementById('productCount');
        if (countEl) countEl.textContent = UI.error;
      }});
  }}

  init();
}})();
</script>'''


# --------------------------------------------------------------------------
# static product grid (SSR fallback, crawlable)
# --------------------------------------------------------------------------
def build_grid(cat, lang, products, i18n, exact):
    c = i18n['category']
    rows = ['      <!-- 静态输出（爬虫与禁用 JS 时可见）；加载后由 JS 渲染保持交互一致 -->']
    for p in products:
        name = pick(p.get('name'), lang) or p['id']
        qs = p.get('quick_specs') or []
        if qs:
            bits = []
            for s in qs[:3]:
                lab = pick(s.get('label'), lang)
                v = pick(s.get('value'), lang)
                bits.append(f"{lab}: {v}" if lab else str(v))
            sub = ' &middot; '.join(bits)
        else:
            sub = pick(p.get('tagline'), lang)
        img = rel_img((p.get('images') or [''])[0])
        pi = p.get('price_indicator') or {}
        lo, hi = num_price(pi.get('min')), num_price(pi.get('max'))
        money = ''
        if lo is not None and hi is not None:
            moq = p.get('moq') or {}
            moq_txt = f"{moq.get('value','')} {i18n.get('moqUnit','pieces')}".strip() if moq.get('value') else ''
            inner = f"{c['moqPrefix']} {moq_txt}".strip()
            money = (f'\n          <div style="margin-bottom:12px;"><div class="price-indicator">'
                     f'${fmt_num(lo)} - ${fmt_num(hi)} <span class="moq">{esc(c["perPiece"])} {esc(inner)}</span></div></div>')
        rows.append(f'''      <div class="product-card">
        <div class="product-img-wrap">
          <img src="{esc(img)}" alt="{esc(name)}" loading="lazy" decoding="async">
        </div>
        <div class="product-body">
          <h3>{esc(name)}</h3>
          <p>{sub}</p>{money}
          <a href="/{lang}/{cat}-{p['id']}.html" class="btn btn-primary" style="width:100%;justify-content:center;text-decoration:none;">{esc(c['viewDetails'])} &#8594;</a>
        </div>
      </div>''')
    return '\n'.join(rows)


GRID_RE = re.compile(r'(<div id="productsGrid" class="products-grid">)(.*?)(\n\s*</div>\s*</div>\s*</section>)', re.S)
SCRIPT_TAIL_RE = re.compile(r'<script>\s*\(function\(\) \{.*?</script>', re.S)

# --- category page: comparison table ---------------------------------------
COMPARE_TABLE_RE = re.compile(r'(id="compare".*?<table>)(.*?)(</table>)', re.S)
# --- category page: buying-guide cards ------------------------------------
GUIDE_GRID_RE = re.compile(r'(id="guide".*?<div class="features-grid"[^>]*>)(.*?)(\s*</div>\s*</div>\s*</section>)', re.S)
GUIDE_SUB_RE = re.compile(r'(id="guide".*?<p class="section-sub">)[^<]*(</p>)', re.S)
GUIDE_CARD_RE = re.compile(r'(<div class="feature-card">.*?<h3>)(.*?)(</h3>\s*<p>)(.*?)(</p>)', re.S)

GUIDES = None


def _moq_unit(i18n):
    return i18n.get('moqUnit', 'pcs')


def rebuild_compare(doc, cat, lang, products, i18n):
    """Rebuild the #compare table from product data.

    The legacy table was hand-written per language and carried a Python repr
    ("US${'currency': 'USD', ...}") plus an untranslatable "/ pc" suffix.  It
    also duplicated the row data that lives in data/products/*.json, so every
    language drifted independently.  Rebuilding keeps one source of truth.

    Six of the nine category pages never got the section at all (only
    handheld-vacuum / robot-vacuum / tire-inflator had one), so the block is
    inserted when missing rather than skipped.
    """
    d = i18n['detail']
    unit = _moq_unit(i18n)
    per = i18n['category']['perPiece']
    dash = i18n.get('dash', '\u2014')
    cols = [d['compareColProduct'], d['compareColModel'], d['compareColMoq'],
            d['compareColPrice'], d['compareColSpecs'], d['compareColCerts']]
    head = '        <thead><tr>' + ''.join(
        f'<th scope="col">{esc(c)}</th>' for c in cols) + '</tr></thead>'

    rows = []
    for p in products:
        name = pick(p.get('name'), lang) or p['id']
        moq = (p.get('moq') or {}).get('value')
        moq_txt = f'{moq} {unit}' if moq else dash
        pi = p.get('price_indicator') or {}
        lo, hi = num_price(pi.get('min')), num_price(pi.get('max'))
        if lo is None or hi is None:
            price = dash
        elif lo == hi:
            price = f'US${fmt_num(lo)} {per}'
        else:
            price = f'US${fmt_num(lo)}\u2013{fmt_num(hi)} {per}'
        qs = (p.get('quick_specs') or [])[:4]
        if not qs:
            qs = (p.get('specs') or [])[:4]
        bits = []
        for s in qs:
            lab = pick(s.get('label'), lang)
            val = pick(s.get('value'), lang)
            bits.append(f'{lab}: {val}' if lab else str(val))
        spec_txt = ' &middot; '.join(bits) if bits else dash
        certs = p.get('certifications') or []
        cert_txt = ', '.join(certs) if certs else dash
        rows.append(
            f'          <tr><td><a href="/{lang}/{cat}-{p["id"]}.html">{esc(name)}</a></td>'
            f'<td>{esc(p["id"])}</td><td>{esc(moq_txt)}</td><td>{esc(price)}</td>'
            f'<td>{spec_txt}</td><td>{esc(cert_txt)}</td></tr>')
    body = '\n' + head + '\n        <tbody>\n' + '\n'.join(rows) + '\n        </tbody>\n      '

    doc, n = COMPARE_TABLE_RE.subn(lambda m: m.group(1) + body + m.group(3), doc, count=1)
    if n == 1:
        return doc

    # --- section missing entirely: insert it before the buying guide ------
    h2 = i18n['category']['compareTitle']
    section = f'''<section class="section section-alt" id="compare">
  <div class="section-inner">
    <div class="text-center">
      <h2 class="section-title">{esc(h2)}</h2>
    </div>
    <div class="aqc-ss">
      <table>{body}</table>
    </div>
  </div>
</section>
'''
    anchor = re.search(r'<section[^>]*\bid="guide"[^>]*>', doc)
    if not anchor:
        anchor = re.search(r'<section[^>]*\bid="related"[^>]*>', doc)
    if not anchor:
        return doc
    return doc[:anchor.start()] + section + doc[anchor.start():]


def rebuild_guide(doc, cat, lang, i18n, n_models):
    """Rebuild the #guide cards.

    Each card is `<h3>{title}</h3><p>Current range: {values}. {explain}</p>`;
    the English `<p>` is a *composed* string that no dictionary can match.  The
    values were extracted once into data/i18n/category-guides.json and the
    explanation is reused from specNote (keyed by the same card title).
    """
    cards = (GUIDES or {}).get(cat) or []
    if not cards:
        return doc

    d = i18n['detail']
    c = i18n['category']
    gtitle = i18n.get('guideTitle', {})
    gvalue = i18n.get('guideValues', {})
    note = i18n.get('specNote', {})
    label = i18n.get('specLabel', {})

    def title_of(t):
        return gtitle.get(t) or label.get(t) or t

    it = iter(cards)

    def card_sub(m):
        card = next(it)
        t = title_of(card['title'])
        # the value list is mostly units/numbers; only a few carry words
        vals = _norm(gvalue.get(_norm(card['values']), card['values']))
        expl = note.get(card['title']) or note.get(card['title'].lower()) or card['explain']
        p = f"{c['currentRange']} {vals}. {expl}".strip()
        return m.group(1) + esc(t) + m.group(3) + esc(p) + m.group(5)

    doc, n = GUIDE_CARD_RE.subn(card_sub, doc, count=len(cards))
    if n != len(cards):
        # fall back to a whole-block rebuild when the markup drifted
        pass
    # count-aware sub-heading ("Five things to compare ..." was hard-coded)
    doc = GUIDE_SUB_RE.sub(
        lambda m: m.group(1) + esc(str(n_models) + ' ' + c['guideSubRest']) + m.group(2),
        doc, count=1)
    return doc


# --- detail page: composed section subtitles ------------------------------
SPEC_SUB_RE = re.compile(r'(id="specifications".*?<p class="section-sub">)[^<]*(</p>)', re.S)
CUSTOM_SUB_RE = re.compile(r'(id="customization".*?<p class="section-sub">)[^<]*(</p>)', re.S)
PRICING_SUB_RE = re.compile(r'(id="pricing".*?<p class="section-sub">)[^<]*(</p>)', re.S)
GALLERY_FILE_ALT_RE = re.compile(r'(\balt=")[^"]*?(\s\d{1,2})\.jpg(")')
SHIP_EST_RE = re.compile(r'Platform shipping estimate:\s*US\$([\d.,]+)')
# matches both a category link ("/es/car-vacuum/") and a related-product link
# ("/es/handheld-vacuum-gv18.html") inside a Related-products / footer <li>
CAT_LINK_RE = re.compile(
    r'(<li><a href="/(?:en|[a-z]{2})/([a-z0-9-]+)(?:/|\.html)">)([^<]*)(</a></li>)')


def rebuild_category_links(doc, lang, i18n):
    """Re-label every related-products / footer link from the canonical data.

    The static templates carry hand-written labels that drift from the real
    names ("Window Cleaner Robot" vs "Smart Window Cleaner Robot", or the
    truncated "V18 Cordless Stick Vacuum" for gv18), which made those nodes
    untranslatable.  Sourcing the label from categories.json / products.json
    keeps all nine languages in step.
    """
    names = {c['slug']: pick(c.get('name'), lang) for c in CATS_JSON['categories']}
    prod = {}
    for cat in CATS:
        for p in load_json(os.path.join(ROOT, 'data/products', cat + '.json')).get('products', []):
            nm = pick(p.get('name'), lang)
            if nm:
                prod[f'{cat}-{p["id"]}'] = nm

    def repl(m):
        nm = names.get(m.group(2)) or prod.get(m.group(2))
        if not nm:
            return m.group(0)
        return m.group(1) + esc(nm) + m.group(4)

    return CAT_LINK_RE.sub(repl, doc)


def rebuild_shipping_estimate(doc, i18n):
    """`Platform shipping estimate: US$17.02` embeds a per-product amount."""
    tpl = i18n.get('chrome', {}).get('Platform shipping estimate: {amount}')
    if not tpl or '{amount}' not in tpl:
        return doc
    return SHIP_EST_RE.sub(
        lambda m: esc(tpl.format(amount='US$' + m.group(1))), doc)


def rebuild_detail_subs(doc, product, pname, lang, i18n):
    """Rebuild the composed `.section-sub` lines that embed product data."""
    d = i18n['detail']
    unit = _moq_unit(i18n)
    moq = (product.get('moq') or {}).get('value')
    sample = (product.get('sample') or {}).get('qty')

    if moq:
        doc = PRICING_SUB_RE.sub(
            lambda m: m.group(1) + esc(d['moqLine'].format(moq=moq, unit=unit)) + m.group(2),
            doc, count=1)
        if sample:
            sub = d['customSub'].format(moq=moq, unit=unit, sample=sample)
        else:
            sub = d['moqLine'].format(moq=moq, unit=unit)
        doc = CUSTOM_SUB_RE.sub(lambda m: m.group(1) + esc(sub) + m.group(2), doc, count=1)

    model = product['id'].upper()
    doc = SPEC_SUB_RE.sub(
        lambda m: m.group(1) + esc(f'{pname} \u2014 {d["modelLabel"]} {model}') + m.group(2),
        doc, count=1)

    # gallery placeholder alt text was the raw file name ("slug 01.jpg")
    doc = GALLERY_FILE_ALT_RE.sub(
        lambda m: m.group(1) + esc(pname) + m.group(2) + m.group(3), doc)
    doc = rebuild_shipping_estimate(doc, i18n)
    return doc


# --------------------------------------------------------------------------
# JSON-LD translation
# --------------------------------------------------------------------------
LD_RE = re.compile(r'(<script type="application/ld\+json">)(.*?)(</script>)', re.S)


def translate_ld_strings(obj, exact):
    if isinstance(obj, dict):
        return {k: translate_ld_strings(v, exact) for k, v in obj.items()}
    if isinstance(obj, list):
        return [translate_ld_strings(v, exact) for v in obj]
    if isinstance(obj, str):
        # JSON-LD bodies are raw text, but the source generators wrote some
        # names through an HTML escaper, so normalise before matching and
        # emit the plain (unescaped) form -- valid JSON and better for crawlers.
        u = _norm(obj)
        if u in exact:
            return exact[u]
        for k, v in exact.items():
            if len(k) > 25 and k in u:
                u = u.replace(k, v)
        return u
    return obj


def localize_ld(doc, exact, lang, canonical_url):
    def repl(m):
        head, body, tail = m.group(1), m.group(2), m.group(3)
        try:
            data = json.loads(body)
        except Exception:
            return m.group(0)
        data = translate_ld_strings(data, exact)
        # fix offers.url -> the product's own canonical url
        if isinstance(data, dict) and data.get('@type') == 'Product':
            off = data.get('offers')
            if isinstance(off, dict) and off.get('url'):
                off['url'] = canonical_url
            if isinstance(data.get('url'), str) and not data['url'].startswith(SITE):
                data['url'] = canonical_url
        return head + '\n' + json.dumps(data, ensure_ascii=False, indent=2) + '\n' + tail
    return LD_RE.sub(repl, doc)


# --------------------------------------------------------------------------
# RTL support
# --------------------------------------------------------------------------
RTL_CSS = '''
  <style>
  /* RTL adjustments (generated) */
  html[dir="rtl"] .nav-links, html[dir="rtl"] .d-breadcrumb-inner { flex-direction: row-reverse; }
  html[dir="rtl"] .footer-top, html[dir="rtl"] .d-attr-item { direction: rtl; }
  html[dir="rtl"] .cat-breadcrumb { flex-direction: row-reverse; }
  html[dir="rtl"] .d-gallery { flex-direction: row-reverse; }
  html[dir="rtl"] th { text-align: right; }
  </style>
'''


def apply_rtl(doc):
    doc = doc.replace('<html lang="ar">', '<html lang="ar" dir="rtl">', 1)
    if 'dir="rtl"' in doc and 'RTL adjustments' not in doc:
        doc = doc.replace('</head>', RTL_CSS + '</head>', 1)
    return doc


# --------------------------------------------------------------------------
# page builders
# --------------------------------------------------------------------------
def gen_category(cat, lang, i18n, exact, frag, prefixes, products):
    src_path = f'{SRC}/{cat}/index.html'
    doc = open(os.path.join(ROOT, src_path), encoding='utf-8').read()

    # keep the icon SVG dictionary verbatim from the template
    mi = ICONS_RE.search(doc)
    icons_block = mi.group(1).strip('\n') if mi else '  var ICONS = { power: "" };'

    rel = f'{cat}/'
    name = pick(next(c for c in CATS_JSON['categories'] if c['slug'] == cat).get('name'), lang)
    cp = i18n['categoryPage'][cat]
    title = f"{cp['heroTitle']} \u2014 AquaClean Home"
    desc = i18n['category']['ogDesc'].format(name=cp['heroTitle'])

    url = page_url(lang, rel)
    doc = localize_ld(doc, exact, lang, url)
    doc = rebuild_head(doc, lang, rel, title, desc, LANGMETA[lang]['locale'])
    doc = rebuild_navbar(doc, lang, i18n)
    doc = rebuild_category_links(doc, lang, i18n)

    # re-generate the static grid + inline script BEFORE the text pass, so the
    # text pass works on already-correct content (also fixes the price/None leaks)
    body = build_grid(cat, lang, products, i18n, exact)
    def _grid(m):
        return m.group(1) + '\n' + body + m.group(3)
    doc, n_grid = GRID_RE.subn(_grid, doc, count=1)
    if n_grid != 1:
        raise RuntimeError(f'productsGrid block not found in {src_path}')
    doc, n_script = SCRIPT_TAIL_RE.subn(lambda m: build_cat_script(cat, lang, i18n, icons_block), doc, count=1)
    if n_script != 1:
        raise RuntimeError(f'inline category script not found in {src_path}')

    # composed blocks that no dictionary can match -> rebuild from data
    doc = rebuild_compare(doc, cat, lang, products, i18n)
    doc = rebuild_guide(doc, cat, lang, i18n, len(products))

    doc = swap_nodes(doc, exact, frag, prefixes)

    # hero product-count badge
    cc = i18n['category']
    n = len(products)
    count_txt = f"{n} {cc['productWord'] if n == 1 else cc['productsWord']}"
    doc, ncnt = re.subn(r'(<span id="productCount">)[^<]*(</span>)',
                        lambda m: m.group(1) + esc(count_txt) + m.group(2), doc, count=1)
    if ncnt != 1:
        raise RuntimeError(f'productCount badge not found in {src_path}')

    if LANGMETA[lang].get('rtl'):
        doc = apply_rtl(doc)
    return doc


MOQ_P_RE = re.compile(r'<p>(MOQ[^<]*)</p>')
# FAQ sections come in four shapes across the 39 templates:
#   3 items  (5 pages)   4 items (31 pages, +packaging)
#   5 rich   (3 pages, bespoke answers — see rebuild_rich_faq)
FAQ_SEC_RE = re.compile(r'<section[^>]*\bid="faq"[^>]*>.*?</section>', re.S)
PACK_SEC_RE = re.compile(r'<section[^>]*\bid="packaging"[^>]*>.*?</section>', re.S)
H1_RE = re.compile(r'<h1>.*?</h1>', re.S)
# three template variants exist in en/ :
#   A "rich"     <h2>{slug} — detail images</h2>
#   B standard   <h2 class="section-title">{truncated name} — detail images</h2>
#   C minimal    (no detail-images section at all)
DETAIL_IMAGES_H2_RE = re.compile(r'<h2[^>]*>[^<]*\u2014 detail images</h2>', re.S)
GALLERY_ALT_RE = re.compile(r'(\balt=")[^"]*(\u2014 \d+")')
PACK_ROW_RE = re.compile(
    r'<th scope="row">([^<]*)</th>\s*<td>([^<]*)</td>')


def _pack_values(doc):
    """Read the Unit size / weight / packaging values off the page.

    They are language-neutral (numbers, units, box names) so reading them from
    the English template is safe and avoids re-deriving them from partial JSON
    (product.packaging only carries `unit` for most records).
    """
    sec = PACK_SEC_RE.search(doc)
    if not sec:
        return None
    vals = {}
    for m in PACK_ROW_RE.finditer(sec.group(0)):
        vals[m.group(1).strip().lower()] = m.group(2).strip()
    return vals


def rebuild_faq(doc, product, i18n):
    """Rebuild the prerendered FAQ so no casing variants of the answers leak.

    Handles the 3-item and 4-item template shapes; rich-template pages
    (gv18 / gt20 / ymc6628) carry a bespoke 5-entry FAQ and are handled by
    `rebuild_rich_faq` instead.

    Returns (doc, handled).
    """
    sec = FAQ_SEC_RE.search(doc)
    if not sec:
        return doc, False
    n_have = len(DETAILS_RE.findall(sec.group(0)))
    if n_have >= 5:
        return doc, False

    d = i18n['detail']
    pairs = [(d['faqQ1'], d['faqA1']), (d['faqQ2'], d['faqA2']), (d['faqQ3'], d['faqA3'])]
    if n_have >= 4:
        pack = _pack_values(doc) or {}
        chrome = i18n.get('chrome', {})
        box = pack.get('packaging', '')
        pairs.append((d['faqQ4'], d['faqA4'].format(
            size=pack.get('unit size (cm)', ''),
            weight=pack.get('unit weight (kg)', ''),
            pack=chrome.get(box, box))))

    items = '\n'.join(
        f'<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>' for q, a in pairs)
    # keep whatever wrapper the section used: replace only the <details> run
    body = sec.group(0)
    first = body.find('<details>')
    last = body.rfind('</details>') + len('</details>')
    if first < 0 or last <= first:
        return doc, False
    new_sec = body[:first] + items + body[last:]
    return doc[:sec.start()] + new_sec + doc[sec.end():], True


DETAILS_RE = re.compile(r'<details>.*?</details>', re.S)
# The three rich templates carry five <details> in #faq *and* two more in the
# supplier block, so the FAQ must be located by section before counting.
FAQ_SECTION_RE = re.compile(r'<section[^>]*\bid="faq"[^>]*>.*?</section>', re.S)


def rebuild_rich_faq(doc, product, pname, i18n):
    """Rebuild the bespoke 5-entry FAQ used by the three rich-template pages.

    Those pages carry a customer-facing FAQ whose answers embed product data
    (MOQ, FOB band, sample quantity, certification, configurable options).
    Rebuilding it from templates keeps every language in sync and lets the
    option labels/values reuse the spec dictionaries.

    Returns (doc, handled) — handled is False for the 36 standard pages.
    """
    sec = FAQ_SECTION_RE.search(doc)
    if not sec:
        return doc, False
    blocks = DETAILS_RE.findall(sec.group(0))
    if len(blocks) != 5 or 'What is the MOQ and price for' not in blocks[1]:
        return doc, False

    d = i18n['detail']

    def inner(b):
        m = re.search(r'<p>(.*?)</p>', b, re.S)
        return re.sub(r'\s+', ' ', m.group(1)).strip() if m else ''

    opts_en = ''
    m = re.search(r'configurable options:\s*(.*?)\.\s*Custom colour', inner(blocks[2]), re.S)
    if m:
        opts_en = re.sub(r'\s+', ' ', m.group(1)).strip()
    cert_en = ''
    m = re.search(r'^(.*?)\.\s*We can share', inner(blocks[3]), re.S)
    if m:
        cert_en = m.group(1).strip()
    # the English answer is either a bare cert list ("CE") or the sentence
    # "certificate documents are on file" — the latter has to be localised.
    if cert_en.lower().startswith('certificate documents'):
        cert_en = d.get('certOnFile', cert_en)
    elif not cert_en:
        certs = product.get('certifications') or []
        cert_en = ', '.join(certs) if certs else d.get('certOnFile', '')

    sample = (product.get('sample') or {}).get('qty') or 1
    moq = (product.get('moq') or {}).get('value') or 1
    pi = product.get('price_indicator') or {}
    lo, hi = num_price(pi.get('min')), num_price(pi.get('max'))
    if lo is not None and hi is not None:
        price = f'US${fmt_num(lo)}' if lo == hi else f'US${fmt_num(lo)}\u2013{fmt_num(hi)}'
    else:
        price = d['moqOnRequest']

    olabels = d.get('optionLabel', {})
    sv = i18n.get('specValue', {})
    opts_t = []
    for part in [x.strip() for x in opts_en.split(' / ') if x.strip()]:
        if ': ' in part:
            lab, val = part.split(': ', 1)
            opts_t.append(f"{olabels.get(lab, lab)}: {sv.get(val, val)}")
        else:
            opts_t.append(sv.get(part, part))
    opts = ' / '.join(opts_t)

    pairs = [
        (d['richFaqQ1'], d['richFaqA1']),
        (d['richFaqQ2'].format(name=pname),
         d['richFaqA2'].format(moq=moq, price=price, sample=sample,
                               unit=i18n.get('moqUnit', 'pcs'))),
        (d['richFaqQ3'], d['richFaqA3'].format(options=opts)),
        (d['richFaqQ4'], d['richFaqA4'].format(cert=cert_en)),
        (d['richFaqQ5'], d['richFaqA5'].format(sample=sample, moq=moq,
                                               unit=i18n.get('moqUnit', 'pcs'))),
    ]
    it = iter(pairs)

    def _sub(m):
        q, a = next(it)
        return f'<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>'

    new_sec = DETAILS_RE.sub(_sub, sec.group(0))
    return doc[:sec.start()] + new_sec + doc[sec.end():], True


FAQ_PAIR_RE = re.compile(
    r'<details>\s*<summary>(.*?)</summary>\s*<p>(.*?)</p>\s*</details>', re.S)
TAG_STRIP_RE = re.compile(r'<[^>]+>')


def sync_ld_faq(doc):
    """Mirror the rebuilt visible #faq into the FAQPage JSON-LD block.

    The prerendered structured data was authored independently of the page and
    drifted: three templates carried a stale answer that leaked a Python repr
    ("US${'currency': 'USD', 'number': 64.5}-None/pc").  Deriving mainEntity
    from the FAQ that was just rebuilt keeps page and structured data in step
    for every template variant and every locale, and means the answers are
    translated as a side effect.
    """
    sec = FAQ_SEC_RE.search(doc)
    if not sec:
        return doc
    pairs = [(_norm(TAG_STRIP_RE.sub('', q)), _norm(TAG_STRIP_RE.sub('', a)))
             for q, a in FAQ_PAIR_RE.findall(sec.group(0))]
    pairs = [(q, a) for q, a in pairs if q and a]
    if not pairs:
        return doc

    def repl(m):
        head, body, tail = m.group(1), m.group(2), m.group(3)
        try:
            data = json.loads(body)
        except Exception:
            return m.group(0)
        if not isinstance(data, dict) or data.get('@type') != 'FAQPage':
            return m.group(0)
        data['mainEntity'] = [
            {'@type': 'Question', 'name': q,
             'acceptedAnswer': {'@type': 'Answer', 'text': a}}
            for q, a in pairs]
        return head + '\n' + json.dumps(data, ensure_ascii=False, indent=2) + '\n' + tail

    return LD_RE.sub(repl, doc)


def rebuild_moq_line(doc, product, lang, i18n):
    """Replace the prerendered MOQ line with one built from data.
    The legacy template leaked Python reprs ("US${'currency': 'USD', ...}")
    and the literal string "None warranty" for products with a malformed
    price_indicator; rebuilding from data removes both defects.
    """
    d = i18n['detail']
    unit = i18n.get('moqUnit', 'pcs')
    prefix = i18n['category']['moqPrefix']
    pi = product.get('price_indicator') or {}
    lo, hi = num_price(pi.get('min')), num_price(pi.get('max'))
    moq = product.get('moq') or {}
    if lo is not None and hi is not None:
        amount = (f"{prefix} {moq.get('value')} {unit}".strip()
                  if moq.get('value') else d['moqOnRequest'])
        price = (f"US${fmt_num(lo)}" if lo == hi
                 else f"US${fmt_num(lo)}\u2013{fmt_num(hi)}")
        line = f"{amount} &middot; {price} {d['perPieceShort'].strip()} &middot; {d['certificatesOnFile']}"
    else:
        line = f"{d['moqOnRequest']} &middot; {d['fobOnRequest']} &middot; {d['yearWarranty']}"
    return MOQ_P_RE.sub(lambda m: '<p>' + line + '</p>', doc, count=1)


def js_str(s):
    """Escape a value for use inside a double-quoted JavaScript string literal."""
    return (str(s).replace('\\', '\\\\').replace('"', '\\"')
            .replace('\n', '\\n').replace('\r', '').replace('</', '<\\/'))


# Keys of the runtime UI dictionary consumed by assets/js/product-detail.js.
# The renderer overwrites #aqc-detail-mount with a JS-built layout, so these
# strings are what a visitor actually reads; they used to exist twice (once in
# the JS `UI` table, once in data/i18n/*.json) and only the JS copy had en/zh.
# Emitting the dictionary into the page keeps both paths on one source.
JS_UI_KEYS = (
    'home', 'model', 'moq', 'inStock', 'priceTitle', 'sampleTitle', 'getSample',
    'addToCart', 'chatWhatsapp', 'highlights', 'specs', 'supplier', 'verified',
    'responseTime', 'rating', 'transactions', 'years', 'customization', 'oemTitle',
    'packaging', 'leadTime', 'applications', 'description', 'inquiry', 'inquiryTitle',
    'name', 'email', 'company', 'country', 'quantity', 'message', 'submit',
    'successTitle', 'successText', 'related', 'viewAll', 'trustShip', 'trustLead',
    'trustPack', 'getQuote', 'customLogo', 'customColor', 'customPackage',
    'customOEM', 'customODM', 'sampleLead', 'productionLead', 'certTitle',
    'currency', 'per', 'inqProduct', 'inqModel', 'whatsappText',
    'bestPrice', 'cartonSize', 'qtyPerCarton', 'grossWeight', 'noImage',
    'supplierName', 'supplierRole', 'productNotFound', 'dataError',
    'placeholderName', 'placeholderCompany', 'placeholderCountry',
    'placeholderMessage', 'defaultLeadTime', 'defaultPackUnit',
)
JS_UI_MARK = '<!-- aqc:ui -->'
# Matches an injected block with or without the marker fence, so pages written
# before the fence existed are also cleaned up.
JS_UI_RE = re.compile(
    r'[ \t]*(?:' + re.escape(JS_UI_MARK) + r'\s*)?'
    r'<script>\s*/\* Generated UI dictionary for lang=.*?window\.AQC_UI\s*=.*?</script>'
    r'\s*(?:' + re.escape(JS_UI_MARK) + r')?[ \t]*\n?', re.S)


def build_js_ui(lang, i18n):
    d = i18n['detail']
    data = {k: d[k] for k in JS_UI_KEYS if k in d}
    payload = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    return JS_UI_MARK + f'''<script>
/* Generated UI dictionary for lang="{lang}" — see data/i18n/{lang}.json.
   Fallback in product-detail.js only covers en/zh, so this must be present. */
window.AQC_UI = {payload};
</script>
''' + JS_UI_MARK + '\n'


def inject_js_ui(doc, lang, i18n):
    """Put the generated UI dictionary *before* product-detail.js.

    Idempotent: the block is fenced with a marker comment, so re-running the
    generator replaces it in place instead of stacking a second copy.
    """
    doc = JS_UI_RE.sub('', doc)
    m = re.search(r'<script[^>]+src="[^"]*product-detail\.js[^"]*"[^>]*>\s*</script>', doc)
    if not m:
        return doc
    return doc[:m.start()] + build_js_ui(lang, i18n) + doc[m.start():]


def gen_detail(cat, lang, i18n, exact, frag, prefixes, product):
    pid = product['id']
    src_path = f'{SRC}/{cat}-{pid}.html'
    doc = open(os.path.join(ROOT, src_path), encoding='utf-8').read()

    rel = f'{cat}-{pid}.html'
    url = page_url(lang, rel)
    pname = pick(product.get('name'), lang) or pid
    tagline = pick(product.get('tagline'), lang)
    title = f'{pname} \u2014 AquaClean Home'
    desc = f"{tagline} {i18n['detail']['ogSuffix']}".strip()

    doc = localize_ld(doc, exact, lang, url)
    doc = rebuild_head(doc, lang, rel, title, desc, LANGMETA[lang]['locale'])
    doc = rebuild_navbar(doc, lang, i18n)
    doc = rebuild_category_links(doc, lang, i18n)
    doc = rebuild_moq_line(doc, product, lang, i18n)
    doc = rebuild_detail_subs(doc, product, pname, lang, i18n)
    doc, rich = rebuild_rich_faq(doc, product, pname, i18n)
    if not rich:
        doc, _n_faq = rebuild_faq(doc, product, i18n)
    doc = sync_ld_faq(doc)

    # The legacy prerender used a *truncated* product name in <h1>, the detail
    # heading and the gallery alt attributes (and the bare slug on three pages).
    # Rebuild them with the full localised name so no truncated remnant survives.
    pname_esc = esc(pname)
    doc, n_h1 = H1_RE.subn(f'<h1>{pname_esc}</h1>', doc, count=1)
    img_suffix = esc(i18n['detail']['detailImagesSuffix'].lstrip('\u2014 '))
    heading = f'{pname_esc} \u2014 {img_suffix}'
    doc, n_h2 = DETAIL_IMAGES_H2_RE.subn(f'<h2 class="section-title">{heading}</h2>', doc, count=1)
    doc = GALLERY_ALT_RE.sub(lambda m: f'{m.group(1)}{pname_esc}{m.group(2)}', doc)

    # window.AQC_PRODUCT  (lang + localised categoryName)
    # note: JS string literals must be JS-escaped, not HTML-escaped, and must
    # already be in the target language so the text-node pass leaves them alone.
    cname = pick(product.get('category_name'), lang) or \
        pick(next((c for c in CATS_JSON['categories'] if c['slug'] == cat), {}).get('name'), lang)
    doc = re.sub(r'(window\.AQC_PRODUCT\s*=\s*\{[^}]*?lang:\s*)"[^"]*"',
                 lambda m: m.group(1) + f'"{lang}"', doc, count=1, flags=re.S)
    doc = re.sub(r'(window\.AQC_PRODUCT\s*=\s*\{[^}]*?categoryName:\s*)"[^"]*"',
                 lambda m: m.group(1) + f'"{js_str(cname)}"', doc, count=1, flags=re.S)

    doc = swap_nodes(doc, exact, frag, prefixes)
    doc = inject_js_ui(doc, lang, i18n)

    if LANGMETA[lang].get('rtl'):
        doc = apply_rtl(doc)
    return doc


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main():
    global EN, CATS_JSON, GUIDES, LOCALIZED, SRC_ONLY, PAGE_IMAGE
    ap = argparse.ArgumentParser()
    ap.add_argument('--langs', default=','.join(ALL_LANGS[2:]))
    ap.add_argument('--dry-run', action='store_true')
    ap.add_argument('--report', default='')
    ap.add_argument('--with-src', action='store_true',
                    help='also regenerate the template locale (en) from itself; '
                         'keeps en in step with the eight translations')
    args = ap.parse_args()

    EN = load_json(os.path.join(ROOT, 'data/i18n/en.json'))
    CATS_JSON = load_json(os.path.join(ROOT, 'data/products/categories.json'))
    gp = os.path.join(ROOT, 'data/i18n/category-guides.json')
    GUIDES = load_json(gp) if os.path.exists(gp) else {}
    cats_by_slug = {c['slug']: c for c in CATS_JSON['categories']}

    # Which locales ship which page, and which image represents each page --
    # both consulted by rebuild_head()/inject_og_meta().
    build_page_availability()
    build_page_image_map()

    # `en` is normally read-only: it is the clone source for the translations.
    langs = [l for l in args.langs.split(',')
             if l and (l != SRC or args.with_src)]
    # A locale without data/i18n/<lang>.json would silently fall back to the
    # English strings (deep_merge(EN, {})) and overwrite its hand-maintained
    # pages with English content -- refuse instead of destroying work.
    dead = [l for l in langs
            if l != SRC and not os.path.exists(os.path.join(ROOT, 'data/i18n', l + '.json'))]
    if dead:
        sys.exit(f'gen_pages: no data/i18n/{{{",".join(dead)}}}.json -- '
                 f'these locales cannot be generated (their pages are hand-maintained); aborting')
    report = {'written': [], 'errors': []}

    for lang in langs:
        raw_path = os.path.join(ROOT, 'data/i18n', lang + '.json')
        raw = load_json(raw_path) if os.path.exists(raw_path) else {}
        i18n = deep_merge(EN, raw)
        missing = []
        for sec in ('nav', 'footer', 'category', 'detail'):
            for k in EN[sec]:
                if k not in raw.get(sec, {}):
                    missing.append(f'{sec}.{k}')
        for k in EN['specLabel']:
            if k not in raw.get('specLabel', {}):
                missing.append(f'specLabel.{k}')
        for k in EN['specNote']:
            if k not in raw.get('specNote', {}):
                missing.append(f'specNote.{k}')
        for slug, ev in EN['categoryPage'].items():
            for k, val in ev.items():
                # heroP is derived from categories.json (never read from the
                # language file) and hasRelated is a boolean flag, not a string
                if k == 'heroP' or not isinstance(val, str):
                    continue
                if k not in raw.get('categoryPage', {}).get(slug, {}):
                    missing.append(f'categoryPage.{slug}.{k}')
        for k in EN.get('guideTitle', {}):
            if k not in raw.get('guideTitle', {}):
                missing.append(f'guideTitle.{k}')
        for k in EN.get('guideValues', {}):
            if k not in raw.get('guideValues', {}):
                missing.append(f'guideValues.{k}')
        report.setdefault('missing', {})[lang] = missing

        for cat in CATS:
            data = load_json(os.path.join(ROOT, 'data/products', cat + '.json'))
            products = data.get('products', [])
            exact, frag, prefixes = build_maps(lang, i18n, cats_by_slug)

            out_dir = os.path.join(ROOT, lang, cat)
            if not args.dry_run:
                os.makedirs(out_dir, exist_ok=True)
                try:
                    out = gen_category(cat, lang, i18n, exact, frag, prefixes, products)
                    with open(os.path.join(out_dir, 'index.html'), 'w', encoding='utf-8') as f:
                        f.write(out)
                    report['written'].append(f'{lang}/{cat}/index.html')
                except Exception as e:
                    report['errors'].append(f'{lang}/{cat}/index.html :: {e!r}')

            for p in products:
                if not os.path.exists(os.path.join(ROOT, f'{SRC}/{cat}-{p["id"]}.html')):
                    report['errors'].append(f'MISSING TEMPLATE {SRC}/{cat}-{p["id"]}.html')
                    continue
                if args.dry_run:
                    continue
                try:
                    out = gen_detail(cat, lang, i18n, exact, frag, prefixes, p)
                    with open(os.path.join(ROOT, lang, f'{cat}-{p["id"]}.html'), 'w', encoding='utf-8') as f:
                        f.write(out)
                    report['written'].append(f'{lang}/{cat}-{p["id"]}.html')
                except Exception as e:
                    report['errors'].append(f'{lang}/{cat}-{p["id"]}.html :: {e!r}')

    print('written:', len(report['written']))
    print('errors :', len(report['errors']))
    for e in report['errors'][:20]:
        print('  !', e)
    for lang, ms in report.get('missing', {}).items():
        print(f'missing i18n keys [{lang}]: {len(ms)}')
        if ms and len(ms) <= 12:
            for m in ms:
                print('   -', m)
    if args.report:
        with open(args.report, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=1)


if __name__ == '__main__':
    main()
