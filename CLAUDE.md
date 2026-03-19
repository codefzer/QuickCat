# QuickCat Development Guide

## Setup

### Requirements
- Python 3.10+
- pip (included with Python)
- Virtual environment (recommended)

### Quick Start

```bash
# Clone and install
git clone https://github.com/codefzer/QuickCat.git
cd QuickCat

# Create virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Verify installation
pytest -v
```

---

## Architecture

### Directory Structure

```
QuickCat/
├── shared-resources/         # Core utilities (stdlib + pymarc only)
│   └── scripts/
│       ├── quickcat_loader.py    # Bootstrap — registers all cross-package imports
│       ├── config_loader.py      # Cached JSON config loaders (config.json, servers.json, validation-rules.json)
│       ├── marc_io.py            # read_mrc() / write_mrc() helpers
│       ├── marc_utils.py         # nfc() NFC normalizer, similarity() scorer
│       ├── normalize_dates.py
│       ├── parse_marc.py
│       └── transaction_log.py
├── skills/                   # Feature modules (loaded on-demand)
│   ├── copy-cataloger/       # Metadata harvesting & consensus
│   ├── batch-cleaner/        # MARC record sanitization
│   ├── brief-to-full-enhancer/  # AI metadata enhancement
│   ├── authority-grounder/   # Authority heading matching
│   ├── marc-importer/        # Excel/MARC import
│   ├── marc-exporter/        # MARC export & validation
│   ├── vision-to-marc/       # OCR to MARC conversion
│   └── record-rollback/      # Revision management
├── tests/
│   ├── conftest.py          # Module shim + fixtures
│   ├── (unit tests by skill)
│   └── integration/          # End-to-end pipeline tests
├── shared-resources/scripts/quickcat_loader.py  # Bootstrap module (solves hyphen/underscore imports)
├── pyproject.toml            # Pytest configuration
└── requirements.txt
```

### The Bootstrap Problem & Solution

**Problem**: Directory names use hyphens (`shared-resources`, `batch-cleaner`) but Python imports use underscores. Standard `sys.path` doesn't resolve hyphens.

**Solution**: `quickcat_loader.py` loads scripts by file path using `importlib` and registers them in `sys.modules`:

```python
import importlib.util
spec = importlib.util.spec_from_file_location("module_name", path)
mod = importlib.util.module_from_spec(spec)
sys.modules["module_name"] = mod
spec.loader.exec_module(mod)
```

This allows normal imports like `from batch_clean import clean_record` even though the actual path is `skills/batch-cleaner/scripts/batch_clean.py`.

### Startup Isolation (Lazy Loading)

QuickCat uses a 4-layer architecture to minimize startup overhead:

| Layer | When Loaded | Dependencies | Use Case |
|-------|------------|--------------|----------|
| **Eager** | On `import quickcat_loader` | stdlib + pymarc | All scripts need this |
| **register_copy_cataloger()** | On demand | httpx, tenacity | Metadata harvest/consensus |
| **register_tie_breaker()** | On demand | (calls copy_cataloger) | Conflict resolution |
| **register_batch_cleaner()** | On demand | pymarc | Record cleaning |
| **register_marc_importer()** | On demand | pandas | Excel import only |

Each script calls only the helpers it needs:

```python
import quickcat_loader
quickcat_loader.register_batch_cleaner()  # Load batch_clean only
from skills.batch_cleaner.scripts.batch_clean import clean_record
```

---

## Testing

### Quick Start

```bash
pytest -v                                    # Run all 146 tests
pytest tests/ --ignore=tests/integration/    # Unit tests only (139)
pytest tests/integration/ -v                 # Integration tests only (7)
```

### Test Structure

