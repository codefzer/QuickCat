"""Batch Cleaner — profile-driven MARC record sanitation.

Deletes unwanted tags, normalizes Unicode to NFC, sets Leader byte 09='a',
and stamps 003 with local MARC org code.

Usage:
    python3 skills/batch-cleaner/scripts/batch_clean.py input.mrc
    python3 skills/batch-cleaner/scripts/batch_clean.py input.mrc --profile assets/default-profile.json
    python3 skills/batch-cleaner/scripts/batch_clean.py input.mrc --org-code MYLIB --out clean.mrc
    python3 skills/batch-cleaner/scripts/batch_clean.py input.mrc --test
"""

import argparse
import json
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

import pymarc

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
import quickcat_loader          # noqa: F401  – registers cross-package import aliases

from shared_resources.scripts.transaction_log import log_edit  # noqa: E402


DEFAULT_PROFILE_PATH = Path(__file__).parent.parent / "assets" / "default-profile.json"


def _load_profile(path: str | None) -> dict:
    p = Path(path) if path else DEFAULT_PROFILE_PATH
    with open(p) as f:
        return json.load(f)


def _should_delete(tag: str, delete_tags: list[str], delete_ranges: list[list[str]]) -> bool:
    if tag in delete_tags:
        return True
    try:
        tag_int = int(tag)
        for start, end in delete_ranges:
            if int(start) <= tag_int <= int(end):
                return True
    except ValueError:
        pass
    return False


def _normalize_field(field: pymarc.Field) -> int:
    """Apply NFC normalization to all subfield values. Returns count of normalized values."""
    count = 0
    if hasattr(field, "data"):
        normalized = unicodedata.normalize("NFC", field.data)
        if normalized != field.data:
            field.data = normalized
            count += 1
    elif hasattr(field, "subfields"):
        for i in range(1, len(field.subfields), 2):
            normalized = unicodedata.normalize("NFC", field.subfields[i])
            if normalized != field.subfields[i]:
                field.subfields[i] = normalized
                count += 1
    return count


def clean_record(
    record: pymarc.Record,
    delete_tags: list[str],
    delete_ranges: list[list[str]],
    org_code: str,
) -> tuple[pymarc.Record, dict]:
    """Apply cleaning operations to a single record.

    Returns the cleaned record and a stats dict.
    """
    stats = {
        "fields_deleted": 0,
        "tags_deleted": defaultdict(int),
        "unicode_fixes": 0,
        "leader_fixed": False,
    }

    # 1. Delete tags
    to_remove = [
        f for f in record.fields
        if _should_delete(f.tag, delete_tags, delete_ranges)
    ]
    for field in to_remove:
        stats["fields_deleted"] += 1
        stats["tags_deleted"][field.tag] += 1
        record.remove_field(field)

    # 2. Unicode NFC normalization
    for field in record.fields:
        stats["unicode_fixes"] += _normalize_field(field)

    # 3. Leader byte 09 — Unicode flag
    leader = list(record.leader)
    if leader[9] != "a":
        leader[9] = "a"
        record.leader = "".join(leader)
        stats["leader_fixed"] = True

    # 4. Stamp 003
    existing_003 = record["003"]
    if existing_003:
        record.remove_field(existing_003)
    record.add_ordered_field(pymarc.Field(tag="003", data=org_code))

    return record, stats


