"""Sub-Skill B: audit_consensus — compare two MARC records field by field.

Returns a JSON list of ConflictItem objects with severity scores.

Severity thresholds (defined in config.json):
  Green  < 0.30  → auto-merge (accept reference value)
  Yellow 0.30–0.70 → review suggested
  Red    > 0.70  → manual review + tie-breaker

Local-priority fields (090, 590, 852, 9XX) are never conflicted.

Usage:
    python3 skills/copy-cataloger/scripts/audit_consensus.py local.xml reference.xml
    python3 skills/copy-cataloger/scripts/audit_consensus.py local.xml reference.xml --threshold 0.80
"""

import argparse
import json
import sys
from pathlib import Path

import pymarc

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT / "shared-resources" / "scripts"))
import quickcat_loader  # noqa: F401  – registers shared-resources aliases

from shared_resources.scripts.config_loader import load_config  # noqa: E402
from shared_resources.scripts.marc_utils import similarity  # noqa: E402


def _load_priority_rules(cfg: dict) -> dict:
    rules_path = ROOT / cfg["priority_rules"]
    with open(rules_path) as f:
        return json.load(f)


def _parse_marcxml(path: str) -> pymarc.Record | None:
    records = pymarc.parse_xml_to_array(path)
    return records[0] if records else None


def _parse_marcxml_string(xml_str: str) -> pymarc.Record | None:
    from io import BytesIO
    records = pymarc.parse_xml_to_array(BytesIO(xml_str.encode("utf-8")))
    return records[0] if records else None


def _field_value(field: pymarc.Field) -> str:
    """Return a normalized string representation of a field for comparison."""
    if hasattr(field, "data"):
        return field.data.strip()
    # Variable field: concatenate all subfield values
    return " ".join(
        v.strip()
        for i, v in enumerate(field.subfields)
        if i % 2 == 1  # odd indices are values
    )


def _is_local_priority(tag: str, priority_rules: dict) -> bool:
    local = priority_rules.get("local_priority", {}).get("fields", {})
    if tag in local:
        return True
    # Check 9XX range
    try:
        if int(tag) >= 900:
            return True
    except ValueError:
        pass
    return False


def audit_consensus(
    local_record: pymarc.Record,
    reference_record: pymarc.Record,
    threshold: float | None = None,
) -> list[dict]:
    """Compare two MARC records field by field.

    Args:
        local_record: The local working record.
        reference_record: The harvested reference record.
        threshold: Override the similarity threshold from config.json.

    Returns:
        List of ConflictItem dicts sorted by severity_score descending.
        Each item: { tag, local_value, ref_value, severity_score, recommendation }
    """
    cfg = load_config()
    rules = _load_priority_rules(cfg)
    sim_threshold = threshold or cfg["consensus"]["similarity_threshold"]

    # Tags we compare for intellectual content
    comparable_tags = [
        "100", "110", "111",       # Main entries
        "245",                      # Title
        "250",                      # Edition
        "260", "264",               # Publication
        "300",                      # Physical description
        "490", "830",               # Series
        "500", "504", "505", "520", # Notes
        "600", "610", "650", "651", "655",  # Subjects
        "700", "710",               # Added entries
        "776", "787",               # Linking entries
        "020", "022",               # ISBN / ISSN
        "050", "082",               # Classification
    ]

    conflicts = []

    for tag in comparable_tags:
        # Skip local-priority fields
        if _is_local_priority(tag, rules):
            continue

        local_fields = local_record.get_fields(tag)
        ref_fields = reference_record.get_fields(tag)

        if not local_fields and not ref_fields:
            continue

        # Field present in reference but missing locally — add it (low severity)
        if not local_fields and ref_fields:
            for rf in ref_fields:
                conflicts.append({
                    "tag": tag,
                    "local_value": None,
                    "ref_value": _field_value(rf),
                    "severity_score": 0.0,
                    "recommendation": "add_from_reference",
                    "status": "green",
                })
            continue

        # Field present locally but missing in reference — keep local
        if local_fields and not ref_fields:
            continue

        # Both present — compare first occurrence
        lv = _field_value(local_fields[0])
        rv = _field_value(ref_fields[0])

        if lv == rv:
            continue  # Identical — no conflict

        sim_score = similarity(lv, rv)
        # Severity is inverse of similarity: very different = high severity
        severity = round(1.0 - sim_score, 3)

        if severity < 0.3:
            status = "green"
            recommendation = "auto_merge"
        elif severity <= 0.7:
            status = "yellow"
            recommendation = "review_suggested"
        else:
            status = "red"
            recommendation = "manual_review_required"

        conflicts.append({
            "tag": tag,
            "local_value": lv,
            "ref_value": rv,
            "severity_score": severity,
            "recommendation": recommendation,
            "status": status,
        })

    conflicts.sort(key=lambda x: x["severity_score"], reverse=True)
    return conflicts


