# Vision-to-MARC: Title Page Zone → MARC Tag Mapping

`image_to_marc.py` sends the image to Claude Vision and requests JSON output
conforming to the `MarcFields` pydantic model. This document maps the visual
zones a cataloger would identify on a title page to the MARC 21 fields that
the script creates.

---

## Zone Map

| Visual Zone | Typical Location | MARC Tag | Subfields |
|-------------|-----------------|----------|-----------|
| Main title | Centre of page, largest text | 245 $a | ISBD: ends ` /` if $c present |
| Subtitle | Below main title, smaller | 245 $b | Preceded by ` :` |
| Statement of responsibility | Below title/subtitle | 245 $c | Author(s) as stated |
| Main author | Title page or verso | 100 $a, $d | Inverted: "Surname, Forename," |
| Edition statement | Above or below imprint | 250 $a | As found; ends `.` |
| Place of publication | Imprint block | 264 $a | Ends ` :` |
| Publisher name | Imprint block | 264 $b | Ends `,` |
| Date of publication | Imprint block | 264 $c | 4-digit year, ends `.` |
| Pagination | Verso or colophon | 300 $a | e.g. `180 pages.` |
| ISBN | Verso (CIP data) or back cover | 020 $a | 13-digit preferred |

---

## ISBD Punctuation Applied Automatically

The script applies these conventions when building the 245 field:

- `$a` ends with ` /` when `$c` is present, ` :` when `$b` follows
- `$b` ends with ` /` when `$c` follows
- `$c` ends with `.`
- 100 $a personal name: ends with `,` if followed by $d; otherwise `.`

---

## Indicator Values

| Tag | ind1 | ind2 | Condition |
|-----|------|------|-----------|
| 100 | `1` | ` ` | Single surname entry (default) |
| 100 | `0` | ` ` | Forename only (no surname detected) |
| 245 | `1` | `0`–`9` | ind1=1 when 1XX is present; ind2 = nonfiling characters |
| 264 | ` ` | `1` | Publication (most common) |

---

## Template Application

After field extraction, the script loads material-specific Leader and 008
defaults from `shared-resources/templates/marc-templates.json`:

- `book` → LDR/06=`a`, LDR/07=`m`
- `ebook` → LDR/06=`a`, LDR/07=`m` + 006/007 for electronic resource
- `journal` → LDR/06=`a`, LDR/07=`s`

Pass `--type <book|ebook|journal>` to select the template.

---

## Provenance

Every field created by the Vision API is stamped with `$9 AI_QUICKCAT` to
distinguish AI-generated data from human-created fields.
