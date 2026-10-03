#!/usr/bin/env python3
"""Rewrite same-host absolute asset URLs to root-relative paths.

Policy: <img src> / data-src / srcset / poster must never carry the live
host - the production site 404s cross-origin references and any other
origin (staging, local preview) breaks outright. Canonical URLs, og:image
and JSON-LD values intentionally stay absolute and are left untouched.

Usage:
    python scripts/fix_absolute_img_urls.py           # apply
    python scripts/fix_absolute_img_urls.py --dry-run # report only
"""
import argparse
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOSTS = ('https://www.hkdmj.net', 'http://www.hkdmj.net',
         'https://hkdmj.net', 'http://hkdmj.net')

# Only media attributes are rewritten; href/canonical/og:image are not.
ATTR_RE = re.compile(
    r'\b(src|data-src|srcset|poster)\s*=\s*"((?:%s)/[^"]*)"' % '|'.join(re.escape(h) for h in HOSTS),
    re.I)


def fix(text):
    def repl(m):
        attr, value = m.group(1), m.group(2)
        for h in HOSTS:
            if value.lower().startswith(h.lower()):
                value = value[len(h):]
                break
        return '%s="%s"' % (attr, value)
    return ATTR_RE.sub(repl, text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()

    changed_files, changed_refs = 0, 0
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames
                       if d not in ('.git', 'node_modules', '__pycache__', '.netlify')]
        for fn in filenames:
            if not fn.endswith(('.html', '.htm')):
                continue
            path = os.path.join(dirpath, fn)
            with open(path, encoding='utf-8') as f:
                src = f.read()
            out = fix(src)
            if out == src:
                continue
            refs = len(ATTR_RE.findall(src))
            changed_files += 1
            changed_refs += refs
            if not args.dry_run:
                with open(path, 'w', encoding='utf-8', newline='') as f:
                    f.write(out)
            print('%s %s (%d ref%s)' % ('would fix' if args.dry_run else 'fixed',
                                        os.path.relpath(path, ROOT).replace('\\', '/'),
                                        refs, '' if refs == 1 else 's'))
    print('\n%s: %d files, %d references' %
          ('dry-run' if args.dry_run else 'done', changed_files, changed_refs))


if __name__ == '__main__':
    main()
