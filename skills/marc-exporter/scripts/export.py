"""MARC Exporter — validate and export records to ISO-2709 with productivity metrics.

Usage:
    python3 skills/marc-exporter/scripts/export.py records.mrc
    python3 skills/marc-exporter/scripts/export.py records.mrc --out export.mrc --report metrics.json
"""

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import pymarc

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))


def _load_validation_rules() -> dict:
    with open(ROOT / "shared-resources" / "references" / "validation-rules.json") as f:
        return json.load(f)


def _is_ai_tagged(record: pymarc.Record) -> tuple[bool, dict[str, int]]:
    """Return True and a tag→count dict if any field has $9 AI_QUICKCAT."""
    found = defaultdict(int)
    for field in record.fields:
        if hasattr(field, "subfields"):
            subs = field.subfields
            for i in range(0, len(subs) - 1, 2):
                if subs[i] == "9" and "AI_QUICKCAT" in (subs[i + 1] or ""):
                    found[field.tag] += 1
    return bool(found), dict(found)


def _is_copy_cataloged(record: pymarc.Record) -> bool:
    """True if the record has a 035 (system control number from external utility)."""
    return bool(record["035"])


def _validate(record: pymarc.Record, rules: dict) -> tuple[bool, list[str]]:
    """Return (is_valid, issues). Records missing 245 are invalid."""
    issues = []
    for tag in ["001", "245"]:
        if not record[tag]:
            issues.append(f"Missing {tag}")
    return len(issues) == 0, issues


def main():
    parser = argparse.ArgumentParser(description="Export validated MARC records to ISO-2709")
    parser.add_argument("mrc_file", nargs="?", help="Input .mrc file")
    parser.add_argument("--out", help="Output .mrc file path")
    parser.add_argument("--report", help="Output metrics JSON file path")
    args = parser.parse_args()

    if not args.mrc_file:
        print("ERROR: provide mrc_file", file=sys.stderr)
        sys.exit(1)

    rules = _load_validation_rules()

    records = []
    with open(args.mrc_file, "rb") as f:
        reader = pymarc.MARCReader(f, to_unicode=True, force_utf8=True)
        for rec in reader:
            if rec:
                records.append(rec)

    print(f"[exporter] Loaded {len(records)} records")

    metrics = {
        "total_records": len(records),
        "exported": 0,
        "skipped_invalid": 0,
        "original_cataloging": 0,
        "copy_cataloging": 0,
        "ai_enhanced_records": 0,
        "ai_tagged_fields": defaultdict(int),
        "invalid_records": [],
    }

    export_records = []

    for rec in records:
        valid, issues = _validate(rec, rules)
        if not valid:
            rec_id = rec["001"].data if rec["001"] else "unknown"
            metrics["skipped_invalid"] += 1
            metrics["invalid_records"].append({"record_id": rec_id, "issues": issues})
            print(f"  [SKIP] {rec_id}: {', '.join(issues)}")
            continue

        # Categorize
        if _is_copy_cataloged(rec):
            metrics["copy_cataloging"] += 1
        else:
            metrics["original_cataloging"] += 1

        is_ai, ai_tags = _is_ai_tagged(rec)
        if is_ai:
            metrics["ai_enhanced_records"] += 1
            for tag, count in ai_tags.items():
                metrics["ai_tagged_fields"][tag] += count

        export_records.append(rec)
        metrics["exported"] += 1

    # Write .mrc
    out_path = Path(args.out) if args.out else Path(args.mrc_file).with_stem(
        Path(args.mrc_file).stem + "_export"
    )
    with open(out_path, "wb") as f:
        writer = pymarc.MARCWriter(f)
        for rec in export_records:
            writer.write(rec)
        writer.close()

    # Write metrics
    metrics["ai_tagged_fields"] = dict(metrics["ai_tagged_fields"])
    report_path = Path(args.report) if args.report else out_path.with_suffix(".json").with_stem(
        out_path.stem + "_metrics"
    )
    with open(report_path, "w") as f:
        json.dump(metrics, f, ensure_ascii=False, indent=2)

    # Print summary
    print(f"\n[exporter] Export Summary:")
    print(f"  Total records:        {metrics['total_records']}")
    print(f"  Exported:             {metrics['exported']}")
    print(f"  Skipped (invalid):    {metrics['skipped_invalid']}")
    print(f"  Original cataloging:  {metrics['original_cataloging']}")
    print(f"  Copy cataloging:      {metrics['copy_cataloging']}")
    print(f"  AI-enhanced records:  {metrics['ai_enhanced_records']}")
    if metrics["ai_tagged_fields"]:
        ai_summary = ", ".join(f"{t}×{c}" for t, c in sorted(metrics["ai_tagged_fields"].items()))
        print(f"  AI-tagged fields:     {ai_summary}")
    print(f"\n  Written: {out_path}")
    print(f"  Metrics: {report_path}")


if __name__ == "__main__":
    main()
