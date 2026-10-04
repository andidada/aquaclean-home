#!/usr/bin/env python3
"""Generate the admin login hash stored in admin/login.html.

The page never holds the password itself - only a salted SHA-256 digest -
so re-run this whenever the password changes and paste the result into the
AQC_PASSWORD_HASH constant.

    python scripts/hash_admin_password.py            # prompts (no echo)
    python scripts/hash_admin_password.py --check    # verify against a hash

Keep AQC_ADMIN_SALT in sync with the constant in admin/login.html. If you
change the salt, every existing hash becomes invalid and must be regenerated.
"""
import argparse
import getpass
import hashlib
import sys

# Must match AQC_ADMIN_SALT in admin/login.html.
SALT = "AQC-Admin-Login-v1"


def digest(password: str) -> str:
    return hashlib.sha256((SALT + ":" + password).encode("utf-8")).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", metavar="HASH",
                    help="verify a password against an existing hash")
    args = ap.parse_args()

    password = getpass.getpass("Password: ") if sys.stdin.isatty() \
        else sys.stdin.readline().rstrip("\n")

    if args.check:
        ok = digest(password) == args.check.strip().lower()
        print("MATCH" if ok else "NO MATCH")
        return 0 if ok else 1

    print("hash: " + digest(password))
    print()
    print("Paste it into AQC_PASSWORD_HASH in admin/login.html.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
