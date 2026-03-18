---
name: authority-grounder
description: >-
  This skill should be used when the user wants to 'verify subject headings',
  'validate LCSH', 'check authority files', 'add LC URIs', 'inject $0 subfields',
  'fix 650 headings', 'ground authority terms', 'authority control', 'validate LC
  headings', 'check LCNAF', 'add authority URIs', or mentions id.loc.gov, LCSH,
  LCNAF, authority control, $0 subfield, $2 lcsh, or name authority. Also trigger
  when the user asks 'is this a valid LC subject heading?' or 'fix my 100 field'.
---

# Authority Grounder

Validate LCSH (subject) and LCNAF (name authority) headings in 1XX/6XX/7XX
fields using live SRU queries to id.loc.gov, inject `$0` URI subfields, apply
ISBD punctuation normalization, and flag unverified headings for HITL review.

## Workflow

```
python3 skills/authority-grounder/scripts/authority_lookup.py input.mrc
python3 skills/authority-grounder/scripts/authority_lookup.py input.mrc --out verified.mrc
```

Steps performed automatically:

1. **Extract candidates** — Pull all 100/110/600/610/650/651/700/710 headings.
2. **SRU query** — Query `id.loc.gov` SRU endpoint per heading with CQL.
3. **Fuzzy match** — Compare returned heading to candidate (threshold from `config.json`).
4. **Inject `$0`** — On match: add `$0 http://id.loc.gov/authorities/...` and `$2 lcsh`.
5. **ISBD punctuation** — Normalize trailing punctuation on 100/650/700 per LC practice.
6. **HITL report** — Unmatched headings listed with top-3 alternatives.
7. **Transaction log** — Before/after snapshot to `.quickcat.log`.
8. **Output** — Updated `.mrc` + `authority-audit.json` sidecar.

## ISBD Punctuation Rules Applied

- 100/700 personal name: trailing period unless last element is an abbreviation or date
- 100/700 with $d dates: comma before $d, period after last date
- 650/651: period after last subfield unless it ends with `)`
- $0 and $2 do not affect punctuation of preceding subfields

## Output

- `{stem}_verified.mrc` — Record with `$0` URIs injected
- `authority-audit.json` — Per-heading report:
  ```json
  {
    "tag": "650",
    "original": "American fiction",
    "matched": "American fiction",
    "uri": "http://id.loc.gov/authorities/subjects/sh85004342",
    "status": "matched",
    "alternatives": []
  }
  ```

## Reference Files

- `references/authority-endpoints.md` — id.loc.gov SRU CQL patterns and VIAF fallback
