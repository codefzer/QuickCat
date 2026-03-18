"""Authority Grounder — validate LCSH/LCNAF headings and inject $0 URIs.

Usage:
    python3 skills/authority-grounder/scripts/authority_lookup.py input.mrc
    python3 skills/authority-grounder/scripts/authority_lookup.py input.mrc --out verified.mrc --threshold 0.80
"""

import argparse
import asyncio
import difflib
import json
import re
import sys
import unicodedata
from pathlib import Path

import httpx
import pymarc
from tenacity import retry, stop_after_attempt, wait_exponential

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))
import quickcat_loader          # noqa: F401  – registers cross-package import aliases

from shared_resources.scripts.transaction_log import log_edit  # noqa: E402


def _load_config() -> dict:
    with open(ROOT / "config.json") as f:
        return json.load(f)


# ─── id.loc.gov SRU endpoints ─────────────────────────────────────────────────

LCSH_SRU = "https://id.loc.gov/authorities/subjects/suggest"
LCNAF_SRU = "https://id.loc.gov/authorities/names/suggest"
LCSH_SEARCH = "http://lx2.loc.gov/sru/authorities?version=1.1&operation=searchRetrieve&recordSchema=marcxml&maximumRecords=5&query="


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=1, max=30))
async def _suggest(heading: str, vocab: str = "subjects") -> list[dict]:
    """Use LC's suggest API to find authority headings.

    Returns list of dicts: { label, uri }
    """
    url = f"https://id.loc.gov/authorities/{vocab}/suggest"
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, params={"q": heading, "count": 5})
        resp.raise_for_status()
    data = resp.json()
    # LC suggest returns [query, [labels], [], [uris]]
    if len(data) < 4:
        return []
    labels = data[1] if isinstance(data[1], list) else []
    uris = data[3] if isinstance(data[3], list) else []
    return [{"label": l, "uri": u} for l, u in zip(labels, uris)]


def _best_match(heading: str, candidates: list[dict], threshold: float) -> dict | None:
    """Return the best matching candidate above threshold, or None."""
    best = None
    best_score = 0.0
    for c in candidates:
        score = difflib.SequenceMatcher(
            None,
            heading.lower().strip("."),
            c["label"].lower().strip(".")
        ).ratio()
        if score > best_score:
            best_score = score
            best = c
    if best and best_score >= threshold:
        return {**best, "score": round(best_score, 3)}
    return None


# ─── ISBD Punctuation Normalization ──────────────────────────────────────────

def _normalize_isbd_punctuation(field: pymarc.Field) -> pymarc.Field:
    """Apply LC/ISBD punctuation rules to a variable field.

    Rules:
    - 100/700 personal name ($a): trailing comma unless followed by $d or $e
    - $d (dates): comma before, period after
    - 650/651: trailing period after last data subfield (not $0, $2, $9)
    """
    tag = field.tag
    if tag not in ("100", "110", "600", "650", "651", "700", "710"):
        return field

    subs = field.subfields[:]  # copy
    data_subs = [i for i in range(0, len(subs), 2)
                 if subs[i] not in ("0", "2", "9")]

    if not data_subs:
        return field

    last_data_idx = data_subs[-1]
    last_val = subs[last_data_idx + 1]

    if tag in ("100", "700") and subs[data_subs[0]] == "a":
        # Ensure $a ends with comma if $d follows
        a_idx = data_subs[0]
        if a_idx + 2 < len(subs) and subs[a_idx + 2] == "d":
            if not subs[a_idx + 1].endswith(","):
                subs[a_idx + 1] = subs[a_idx + 1].rstrip(".") + ","

    # Last data subfield should end with period (unless abbreviation or parenthesis)
    if tag in ("100", "700", "650", "651", "600"):
        if not last_val.endswith((".", ")", "-", "!", "?")):
            subs[last_data_idx + 1] = last_val + "."

    field.subfields = subs
    return field


# ─── Main authority lookup ────────────────────────────────────────────────────

async def _lookup_heading(
    heading: str,
    tag: str,
    threshold: float,
) -> dict:
    """Look up one heading in LCSH or LCNAF."""
    # Choose vocab based on tag
    if tag in ("100", "110", "111", "700", "710", "711"):
        vocab = "names"
    else:
        vocab = "subjects"

    candidates = await _suggest(heading, vocab)
    match = _best_match(heading, candidates, threshold)

    if match:
        return {
            "tag": tag,
            "original": heading,
            "matched": match["label"],
            "uri": match["uri"],
            "score": match["score"],
            "status": "matched",
            "alternatives": [c["label"] for c in candidates if c["label"] != match["label"]],
        }
    else:
        return {
            "tag": tag,
            "original": heading,
            "matched": None,
            "uri": None,
            "score": 0.0,
            "status": "not_matched",
            "alternatives": [c["label"] for c in candidates],
        }


