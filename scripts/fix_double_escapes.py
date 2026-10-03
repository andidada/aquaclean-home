#!/usr/bin/env python3
"""Collapse HTML entities that were escaped twice.

Some page sections were emitted through an escaper twice, so a literal
ampersand became `&amp;amp;`.  The rendered page then shows the text
"&amp;" instead of "&", and dictionary matching (which unescapes exactly
once) misses every affected string, leaving English copy on localised
pages.

Fix: `&amp;<name>;`  ->  `&<name>;`   (one level of un-escaping)

Usage:
    python scripts/fix_double_escapes.py            # apply
    python scripts/fix_double_escapes.py --dry-run  # report only
"""
import argparse
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# &amp; immediately followed by a named entity or a numeric reference
DOUBLE = re.compile(r'&amp;(#[0-9]{1,5}|#x[0-9a-fA-F]{1,4}|[A-Za-z][A-Za-z0-9]{1,31});')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    files, hits = 0, 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in ('.git', 'node_modules', '__pycache__', '.netlify')]
        for fn in filenames:
            if not fn.endswith(('.html', '.htm')):
                continue
            path = os.path.join(dirpath, fn)
            with open(path, encoding='utf-8') as f:
                src = f.read()
            out = DOUBLE.sub(lambda m: '&' + m.group(1) + ';', src)
            if out == src:
                continue
            n = len(DOUBLE.findall(src))
            files, hits = files + 1, hits + n
            rel = os.path.relpath(path, ROOT).replace('\\', '/')
            print('%s %s (%d)' % ('would fix' if args.dry_run else 'fixed', rel, n))
            if not args.dry_run:
                with open(path, 'w', encoding='utf-8', newline='') as f:
                    f.write(out)

    print('\n%s: %d files, %d double-escaped entities' %
          ('dry-run' if args.dry_run else 'done', files, hits))


if __name__ == '__main__':
    main()
