# QuickCat Development Guide

## Testing

### Quick Start

```bash
pytest -v                                    # Run all 127 tests
pytest tests/ --ignore=tests/integration/    # Unit tests only (120)
pytest tests/integration/ -v                 # Integration tests only (7)
```

### Test Structure

- **Unit Tests (120)**: Isolated tests for each module in `tests/*/test_*.py`
- **Integration Tests (7)**: End-to-end pipeline tests in `tests/integration/`

### Key Testing Insights

#### 1. Module Import Problem (Solved)

Directory names use hyphens (`shared-resources`, `batch-cleaner`) but Python imports use underscores. The solution in `tests/conftest.py`:

```python
def _reg(name, path):
    """Load a script by file path and register in sys.modules."""
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
```

This allows test files to use normal imports like `import import_pipeline` even though the actual path is `skills/marc-importer/scripts/import_pipeline.py`.

#### 2. Startup Isolation

QuickCat uses **lazy loading** to avoid unnecessary dependencies:

- **Eager layer** (always loaded):
  - `normalize_dates`, `transaction_log`, `parse_marc` (stdlib only)

- **On-demand layers** (loaded when needed):
  - `register_copy_cataloger()` – heavy: httpx, tenacity
  - `register_batch_cleaner()` – needs pymarc
  - `register_marc_importer()` – heavy: pandas

Scripts only load what they need. Tests verify this isolation (see `test_import_pipeline_e2e.py`).

#### 3. Mocking Strategy

| What | How | When |
|------|-----|------|
| httpx calls | `respx` fixtures | `test_harvest_metadata.py` |
| Anthropic API | monkeypatch `_call_claude` | `test_enhance_record.py` |
| File I/O | `tmp_path` fixture | All file tests |
| Config loading | `monkeypatch.setattr` | Integration tests |

#### 4. Async Testing

- `@pytest.mark.asyncio` for async functions
- `pytest-asyncio` configured in `pyproject.toml` with `asyncio_mode = "auto"`
- No manual `asyncio.run()` needed in test definitions

### Test Coverage by Skill

| Skill | Tests | Focus |
|-------|-------|-------|
| shared_resources | 21 | Date normalization, MARC parsing, revision log |
| copy_cataloger | 17 | ISBN/LCCN validation, metadata consensus |
| batch_cleaner | 11 | Record sanitization, field deletion, org codes |
| brief_to_full_enhancer | 10 | AI-powered summaries, field stamping |
| authority_grounder | 8 | Authority heading matching, LC API mocking |
| marc_exporter | 7 | Record classification, validation |
| marc_importer | 9 | Name inversion, column mapping, CSV parsing |
| vision_to_marc | 6 | OCR → MARC conversion, template application |
| record_rollback | 5 | Revision log parsing, record restoration |
| **Integration** | **7** | Full pipeline workflows, output validation |
| **TOTAL** | **127** | **Comprehensive coverage** |

### Adding New Tests

1. Create test file in appropriate `tests/SKILL_NAME/` directory
2. Import modules directly: `import module_name` (conftest handles paths)
3. Use shared fixtures from `conftest.py`: `sample_record`, `tmp_path`, etc.
4. For async tests, use `@pytest.mark.asyncio`
5. For httpx mocking, use `respx` (already in requirements.txt)

### Important Files

- `tests/conftest.py` – Module shim + shared fixtures
- `pyproject.toml` – pytest config with asyncio_mode="auto"
- `requirements.txt` – Must include: pytest, pytest-asyncio, respx, pymarc

### Startup Isolation Verification

To verify a script only loads expected dependencies:

```bash
# Check what gets loaded with lightweight input
python3 skills/marc-importer/scripts/import_pipeline.py sample.mrc
# Should NOT import pandas/excel libraries
```

Test: `test_import_pipeline_e2e.py` verifies ISO-2709 path never touches Excel stack.
