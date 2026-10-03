#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Rewrite every page's <link rel="alternate" hreflang> block from the filesystem.

Why this exists
---------------
The `zh/` tree predates the seven locales added afterwards (ar/es/fr/id/ru/th/vi),
so its 58 shared pages still advertised only `en` + `zh` as alternates -- and nine
of them even pointed `x-default` at the Chinese page instead of English.  A page
that omits an existing translation tells Google the translation does not exist,
which is worse than having no hreflang at all.

Instead of hand-patching `zh/`, this script derives the correct set from what is
actually on disk, which is the same source `gen_sitemap.py` uses.  Page markup and
sitemap therefore cannot drift apart.

Rules applied
-------------
* one `<link rel="alternate" hreflang>` per locale that actually ships the page,
  in canonical order (en, zh, ar, es, fr, id, ru, th, vi);
* `x-default` first, always pointing at the English URL (English is complete --
  it ships all 60 paths, so it is the safe fallback);
* `en` and `zh` never gain alternates for pages only they have (`about.html`,
  the FAQ, the OEM landings, ...) -- those stay a two-locale group.

Idempotent: re-running produces byte-identical files.

Usage
    python scripts/fix_hreflang.py
    python scripts/fix_hreflang.py --check     # report drift, write nothing
"""
from __future__ import annotations
import argparse, os, re, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_sitemap import LANGS, X_DEFAULT, discover, file_for, site_url  # noqa: E402

HEAD_END = '</head>'

# A contiguous run of hreflang links.  The named backreference keeps the run
# from swallowing a following, differently-indented <link rel="canonical">.
RUN_RE = re.compile(
    r'(?P<i>[ \t]*)<link rel="alternate" hreflang="[^"]*" href="[^"]*">'
    r'(?:\r?\n(?P=i)[ \t]*<link rel="alternate" hreflang="[^"]*" href="[^"]*">)*'
)


def block(indent: str, path: str, langs: list[str]) -> str:
    rows = [f'{indent}<link rel="alternate" hreflang="x-default"'
            f' href="{site_url(X_DEFAULT, path)}">']
    for lang in langs:
        rows.append(f'{indent}<link rel="alternate" hreflang="{lang}"'
                    f' href="{site_url(lang, path)}">')
    return '\n'.join(rows)


def fix_doc(doc: str, path: str, langs: list[str]) -> tuple[str, str]:
    """Return (new_doc, status) where status is 'ok' | 'fixed' | 'error'."""
    end = doc.find(HEAD_END)
    if end < 0:
        return doc, 'error'
    head, rest = doc[:end], doc[end:]

    m = RUN_RE.search(head)
    if not m:
        return doc, 'error'

    want = block(m.group('i'), path, langs)
    if m.group(0) == want:
        return doc, 'ok'
    return head[: m.start()] + want + head[m.end():] + rest, 'fixed'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true',
                    help='report how many pages are stale without writing')
    args = ap.parse_args()

    index = discover()
    stats = {'ok': 0, 'fixed': 0, 'error': 0}
    errors: list[str] = []

    for path, langs in sorted(index.items()):
        for lang in langs:
            fp = file_for(lang, path)
            if not os.path.exists(fp):
                stats['error'] += 1
                errors.append(f'missing file {fp}')
                continue
            with open(fp, encoding='utf-8') as f:
                doc = f.read()
            new, status = fix_doc(doc, path, langs)
            stats[status] += 1
            if status == 'error':
                errors.append(f'no hreflang run found in {fp}')
                continue
            if status == 'fixed' and not args.check:
                with open(fp, 'w', encoding='utf-8', newline='\n') as f:
                    f.write(new)

    verb = 'would fix' if args.check else 'fixed'
    sys.stderr.write(f'pages ok: {stats["ok"]}   {verb}: {stats["fixed"]}'
                     f'   errors: {stats["error"]}\n')
    for e in errors[:10]:
        sys.stderr.write(f'   ! {e}\n')
    if stats['error']:
        sys.exit(1)


if __name__ == '__main__':
    main()