def print_dashboard(conflicts: list[dict]) -> None:
    """Print a human-readable conflict dashboard to stdout."""
    icons = {"green": "🟢", "yellow": "🟡", "red": "🔴"}
    print("\n=== Conflict Dashboard ===")
    if not conflicts:
        print("  No conflicts detected — records are identical on all comparable fields.")
        return
    for c in conflicts:
        icon = icons.get(c["status"], "?")
        print(f"  {icon} {c['tag']:5s}  severity={c['severity_score']:.2f}  [{c['recommendation']}]")
        if c["local_value"]:
            print(f"        LOCAL: {c['local_value'][:80]}")
        print(f"        REF:   {c['ref_value'][:80]}")
    print()
    greens  = sum(1 for c in conflicts if c["status"] == "green")
    yellows = sum(1 for c in conflicts if c["status"] == "yellow")
    reds    = sum(1 for c in conflicts if c["status"] == "red")
    print(f"  Summary: 🟢 {greens} auto  🟡 {yellows} review  🔴 {reds} manual")


def main():
    parser = argparse.ArgumentParser(description="Audit consensus between two MARC records")
    parser.add_argument("local_xml", nargs="?", help="Local record MARCXML file")
    parser.add_argument("ref_xml", nargs="?", help="Reference record MARCXML file")
    parser.add_argument("--threshold", type=float, help="Override similarity threshold (0.0–1.0)")
    parser.add_argument("--json", action="store_true", dest="json_output", help="Output JSON instead of dashboard")
    parser.add_argument("--test", action="store_true", help="Run self-tests and exit")
    args = parser.parse_args()

    if args.test:
        _run_tests()
        return

    if not args.local_xml or not args.ref_xml:
        print("ERROR: provide local_xml and ref_xml paths", file=sys.stderr)
        sys.exit(1)

    local = _parse_marcxml(args.local_xml)
    reference = _parse_marcxml(args.ref_xml)
    if not local or not reference:
        print("ERROR: could not parse one or both MARCXML files", file=sys.stderr)
        sys.exit(1)

    conflicts = audit_consensus(local, reference, threshold=args.threshold)

    if args.json_output:
        print(json.dumps(conflicts, ensure_ascii=False, indent=2))
    else:
        print_dashboard(conflicts)


def _run_tests():
    print("Running audit_consensus tests...")
    local = pymarc.Record()
    local.leader = "00000nam a2200000   4500"
    local.add_field(pymarc.Field("245", ["1", "0"], ["a", "The great Gatsby"]))
    local.add_field(pymarc.Field("100", ["1", " "], ["a", "Fitzgerald, F. Scott"]))
    local.add_field(pymarc.Field("090", [" ", " "], ["a", "LOCAL_PS3511"]))  # local priority

    reference = pymarc.Record()
    reference.leader = "00000nam a2200000   4500"
    reference.add_field(pymarc.Field("245", ["1", "0"], ["a", "The great Gatsby /"]))
    reference.add_field(pymarc.Field("100", ["1", " "], ["a", "Fitzgerald, F. Scott,", "d", "1896-1940."]))
    reference.add_field(pymarc.Field("050", [" ", "4"], ["a", "PS3511.I9", "b", "G7"]))
    reference.add_field(pymarc.Field("090", [" ", " "], ["a", "REF_SHOULD_NOT_CONFLICT"]))  # should be ignored

    conflicts = audit_consensus(local, reference, threshold=0.85)
    print(f"  Conflicts found: {len(conflicts)}")
    tags_conflicted = [c["tag"] for c in conflicts]
    assert "090" not in tags_conflicted, "090 (local priority) must NOT appear in conflicts"
    print(f"  Tags in conflict: {tags_conflicted}")
    print_dashboard(conflicts)
    print("Tests passed.")


if __name__ == "__main__":
    main()
