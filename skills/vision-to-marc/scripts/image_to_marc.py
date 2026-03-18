"""Vision-to-MARC — extract bibliographic fields from a title page image.

Sends the image to Claude's vision API and builds a pymarc Record from the response.
Every AI-generated field is stamped $9 AI_QUICKCAT.

Usage:
    python3 skills/vision-to-marc/scripts/image_to_marc.py --image title_page.jpg --type book
    python3 skills/vision-to-marc/scripts/image_to_marc.py --image cover.png --out record.mrc --auto-accept
"""

import argparse
import base64
import json
import sys
import unicodedata
from pathlib import Path
from typing import Optional

import anthropic
import pymarc
from pydantic import BaseModel, Field
from tenacity import retry, stop_after_attempt, wait_exponential

ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from shared_resources.scripts.transaction_log import log_edit  # noqa: E402


VISION_PROMPT = """You are a professional library cataloger. Examine this title page image and extract
bibliographic information. Return a JSON object with ONLY these keys (omit any you cannot
confidently determine from the image):

{
  "author_main": "Surname, Forename [birth-death if visible]",
  "title": "Main title",
  "subtitle": "Subtitle if present",
  "statement_of_responsibility": "Author statement as it appears (e.g., 'by F. Scott Fitzgerald')",
  "edition": "Edition statement if present (e.g., '2nd ed.')",
  "publisher": "Publisher name",
  "place_of_publication": "City",
  "date": "Year of publication (4 digits)",
  "pagination": "Number of pages if visible (e.g., '250')",
  "isbn": "ISBN if visible on page (digits only, no hyphens)"
}

Rules:
- author_main: use inverted form (Surname, Forename)
- title: transcribe as it appears, preserving capitalization
- All values must be strings; omit keys you cannot read confidently
- Do not invent information not visible in the image"""


class MarcFields(BaseModel):
    """Pydantic model for validating Claude's vision response."""
    author_main: Optional[str] = None
    title: str = Field(..., description="Title is required")
    subtitle: Optional[str] = None
    statement_of_responsibility: Optional[str] = None
    edition: Optional[str] = None
    publisher: Optional[str] = None
    place_of_publication: Optional[str] = None
    date: Optional[str] = None
    pagination: Optional[str] = None
    isbn: Optional[str] = None


def _nfc(s: str | None) -> str | None:
    if s is None:
        return None
    return unicodedata.normalize("NFC", s).strip()


@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=2, min=1, max=30))
def _call_vision_api(image_b64: str, media_type: str) -> MarcFields:
    """Call Claude Vision API and parse the response into a MarcFields model."""
    client = anthropic.Anthropic()
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": media_type,
                            "data": image_b64,
                        },
                    },
                    {"type": "text", "text": VISION_PROMPT},
                ],
            }
        ],
    )
    raw = message.content[0].text.strip()
    # Extract JSON block if wrapped in markdown
    if "```json" in raw:
        raw = raw.split("```json")[1].split("```")[0].strip()
    elif "```" in raw:
        raw = raw.split("```")[1].split("```")[0].strip()
    data = json.loads(raw)
    return MarcFields(**data)


def _load_template(material_type: str) -> dict:
    templates_path = ROOT / "shared-resources" / "templates" / "marc-templates.json"
    with open(templates_path) as f:
        templates = json.load(f)
    return templates.get(material_type, templates["book"])


