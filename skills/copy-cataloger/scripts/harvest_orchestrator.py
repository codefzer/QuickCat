"""Harvest Orchestrator — run the full copy-cataloging pipeline.

1. Validation gate (ISBN check-digit, LCCN format, material type)
2. Parallel harvest from all configured sources
3. Consensus check (audit_consensus)
4. Tie-breaker for Red conflicts
5. Merge and output

Usage:
    python3 skills/copy-cataloger/scripts/harvest_orchestrator.py --isbn 9780743273565
    python3 skills/copy-cataloger/scripts/harvest_orchestrator.py --lccn n78890335 --sources loc,nls
    python3 skills/copy-cataloger/scripts/harvest_orchestrator.py --isbn 9780743273565 --out merged.mrc
"""

import argparse
import asyncio
import json
import sys
import unicodedata
from io import BytesIO
from pathlib import Path

import pymarc

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from skills.copy_cataloger.scripts.validation_gate import validate_isbn13, validate_lccn, detect_material_type  # noqa: E402
from skills.copy_cataloger.scripts.harvest_metadata import harvest_metadata  # noqa: E402
from skills.copy_cataloger.scripts.audit_consensus import audit_consensus, print_dashboard, _parse_marcxml_string  # noqa: E402
from skills.copy_cataloger.scripts.resolve_tie_breaker import resolve_tie_breaker  # noqa: E402
from shared_resources.scripts.transaction_log import log_edit  # noqa: E402


def _load_config() -> dict:
    with open(ROOT / "config.json") as f:
        return json.load(f)


def _apply_merge(
    base_record: pymarc.Record,
    reference_record: pymarc.Record,
    conflicts: list[dict],
) -> tuple[pymarc.Record, list[str]]:
    """Apply consensus decisions to base_record.

    Returns the merged record and a list of change descriptions.
    """
    changes = []
    for c in conflicts:
        tag = c["tag"]
        status = c["status"]

        if status == "green":
            # Auto-merge: add missing field from reference
            if c["local_value"] is None:
                for rf in reference_record.get_fields(tag):
                    base_record.add_field(rf)
                    changes.append(f"{tag} added from reference (auto-merge)")

        elif status in ("yellow", "red"):
            # For yellow: accept reference by default (cataloger can override)
            ref_fields = reference_record.get_fields(tag)
            if ref_fields and c.get("recommendation") != "keep_local":
                # Remove local, add reference
                for lf in base_record.get_fields(tag):
                    base_record.remove_field(lf)
                for rf in ref_fields:
                    base_record.add_field(rf)
                changes.append(f"{tag} updated from reference ({status})")

    return base_record, changes


async def orchestrate(
    identifier: str,
    sources: list[str],
    output_path: str | None = None,
) -> dict:
    """Run the full harvest pipeline.

    Returns summary dict with keys: status, merged_path, conflicts, changes.
    """
    cfg = _load_config()

    # 1. Validation gate
    import re
    if re.match(r"^[\d\-X]+$", identifier):
        ok, msg = validate_isbn13(identifier)
        if not ok:
            return {"status": "error", "message": f"Validation failed: {msg}"}
    else:
        ok, msg = validate_lccn(identifier)
        if not ok:
            return {"status": "error", "message": f"Validation failed: {msg}"}

    material_type = detect_material_type(identifier)
    print(f"[orchestrator] Identifier: {identifier!r}  Material type: {material_type}")

    # 2. Parallel harvest
    if not sources:
        sources = list(cfg["servers"].keys())

    print(f"[orchestrator] Harvesting from: {sources}")
    tasks = [harvest_metadata(identifier, src) for src in sources]
    results = await asyncio.gather(*tasks)

    records = []
    for src, xml in zip(sources, results):
        if xml.startswith("Record Not Found") or xml.startswith("Protocol") or xml.startswith("Authentication"):
            print(f"[orchestrator]   {src}: {xml}")
        else:
            rec = _parse_marcxml_string(xml)
            if rec:
                records.append((src, rec))
                print(f"[orchestrator]   {src}: record found")

    if not records:
        return {"status": "error", "message": "No records found from any source"}

    # Use first record as base; merge subsequent records
    _, base = records[0]
    all_conflicts = []

    for src, ref_rec in records[1:]:
        print(f"[orchestrator] Comparing with {src}...")
        conflicts = audit_consensus(base, ref_rec)
        print_dashboard(conflicts)
        all_conflicts.extend(conflicts)

        # Resolve Red conflicts via tie-breaker
        red = [c for c in conflicts if c["status"] == "red"]
        if red:
            print(f"[orchestrator] {len(red)} Red conflict(s) — invoking tie-breaker")
            tb_result = await resolve_tie_breaker(red, identifier)
            # Apply tie-breaker resolutions
            for resolution in tb_result.get("resolved", []):
                for c in conflicts:
                    if c["tag"] == resolution["tag"]:
                        if resolution["source"] == "local":
                            c["recommendation"] = "keep_local"

        record_before = pymarc.Record()
        record_before.leader = base.leader
        for f in base.fields:
            record_before.add_field(f)

        base, changes = _apply_merge(base, ref_rec, conflicts)

        log_edit(
            skill_name="copy-cataloger",
            record_before=record_before,
            record_after=base,
            mrc_path=output_path or ".",
            changes=changes,
        )

    # Write output
    out_path = Path(output_path) if output_path else Path(f"merged_{identifier.replace('-','')}.mrc")
    with open(out_path, "wb") as f:
        writer = pymarc.MARCWriter(f)
        writer.write(base)
        writer.close()

    conflict_path = out_path.parent / (out_path.stem + "_conflicts.json")
    with open(conflict_path, "w") as f:
        json.dump(all_conflicts, f, ensure_ascii=False, indent=2)

    print(f"\n[orchestrator] Output: {out_path}")
    print(f"[orchestrator] Conflict report: {conflict_path}")

    return {
        "status": "ok",
        "merged_path": str(out_path),
        "conflict_report": str(conflict_path),
        "sources_used": [s for s, _ in records],
        "total_conflicts": len(all_conflicts),
    }


def main():
    parser = argparse.ArgumentParser(description="QuickCat Harvest Orchestrator")
    parser.add_argument("--isbn", help="ISBN-10 or ISBN-13")
    parser.add_argument("--lccn", help="Library of Congress Control Number")
    parser.add_argument("--sources", help="Comma-separated source keys (default: all configured)")
    parser.add_argument("--out", help="Output .mrc file path")
    args = parser.parse_args()

    identifier = args.isbn or args.lccn
    if not identifier:
        print("ERROR: provide --isbn or --lccn", file=sys.stderr)
        sys.exit(1)

    sources = [s.strip() for s in args.sources.split(",")] if args.sources else []
    result = asyncio.run(orchestrate(identifier, sources, args.out))
    print(json.dumps(result, ensure_ascii=False, indent=2))

    if result["status"] != "ok":
        sys.exit(1)


if __name__ == "__main__":
    main()
