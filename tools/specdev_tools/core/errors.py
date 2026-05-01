from __future__ import annotations

import re
from collections.abc import Sequence
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
    # Canonical integrity (1xx)
    "E110": "UNKNOWN_CANONICAL_ID",
    "E120": "CANONICAL_KIND_MISMATCH",
    "E125": "ALIAS_SUNSET_EXPIRED",
    "E130": "CANONICAL_VERSION_MISMATCH",
    "E140": "AMBIGUOUS_ALIAS",
    "E141": "TASK_DEPENDENCY_CYCLE",
    "E142": "TECH_STACK_MISMATCH",
    "E150": "SEED_MANIFEST_NOT_PROVIDED",
    "W110": "DEPRECATED_CANONICAL_USED",
    "W120": "ALIAS_DEPRECATED",
    "W130": "CANONICAL_REF_VERSION_OMITTED",
    "W140": "SEED_CONTENT_OVERLAP_LOW",
    "W150": "SEED_MANIFEST_NOT_PROVIDED",
    # Cross-artifact drift (2xx)
    "E210": "CROSS_ARTIFACT_DRIFT",
    "E211": "PARTIAL_DRIFT",
    # Proof / review closure (3xx)
    "E301": "MISSING_PROOF_CLOSURE",
    "E302": "UNPROVEN_VERIFIED_REVIEW",
    "E303": "CI_GATE_VIOLATION",
    "E304": "ROADMAP_TASK_UNCOVERED",
    "E305": "PLANNED_UNEXECUTED",
    "E306": "SEMANTIC_REVIEW_FR_MISMATCH",
    "E307": "BEHAVIOR_VALIDATION_PAIRING",
    "E308": "ANCHOR_SCOPE_DRIFT",
    "E309": "ANCHOR_CHECKLIST_DRIFT",
    "E310": "PROMPT_SCHEMA_DRIFT",
    "E311": "MISSING_ENUM_PROVENANCE",
    "E320": "STEP13_EXTENSION_ERROR",
    # Canonical registry (4xx)
    "E410": "CANONICAL_ALIAS_COLLISION",
    "E420": "INVALID_DEPRECATION_LIFECYCLE",
    "W421": "CANON_ID_COLLISION_PROJECT_WINS",
    "E422": "CORE_ENTRY_IN_PROJECT_CANON",
    # Spec content quality (5xx)
    "E510": "PLACEHOLDER_VALUE_FOUND",
    "E512": "ASSUMPTION_HAS_PLACEHOLDER",
    "E520": "UNRESOLVED_INPUT",
    "E521": "VALIDATOR_RUNTIME",
    "E530": "INVENTED_ENUM_OR_ID",
    "E535": "CONTRADICTORY_OUT_OF_SCOPE_FR",
    "E540": "SELF_OR_FORWARD_DEPENDENCY",
    "E541": "UNBOUND_CANONICAL_TERM",
    "E543": "STEP_METADATA_INCONSISTENT",
    "E550": "FORWARD_REPLAY_MISSING",
    "E551": "SCHEMA_ENUM_EXTRA",
    "E552": "MISSING_PAIRED_SCHEMA",
    "E553": "MISSING_ENUM_PATH",
    "E554": "CANON_ENUM_DRIFT",
    "E555": "SEMANTIC_COVERAGE_REGRESSION",
    "E560": "TRACEABILITY_GAP",
    "E561": "UNCOVERED_FR",
    "E562": "ORPHAN_MILESTONE",
    "E563": "CHECKLIST_ROADMAP_MISMATCH",
    "E564": "UNCOVERED_FR_API",
    "E565": "UNCOVERED_FR_FIXTURE",
    "E566": "UNCOVERED_FR_MILESTONE",
    "E567": "INCOMPLETE_MILESTONE_DECOMPOSITION",
    "E568": "UNCOVERED_CAPABILITY",
    "E569": "GOVERNANCE_PR_RULE_UNCOVERED",
    "E571": "ASSUMPTION_VAGUE_QUANTIFIER",
    "E572": "ASSUMPTION_COUNT_HIGH",
    "E573": "ASSUMPTION_UNBOUND_ID",
    "E575": "IMPL_PLAN_DELIVERABLE_UNCOVERED",
    "E576": "TASK_EXECUTION_MISSING",
    "E580": "SUBSTEP_DRIFT",
    "E581": "MILESTONE_REF_MISSING",
    "E582": "UNCOVERED_FR_REVIEW_COVERAGE",
    "E585": "DAG_CIRCULAR_DEPENDENCY",
    "W550": "SEMANTIC_COVERAGE_SKIP",
    "W551": "UNDECLARED_SEED",
    "W552": "POTENTIAL_UNREGISTERED_PAIRING",
    "W553": "SEED_STEP_OUT_OF_RANGE",
    "W560": "TRACEABILITY_GAP",
    "W561": "UNCOVERED_FR",
    "W562": "ORPHAN_MILESTONE",
    "W563": "CHECKLIST_ROADMAP_MISMATCH",
    "W564": "UNCOVERED_FR_API",
    "W565": "UNCOVERED_FR_FIXTURE",
    "W566": "UNCOVERED_FR_MILESTONE",
    "W567": "INCOMPLETE_MILESTONE_DECOMPOSITION",
    "W568": "UNCOVERED_CAPABILITY",
    "W569": "GOVERNANCE_PR_RULE_UNCOVERED",
    "W570": "GRACEFUL_SKIP",
    "W571": "ASSUMPTION_VAGUE_QUANTIFIER",
    "W572": "ASSUMPTION_COUNT_HIGH",
    "W573": "ASSUMPTION_UNBOUND_ID",
    "W574": "TECH_STACK_COHERENCE_MISMATCH",
    "W575": "IMPL_PLAN_DELIVERABLE_UNCOVERED",
    "W576": "TASK_EXECUTION_MISSING",
    "W580": "SUBSTEP_DRIFT",
    "W581": "MILESTONE_REF_MISSING",
    "W582": "UNCOVERED_FR_REVIEW_COVERAGE",
    "W583": "API_UNCOVERED_BY_THREAT",
    "W584": "REMEDIATION_TASK_LINK_UNKNOWN",
    "W585": "ANCHOR_DRIFT_SKIP",
    "W586": "ANCHOR_VALIDATOR_WRONG_ARTIFACT",
    "W587": "ANCHOR_DRIFT_CHECKS_STALE",
    "W588": "ANCHOR_MILESTONE_UNREADABLE",
    "W589": "ANCHOR_MILESTONE_MISSCHEMAED",
    # R9: Cross-step validation (59x)
    "E590": "CROSS_STEP_ID_NOT_FOUND",
    "E591": "EXTRACTION_INTENT_EMPTY",
    "E592": "COVERAGE_THRESHOLD_BREACH",
    "E593": "VAGUE_LANGUAGE_FREE_TEXT",
    "E594": "CONTENT_DERIVATION_LOW_OVERLAP",
    "E595": "CONTENT_STALENESS",
    "E596": "DAG_DEAD_END_PRODUCER",
    "E597": "EXTRACTION_INTENT_UPSTREAM_GAP",
    "E598": "EXTRACTION_INTENT_INVALID_REF",
    "E599": "DAG_CONSUMER_INCONSISTENCY",
    "W590": "CROSS_STEP_UPSTREAM_MISSING",
    "W591": "EXTRACTION_INTENT_EMPTY",
    "W592": "COVERAGE_THRESHOLD_WARN",
    "W593": "VAGUE_LANGUAGE_FREE_TEXT",
    "W594": "CONTENT_DERIVATION_LOW_OVERLAP",
    "W595": "CONTENT_STALENESS",
    "W596": "UNDECLARED_UPSTREAM_REF",
    "W597": "EXTRACTION_INTENT_VAGUE",
    "W598": "ID_STABILITY_REMOVAL",
    "W599": "EVIDENCE_TOO_SHORT",
    "W600": "VERIFIED_ACTION_NO_EVIDENCE",
    "W601": "EVIDENCE_NO_ARTIFACT_REF",
    "W602": "TECH_STACK_02_MISMATCH",
    "W603": "FILES_OUTSIDE_TASK_SCOPE",
    "E604": "TRACE_MATRIX_STALE",
    "W604": "TRACE_MATRIX_STALE",
    "W605": "TECH_STACK_02_MISSING",
    # Glossary parity (6xx)
    "E606": "GLOSSARY_PROPOSAL_DRIFT",
    "E607": "GLOSSARY_CANON_DRIFT",
    "W606": "GLOSSARY_CANON_ORPHAN",
    # Anchor context_path integrity (follows the W585-W589 anchor group;
    # W590-W606 are already allocated to unrelated semantics).
    "W607": "ANCHOR_CONTEXT_PATH_MISSING",
    # Legacy schema surfaced when a post-split host repo still declares the
    # pre-split schema on its anchor artifact.  Soft-warn only — schema
    # validation against vc:16-impl-context still passes, but host repos
    # need the signal to migrate per the 0.6.0 breaking-change entry.
    "W608": "ANCHOR_LEGACY_SCHEMA",
    # Misfiled anchor: an artifact_role="anchor" file landed inside
    # spec/impl_context/ instead of at spec/ root.  Routing
    # (validate.py:_refine_impl_context_substep) demotes the dispatch back
    # to "16" so the anchor validator runs, but every drift check then
    # resolves impl_context_dir to spec/impl_context/impl_context/ — which
    # does not exist — so E308/E309/W607/W588/W589 silently no-op.  Without
    # this warning the misfiling is invisible: the file passes the anchor
    # schema and emits zero drift errors despite contributing nothing to
    # cross-milestone drift detection.  W609 makes the misfiling
    # discoverable at spec-check time and tells the author where to move
    # the file.
    "W609": "ANCHOR_MISFILED",
    # Milestone plan checklist IDs that don't start with the prefix declared
    # in the anchor's milestone_index[].checklist_id_prefix.  Soft-warn
    # because the prefix is a namespace convention that prevents E309
    # collisions — violating it doesn't break anything immediately but
    # undermines the anchor's drift-prevention guarantee.
    "W610": "ANCHOR_PREFIX_VIOLATION",
    # All JSON files in impl_context/ were filtered out by W588/W589 (parse
    # failures or wrong $schema).  Cross-milestone E308/E309 drift detection
    # is completely suppressed because no milestone contexts survived filtering.
    # Without this warning, the anchor appears clean while contributing nothing
    # to drift detection.
    "W611": "ANCHOR_DRIFT_SUPPRESSED",
    # Milestone ID declared in milestone_index does not match any milestone in
    # 14_roadmap.json.  Phantom milestones bypass all downstream checks —
    # ownership, prefix, and scope drift detection are silently skipped for IDs
    # that don't exist in the roadmap.
    "W612": "ANCHOR_PHANTOM_MILESTONE",
    # Upstream backlog: ambiguity's impact[] matches none of the 4 classifier
    # rules (see analysis/upstream_backlog.py). Informational only — never
    # promoted (deliberately excluded from PROMOTABLE_PAIRS).
    "W613": "UPSTREAM_BACKLOG_UNCLASSIFIED",
}

