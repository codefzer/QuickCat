"""MARC Import Pipeline — ingest → clean → validate → output.

Accepts ISO-2709 binary .mrc files or Excel/CSV spreadsheets.

Usage:
    python3 skills/marc-importer/scripts/import_pipeline.py records.mrc
    python3 skills/marc-importer/scripts/import_pipeline.py acquisitions.xlsx --type ebook
    python3 skills/marc-importer/scripts/import_pipeline.py records.mrc --out ready.mrc
"""

import argparse
import json
import sys
from pathlib import Path

import pymarc

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
import quickcat_loader                    # noqa: F401  – registers shared-resources aliases
quickcat_loader.register_batch_cleaner()  # registers batch_clean on demand (both paths need it)

from skills.batch_cleaner.scripts.batch_clean import clean_record, _load_profile  # noqa: E402
# NOTE: excel_to_marc (and pandas) is imported lazily inside main() — only when the
# input is actually an Excel/CSV file.  See the register_marc_importer() call below.


def _load_validation_rules() -> dict:
    with open(ROOT / "shared-resources" / "references" / "validation-rules.json") as f:
        return json.load(f)


def _validate_record(record: pymarc.Record, rules: dict) -> tuple[str, list[str]]:
    """Validate a record against minimum field requirements.

    Returns (status, issues) where status is 'ok', 'warning', or 'error'.
    """
    issues = []
    required = rules.get("required_fields", {}).get("core_level", {}).get("fields", ["001", "245", "008"])

    for tag in required:
        if not record[tag]:
            issues.append(f"Missing required field: {tag}")

    # Check Leader byte 09 for Unicode
    if record.leader[9] not in ("a", " "):
        issues.append(f"Leader byte 09 unexpected value: {record.leader[9]!r}")

    if not issues:
        return "ok", []
    if "245" in [i.split(": ")[-1] for i in issues]:
        return "error", issues
    return "warning", issues


def main():
    parser = argparse.ArgumentParser(description="QuickCat MARC Import Pipeline")
    parser.add_argument("input_file", help="Input .mrc or .xlsx/.csv file")
    parser.add_argument("--type", dest="material_type", default="book",
                        choices=["book", "ebook", "journal"],
                        help="Material type for Excel imports")
    parser.add_argument("--profile", help="Path to batch-cleaner profile JSON")
    parser.add_argument("--org-code", help="MARC org code for 003 stamping")
    parser.add_argument("--out", help="Output .mrc file path")
    args = parser.parse_args()

    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"ERROR: file not found: {args.input_file}", file=sys.stderr)
        sys.exit(1)

    # Load cleaning profile
    profile = _load_profile(args.profile)
    delete_tags = profile.get("delete_tags", [])
    delete_ranges = profile.get("delete_ranges", [["900", "999"]])
    org_code = args.org_code or profile.get("org_code", "QUICKCAT")

    # Load validation rules
    rules = _load_validation_rules()

    # 1. Parse input
    records = []
    raw_report = []
    suffix = input_path.suffix.lower()

    if suffix in (".xlsx", ".xlsm", ".csv"):
        quickcat_loader.register_marc_importer()  # deferred — pulls pandas only when needed
        from skills.marc_importer.scripts.excel_to_marc import excel_to_records  # noqa: E402
        print(f"[import] Excel/CSV mode: {input_path.name}")
        records, raw_report = excel_to_records(str(input_path), args.material_type)
        print(f"[import] Parsed {len(records)} rows")
    else:
        print(f"[import] ISO-2709 mode: {input_path.name}")
        with open(input_path, "rb") as f:
            reader = pymarc.MARCReader(f, to_unicode=True, force_utf8=True)
            for rec in reader:
                if rec:
                    records.append(rec)
                    raw_report.append({"status": "ok", "warnings": []})
        print(f"[import] Parsed {len(records)} records")

    # 2. Clean + validate
    final_records = []
    report = []
    stats = {"ok": 0, "warning": 0, "error": 0}

    for i, (rec, parse_info) in enumerate(zip(records, raw_report)):
        rec_id = rec["001"].data if rec["001"] else f"row_{i+2}"

        # Clean
        cleaned, _ = clean_record(rec, delete_tags, delete_ranges, org_code)

        # Validate
        status, issues = _validate_record(cleaned, rules)

        # Merge parse warnings
        all_issues = parse_info.get("warnings", []) + issues
        final_status = "error" if status == "error" or parse_info.get("status") == "error" else (
            "warning" if all_issues else "ok"
        )
        stats[final_status] += 1

        report.append({
            "record_id": rec_id,
            "index": i + 1,
            "status": final_status,
            "issues": all_issues,
        })

        if final_status != "error":
            final_records.append(cleaned)

    # 3. Write output
    out_path = Path(args.out) if args.out else input_path.with_stem(
        input_path.stem + "_import_ready"
    ).with_suffix(".mrc")
    report_path = out_path.with_stem(out_path.stem.replace("_import_ready", "") + "_import_report").with_suffix(".json")

    with open(out_path, "wb") as f:
        writer = pymarc.MARCWriter(f)
        for rec in final_records:
            writer.write(rec)
        writer.close()

    with open(report_path, "w") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print(f"\n[import] Results:")
    print(f"  ✅ OK:      {stats['ok']}")
    print(f"  ⚠️  Warning: {stats['warning']}")
    print(f"  ❌ Error:   {stats['error']} (excluded from output)")
    print(f"\n[import] Written: {out_path}  ({len(final_records)} records)")
    print(f"[import] Report:  {report_path}")


if __name__ == "__main__":
    main()
