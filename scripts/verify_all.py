#!/usr/bin/env python3
"""Run every site-integrity check in one pass and print a single verdict.

Each check is a standalone script under scripts/. This driver only orchestrates
them, parses their exit codes, and summarises the result so a full regression is
one command instead of eight.

Usage:
    python scripts/verify_all.py          # run everything
    python scripts/verify_all.py --fix    # run fixers first, then verify
"""
import argparse
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable

# (script, one-line description). Order matters only for readability.
CHECKS = [
    ('fix_hreflang.py',        'hreflang cluster correctness'),
    ('check_og_meta.py',       'Open Graph / Twitter card structure'),
    ('audit_links.py',         'static link + asset reachability'),
    ('audit_images.py',        'rendering-level image resolution'),
    ('check_product_imgs.py',  'product data image references'),
    ('check_dynamic_imgs.py',  'JS-injected image references'),
    ('check_i18n_leftovers.py','untranslated English leftovers'),
]

# Run before the checks when --fix is passed.
FIXERS = [
    ('fix_og_meta.py',     'normalise OG meta across all pages'),
    ('gen_sitemap.py',     'rebuild sitemap.xml'),
]

# gen_sitemap --check is a verification, not a fix
POST = [
    (['gen_sitemap.py', '--check'], 'sitemap drift'),
]


def run(script, args=()):
    cmd = [PY, os.path.join(ROOT, 'scripts', script), *args]
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return p.returncode, (p.stdout or '') + (p.stderr or '')


def summarise(out, limit=4):
    lines = [l.rstrip() for l in out.splitlines() if l.strip()]
    return lines[-limit:]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--fix', action='store_true', help='run fixers before checks')
    args = ap.parse_args()

    failures = []

    if args.fix:
        print('=== FIXERS ===')
        for script, desc in FIXERS:
            rc, out = run(script)
            print(f'[{"ok" if rc == 0 else "??"}] {script} - {desc}')
            for l in summarise(out, 2):
                print('        ', l)
        print()

    print('=== CHECKS ===')
    for script, desc in CHECKS:
        rc, out = run(script)
        mark = 'PASS' if rc == 0 else 'FAIL'
        print(f'[{mark}] {script:26s} {desc}')
        for l in summarise(out):
            print('        ', l)
        if rc != 0:
            failures.append(script)
    print()

    print('=== POST ===')
    for argv, desc in POST:
        rc, out = run(argv[0], argv[1:])
        mark = 'PASS' if rc == 0 else 'FAIL'
        print(f'[{mark}] {" ".join(argv):26s} {desc}')
        for l in summarise(out, 2):
            print('        ', l)
        if rc != 0:
            failures.append(' '.join(argv))

    print()
    if failures:
        print('VERDICT: FAIL ->', ', '.join(failures))
        return 1
    print('VERDICT: ALL CHECKS PASSED')
    return 0


if __name__ == '__main__':
    sys.exit(main())
