"""Sub-Skill C: resolve_tie_breaker — invoke a third 'juror' library for Red conflicts.

Only called when audit_consensus returns severity_score > 0.70 on any field.
Decoupled from harvest_metadata to prevent unnecessary network traffic.

Usage:
    python3 skills/copy-cataloger/scripts/resolve_tie_breaker.py \
        --conflicts conflicts.json --isbn 9780743273565
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
import quickcat_loader                      # noqa: F401  – registers shared-resources aliases
quickcat_loader.register_copy_cataloger()   # registers harvest_metadata + audit_consensus

from skills.copy_cataloger.scripts.harvest_metadata import harvest_metadata  # noqa: E402
from skills.copy_cataloger.scripts.audit_consensus import _parse_marcxml_string  # noqa: E402


def _load_config() -> dict:
    with open(ROOT / "config.json") as f:
        return json.load(f)


async def resolve_tie_breaker(
    conflict_items: list[dict],
    identifier: str,
) -> dict:
    """Fetch a third MARCXML record from the juror library to break high-severity conflicts.

    Args:
        conflict_items: List of ConflictItem dicts from audit_consensus (Red status).
        identifier: ISBN or LCCN used to fetch the tie-breaker record.

    Returns:
        dict with keys:
          - 'juror_marcxml': MARCXML string (or error string)
          - 'resolved': list of { tag, winning_value, source } for resolved conflicts
          - 'unresolved': list of tags still needing manual review
    """
    cfg = _load_config()
    juror_key = cfg["consensus"]["tie_breaker_server"]

    print(f"[tie_breaker] Fetching from juror source: {juror_key!r}")
    juror_xml = await harvest_metadata(identifier, juror_key)

    if juror_xml.startswith("Record Not Found") or juror_xml.startswith("Protocol") or juror_xml.startswith("Authentication"):
        print(f"[tie_breaker] Juror returned: {juror_xml}", file=sys.stderr)
        return {
            "juror_marcxml": juror_xml,
            "resolved": [],
            "unresolved": [c["tag"] for c in conflict_items],
        }

    juror_record = _parse_marcxml_string(juror_xml)
    if not juror_record:
        return {
            "juror_marcxml": juror_xml,
            "resolved": [],
            "unresolved": [c["tag"] for c in conflict_items],
        }

    resolved = []
    unresolved = []

    for conflict in conflict_items:
        tag = conflict["tag"]
        juror_fields = juror_record.get_fields(tag)
        if not juror_fields:
            unresolved.append(tag)
            continue

        juror_val = " ".join(
            v for i, v in enumerate(juror_fields[0].subfields) if i % 2 == 1
        ).strip()

        local_val = conflict.get("local_value", "")
        ref_val = conflict.get("ref_value", "")

        import difflib
        sim_local = difflib.SequenceMatcher(None, juror_val.lower(), local_val.lower()).ratio() if local_val else 0
        sim_ref = difflib.SequenceMatcher(None, juror_val.lower(), ref_val.lower()).ratio() if ref_val else 0

        if sim_local >= sim_ref:
            winner = local_val
            source = "local"
        else:
            winner = ref_val
            source = "reference"

        resolved.append({
            "tag": tag,
            "winning_value": winner,
            "source": source,
            "juror_value": juror_val,
            "juror_sim_local": round(sim_local, 3),
            "juror_sim_ref": round(sim_ref, 3),
        })
        print(f"[tie_breaker] {tag}: winner={source!r} (juror sim: local={sim_local:.2f}, ref={sim_ref:.2f})")

    return {
        "juror_marcxml": juror_xml,
        "resolved": resolved,
        "unresolved": unresolved,
    }


def main():
    parser = argparse.ArgumentParser(description="Tie-breaker: resolve Red conflicts via juror library")
    parser.add_argument("--conflicts", required=True, help="JSON file of ConflictItem list from audit_consensus")
    parser.add_argument("--isbn", help="ISBN for the tie-breaker query")
    parser.add_argument("--lccn", help="LCCN for the tie-breaker query")
    args = parser.parse_args()

    identifier = args.isbn or args.lccn
    if not identifier:
        print("ERROR: provide --isbn or --lccn", file=sys.stderr)
        sys.exit(1)

    with open(args.conflicts) as f:
        conflicts = json.load(f)

    red_conflicts = [c for c in conflicts if c.get("status") == "red"]
    if not red_conflicts:
        print("[tie_breaker] No Red conflicts — tie-breaker not needed.")
        return

    print(f"[tie_breaker] {len(red_conflicts)} Red conflict(s) to resolve")
    result = asyncio.run(resolve_tie_breaker(red_conflicts, identifier))
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