- **Unit Tests (139)**: Isolated tests for each module in `tests/*/test_*.py`
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
  - `normalize_dates`, `transaction_log`, `parse_marc`, `config_loader`, `marc_io`, `marc_utils` (stdlib + pymarc)

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
| shared_resources | 34 | Config loading, MARC I/O, utils, date normalization, MARC parsing, revision log |
| copy_cataloger | 17 | ISBN/LCCN validation, metadata consensus |
| batch_cleaner | 11 | Record sanitization, field deletion, org codes |
| brief_to_full_enhancer | 10 | AI-powered summaries, field stamping |
| authority_grounder | 8 | Authority heading matching, LC API mocking |
| marc_exporter | 7 | Record classification, validation |
| marc_importer | 9 | Name inversion, column mapping, CSV parsing |
| vision_to_marc | 6 | OCR → MARC conversion, template application |
| record_rollback | 5 | Revision log parsing, record restoration |
| **Integration** | **7** | Full pipeline workflows, output validation |
| **TOTAL** | **146** | **Comprehensive coverage** |

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

---

## Development Workflow

### Editing Scripts

1. **Never rename directories** – Hyphenated names are integral to the design
2. **Add imports at module level** – Lazy-load heavy dependencies only where used
3. **Document module boundaries** – Comments show which helpers register which modules
4. **Run tests after changes** – `pytest -v` must pass before committing

### Running Scripts Locally

```bash
# Example: MARC import pipeline with ISO-2709 input
python3 skills/marc-importer/scripts/import_pipeline.py input.mrc --out output.mrc

# With validation profile
python3 skills/marc-importer/scripts/import_pipeline.py input.mrc \
  --profile skills/batch-cleaner/assets/default-profile.json

# Check startup overhead for lightweight operations
python3 skills/marc-importer/scripts/import_pipeline.py sample.mrc
# Should NOT import pandas since input is .mrc (ISO-2709)
```

### Adding New Features

1. **Create in `skills/NEW_SKILL/scripts/`**
2. **Add unit tests in `tests/new_skill/`**
3. **If heavy dependencies, create a register function in `quickcat_loader.py`**
4. **Add integration test if pipeline-relevant**
5. **Update this CLAUDE.md with gotchas**

### Git Workflow

```bash
# Create feature branch
git checkout -b feature/my-feature

# Make changes and test
pytest -v
git add .
git commit -m "Add my feature description"

# Push and open PR
git push origin feature/my-feature
```

**Important**: All 127 tests must pass before pushing.

---

## Known Gotchas

### 1. Double-Import Problem (Fixed)

**Gotcha**: Running a script directly (e.g., `python3 batch_clean.py`) causes the file to be imported twice: once as `__main__`, and again via `quickcat_loader._reg()`.

**Solution**: `_reg()` checks if the target path matches `sys.modules["__main__"].__file__` and aliases instead of re-executing. See `quickcat_loader.py` lines 49-55.

### 2. Module-Level Side Effects

**Gotcha**: Code at module level in shared modules runs every time the module is loaded.

**Solution**: Isolate heavy imports behind `register_*()` helpers so unrelated scripts don't pay the cost. Example:

```python
# harvest_metadata.py imports httpx at module level — this is fine,
# but quickcat_loader defers its registration so only scripts that
# call register_copy_cataloger() load it.

# In quickcat_loader.py:
def register_copy_cataloger():
    """Deferred because harvest_metadata imports httpx/tenacity at module level."""
    _reg("harvest_metadata", ROOT / "skills/copy-cataloger/scripts/harvest_metadata.py")
```

### 3. Configuration Files Must Exist

**Gotcha**: Scripts define `_load_config()` at module level but call it inside runtime functions (e.g., `orchestrate()`, `harvest_metadata()`). The real `config.json` must exist at the repo root for production use, but tests should mock it to avoid file I/O.

**Solution**: Use the shared `mock_config_factory` fixture from `conftest.py`:

```python
async def test_example(mock_config_factory):
    mock_config_factory(harvest_orchestrator, {"org_code": "TEST_ORG"})
```

### 4. Integration Tests Need Multiple Sources

**Gotcha**: Testing merge/consensus logic requires multiple metadata sources, otherwise the loop never executes.

**Solution**: Always test with `sources=["loc", "nls"]` or similar to trigger `records[1:]` loop. See `test_orchestrate_full_harvest_workflow()`.

### 5. Async Tests Need `@pytest.mark.asyncio`

**Gotcha**: Async functions without the decorator won't run under pytest.

**Solution**: Add `@pytest.mark.asyncio` above async test functions. `pyproject.toml` sets `asyncio_mode = "auto"` so no manual `asyncio.run()` needed.
