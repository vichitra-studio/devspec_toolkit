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
    owner: Optional[str] = None
    node_id: Optional[str] = None
    target: Optional[str] = None
    """The link a finding is about, as ``<field>-><target id>``; part of the identity of a link finding, never printed."""
    route: Optional[tuple[str, str]] = None
    """The seed route a finding is about, as ``(seed id, step)``; the step gate reads it to tell whether an open item about the seed makes the finding wait."""

    def render(self) -> str:
        if self.path:
            return f"{self.code} {self.path} {self.message}"
        return f"{self.code} {self.message}"


def link_target(field: str, target: str) -> str:
    """The ``SpecError.target`` of a finding about the link *field* of a node to *target*: ``<field>-><target>``."""
    return f"{field}->{target}"


class FindingError(Exception):
    """An exception that carries one finding: ``error`` is the ``SpecError`` a command prints before exiting 1.

    The base of the graph library's refusals (``QueryTargetError``, ``RecipeError``, ``GitViewError``, ...), so a
    command catches this one class instead of listing each.  ``unknown_id`` is set by the raiser when the finding says that
    no node has the id the user typed; a command may then add what it knows about files it could not read.
    """

    def __init__(self, error: SpecError, *, unknown_id: bool = False) -> None:
        super().__init__(error.message)
        self.error = error
        self.unknown_id = unknown_id