def _build_record(fields: MarcFields, material_type: str) -> pymarc.Record:
    """Build a pymarc Record from extracted fields."""
    template = _load_template(material_type)
    record = pymarc.Record()

    # Apply Leader from template
    leader = list("00000nam a2200000   4500")
    ldr = template.get("leader", {})
    for pos, val in ldr.items():
        try:
            idx = int(pos)
            leader[idx] = val
        except (ValueError, IndexError):
            pass
    record.leader = "".join(leader)

    def stamp(subfields: list[str]) -> list[str]:
        """Add $9 AI_QUICKCAT provenance stamp."""
        return subfields + ["9", "AI_QUICKCAT"]

    # 100 — Main Author
    if fields.author_main:
        author = _nfc(fields.author_main)
        # Ensure trailing comma/period for ISBD
        if not author.endswith((".","," , "-")):
            author += ","
        record.add_field(pymarc.Field(
            tag="100",
            indicators=["1", " "],
            subfields=stamp(["a", author]),
        ))

    # 245 — Title Statement
    title_a = _nfc(fields.title) or "Title not determined"
    title_b = _nfc(fields.subtitle)
    title_c = _nfc(fields.statement_of_responsibility)

    subs_245 = ["a", title_a]
    if title_b:
        # Ensure colon separator
        if not title_a.endswith(":"):
            subs_245[-1] += " :"
        subs_245 += ["b", title_b]
    if title_c:
        tail = subs_245[-1]
        if not tail.endswith("/"):
            subs_245[-1] += " /"
        subs_245 += ["c", title_c]
    # Title must end with period/mark
    if not subs_245[-1].endswith((".", "!", "?", "]", ")")):
        subs_245[-1] += "."

    ind1 = "1" if fields.author_main else "0"
    record.add_field(pymarc.Field(
        tag="245",
        indicators=[ind1, "0"],
        subfields=stamp(subs_245),
    ))

    # 250 — Edition
    if fields.edition:
        record.add_field(pymarc.Field(
            tag="250",
            indicators=[" ", " "],
            subfields=stamp(["a", _nfc(fields.edition) + "."]),
        ))

    # 264 — Production/Publication
    pub_subs = []
    if fields.place_of_publication:
        pub_subs += ["a", _nfc(fields.place_of_publication) + " :"]
    if fields.publisher:
        pub_subs += ["b", _nfc(fields.publisher) + ","]
    if fields.date:
        pub_subs += ["c", _nfc(fields.date) + "."]
    if pub_subs:
        record.add_field(pymarc.Field(
            tag="264",
            indicators=[" ", "1"],
            subfields=stamp(pub_subs),
        ))

    # 300 — Physical Description
    if fields.pagination:
        from shared_resources.scripts.normalize_dates import format_pagination
        pages = format_pagination(fields.pagination) or fields.pagination
        record.add_field(pymarc.Field(
            tag="300",
            indicators=[" ", " "],
            subfields=stamp(["a", _nfc(pages) + "."]),
        ))

    # 020 — ISBN
    if fields.isbn:
        isbn_clean = "".join(c for c in fields.isbn if c.isdigit() or c in "Xx")
        record.add_field(pymarc.Field(
            tag="020",
            indicators=[" ", " "],
            subfields=stamp(["a", isbn_clean]),
        ))

    # 040 — Cataloging Source
    record.add_field(pymarc.Field(
        tag="040",
        indicators=[" ", " "],
        subfields=["a", "QuickCat", "b", "eng", "e", "rda", "c", "QuickCat"],
    ))

    return record


def _print_diff(record: pymarc.Record) -> None:
    print("\n[vision-to-marc] Preview — confirm before writing:")
    for field in record.fields:
        if hasattr(field, "subfields"):
            subs = " ".join(
                f"${field.subfields[i]}{field.subfields[i+1]}"
                for i in range(0, len(field.subfields), 2)
            )
            print(f"  {field.tag} {field.indicator1}{field.indicator2} {subs}")
        else:
            print(f"  {field.tag}    {field.data}")
    print()


def main():
    parser = argparse.ArgumentParser(description="Extract MARC fields from a title page image")
    parser.add_argument("--image", required=True, help="Path to image file (jpg, png, gif, webp)")
    parser.add_argument("--type", dest="material_type", default="book",
                        choices=["book", "ebook", "journal"],
                        help="Material type for Leader/008 template")
    parser.add_argument("--out", help="Output .mrc file path (default: <image_stem>.mrc)")
    parser.add_argument("--auto-accept", action="store_true",
                        help="Skip HITL confirmation prompt")
    args = parser.parse_args()

    image_path = Path(args.image)
    if not image_path.exists():
        print(f"ERROR: image file not found: {args.image}", file=sys.stderr)
        sys.exit(1)

    suffix = image_path.suffix.lower()
    media_types = {".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                   ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp"}
    media_type = media_types.get(suffix, "image/jpeg")

    with open(image_path, "rb") as f:
        image_b64 = base64.standard_b64encode(f.read()).decode("utf-8")

    print(f"[vision-to-marc] Sending {image_path.name} to Claude Vision API...")
    extracted = _call_vision_api(image_b64, media_type)
    print(f"[vision-to-marc] Extracted title: {extracted.title!r}")

    record = _build_record(extracted, args.material_type)
    _print_diff(record)

    out_path = Path(args.out) if args.out else image_path.with_suffix(".mrc")

    if not args.auto_accept:
        answer = input(f"Write to {out_path}? [y/N] ").strip().lower()
        if answer != "y":
            print("[vision-to-marc] Aborted.")
            sys.exit(0)

    # Log before (empty record) and after
    empty = pymarc.Record()
    empty.leader = record.leader
    log_edit(
        skill_name="vision-to-marc",
        record_before=empty,
        record_after=record,
        mrc_path=str(out_path),
        changes=[f"Created from image: {image_path.name}"],
    )

    with open(out_path, "wb") as f:
        writer = pymarc.MARCWriter(f)
        writer.write(record)
        writer.close()

    # JSON sidecar
    json_path = out_path.with_suffix(".json")
    from shared_resources.scripts.parse_marc import record_to_dict
    with open(json_path, "w") as f:
        json.dump(record_to_dict(record), f, ensure_ascii=False, indent=2)

    print(f"[vision-to-marc] Written: {out_path}")
    print(f"[vision-to-marc] JSON sidecar: {json_path}")


if __name__ == "__main__":
    main()
