"""Brief-to-Full Enhancer — generate MARC 520 and 505 fields using Claude.

Usage:
    python3 skills/brief-to-full-enhancer/scripts/enhance_record.py input.mrc
    python3 skills/brief-to-full-enhancer/scripts/enhance_record.py input.mrc --fields 520 --auto-accept
    python3 skills/brief-to-full-enhancer/scripts/enhance_record.py input.mrc --force  # overwrite existing
"""

import argparse
import json
import sys
import unicodedata
from pathlib import Path

import anthropic
import pymarc
from tenacity import retry, stop_after_attempt, wait_exponential

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from shared_resources.scripts.transaction_log import log_edit  # noqa: E402


ENHANCE_PROMPT = """You are a professional library cataloger writing MARC bibliographic notes.

Given this book's metadata:
- Title: {title}
- Author: {author}
- Publication: {publication}
- Subjects: {subjects}

Generate the following in JSON format:

{{
  "summary_520": "A 2-3 sentence factual summary suitable for a MARC 520 field.
                  Be neutral, informative, and scholarly in tone.",
  "contents_505": "A brief formatted contents note listing 4-8 chapter or section titles,
                   separated by ' -- ' (space-dash-dash-space). Only include if the book
                   likely has discrete chapters (exclude journals and poetry collections)."
}}

Rules:
- summary_520 is required; return it even if you have limited context
- contents_505 is optional; return null if not appropriate for this material type
- Both fields will be added verbatim to a library catalog record
- Write in present tense for summary ('Examines...', 'Presents...', not 'This book examines')
- No markdown, no HTML, plain text only"""


def _nfc(s: str | None) -> str | None:
    if s is None:
        return None
    return unicodedata.normalize("NFC", s).strip()


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=1, max=30))
def _call_claude(prompt: str) -> dict:
    """Call Claude API and return parsed JSON response."""
    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = message.content[0].text.strip()
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()
    return json.loads(raw)


def _build_context(record: pymarc.Record) -> dict:
    """Extract context fields from a MARC record for the prompt."""
    def first(tag: str, subfield: str = "a") -> str:
        f = record[tag]
        val = f[subfield] if f else None
        return _nfc(val) or ""

    title_field = record["245"]
    title = ""
    if title_field:
        parts = [title_field["a"] or "", title_field["b"] or ""]
        title = " ".join(p.strip(" /") for p in parts if p).strip()

    author = first("100") or first("110") or first("111") or "Unknown"

    pub_field = record["264"] or record["260"]
    publication = ""
    if pub_field:
        parts = [pub_field["b"] or "", pub_field["c"] or ""]
        publication = " ".join(p.strip(",:") for p in parts if p)

    subjects = []
    for tag in ("650", "651", "600", "655"):
        for f in record.get_fields(tag):
            subj = _nfc(f["a"])
            if subj:
                subjects.append(subj.strip("."))

    return {
        "title": title or "Unknown title",
        "author": author,
        "publication": publication or "Unknown",
        "subjects": "; ".join(subjects[:8]) if subjects else "Not specified",
    }


def _print_diff(tag: str, value: str, indicator1: str, indicator2: str) -> None:
    print(f"  {tag} {indicator1}{indicator2} $a {value[:120]}{'...' if len(value) > 120 else ''} $9 AI_QUICKCAT")


