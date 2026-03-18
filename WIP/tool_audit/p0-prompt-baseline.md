# P0: Baseline Capture

## Execution

Run inline (no agent needed). Assumes venv `devspec_env` is active.
If any Python import fails, ensure specdev_tools is installed: `pip install -e ./tools`

**Error handling**: If any command fails, record the error message in the 'Actual' column and note it in the Drift section.

## Commands

```bash
# Activate venv
source devspec_env/bin/activate

# 1. Test count and pass/fail
pytest tests/ --collect-only -q 2>&1 | tail -1
pytest tests/ -q 2>&1 | tail -3

# 2. Source LOC (specdev_tools/ only — NOT all of tools/)
find tools/specdev_tools -name '*.py' | xargs wc -l | tail -1

# 3. Source file count
find tools/specdev_tools -name '*.py' | wc -l

# 4. Test LOC
find tests -name '*.py' | xargs wc -l | tail -1

# 5. Test file count (all .py)
find tests -name '*.py' | wc -l

# 6. Unit test file count
find tests -maxdepth 1 -name 'test_*.py' | wc -l

# 7. Integration test file count
find tests/integration -name 'test_*.py' | wc -l

# 8. Conftest count
find tests -name 'conftest.py' | wc -l

# 9. Duplicate _load function count
grep -rn 'def _load_' tools/specdev_tools/validation/validators/ | wc -l

# 10. Schema registry entry count
python3 -c "import json; print(len(json.load(open('tools/schema_registry.json'))))"

# 11. CLI subcommand count
grep -c 'sub.add_parser' tools/specdev_tools/cli.py

# 12. Error code count
python3 -c "
from specdev_tools.core.errors import PROMOTABLE_PAIRS
import re
with open('tools/specdev_tools/core/errors.py') as f:
    src = f.read()
codes = set(re.findall(r'\"[EW]\d{3}\"', src))
e_codes = [c for c in codes if c[1] == 'E']
w_codes = [c for c in codes if c[1] == 'W']
print(f'Total codes: {len(codes)}')
print(f'E-codes: {len(e_codes)}')
print(f'W-codes: {len(w_codes)}')
print(f'PROMOTABLE_PAIRS: {len(PROMOTABLE_PAIRS)}')
"

# 13. Test fixture file count
find tests/fixtures -type f | wc -l

# 14. Schema file count
find schema -name '*.schema.json' | wc -l

# 15. Version check
grep 'version' tools/pyproject.toml | head -1
```

## Output

Write results to: `WIP/tool_audit/p0-baseline.md`

Use this template:

```markdown
# P0: Baseline Snapshot

Captured at: {timestamp}
Branch: {branch}

## Metrics

| Metric | Expected (from ground truth) | Actual |
|--------|------------------------------|--------|
| Tests collected | 830 | |
| Tests passed | 830 | |
| Source files (specdev_tools/) | 61 | |
| Source LOC (specdev_tools/) | 13,228 | |
| Test .py files (all) | 73 | |
| Test LOC | 17,709 | |
| Unit test files | 50 | |
| Integration test files | 21 | |
| Conftest files | 2 | |
| _load_* functions | 23 | |
| Schema registry entries | 29 | |
| CLI subcommands | 25 | |
| Error codes total | 77 | |
| E-codes | 52 | |
| W-codes | 25 | |
| PROMOTABLE_PAIRS | 18 | |
| Test fixture files | 133 | |
| Schema files | 24 | |
| pyproject.toml version | 0.4.0 | |

## Drift from Ground Truth

{List any metrics where Actual differs from Expected. If none, write "None — baseline matches ground truth."}
```