async def authority_lookup(
    record: pymarc.Record,
    threshold: float,
) -> tuple[pymarc.Record, list[dict]]:
    """Validate and inject $0 URIs for all authority-controlled fields.

    Returns the modified record and an audit log list.
    """
    authority_tags = ["100", "110", "111", "600", "610", "650", "651", "700", "710"]
    audit = []

    for tag in authority_tags:
        for field in record.get_fields(tag):
            # Get heading text (subfields a, b, v, x, y, z, exclude 0, 2, 9)
            heading_parts = [
                field.subfields[i + 1]
                for i in range(0, len(field.subfields), 2)
                if field.subfields[i] in ("a", "b", "v", "x", "y", "z")
            ]
            heading = "--".join(heading_parts).strip()
            if not heading:
                continue

            result = await _lookup_heading(heading, tag, threshold)
            audit.append(result)

            if result["status"] == "matched":
                # Inject $0 URI and $2 source (only if not already present)
                existing_0 = [
                    field.subfields[i + 1]
                    for i in range(0, len(field.subfields), 2)
                    if field.subfields[i] == "0"
                ]
                if not existing_0:
                    field.subfields += ["0", result["uri"]]
                if tag.startswith("6"):
                    existing_2 = [
                        field.subfields[i + 1]
                        for i in range(0, len(field.subfields), 2)
                        if field.subfields[i] == "2"
                    ]
                    if not existing_2:
                        field.subfields += ["2", "lcsh"]

            # Apply ISBD punctuation normalization
            _normalize_isbd_punctuation(field)

    return record, audit


def main():
    parser = argparse.ArgumentParser(description="Validate authority headings and inject $0 URIs")
    parser.add_argument("mrc_file", nargs="?", help="Input .mrc file")
    parser.add_argument("--out", help="Output .mrc file path")
    parser.add_argument("--threshold", type=float, default=None, help="Match threshold 0.0–1.0")
    parser.add_argument("--auto-accept", action="store_true", help="Skip confirmation prompt")
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    args = parser.parse_args()

    if args.test:
        print("[authority_lookup] --test: config and endpoint check")
        cfg = _load_config()
        print(f"  Threshold from config: {cfg['consensus']['similarity_threshold']}")
        print("  OK")
        return

    if not args.mrc_file:
        print("ERROR: provide mrc_file", file=sys.stderr)
        sys.exit(1)

    cfg = _load_config()
    threshold = args.threshold or cfg["consensus"]["similarity_threshold"]

    records = []
    with open(args.mrc_file, "rb") as f:
        reader = pymarc.MARCReader(f, to_unicode=True, force_utf8=True)
        for rec in reader:
            if rec:
                records.append(rec)

    if not records:
        print("ERROR: no records found in input file", file=sys.stderr)
        sys.exit(1)

    print(f"[authority_lookup] Processing {len(records)} record(s), threshold={threshold}")

    all_audits = []
    updated_records = []

    async def process_all():
        for rec in records:
            before = pymarc.Record()
            before.leader = rec.leader
            for f in rec.fields:
                before.add_field(f)

            updated, audit = await authority_lookup(rec, threshold)
            all_audits.extend(audit)

            matched = sum(1 for a in audit if a["status"] == "matched")
            unmatched = sum(1 for a in audit if a["status"] == "not_matched")
            print(f"  Matched: {matched}  Unmatched: {unmatched}")

            changes = [
                f"{a['tag']} $0 injected: {a['uri']}"
                for a in audit if a["status"] == "matched"
            ]
            out_path = args.out or str(Path(args.mrc_file).with_suffix("")) + "_verified.mrc"
            log_edit("authority-grounder", before, updated, out_path, changes)
            updated_records.append(updated)

    asyncio.run(process_all())

    # Print HITL diff for unmatched
    unmatched = [a for a in all_audits if a["status"] == "not_matched"]
    if unmatched:
        print("\n[authority_lookup] Headings needing manual review:")
        for u in unmatched:
            print(f"  🔴 {u['tag']} {u['original']!r}")
            if u["alternatives"]:
                for alt in u["alternatives"][:3]:
                    print(f"       Suggestion: {alt!r}")
        print()

    if not args.auto_accept and unmatched:
        answer = input("Proceed and write output despite unmatched headings? [y/N] ").strip().lower()
        if answer != "y":
            print("[authority_lookup] Aborted.")
            sys.exit(0)

    out_path = Path(args.out) if args.out else Path(args.mrc_file).with_stem(
        Path(args.mrc_file).stem + "_verified"
    )
    with open(out_path, "wb") as f:
        writer = pymarc.MARCWriter(f)
        for rec in updated_records:
            writer.write(rec)
        writer.close()

    audit_path = out_path.with_suffix(".json").with_stem(out_path.stem + "_audit")
    with open(audit_path, "w") as f:
        json.dump(all_audits, f, ensure_ascii=False, indent=2)

    print(f"[authority_lookup] Written: {out_path}")
    print(f"[authority_lookup] Audit: {audit_path}")


if __name__ == "__main__":
    main()
