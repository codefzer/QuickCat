---
name: vision-to-marc
description: >-
  This skill should be used when the user uploads a photo or scan of a title page,
  wants to 'catalog from image', 'OCR a book cover', 'extract MARC from title page',
  'create a record from a photo', 'catalog without ISBN', 'photograph a book to catalog it',
  'generate a MARC record from an image', or needs to extract bibliographic fields
  (100, 245, 250, 260/264, 300) from a visual source. Also trigger when the user says
  'I have a picture of this book', 'scan a title page', or 'build a record from a cover scan'.
---

# Vision-to-MARC

Use Claude's vision capability to extract bibliographic data from an image of a
title page, back cover, or colophon, and build a valid MARC 21 record.

## Workflow

```
python3 skills/vision-to-marc/scripts/image_to_marc.py --image title_page.jpg --type book
python3 skills/vision-to-marc/scripts/image_to_marc.py --image cover.png --type ebook --out record.mrc
```

Steps performed automatically:

1. **Image encoding** — Load and base64-encode the image file.
2. **Claude Vision extraction** — Send to Claude claude-sonnet-4-6 with a structured prompt
   requesting JSON output for MARC fields visible on the page.
3. **Pydantic validation** — Validate the response against the `MarcFields` model.
4. **Template application** — Load material-specific Leader/008 defaults from
   `shared-resources/templates/marc-templates.json`.
5. **Provenance stamping** — Every AI-generated field gets `$9 AI_QUICKCAT`.
6. **Transaction log** — Before/after snapshot written to `.quickcat.log`.
7. **HITL diff** — All created fields printed to stdout before any file is written.
8. **Output** — Binary `.mrc` + JSON sidecar (same stem, `.json` extension).

## Fields Extracted

| MARC Tag | Content | Notes |
|----------|---------|-------|
| 100 | Main author | Inverted: "Surname, Forename" |
| 245 | Title / subtitle / statement of responsibility | ISBD punctuation applied |
| 250 | Edition statement | Only if visible on page |
| 264 | Publisher, place, date | Preferred over 260 |
| 300 | Physical description | Pagination if on page |
| 020 | ISBN | Only if barcode or ISBN text is visible |

## HITL Diff Example

```
[vision-to-marc] Preview — confirm before writing:
  100 1_ $a Fitzgerald, F. Scott, $d 1896-1940. $9 AI_QUICKCAT
  245 10 $a The great Gatsby / $c F. Scott Fitzgerald. $9 AI_QUICKCAT
  264 _1 $a New York : $b Scribner, $c 1925. $9 AI_QUICKCAT
  300 __ $a 180 pages $9 AI_QUICKCAT
Write to gatsby.mrc? [y/N]
```

Pass `--auto-accept` to skip the prompt in batch workflows.

## Reference Files

- `references/title-page-mapping.md` — Title page zones → MARC tag mapping
- `assets/marc-template.json` — Empty record template for reference
