# MARC 21 Field Reference — QuickCat

Quick-reference for the MARC 21 fields used across QuickCat skills.
Full specification: <https://www.loc.gov/marc/bibliographic/>

---

## Control Fields (00X)

| Tag | Name | Notes |
|-----|------|-------|
| 001 | Control Number | Assigned by the organization creating the record |
| 003 | Control Number Identifier | MARC org code of 001 source (e.g. `OCoLC`) |
| 005 | Date/Time of Latest Transaction | `YYYYMMDDHHMMSS.F` format |
| 008 | Fixed-Length Data Elements | 40 character positions; material-type specific |

### 008 Byte Positions (Books — Type `a`)

| Position | Name | Values |
|----------|------|--------|
| 07–10 | Date 1 (year of publication) | 4-digit year |
| 11–14 | Date 2 | `||||` if not applicable |
| 15–17 | Place of publication | ISO country code |
| 35–37 | Language | ISO 639-2/B language code |
| 38 | Modified record | ` ` = not modified |
| 39 | Cataloging source | `d` = other |

---

## Main Entry Fields (1XX)

| Tag | Name | Indicators | Key Subfields |
|-----|------|-----------|---------------|
| 100 | Personal Name | `1 _` (surname) | `$a` name, `$d` dates, `$e` relator |
| 110 | Corporate Name | `2 _` | `$a` name, `$b` subordinate |
| 111 | Meeting Name | `2 _` | `$a` name, `$d` date |

ISBD punctuation: `$a` ends with `,` if `$d` follows; last subfield ends with `.`

---

## Title Fields (2XX)

| Tag | Name | Indicators | Key Subfields |
|-----|------|-----------|---------------|
| 245 | Title Statement | `ind1` = 1 if 1XX present, else 0; `ind2` = nonfiling characters | `$a` title, `$b` remainder, `$c` SOR |
| 246 | Varying Form of Title | `1 _` | `$a` title |
| 250 | Edition Statement | `_ _` | `$a` edition |
| 264 | Production/Publication | `_ 1` (publication) | `$a` place, `$b` publisher, `$c` date |

---

## Physical Description (3XX)

| Tag | Name | Key Subfields |
|-----|------|---------------|
| 300 | Physical Description | `$a` extent (e.g. `250 pages`), `$b` illustrations, `$c` dimensions |
| 336 | Content Type | `$a` text, `$b` txt, `$2` rdacontent |
| 337 | Media Type | `$a` unmediated, `$b` n, `$2` rdamedia |
| 338 | Carrier Type | `$a` volume, `$b` nc, `$2` rdacarrier |

---

## Series (4XX / 8XX)

| Tag | Name | Key Subfields |
|-----|------|---------------|
| 490 | Series Statement | `$a` series title, `$v` volume |
| 830 | Series Added Entry — Uniform Title | `$a` title, `$v` volume |

---

## Note Fields (5XX)

| Tag | Name | Key Subfields |
|-----|------|---------------|
| 500 | General Note | `$a` note |
| 504 | Bibliography Note | `$a` text |
| 505 | Formatted Contents Note | `ind1` = 0 (complete); `$a` note |
| 520 | Summary | `ind1` = ` ` (summary); `$a` text |
| 588 | Source of Description Note | `$a` text |

---

## Subject Fields (6XX)

| Tag | Name | ind2 | Key Subfields |
|-----|------|------|---------------|
| 600 | Personal Name Subject | 0 = LCSH | `$a` name, `$x` general, `$0` URI, `$2` lcsh |
| 650 | Topical Term | 0 = LCSH | `$a` term, `$x` general, `$0` URI, `$2` lcsh |
| 651 | Geographic Name | 0 = LCSH | `$a` place, `$0` URI, `$2` lcsh |
| 655 | Index Term — Genre/Form | 0 = LCSH | `$a` term |

ISBD: last data subfield ends with `.` (except when followed by `)`)

---

## Added Entry Fields (7XX)

| Tag | Name | Key Subfields |
|-----|------|---------------|
| 700 | Personal Name | `$a` name, `$e` relator, `$0` URI |
| 710 | Corporate Name | `$a` name |
| 776 | Additional Physical Form Entry | `$i` relationship, `$a` author, `$t` title, `$z` ISBN |

---

## Holdings / Local Fields (8XX / 9XX)

| Tag | Name | Notes |
|-----|------|-------|
| 852 | Location/Call Number | Local — never overwritten by copy-cataloging |
| 856 | Electronic Location | `$u` URL, `$z` public note |
| 090 | Local Call Number | Local LC-style call number — local priority |
| 590 | Local Note | Internal use — local priority |
| 9XX | Local fields (900–999) | Always local priority; deleted during batch clean |

---

## Identifiers (020 / 022 / 035)

| Tag | Name | Key Subfields |
|-----|------|---------------|
| 020 | ISBN | `$a` ISBN (digits only, no hyphens for storage) |
| 022 | ISSN | `$a` ISSN |
| 035 | System Control Number | `$a` (OCoLC)NNNNNNNN — presence indicates copy-cataloged record |

---

## QuickCat-Specific Conventions

| Convention | Description |
|-----------|-------------|
| `$9 AI_QUICKCAT` | Provenance stamp on every AI-generated subfield |
| `003 OCoLC` | Copy-cataloged from OCLC WorldCat |
| Leader byte 09 = `a` | Unicode / UTF-8 encoding (set by batch-cleaner) |
| `.quickcat.log` | Transaction journal alongside each `.mrc` file |
