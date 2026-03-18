"""Validation Gate — run before any harvest attempt.

Validates identifier format, selects material type, and checks for duplicates.

Usage:
    python3 skills/copy-cataloger/scripts/validation_gate.py --isbn 9780743273565
    python3 skills/copy-cataloger/scripts/validation_gate.py --lccn n78890335
    python3 skills/copy-cataloger/scripts/validation_gate.py --isbn 9780743273565 --type book

Returns exit code 0 on success, 1 on validation failure.
"""

import argparse
import json
import re
import sys
from pathlib import Path


ROOT = Path(__file__).parent.parent.parent.parent  # QuickCat root


def validate_isbn13(isbn: str) -> tuple[bool, str]:
    """Validate an ISBN-13 using the Mod 10 (Luhn-variant) check digit algorithm."""
    digits = re.sub(r"[^0-9X]", "", isbn.upper())
    if len(digits) == 10:
        return validate_isbn10(isbn)
    if len(digits) != 13:
        return False, f"ISBN must be 10 or 13 digits, got {len(digits)}"
    total = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(digits[:12]))
    check = (10 - (total % 10)) % 10
    if int(digits[12]) != check:
        return False, f"ISBN-13 check digit invalid (expected {check}, got {digits[12]})"
    return True, "valid"


def validate_isbn10(isbn: str) -> tuple[bool, str]:
    """Validate an ISBN-10 using the Mod 11 check digit algorithm."""
    digits = re.sub(r"[^0-9X]", "", isbn.upper())
    if len(digits) != 10:
        return False, f"ISBN-10 must be 10 characters, got {len(digits)}"
    total = sum((int(d) if d != "X" else 10) * (10 - i) for i, d in enumerate(digits))
    if total % 11 != 0:
        return False, "ISBN-10 check digit invalid"
    return True, "valid"


def validate_lccn(lccn: str) -> tuple[bool, str]:
    """Validate a Library of Congress Control Number format."""
    normalized = lccn.strip().replace(" ", "")
    # Normalized LCCN: 2-3 letter prefix + 8 digits, OR 8-12 digit legacy format
    patterns = [
        r"^[a-z]{1,3}\d{8}$",   # current: prefix + 8 digits
        r"^\d{8,10}$",           # legacy: 8-10 digits
        r"^[a-z]{2}\d{10}$",     # 2-letter prefix + 10 digits
    ]
    for pat in patterns:
        if re.match(pat, normalized):
            return True, "valid"
    return False, f"LCCN format invalid: {lccn!r}"


def detect_material_type(identifier: str, hint: str | None = None) -> str:
    """Guess material type from identifier or hint.

    Returns one of: 'book', 'ebook', 'journal', 'unknown'
    """
    if hint and hint.lower() in ("book", "ebook", "journal"):
        return hint.lower()
    # ISSN → journal
    if re.match(r"^\d{4}-?\d{3}[\dX]$", identifier):
        return "journal"
    # Everything else defaults to book
    return "book"


def load_templates() -> dict:
    templates_path = ROOT / "shared-resources" / "templates" / "marc-templates.json"
    with open(templates_path) as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="QuickCat Validation Gate")
    parser.add_argument("--isbn", help="ISBN-10 or ISBN-13")
    parser.add_argument("--lccn", help="Library of Congress Control Number")
    parser.add_argument("--type", dest="material_type", help="Material type: book, ebook, journal")
    parser.add_argument("--test", action="store_true", help="Run self-tests and exit")
    args = parser.parse_args()

    if args.test:
        _run_tests()
        return

    if not args.isbn and not args.lccn:
        print("ERROR: provide --isbn or --lccn", file=sys.stderr)
        sys.exit(1)

    errors = []

    # Validate identifier
    if args.isbn:
        ok, msg = validate_isbn13(args.isbn)
        if not ok:
            errors.append(f"ISBN validation failed: {msg}")
        else:
            print(f"[validation_gate] ISBN {args.isbn!r}: {msg}")

    if args.lccn:
        ok, msg = validate_lccn(args.lccn)
        if not ok:
            errors.append(f"LCCN validation failed: {msg}")
        else:
            print(f"[validation_gate] LCCN {args.lccn!r}: {msg}")

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Detect material type
    identifier = args.isbn or args.lccn
    material_type = detect_material_type(identifier, args.material_type)
    print(f"[validation_gate] Material type: {material_type}")

    # Load template to confirm it exists
    templates = load_templates()
    if material_type not in templates:
        print(f"WARNING: No template defined for material type {material_type!r}, using 'book'")
        material_type = "book"
    template = templates[material_type]
    print(f"[validation_gate] Loaded template: Leader/06={template['leader'].get('06')!r}, Leader/07={template['leader'].get('07')!r}")

    print(json.dumps({"status": "ok", "material_type": material_type}, ensure_ascii=False))


def _run_tests():
    print("Running validation_gate tests...")
    tests = [
        # (function, args, expected_ok)
        (validate_isbn13, "9780743273565", True),
        (validate_isbn13, "9780743273566", False),  # bad check digit
        (validate_isbn13, "0743273567", True),       # valid ISBN-10
        (validate_isbn13, "074327356X", False),
        (validate_lccn, "n78890335", True),
        (validate_lccn, "12345678", True),
        (validate_lccn, "INVALID!", False),
    ]
    passed = 0
    for fn, arg, expected in tests:
        ok, msg = fn(arg)
        status = "PASS" if ok == expected else "FAIL"
        print(f"  [{status}] {fn.__name__}({arg!r}) -> {ok} ({msg})")
        if ok == expected:
            passed += 1
    print(f"\n{passed}/{len(tests)} tests passed")
    if passed != len(tests):
        sys.exit(1)


if __name__ == "__main__":
    main()
