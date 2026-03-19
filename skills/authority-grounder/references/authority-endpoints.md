# Authority Grounder: id.loc.gov Endpoints and CQL Patterns

`authority_lookup.py` queries the Library of Congress Linked Data Service SRU
endpoint to verify and ground LCSH subject headings and LCNAF name authority
headings.

---

## Primary Endpoint

```
https://id.loc.gov/authorities/{index}/suggest/?q={TERM}&count=5
```

| Index | Authority File | Tags targeted |
|-------|---------------|--------------|
| `subjects` | Library of Congress Subject Headings (LCSH) | 600, 610, 650, 651, 655 |
| `names` | LC Name Authority File (LCNAF) | 100, 110, 600, 610, 700, 710 |

The suggest endpoint returns JSON:
```json
["query", ["Label 1", "Label 2"], ["", ""], ["URI 1", "URI 2"]]
```

The script extracts `labels[i]` and `uris[i]` and uses `marc_utils.similarity()`
to score each candidate against the original heading.

---

## Similarity Threshold

Controlled by `config.json → consensus.similarity_threshold` (default `0.85`).
Override per-run with `--threshold 0.90`.

A heading is **matched** when `best_score >= threshold`. Matched headings receive:
- `$0 https://id.loc.gov/authorities/.../{id}` — machine-actionable URI
- `$2 lcsh` — vocabulary code subfield

---

## Heading Tags Processed

```
1XX:  100, 110                (personal / corporate name main entry)
6XX:  600, 610, 650, 651      (subject added entries)
7XX:  700, 710                (added entries)
```

Tags not in this list are left unchanged.

---

## VIAF Fallback

If id.loc.gov returns no candidates above threshold, the heading is marked
`"unmatched"` in the audit JSON. VIAF (`https://viaf.org/search/`) may be
queried manually for headings not found in LC files.

There is no automatic VIAF fallback in the current implementation.

---

## Request Behaviour

- Requests are made asynchronously (one per heading) using `httpx.AsyncClient`.
- `tenacity` retry: up to 5 attempts with exponential backoff (params from `config.json`).
- A single HTTP session is shared across all headings per run to reuse connections.

---

## Audit Output (`authority-audit.json`)

One entry per heading processed:

```json
{
  "tag": "650",
  "original": "American fiction",
  "matched": "American fiction",
  "uri": "http://id.loc.gov/authorities/subjects/sh85004342",
  "score": 1.0,
  "status": "matched",
  "alternatives": []
}
```

`status` values: `"matched"` | `"unmatched"` | `"skipped"` (tag not in scope)
