# Z39.50 Bib-1 Attribute Set Reference

Used in `config.json → search` to build PQF queries.

## Use Attribute (Type 1) — What field to search

| Value | Field |
|-------|-------|
| 1 | Personal name |
| 4 | Title |
| 7 | ISBN |
| 8 | ISSN |
| 12 | Control number (LCCN) |
| 21 | Subject heading |
| 31 | Date of publication |
| 45 | LCCN |
| 54 | Title keyword |

## Relation Attribute (Type 2)

| Value | Meaning |
|-------|---------|
| 1 | Less than |
| 2 | Less than or equal |
| 3 | Equal |
| 4 | Greater than or equal |
| 5 | Greater than |
| 100 | Phonetic |
| 101 | Stem |
| 102 | Relevance |

## Structure Attribute (Type 4)

| Value | Meaning |
|-------|---------|
| 1 | Phrase |
| 2 | Word |
| 3 | Key |
| 4 | Year |
| 5 | Date (normalized) |
| 6 | Word list |
| 100 | Date (un-normalized) |
| 101 | Name (normalized) |
| 102 | Date-time (normalized) |
| 103 | URXNORM |

## Completeness Attribute (Type 6)

| Value | Meaning |
|-------|---------|
| 1 | Incomplete subfield |
| 2 | Complete subfield |
| 3 | Complete field |

## Example PQF Queries

```
# ISBN exact match
@attr 1=7 @attr 2=3 @attr 4=2 @attr 6=3 "9780743273565"

# Title keyword
@attr 1=4 @attr 2=3 @attr 4=6 "great gatsby"

# Author name
@attr 1=1 @attr 2=3 @attr 4=6 "Fitzgerald"
```

## Library-Specific Notes

### Library of Congress (loc)
- Z39.50: z3950.loc.gov port 7090, database VOYAGER
- LOC returns MARC as bytes; encode as latin-1 before parsing with pymarc

### British Library (bl)
- Z39.50: z3950.bl.uk port 9909, database BNB
- Requires IP registration for institutional access

### NLS (National Library of Scotland)
- Z39.50: z3950.nls.uk port 210, database JANUS
- Used as default tie-breaker server

### OCLC WorldCat (oclc)
- Z39.50: z3950.oclc.org port 210, database WorldCat
- Requires OCLC authorization credentials