def enhance_record(
    record: pymarc.Record,
    fields_to_add: list[str],
    force: bool = False,
) -> tuple[pymarc.Record, list[str]]:
    """Generate and add 520/505 fields to a record.

    Args:
        record: The pymarc Record to enhance.
        fields_to_add: List of MARC tags to generate, e.g. ['520', '505'].
        force: If True, overwrite existing 520/505 fields.

    Returns:
        Tuple of (updated record, list of change descriptions).
    """
    ctx = _build_context(record)
    prompt = ENHANCE_PROMPT.format(**ctx)
    generated = _call_claude(prompt)
    changes = []

    if "520" in fields_to_add:
        if record["520"] and not force:
            print("[enhancer] 520 already present — skipping (use --force to overwrite)")
        else:
            summary = _nfc(generated.get("summary_520", ""))
            if summary:
                if record["520"] and force:
                    record.remove_field(record["520"])
                record.add_field(pymarc.Field(
                    tag="520",
                    indicators=[" ", " "],
                    subfields=["a", summary, "9", "AI_QUICKCAT"],
                ))
                changes.append(f"520 generated: {summary[:60]}...")

    if "505" in fields_to_add:
        contents = _nfc(generated.get("contents_505"))
        if not contents:
            print("[enhancer] 505 not generated (material type may not warrant a contents note)")
        elif record["505"] and not force:
            print("[enhancer] 505 already present — skipping (use --force to overwrite)")
        else:
            if record["505"] and force:
                record.remove_field(record["505"])
            record.add_field(pymarc.Field(
                tag="505",
                indicators=["0", "0"],
                subfields=["a", contents, "9", "AI_QUICKCAT"],
            ))
            changes.append(f"505 generated: {contents[:60]}...")

    return record, changes


def main():
    parser = argparse.ArgumentParser(description="Generate 520 and 505 fields using Claude")
    parser.add_argument("mrc_file", nargs="?", help="Input .mrc file")
    parser.add_argument("--out", help="Output .mrc file path")
    parser.add_argument("--fields", default="520,505",
                        help="Comma-separated list of fields to generate (default: 520,505)")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing 520/505 fields")
    parser.add_argument("--auto-accept", action="store_true",
                        help="Skip confirmation prompt")
    parser.add_argument("--test", action="store_true", help="Run self-tests")
    args = parser.parse_args()

    if args.test:
        print("[enhancer] --test: verifying config and anthropic import")
        import anthropic as _a
        print(f"  anthropic SDK version: {_a.__version__}")
        print("  OK")
        return

    if not args.mrc_file:
        print("ERROR: provide mrc_file", file=sys.stderr)
        sys.exit(1)

    fields_to_add = [f.strip() for f in args.fields.split(",")]
    records = []
    with open(args.mrc_file, "rb") as f:
        reader = pymarc.MARCReader(f, to_unicode=True, force_utf8=True)
        for rec in reader:
            if rec:
                records.append(rec)

    if not records:
        print("ERROR: no records found", file=sys.stderr)
        sys.exit(1)

    print(f"[enhancer] Processing {len(records)} record(s), fields={fields_to_add}")

    all_changes = []
    updated_records = []

    for i, rec in enumerate(records, 1):
        ctx = _build_context(rec)
        print(f"\n[enhancer] Record {i}: {ctx['title']!r} / {ctx['author']!r}")

        before = pymarc.Record()
        before.leader = rec.leader
        for f in rec.fields:
            before.add_field(f)

        updated, changes = enhance_record(rec, fields_to_add, args.force)
        all_changes.extend(changes)

        # Show diff
        if changes:
            print("[enhancer] New fields to be added:")
            for tag in fields_to_add:
                field = updated[tag]
                if field:
                    _print_diff(tag, field["a"] or "", field.indicator1, field.indicator2)

        out_path = args.out or str(Path(args.mrc_file).with_suffix("")) + "_enhanced.mrc"
        log_edit("brief-to-full-enhancer", before, updated, out_path, changes)
        updated_records.append(updated)

    if not args.auto_accept:
        answer = input(f"\nWrite to output? [y/N] ").strip().lower()
        if answer != "y":
            print("[enhancer] Aborted.")
            sys.exit(0)

    out_path = Path(args.out) if args.out else Path(args.mrc_file).with_stem(
        Path(args.mrc_file).stem + "_enhanced"
    )
    with open(out_path, "wb") as f:
        writer = pymarc.MARCWriter(f)
        for rec in updated_records:
            writer.write(rec)
        writer.close()

    print(f"\n[enhancer] Written: {out_path}")
    print(f"[enhancer] Changes: {len(all_changes)}")


if __name__ == "__main__":
    main()
