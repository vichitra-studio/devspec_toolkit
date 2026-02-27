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
    "E125": "ALIAS_SUNSET_EXPIRED",
    "E130": "CANONICAL_VERSION_MISMATCH",
    "E140": "AMBIGUOUS_ALIAS",
    "E210": "CROSS_ARTIFACT_DRIFT",
    "E211": "PARTIAL_DRIFT",
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
    "E561": "UNCOVERED_FR",
    "E562": "ORPHAN_MILESTONE",
    "E563": "CHECKLIST_ROADMAP_MISMATCH",
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
    "W581": "MILESTONE_REF_MISSING",
    "E582": "MILESTONE_REF_MISMATCH",
    "W140": "SEED_CONTENT_OVERLAP_LOW",
    "W561": "UNCOVERED_FR",
    "W562": "ORPHAN_MILESTONE",
    "W563": "CHECKLIST_ROADMAP_MISMATCH",
}


def make_error(code: str, message: str, path: Optional[str] = None) -> SpecError:
    if code not in ERROR_CODES:
        raise ValueError(f"Unknown error code: {code}")
    return SpecError(code=code, message=message, path=path)


class SpecdevError(Exception):
    """Base exception for specdev toolkit errors."""
    pass


class SubmoduleDetectionError(SpecdevError):
    """Raised when submodule root detection fails.

    Typical causes:
    - The toolkit is not checked out as a git submodule
    - The git working tree is in a detached HEAD state
    - The --repo-root flag points to the wrong directory

    Resolution: pass --git-root pointing to the host repo's git root,
    and --spec-root pointing to the spec directory within the host repo.
    """

    def __init__(self, message: str | None = None):
        default = (
            "Could not detect submodule root. "
            "Pass --git-root (host repo git root) and --spec-root (spec directory) explicitly."
        )
        super().__init__(message or default)


class SchemaRegistryError(SpecdevError):
    """Raised when a schema URI cannot be resolved from schema_registry.json.

    Typical causes:
    - The schema URI is missing from tools/schema_registry.json
    - The --repo-root flag does not point to the toolkit directory
    - The schema file referenced in the registry does not exist on disk

    Resolution: check tools/schema_registry.json for the expected URI mapping,
    and verify that --repo-root points to the devspec_toolkit directory.
    """

    def __init__(self, uri: str, detail: str | None = None):
        msg = f"Schema not found for URI '{uri}'. Check tools/schema_registry.json."
        if detail:
            msg += f" Detail: {detail}"
        self.uri = uri
        super().__init__(msg)