# Codes removed in 1.2.0 (numbers are not reused; `docs/developers/error-codes.md`, "Removed Codes", says what replaced each):
#   forward replay and the seed overlap check: E550, W550, E555, W598, W140, W551;
#   the traceability closure and completeness checks: E535, E536, E560, E561, E562, E563, E564, E565, E568, E569, E575, E576
#   and their warnings W560, W561, W562, W563, W564, W565, W568, W569, W575, W576 (W566 and W567 are gone too: E566 and E567
#   stay, as errors computed from the graph);
#   the trace matrix and the coverage thresholds: E592, W592, E604, W604;
#   the proof and review checks of the step-16 validator, whose inputs the plan schema no longer has (a milestone closes
#   on the close gate, E810 to E814): E301, E302, E305, E306, E307, W599, W600, W601.
#   the assumption id scan and the derivation token-overlap check, which the graph replaced (an id in prose is E752,
#   derivation is `derives_from`): E573, W573, E594, W594.
# E303 stays: `governance-check` raises it for a commit message that does not match the governance rule.
# `tests/unit/core/test_error_code_registry.py` (REMOVED_CODES) fails if one of them is registered or written as a code literal again.
ERROR_CODES = {
    # Canonical integrity (1xx)
    "E110": "UNKNOWN_CANONICAL_ID",
    "E120": "CANONICAL_KIND_MISMATCH",
    "E125": "ALIAS_SUNSET_EXPIRED",
    "E130": "CANONICAL_VERSION_MISMATCH",
    "E140": "AMBIGUOUS_ALIAS",
    "E150": "SEED_MANIFEST_NOT_PROVIDED",
    "W110": "DEPRECATED_CANONICAL_USED",
    "W120": "ALIAS_DEPRECATED",
    "W130": "CANONICAL_REF_VERSION_OMITTED",
    "W150": "SEED_MANIFEST_NOT_PROVIDED",
    # Cross-artifact drift (2xx)
    "E210": "CROSS_ARTIFACT_DRIFT",
    "E211": "PARTIAL_DRIFT",
    # Proof / review closure (3xx)
    "E303": "COMMIT_MESSAGE_MISMATCH",
    "E304": "ROADMAP_TASK_UNCOVERED",
    "E308": "ANCHOR_SCOPE_DRIFT",
    "E309": "ANCHOR_CHECKLIST_DRIFT",
    "E310": "PROMPT_SCHEMA_DRIFT",
    "E311": "MISSING_ENUM_PROVENANCE",
    "E320": "STEP13_EXTENSION_ERROR",
    # Bindings and runs (33x, 35x): E330 to E334 are refusals of ``verify bind`` (E330 and E334 are also findings of the
    # record check, owner merge-check); W350 and W351 are warnings of ``verify run``.
    "E330": "BINDING_STAGE_MISMATCH",
    "E331": "BINDING_TARGET_NOT_VERIFIED",
    "E332": "BINDING_GUARD_INVALID",
    "E333": "BINDING_DUPLICATE_TARGET",
    "E334": "UNKNOWN_STAGE_FOR_ENVIRONMENT",
    # Third-party pins: E336 to E338 are findings of ``third-party check`` and refusals of ``third-party pin`` (owner
    # step 02); E339 stops a deploy and has no owner.
    "E336": "THIRD_PARTY_PIN_NOT_EXACT",
    "E337": "THIRD_PARTY_PIN_MISMATCH",
    "E338": "THIRD_PARTY_SOURCE_UNRESOLVED",
    "E339": "THIRD_PARTY_INSTALLED_MISMATCH",
    # Removal and proof: E341 and E342 are findings of the ``removal-rules`` check (owner step 14); E343 and E344 are the release
    # gate's (owner release-gate, computed by ``proof.realisation``); E347 and E348 are the findings of ``proof_errors`` (owner: the step of the node).
    "E341": "REMOVAL_FIXTURE_MISMATCH",
    "E342": "REMOVES_TARGET_PRESENT",
    "E343": "REALISATION_OUTDATED",
    "E344": "REALISATION_REMOVED",
    "E347": "VERIFIER_NO_VALID_EVIDENCE",
    "E348": "OBLIGATION_NOT_PROVEN",
    "W350": "SUBMODULE_DIRTY_NOT_COVERED",
    "W351": "RUN_CHANGED_CODE_TREE",
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
    "E540": "SELF_OR_FORWARD_DEPENDENCY",
    "E541": "UNBOUND_CANONICAL_TERM",
    "E543": "STEP_METADATA_INCONSISTENT",
    "E551": "SCHEMA_ENUM_EXTRA",
    "E552": "MISSING_PAIRED_SCHEMA",
    "E553": "MISSING_ENUM_PATH",
    "E554": "CANON_ENUM_DRIFT",
    "E566": "UNCOVERED_FR_MILESTONE",
    "E567": "INCOMPLETE_MILESTONE_DECOMPOSITION",
    "E571": "ASSUMPTION_VAGUE_QUANTIFIER",
    "E572": "ASSUMPTION_COUNT_HIGH",
    "E580": "SUBSTEP_DRIFT",
    "E585": "DAG_CIRCULAR_DEPENDENCY",
    "W552": "POTENTIAL_UNREGISTERED_PAIRING",
    "W553": "SEED_STEP_UNKNOWN",
    "W554": "HARDCODED_SEED_REFERENCE",
    # W555 STEP00_SEED_OUT_OF_SCOPE_THIN — warn-only, non-promotable.
    # W555 is intentionally excluded from PROMOTABLE_PAIRS so neither
    # SPECDEV_WARNINGS_AS_ERRORS nor SPECDEV_PROMOTE_CODES can escalate it.
    "W555": "STEP00_SEED_OUT_OF_SCOPE_THIN",
    "W570": "GRACEFUL_SKIP",
    "W571": "ASSUMPTION_VAGUE_QUANTIFIER",
    "W572": "ASSUMPTION_COUNT_HIGH",
    "W580": "SUBSTEP_DRIFT",
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
    "E593": "VAGUE_LANGUAGE_FREE_TEXT",
    "E595": "CONTENT_STALENESS",
    "E596": "DAG_DEAD_END_PRODUCER",
    "E597": "EXTRACTION_INTENT_UPSTREAM_GAP",
    "E598": "EXTRACTION_INTENT_INVALID_REF",
    "E599": "DAG_CONSUMER_INCONSISTENCY",
    "W590": "CROSS_STEP_UPSTREAM_MISSING",
    "W591": "EXTRACTION_INTENT_EMPTY",
    "W593": "VAGUE_LANGUAGE_FREE_TEXT",
    "W595": "CONTENT_STALENESS",
    "W596": "UNDECLARED_UPSTREAM_REF",
    "W597": "EXTRACTION_INTENT_VAGUE",
    "W603": "FILES_OUTSIDE_TASK_SCOPE",
    # Glossary parity (6xx)
    "E606": "GLOSSARY_PROPOSAL_DRIFT",
    "E607": "GLOSSARY_CANON_DRIFT",
    # Toolkit version gate (6xx)
    "E608": "TOOLKIT_VERSION_MISMATCH",
    "W606": "GLOSSARY_CANON_ORPHAN",
    # Legacy schema surfaced when a post-split host repo still declares the
    # pre-split schema on its anchor artifact.  Soft-warn only — schema
    # validation against vc:16-impl-context still passes, but host repos
    # need the signal to migrate per the 0.6.0 breaking-change entry.  Also
    # reported for a plan file in impl_context/ that has no `milestone` key.
    "W608": "ANCHOR_LEGACY_SCHEMA",
    # Misfiled anchor: an artifact_role="anchor" file landed inside
    # spec/impl_context/ instead of at spec/ root.  Routing
    # (core/step_paths.py:refine_impl_context_substep) demotes the dispatch back
    # to "16" so the anchor validator runs, but every drift check then
    # resolves impl_context_dir to spec/impl_context/impl_context/ — which
    # does not exist — so E308/E309/W588/W589 silently no-op.  Without
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
    # impl_context/ holds JSON files and none takes part in E308/E309 drift
    # detection (W588/W589/W608 filtered them all out), or a plan file names a
    # milestone that no anchor row is about.  Without this warning the anchor
    # appears clean while contributing nothing to drift detection.
    "W611": "ANCHOR_DRIFT_SUPPRESSED",
    # Upstream backlog: a legacy-shape ambiguity's impact[] matches none of the three
    # classifier rules (see analysis/upstream_backlog.py); a 1.2.0 open item has
    # no impact[] and never fires it. Informational only — never
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
    # DEVSPEC-123: upstream-backlog's --status filter (default "open") drops
    # resolved records from the per-bucket detail view without any indication
    # that anything was hidden -- the exact condition that made a real
    # 87-entry execution.emergent_ambiguities[] array look completely empty
    # to a caller who ran the bare command. Informational only (never
    # promoted, like W613): the filtering itself is correct behavior, this
    # just discloses that it happened.
    "W617": "UPSTREAM_BACKLOG_STATUS_FILTERED",
    # Open items (63x). W630 and W633 are warn-only and non-promotable: like W555 they are excluded from
    # PROMOTABLE_PAIRS (E630 and E633 do not exist), so SPECDEV_WARNINGS_AS_ERRORS and SPECDEV_PROMOTE_CODES
    # cannot turn an open-item warning into a step blocker.  E631 (merge) and E632 (close) are errors of their gate.
    "W630": "OPEN_ITEM",
    "E631": "OPEN_ITEM_AT_MERGE",
    "E632": "OPEN_ITEM_IN_PLAN",
    "W633": "OPEN_ITEM_LEGACY_TRIAGE",
    # Spec graph (7xx). E700-E704 are findings about the spec and carry an owner
    # and a node id; E705-E709 are command usage errors and carry neither.
    "E700": "LINK_TARGET_NOT_FOUND",
    "E701": "LINK_TARGET_WRONG_KIND",
    "E702": "LINK_POINTS_DOWNSTREAM",
    "E703": "LINK_CYCLE_SAME_STEP",
    "E704": "DUPLICATE_NODE_ID",
    "E705": "LIFECYCLE_CHANGE_REFUSED",
    "E706": "GRAPH_COMMAND_TARGET_UNKNOWN",
    "E707": "RECIPE_START_KIND_INVALID",
    "E708": "DIFF_REF_UNRESOLVED",
    "E709": "DIFF_REF_PREDATES_GRAPH_MODEL",
    # Trace lock (76x, 77x). E760 is a finding about the spec (owner merge-check); E761, E762, E763, E768, E771, E772,
    # E774, E778 and E882 are findings (an owner and a node id, or the merge check); E764, E765, E767, E769, E770 and
    # E773 are command refusals. E766 is unassigned (an unknown id is E706).
    "E760": "TRACE_LOCK_MALFORMED",
    "E761": "LINK_LOCK_ENTRY_MISSING",
    "E762": "LOCK_ENTRY_ORPHAN",
    "E763": "SUSPECT_LINK",
    "E764": "ATTEST_REFUSED_TARGET_SUSPECT",
    "E765": "ATTEST_REFUSED_HISTORICAL",
    "E767": "WRITE_REFUSED",
    "E768": "STORED_COMPUTED_FIELD",
    "E769": "LOCK_WRITE_CONFLICT",
    "E770": "RENAME_REFUSED",
    "E771": "ALIAS_COLLISION",
    "E772": "REPLACES_NAMES_LIVE_NODE",
    "E773": "STEP_NOT_READY",
    "E774": "RECORD_INVALID",
    "E778": "STALE_ALIAS_USE",
    # Graph role checks (74x): findings about the spec, each with an owner and a node id (E743 and E747 owned by a fixed
    # step).  E750, E751 and E753 are unassigned; E754..E759 are reserved.
    "E740": "NODE_DANGLING",
    "E741": "TERM_NOT_USED_BY_LABEL",
    "E742": "UNUSED_VERIFIER",
    "E743": "MISSING_VERIFIER",
    "E744": "CROSS_CUTTING_NOT_REFINED",
    "E745": "VERIFIER_DOES_NOT_VERIFY_REFINED",
    "E746": "SCAFFOLD_PATH_NOT_TRACKED",
    "E747": "SEED_NOT_ROUTED",
    "E748": "SEED_ROUTE_UNUSED",
    "E749": "SEED_LINK_NOT_ROUTED",
    "E752": "NODE_ID_IN_PROSE",
    # Review loop (850): ``specdev loop`` and ``specdev pass`` refuse a command with E850 and change nothing.
    "E850": "LOOP_REFUSED",
    # Migration (880 to 884): ``specdev align apply --auto`` refuses with E880 (a host the runner cannot start on) and
    # stops with E881 (a script broke an invariant; nothing was written); E884 is a finding of the changelog check (an
    # ``auto`` entry that names no script).  E882 is the baseline residue finding of the trace check; E883 is unassigned.
    "E880": "MIGRATION_PREFLIGHT",
    "E881": "MIGRATION_SCRIPT_INVARIANT",
    "E882": "MIGRATION_BASELINE_NOT_REATTESTED",
    "E884": "MIGRATION_CHANGELOG_SCRIPT_MISSING",
    # Merge gate (900 to 901): findings of ``spec-check --merge`` (owner merge-check).
    "E900": "MERGE_BASE_UNRESOLVED",
    "E901": "MERGE_BINDING_FAILED",
    # Release (910 to 914, 920 to 928): ``specdev release`` and ``release rollback`` refuse with E910 to E912 and E925 to
    # E927 (command usage errors, no owner).  The release gate reports E913 and E914 (re-checks of the close gate's and
    # the consumer step's classes: owners close-gate and consumer_step), E920 and E928 (owner release-gate); the
    # production-deploy gate of ``release check --stage prod`` reports E921, E923 and E924 (owner release-gate).
    "E910": "RELEASE_REPO_DIRTY",
    "E911": "RELEASE_TAG_PATTERN_UNDECLARED",
    "E912": "RELEASE_TAG_INVALID",
    "E913": "RELEASE_MILESTONE_UNSIGNED",
    "E914": "RELEASE_OBLIGATION_NOT_BUILT",
    "E920": "RELEASE_PREVIOUS_UNVERIFIED",
    "E921": "PROD_TAG_UNRESOLVED",
    "E923": "PROD_DELIVERY_NOT_BUILT",
    "E924": "PROD_RELIEVED_NODE_FAILS",
    "E925": "ROLLBACK_TAG_UNKNOWN",
    "E926": "ROLLBACK_REASON_EMPTY",
    "E927": "ROLLBACK_ALREADY_RECORDED",
    "E928": "RELEASE_UNREALISED_DESIGN_MILESTONE",
    "W720": "LINK_TO_DEPRECATED_NODE",
    # Host install and release warnings (930 to 938; none is promotable).  W930, W931, W932 and W935 are strings in
    # ``UpdateResult.warnings`` of ``specdev update`` (no owner); W933, W934 and W936 to W938 are findings of the release
    # gate and of ``release check --stage prod`` (owner release-gate).
    "W930": "HOST_TEMPLATE_DRIFT",
    "W931": "HOST_INSTALL_REFUSED",
    "W932": "HOST_RETIRED_COMMAND",
    "W933": "RELEASE_SCOPE_LISTED",
    "W934": "PROD_STAGING_SKIPPED",
    "W935": "HOST_SETUP_UNDECLARED",
    "W936": "RELEASE_STAGE_SKIPPED",
    "W937": "RELEASE_NO_PREVIOUS",
    "W938": "RELEASE_PREVIOUS_PREDATES_1_2_0",
    # Milestone lifecycle (8xx). E800 to E803, E820 to E824 are command refusals (no owner, no node; E820 is raised by the
    # plan and review writers, not by a validator).  E810 to E814 are the close gate's (owner close-gate) and E830 the
    # release gate's.  E827 is a finding of the ``frozen-plans`` check (owner step 16); W825 and W826 are findings of the
    # ``plan-records`` check (owner step 16) and W837 of the step-16 validator.
    "E800": "MILESTONE_NOT_STARTABLE",
    "E801": "MILESTONE_TRANSITION_INVALID",
    "E802": "DEFER_REASON_MISSING",
    "E803": "PLAN_MILESTONE_UNKNOWN",
    "E810": "CLOSE_CRITERION_UNREALISED",
    "E811": "CLOSE_CRITERION_UNPROVEN",
    "E812": "CLOSE_ITEM_NOT_EXECUTED",
    "E813": "CLOSE_REVIEW_NOT_VERIFIED",
    "E814": "CLOSE_NO_SIGNOFF",
    "E820": "PLAN_FROZEN",
    "E821": "RECORD_TARGET_UNKNOWN",
    "E822": "RECORD_ACTION_NAMES_VERIFIER",
    "E823": "REVIEW_RECORD_INVALID",
    "E824": "ATTEST_TARGET_NOT_ATTESTABLE",
    "E827": "PLAN_CHANGED_AFTER_CLOSE",
    "E830": "REVIEW_RULE_UNATTESTED",
    "W825": "EXECUTION_STALE",
    "W826": "PLAN_ITEM_REALISES_EXCLUDED_TASK",
    "W837": "PLAN_FILE_LARGE",
}

