"""Support for the tests of the error-code catalogue: where the code lives, the retired codes and the codes with no emitter."""
from __future__ import annotations

import re
from pathlib import Path

TOOLS_DIR = Path(__file__).resolve().parents[3] / "tools" / "specdev_tools"
ERRORS_MODULE = TOOLS_DIR / "core" / "errors.py"
CODE_LITERAL_RE = re.compile(r'["\']([EW]\d{3})["\']')

# Codes whose only input was a removed field or a removed check. No emitter is left for any of them.
# Retired in 1.2.0 (M6c): forward replay (E550, W550, E555, W598, W560), the seed overlap and undeclared seed warnings
# (W140, W551), the traceability closure and completeness checks (E535 to E576 and their warnings, W561 to W576, W566 and W567
# with them: E566 and E567 stay), the trace matrix (E604, W604) and the coverage thresholds (E592, W592).
REMOVED_CODES = (
    "E142", "W574", "W581", "W582", "E581", "E582",
    "W602", "W605", "W607", "W612", "W616", "E141",
    "E592", "W592", "E604", "W604",
    "E550", "W550", "E555", "W598", "W560", "W140", "W551",
    "E560", "E561", "W561", "E562", "W562", "E563", "W563", "E564", "W564", "E565", "W565",
    "W566", "W567", "E568", "W568", "E569", "W569", "E575", "W575", "E576", "W576",
    "E535", "E536",
    "E301", "E302", "E305", "E306", "E307", "W599", "W600", "W601",
)

# Registered codes with no string literal outside errors.py that are not the E side
# of a PROMOTABLE_PAIRS row: kept for compatibility or reserved, not emitted.
# A code that a work item registers before the code that writes it exists stays here until that work item writes it
# as a literal.
REGISTERED_WITHOUT_EMITTER = {
    "E422", "E620", "W150", "W591",
    # W595 is emitted, but only inside longer message strings (context/seed_indexer.py), which the literal pattern
    # above does not match; file-level forward replay and the freshness stderr lines, which wrote it, are gone.
    "W595",
}
