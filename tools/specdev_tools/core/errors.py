from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SpecError:
    code: str
    message: str
    path: Optional[str] = None

    def render(self) -> str:
        if self.path:
            return f"{self.code} {self.path} {self.message}"
        return f"{self.code} {self.message}"


ERROR_CODES = {
    "E110": "UNKNOWN_CANONICAL_ID",
    "E120": "CANONICAL_KIND_MISMATCH",
    "E130": "CANONICAL_VERSION_MISMATCH",
    "E140": "AMBIGUOUS_ALIAS",
    "E210": "CROSS_ARTIFACT_DRIFT",
    "E310": "PROMPT_SCHEMA_DRIFT",
    "E410": "CANONICAL_ALIAS_COLLISION",
    "E420": "INVALID_DEPRECATION_LIFECYCLE",
    "E510": "PLACEHOLDER_VALUE_FOUND",
    "E511": "PLACEHOLDER_SCAN_MISMATCH",
    "E512": "ASSUMPTION_HAS_PLACEHOLDER",
    "E520": "UNRESOLVED_INPUT",
    "E521": "VALIDATOR_RUNTIME",
    "E530": "INVENTED_ENUM_OR_ID",
    "E540": "SELF_OR_FORWARD_DEPENDENCY",
    "E541": "UNBOUND_CANONICAL_TERM",
    "E550": "FORWARD_REPLAY_MISSING",
    "E560": "TRACEABILITY_GAP",
    "W110": "DEPRECATED_CANONICAL_USED",
    "W120": "ALIAS_DEPRECATED",
    "W130": "CANONICAL_REF_VERSION_OMITTED",
    "W550": "SEMANTIC_COVERAGE_SKIP",
    "W560": "TRACEABILITY_GAP",
    "W570": "GRACEFUL_SKIP",
    "W571": "ASSUMPTION_VAGUE_QUANTIFIER",
    "W572": "ASSUMPTION_COUNT_HIGH",
    "E301": "MISSING_PROOF_CLOSURE",
    "E302": "UNPROVEN_VERIFIED_REVIEW",
    "E303": "CI_GATE_VIOLATION",
    "E304": "ROADMAP_TASK_UNCOVERED",
    "E305": "PLANNED_UNEXECUTED",
    "E306": "SEMANTIC_REVIEW_FR_MISMATCH",
    "E307": "BEHAVIOR_VALIDATION_PAIRING",
    "W573": "ASSUMPTION_UNBOUND_ID",
    "W580": "SUBSTEP_DRIFT",
}


def make_error(code: str, message: str, path: Optional[str] = None) -> SpecError:
    if code not in ERROR_CODES:
        raise ValueError(f"Unknown error code: {code}")
    return SpecError(code=code, message=message, path=path)
