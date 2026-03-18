---
name: url-checker
description: >-
  This skill should be used when the user wants to 'check links in MARC records',
  'verify 856 URLs', 'test electronic access links', 'find broken links', 'check
  URL viability', 'audit 856 fields', 'diagnose dead links', 'link checker', or
  needs to validate that electronic resource URLs in bibliographic records are
  still active. Also trigger when the user says 'which records have dead links'
  or 'check all my 856 $u fields'.
---

# URL Checker

Extract all 856 $u (Electronic Access) URLs from a `.mrc` file and run
asynchronous HTTP HEAD requests to verify viability. Outputs a CSV status
report sorted by HTTP status code.

## Workflow

```
python3 skills/url-checker/scripts/check_856.py records.mrc
python3 skills/url-checker/scripts/check_856.py records.mrc --out links.csv --concurrency 20
```

## Output CSV Format

```
record_id,url,status_code,status_text,redirect_url,response_ms
001:ocn12345,https://example.com/ebook,200,OK,,342
001:ocn67890,https://dead.example.com/,404,Not Found,,891
001:ocn11111,https://redirect.com/,301,Moved Permanently,https://new.com/,234
```

## Status Color Key

- ✅ 200–299: Active
- ⚠️ 301/302: Redirected (update the URL)
- ❌ 400+: Dead link (review and remove or update)
- ⏱️ Timeout: Server unreachable
