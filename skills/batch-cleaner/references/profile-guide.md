# Batch Cleaner: Profile Guide

`batch_clean.py` is driven by a JSON cleaning profile. This document covers
profile structure, MARC org codes, Leader byte positions, and deletion strategy.

---

## Profile Structure

```json
{
  "delete_tags": ["019", "029", "035", "049", "263", "938"],
  "delete_ranges": [["900", "999"]],
  "org_code": "YOUR_MARC_ORG_CODE",
  "note": "Customize for your institution"
}
```

| Key | Type | Description |
|-----|------|-------------|
| `delete_tags` | `list[str]` | Exact tags to delete (e.g. `"035"`) |
| `delete_ranges` | `list[[start, end]]` | Inclusive tag ranges to delete |
| `org_code` | `str` | Your MARC organization code (placed in 003) |
| `note` | `str` | Human-readable description; ignored by the script |

The default profile (`assets/default-profile.json`) targets common
OCLC/vendor utility fields. Customize before use.

---

## Finding Your MARC Org Code

MARC organization codes are registered by the Library of Congress:
<https://www.loc.gov/marc/organizations/>

Format: 2-letter country code + up to 12 alphanumeric characters.
Example: `US-IEdS` (Southeastern Illinois College), `UK-OBL` (British Library).

---

## Common Tags to Delete

| Tag | Description | Why delete |
|-----|-------------|-----------|
| 019 | OCLC control number cross-reference | Local utility; not needed post-import |
| 029 | Other system control number | Vendor/system-specific |
| 035 | System control number | OCLC/vendor number leaks into local catalog |
| 049 | Local holdings (OCLC) | Replace with local 852 |
| 263 | Projected publication date | Temporary; should be deleted on receipt |
| 938 | Vendor added entry | Vendor-specific enrichment |
| 9XX (range 900–999) | All local/vendor fields | Strip entirely before local ILS import |

---

## Leader Byte 09 (Character Encoding Scheme)

| Value | Meaning |
|-------|---------|
| ` ` (space) | MARC-8 (legacy encoding) |
| `a` | Unicode / UTF-8 |

`batch_clean.py` always sets LDR/09 = `'a'` to signal UTF-8 encoding.
This is required for correct rendering in modern ILS systems.

Other Leader positions set at byte level 05 (Record status), 06 (Type of record),
and 07 (Bibliographic level) are **not modified** by the batch cleaner — those
should come from the copy-cataloger or original cataloging workflow.

---

## Unicode NFC Normalization

All string subfield values are passed through
`unicodedata.normalize('NFC', value)`. This converts decomposed characters
(e.g. `e` + combining acute → `é`) to their precomposed equivalents.

Statistics printed after each run include count of normalized subfields.

---

## Running with a Custom Profile

```bash
# Use a profile in a non-standard location
python3 skills/batch-cleaner/scripts/batch_clean.py input.mrc \
  --profile /path/to/my-profile.json \
  --org-code MYLIB
```

`--org-code` on the command line overrides the profile's `org_code` field.
