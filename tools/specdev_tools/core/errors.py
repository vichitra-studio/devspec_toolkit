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
    subcode: Optional[str] = None
    file: Optional[str] = None
    jq_path: Optional[str] = None
    value: Optional[str] = None

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
    "W553": "SEED_STEP_UNKNOWN",
    "W554": "HARDCODED_SEED_REFERENCE",
    # W555 STEP00_SEED_OUT_OF_SCOPE_THIN — warn-only, non-promotable.
    # E555 is SEMANTIC_COVERAGE_REGRESSION (different semantic); W555 is intentionally
    # excluded from PROMOTABLE_PAIRS so neither SPECDEV_WARNINGS_AS_ERRORS nor
    # SPECDEV_PROMOTE_CODES can escalate it.
    "W555": "STEP00_SEED_OUT_OF_SCOPE_THIN",
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
    # Toolkit version gate (6xx)
    "E608": "TOOLKIT_VERSION_MISMATCH",
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
    # Registry checks (R001–R003 / 620–622) and R004 / W614
    # Checks performed by `specdev registry-check` and folded into `spec-check`.
    "E620": "REGISTRY_MISSING_STEP",     # R001: step in step_order.json not registered (moved to toolkit T-step-registry-coverage)
    "E621": "REGISTRY_PHANTOM_BASENAME", # R002: registered basename not in extraction_paths.json
    "E622": "REGISTRY_DRIFT",            # R003: registered (array_path, id_field) doesn't match live file
    # R004: host-side novelty detection — array with id-pattern items not declared in registry.
    # Severity is WARNING (not error) because the generator may not yet cover the new array.
    "W614": "UNREGISTERED_ARRAY",        # R004: host spec has array with *_id items unknown to toolkit registry
    # DEVSPEC-89: invariant↔threat drift detection (61x)
    # W615 fires when a step-06 invariant has a risk_category_ref but no step-11 threat
    # mitigation references it — indicating the invariant is not exercised by any threat.
    # E615 is its promotable counterpart (SPECDEV_WARNINGS_AS_ERRORS or SPECDEV_PROMOTE_CODES=W615).
    "W615": "INVARIANT_UNEXERCISED_BY_THREAT",
    "E615": "INVARIANT_UNEXERCISED_BY_THREAT",
}

# Maps W-codes to their E-code counterparts for dynamic promotion.
# Consumed by validate.py: SPECDEV_WARNINGS_AS_ERRORS=1 promotes all;
# SPECDEV_PROMOTE_CODES=W571,W593 promotes selectively.
# Non-promotable codes are excluded: W110/W120/W130/W140/W552/W553/W554/W555/W590/
# W596/W597/W606 have E-counterparts with different semantics; W570
# (GRACEFUL_SKIP) has no E-counterpart at all; W604 (TRACE_MATRIX_STALE) shares
# its name with the registered-but-unemitted E604 and stays advisory (see the
# inline W604 note below).
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
    # W590 (CROSS_STEP_UPSTREAM_MISSING) is intentionally NOT in PROMOTABLE_PAIRS.
    # E590 (CROSS_STEP_ID_NOT_FOUND) is a structurally different condition — a
    # referenced ID is absent from a *present* upstream file — not a fatal form
    # of "upstream file missing". Promoting W590 to E590 would emit
    # CROSS_STEP_ID_NOT_FOUND for a check that never ran (the file was absent),
    # mislabelling the defect and pointing users at the wrong fix (generate the
    # missing artifact vs. fix a broken ID reference). W590 has no
    # semantically-correct E-counterpart at this time; a fatal "upstream missing"
    # would need a new dedicated E-code rather than reusing E590.
    "W591": "E591",
    "W592": "E592",
    "W593": "E593",
    "W594": "E594",
    "W595": "E595",
    # W597 (EXTRACTION_INTENT_VAGUE) is intentionally NOT in PROMOTABLE_PAIRS.
    # E597 (EXTRACTION_INTENT_UPSTREAM_GAP) is a structurally different
    # condition — a required upstream artifact has NO intent entry at all —
    # not a fatal form of vague text. Promoting W597 to E597 would emit an
    # UPSTREAM_GAP code for a present-but-vague entry, mislabelling the defect
    # and pointing users at the wrong fix (add an entry vs. expand its text).
    # W597 has no semantically-correct E-counterpart, so it stays a warning.
    # W604 (TRACE_MATRIX_STALE) is intentionally NOT in PROMOTABLE_PAIRS.
    # Only W604 is emitted — by the step_14 staleness check, when
    # trace_matrix.json is missing or older than 14_roadmap.json (an mtime-based
    # freshness heuristic that can false-positive on checkout/touch order). E604
    # is registered under the same name as the nominal error form but is never
    # emitted by any code path, and staleness is advisory (regenerate the matrix)
    # rather than a hard correctness failure — so W604 stays a warning and E604
    # is not wired to promotion.
    # W615 INVARIANT_UNEXERCISED_BY_THREAT → E615: step-06 invariant with a
    # risk_category_ref is not referenced by any step-11 threat mitigation.
    "W615": "E615",
}


def make_error(
    code: str,
    message: str,
    path: Optional[str] = None,
    *,
    subcode: Optional[str] = None,
    file: Optional[str] = None,
    jq_path: Optional[str] = None,
    value: Optional[str] = None,
) -> SpecError:
    if code not in ERROR_CODES:
        raise ValueError(f"Unknown error code: {code}")
    return SpecError(
        code=code, message=message, path=path,
        subcode=subcode, file=file, jq_path=jq_path, value=value,
    )


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