# Maps W-codes to their E-code counterparts for dynamic promotion.
# Consumed by validate.py: SPECDEV_WARNINGS_AS_ERRORS=1 promotes all;
# SPECDEV_PROMOTE_CODES=W571,W593 promotes selectively.
# Non-promotable codes are excluded: W110/W120/W130/W552/W553/W554/W590/
# W596/W597/W606 have E-counterparts with different semantics; W555
# (STEP00_SEED_OUT_OF_SCOPE_THIN) and W570
# (GRACEFUL_SKIP) have no E-counterpart at all; W617 (UPSTREAM_BACKLOG_STATUS_FILTERED) has no
# E-counterpart at all -- it is an informational nudge, not a hard failure.
# W720 (LINK_TO_DEPRECATED_NODE) likewise has no E-counterpart (no E720 exists).
# W630 (OPEN_ITEM) and W633 (OPEN_ITEM_LEGACY_TRIAGE) likewise have none (no E630 or E633 exists).
PROMOTABLE_PAIRS = {
    "W571": "E571",
    "W572": "E572",
    "W580": "E580",
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
    "W593": "E593",
    "W595": "E595",
    # W597 (EXTRACTION_INTENT_VAGUE) is intentionally NOT in PROMOTABLE_PAIRS.
    # E597 (EXTRACTION_INTENT_UPSTREAM_GAP) is a structurally different
    # condition — a required upstream artifact has NO intent entry at all —
    # not a fatal form of vague text. Promoting W597 to E597 would emit an
    # UPSTREAM_GAP code for a present-but-vague entry, mislabelling the defect
    # and pointing users at the wrong fix (add an entry vs. expand its text).
    # W597 has no semantically-correct E-counterpart, so it stays a warning.
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
    owner: Optional[str] = None,
    node_id: Optional[str] = None,
    target: Optional[str] = None,
    route: Optional[tuple[str, str]] = None,
) -> SpecError:
    if code not in ERROR_CODES:
        raise ValueError(f"Unknown error code: {code}")
    return SpecError(
        code=code, message=message, path=path,
        subcode=subcode, file=file, jq_path=jq_path, value=value,
        owner=owner, node_id=node_id, target=target, route=route,
    )


def refusal(code: str, message: str) -> FindingError:
    """The finding a command prints before it exits 1: *code* with *message*, no owner, no node."""
    return FindingError(make_error(code, message))


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