# Maps W-codes to their E-code counterparts for dynamic promotion.
# Consumed by validate.py: SPECDEV_WARNINGS_AS_ERRORS=1 promotes all;
# SPECDEV_PROMOTE_CODES=W571,W593 promotes selectively.
# Non-promotable codes (W110/W120/W130/W140/W552/W570/W606) are excluded —
# their E-counterparts have different semantics or promotion is inappropriate.
PROMOTABLE_PAIRS = {
    # W550 SEMANTIC_COVERAGE_SKIP → E550 FORWARD_REPLAY_MISSING: both gate
    # on semantic coverage; the warning fires when coverage is skipped, the
    # error when it is provably missing — promotion is appropriate.
    "W550": "E550",
    "W560": "E560",
    # W561 (UNCOVERED_FR) is intentionally NOT in PROMOTABLE_PAIRS.
    # W561 is a legacy informational signal that co-fires with W566 for the
    # same condition (FR not covered by any milestone fr_refs). W566 is the
    # designated pairwise completeness code that is promoted. Including W561
    # here would cause double-promotion: one FR gap would generate both E561
    # and E566 under SPECDEV_WARNINGS_AS_ERRORS=1.
    "W562": "E562",
    "W563": "E563",
    "W564": "E564",
    "W565": "E565",
    "W566": "E566",
    "W567": "E567",
    "W568": "E568",
    "W569": "E569",
    "W571": "E571",
    "W572": "E572",
    "W573": "E573",
    "W575": "E575",
    "W576": "E576",
    "W580": "E580",
    "W581": "E581",
    "W582": "E582",
    "W150": "E150",
    "W590": "E590",
    "W591": "E591",
    "W592": "E592",
    "W593": "E593",
    "W594": "E594",
    "W595": "E595",
    # W597 EXTRACTION_INTENT_VAGUE → E597 EXTRACTION_INTENT_UPSTREAM_GAP:
    # both flag extraction-intent quality issues; vague entries are a softer
    # form of the upstream-gap error — promotion is appropriate.
    "W597": "E597",
}


