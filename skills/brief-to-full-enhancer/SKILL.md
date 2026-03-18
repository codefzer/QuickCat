---
name: brief-to-full-enhancer
description: >-
  This skill should be used when the user wants to 'add a summary field', 'generate
  a 520', 'create a 505 contents note', 'enhance a brief record', 'add an abstract',
  'fill in 505', 'upgrade a minimal record', 'add a summary to MARC', 'enrich this
  record', or needs to upgrade copy-cataloged records to full bibliographic level.
  Also trigger when the user says 'this record is missing a summary', 'add notes to
  MARC record', or 'generate a table of contents note'.
---

# Brief-to-Full Enhancer

Generate MARC 520 (Summary) and 505 (Contents Note) fields for records that
lack them, using Claude to synthesize content from existing bibliographic
context (title, author, subject headings).

## Workflow

```
python3 skills/brief-to-full-enhancer/scripts/enhance_record.py input.mrc
python3 skills/brief-to-full-enhancer/scripts/enhance_record.py input.mrc --fields 520,505 --auto-accept
```

Steps performed automatically:

1. **Parse input** — Load `.mrc`, extract 100/245/260/650 as context.
2. **Skip if present** — If 520 already exists, skip 520 generation (use `--force` to override).
3. **Claude generation** — Prompt Claude for a 2–3 sentence summary and chapter list.
4. **Retry** — Exponential backoff up to 5 attempts if API call fails.
5. **Write fields** — 520 (ind1=`' '`) and 505 (ind1=`'0'`, ind2=`'0'`) added to record.
6. **Provenance stamp** — Both fields stamped `$9 AI_QUICKCAT`.
7. **HITL diff** — New fields printed to stdout before writing.
8. **Transaction log** — Before/after snapshot to `.quickcat.log`.

## Field Indicators

| Tag | ind1 | ind2 | Meaning |
|-----|------|------|---------|
| 520 | ` ` | ` ` | Summary (general) |
| 505 | `0` | `0` | Complete contents (enhanced) |

## HITL Diff Example

```
[enhancer] New fields to be added:
  520 __ $a A wealthy and mysterious man throws lavish parties at his Long Island
  estate while pursuing a lost love across the class divide of 1920s America.
  $9 AI_QUICKCAT
  505 0_ $a Chapter 1. In my younger and more vulnerable years --
  Chapter 2. Some time toward the end of August ... $9 AI_QUICKCAT
Write to output.mrc? [y/N]
```

## Reference Files

- `references/marc-notes-guide.md` — 520/505 indicator values, subfield codes, LC examples