def main():
    parser = argparse.ArgumentParser(description="Profile-driven MARC batch cleaner")
    parser.add_argument("mrc_file", nargs="?", help="Input .mrc binary file")
    parser.add_argument("--profile", help="Path to profile JSON file")
    parser.add_argument("--org-code", help="MARC org code to stamp in 003 (overrides profile)")
    parser.add_argument("--out", help="Output .mrc file path")
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    args = parser.parse_args()

    if args.test:
        _run_tests()
        return

    if not args.mrc_file:
        print("ERROR: provide mrc_file", file=sys.stderr)
        sys.exit(1)

    profile = _load_profile(args.profile)
    delete_tags = profile.get("delete_tags", [])
    delete_ranges = profile.get("delete_ranges", [["900", "999"]])
    org_code = args.org_code or profile.get("org_code", "QUICKCAT")

    print(f"[batch_cleaner] Profile: delete {len(delete_tags)} specific tags + {len(delete_ranges)} range(s)")
    print(f"[batch_cleaner] Org code: {org_code!r}")

    total_stats = {
        "processed": 0,
        "fields_deleted": 0,
        "tags_deleted": defaultdict(int),
        "unicode_fixes": 0,
        "leader_fixed": 0,
    }

    out_path = Path(args.out) if args.out else Path(args.mrc_file).with_stem(
        Path(args.mrc_file).stem + "_cleaned"
    )

    cleaned_records = []
    with open(args.mrc_file, "rb") as f:
        reader = pymarc.MARCReader(f, to_unicode=True, force_utf8=True)
        for rec in reader:
            if not rec:
                continue

            before = pymarc.Record()
            before.leader = rec.leader
            for field in rec.fields:
                before.add_field(field)

            cleaned, stats = clean_record(rec, delete_tags, delete_ranges, org_code)
            total_stats["processed"] += 1
            total_stats["fields_deleted"] += stats["fields_deleted"]
            for tag, count in stats["tags_deleted"].items():
                total_stats["tags_deleted"][tag] += count
            total_stats["unicode_fixes"] += stats["unicode_fixes"]
            if stats["leader_fixed"]:
                total_stats["leader_fixed"] += 1

            changes = []
            if stats["fields_deleted"]:
                changes.append(f"Deleted {stats['fields_deleted']} fields: {dict(stats['tags_deleted'])}")
            if stats["unicode_fixes"]:
                changes.append(f"NFC normalized {stats['unicode_fixes']} subfields")
            if stats["leader_fixed"]:
                changes.append("Leader byte 09 set to 'a' (Unicode)")
            changes.append(f"003 stamped: {org_code}")

            log_edit("batch-cleaner", before, cleaned, str(out_path), changes)
            cleaned_records.append(cleaned)

    with open(out_path, "wb") as f:
        writer = pymarc.MARCWriter(f)
        for rec in cleaned_records:
            writer.write(rec)
        writer.close()

    # Print summary
    print(f"\n[batch_cleaner] Processed:      {total_stats['processed']} records")
    print(f"[batch_cleaner] Fields deleted:  {total_stats['fields_deleted']}")
    if total_stats["tags_deleted"]:
        tag_summary = ", ".join(f"{t}×{c}" for t, c in sorted(total_stats["tags_deleted"].items()))
        print(f"[batch_cleaner] By tag:          {tag_summary}")
    print(f"[batch_cleaner] Unicode fixes:   {total_stats['unicode_fixes']} subfields")
    print(f"[batch_cleaner] Leader fixed:    {total_stats['leader_fixed']} records")
    print(f"[batch_cleaner] Written:         {out_path}")


def _run_tests():
    print("Running batch_cleaner tests...")

    record = pymarc.Record()
    record.leader = "00000nam a2200000   4500"
    record.leader = list(record.leader)
    record.leader[9] = " "  # Unicode NOT set
    record.leader = "".join(record.leader)

    record.add_field(pymarc.Field("001", data="test001"))
    record.add_field(pymarc.Field("245", ["1", "0"], ["a", "Test title"]))
    record.add_field(pymarc.Field("035", [" ", " "], ["a", "(OCoLC)12345"]))  # should be deleted
    record.add_field(pymarc.Field("938", [" ", " "], ["a", "vendor data"]))  # 9XX — should be deleted
    record.add_field(pymarc.Field("003", data="OLD_ORG"))  # should be replaced

    # Add a field with combining character (not NFC)
    nfd_value = unicodedata.normalize("NFD", "caf\u00e9")  # caf + combining accent
    record.add_field(pymarc.Field("500", [" ", " "], ["a", nfd_value]))

    cleaned, stats = clean_record(
        record,
        delete_tags=["019", "035", "938"],
        delete_ranges=[["900", "999"]],
        org_code="TESTLIB",
    )

    tests = [
        ("035 deleted", record["035"] is None),
        ("938 deleted", record["938"] is None),
        ("003 stamped", cleaned["003"].data == "TESTLIB"),
        ("leader byte 09 = 'a'", cleaned.leader[9] == "a"),
        ("unicode normalized", cleaned["500"]["a"] == unicodedata.normalize("NFC", nfd_value)),
        ("245 preserved", cleaned["245"]["a"] == "Test title"),
    ]
    passed = 0
    for name, result in tests:
        status = "PASS" if result else "FAIL"
        print(f"  [{status}] {name}")
        if result:
            passed += 1
    print(f"\n{passed}/{len(tests)} tests passed")
    if passed != len(tests):
        sys.exit(1)


if __name__ == "__main__":
    main()