def make_error(code: str, message: str, path: Optional[str] = None) -> SpecError:
    if code not in ERROR_CODES:
        raise ValueError(f"Unknown error code: {code}")
    return SpecError(code=code, message=message, path=path)


def render_errors(errors: list[SpecError]) -> list[str]:
    """Convert SpecError list to string list for backward compat."""
    return [e.render() for e in errors]


_RE_THREE_PART = re.compile(r"^([EW]\d{3})\s+(\S+)\s+(.*)")
_RE_TWO_PART = re.compile(r"^([EW]\d{3})\s+(.*)")


def ensure_spec_errors(items: Sequence[str | SpecError]) -> list[SpecError]:
    """Parse string errors into SpecError objects during transition.

    Parsing heuristics (applied in order):
    1. If item is already a SpecError, pass through unchanged.
    2. If item is a string matching ``^([EW]\\d{3})\\s+(\\S+)\\s+(.*)``:
       code=group(1), message=f"{group(2)} {group(3)}"
    3. If item is a string matching ``^([EW]\\d{3})\\s+(.*)``:
       code=group(1), message=group(2)
    4. Fallback: SpecError(code="E521", message=str(item))
    """
    result: list[SpecError] = []
    for item in items:
        if isinstance(item, SpecError):
            result.append(item)
            continue
        s = str(item)
        m = _RE_THREE_PART.match(s)
        if m:
            result.append(SpecError(code=m.group(1), message=f"{m.group(2)} {m.group(3)}"))
            continue
        m = _RE_TWO_PART.match(s)
        if m:
            result.append(SpecError(code=m.group(1), message=m.group(2)))
            continue
        result.append(SpecError(code="E521", message=s))
    return result


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
