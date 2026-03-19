# Copy-Cataloger: Search Hierarchy

`harvest_orchestrator.py` queries all configured sources in parallel. This
document describes the identifier strategy and fall-through logic used.

---

## Identifier Priority

1. **ISBN-13** — preferred; validated (Mod-10 check digit) by `validation_gate.py`
   before any network call.
2. **LCCN** — normalized to bare 8-digit form before querying.
3. **Title + Author** — fuzzy fallback when neither ISBN nor LCCN is known.

---

## Source Query Order

Each configured source (LOC, BL, NLS, OCLC — see `config.json → servers`) is
queried concurrently using `harvest_metadata.py`. All sources that return a
record are collected; the first (by source order in config) becomes the *base*
record.

---

## Search Strategies

### SRU (default for most sources)

```
ISBN:    query=dc.identifier={ISBN}
LCCN:    query=bath.lccn={LCCN}
Title:   query=dc.title="{TITLE}" AND dc.creator="{AUTHOR}"
```

### Z39.50 Bib-1 attribute sets

See `references/z3950-bib1-attributes.md` for Use/Relation/Structure codes.

Common attribute combinations:
- ISBN search: Use=7 (ISBN), Relation=3 (equals), Structure=1 (phrase)
- LCCN search: Use=9 (LC control number), Relation=3, Structure=1
- Title search: Use=4 (title), Relation=3, Structure=2 (word)

---

## Fall-Through Logic

```
1. Try ISBN exact match → all sources in parallel
   → If ≥ 1 source returns a record: proceed to consensus
   → If 0 sources return a record: fall through to step 2

2. Try Title + Author fuzzy match → all sources in parallel
   → If ≥ 1 source returns a record: proceed to consensus
   → If 0 sources return a record: fall through to step 3

3. Authority heading search (LCNAF lookup)
   → If found: return minimal record skeleton for manual completion
   → If not found: exit with "Record Not Found" status
```

---

## Error Strings

`harvest_metadata.py` returns structured error strings (not exceptions) so the
orchestrator can continue with other sources:

| String | Meaning | Orchestrator action |
|--------|---------|-------------------|
| `"Record Not Found"` | Source has no matching record | Skip source |
| `"Protocol Timeout"` | Network timeout | Retry up to `max_attempts` |
| `"Authentication Failure: ..."` | Credentials rejected or unknown source | Log, skip |

---

## Configuration

All parameters are in `config.json`:

```json
{
  "sources": ["loc", "bl", "nls"],
  "consensus": {
    "tie_breaker_server": "nls",
    "similarity_threshold": 0.85
  },
  "server_defaults": {
    "timeout": 10,
    "max_attempts": 3
  }
}
```

Never hardcode server addresses or credentials in scripts.
