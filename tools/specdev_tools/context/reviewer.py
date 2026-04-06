"""Two-pass structural + semantic review gate for freshly-emitted spec artifacts.

Implements A5 from the toolkit optimisation plan:
  - Pass 1: Structural review (zero LLM tokens) — ID coverage, reverse trace, AC coverage.
  - Pass 2: Semantic pair generation (heuristics, no LLM) — faithfulness, acceptance_gap,
            quantifier_weakening, seed_distillation, scope_completeness.

Public API:
    review_artifact(artifact_path, step_id, spec_dir, repo_root, entry_id=None) -> ReviewResult
"""
from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from ..core.registry import SchemaRegistry
from ._utils import find_step_schema_uri as _u_find_step_schema_uri
from ._utils import get_boilerplate_keys as _u_get_boilerplate_keys
from ._utils import merge_allof as _u_merge_allof

# ---------------------------------------------------------------------------
# Stopword list for faithfulness check.
# ---------------------------------------------------------------------------
_STOPWORDS: frozenset[str] = frozenset([
    "the", "and", "that", "this", "with", "from", "have", "will",
    "must", "shall", "should", "when", "then", "able", "been",
])

# ---------------------------------------------------------------------------
# Early-step IDs for seed_distillation check.
# ---------------------------------------------------------------------------
_SEED_STEPS: frozenset[str] = frozenset(["00", "01", "02", "02a", "03", "04"])

# ---------------------------------------------------------------------------
# Steps that produce checklist-style artifacts with linked_test_expectations
# and acceptance criteria mapped to checklist items.  The acceptance_gap and
# AC-coverage structural checks only make sense for these steps; running them
# on invariants (06), NFRs (07), or other non-checklist steps produces false
# positives because those artifacts use trace arrays, not linked_test_expectations.
# ---------------------------------------------------------------------------
_CHECKLIST_STEPS: frozenset[str] = frozenset(["13a", "16a", "16b", "16c"])

# ---------------------------------------------------------------------------
# Compiled regex patterns used by semantic checks.
# ---------------------------------------------------------------------------
_METRIC_PATTERN = re.compile(
    r'(\d+(?:\.\d+)?)\s*(ms|s|%|MB|GB|req/s|rps|rpm)',
    re.IGNORECASE,
)
_VAGUE_PATTERN = re.compile(
    r'\b(fast|quick|acceptable|reasonable|appropriate|adequate|sufficient)\b',
    re.IGNORECASE,
)
_COMMON_WORDS: frozenset[str] = frozenset([
    "The", "This", "That", "These", "Those", "When", "Then",
    "Must", "Shall", "Should", "Will", "With", "From",
])
_ACRONYM_PATTERN = re.compile(r'\b[A-Z]{2,}\b')
_PROPER_NOUN_PATTERN = re.compile(r'\b[A-Z][a-z]{2,}\b')


# ---------------------------------------------------------------------------
# Shared text-extraction helper (used by multiple semantic checks).
# ---------------------------------------------------------------------------

def _extract_all_strings(obj: Any) -> list[str]:
    """Flatten all string values from a JSON object recursively."""
    results: list[str] = []
    if isinstance(obj, str):
        results.append(obj)
    elif isinstance(obj, dict):
        for v in obj.values():
            results.extend(_extract_all_strings(v))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(_extract_all_strings(item))
    return results


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class SourceRef:
    """Reference to a source entity in an upstream spec file."""
    id: str          # e.g., "fr-payment-create"
    file: str        # e.g., "spec/04_fr_list.json"
    path: str        # e.g., ".functional_requirements[3].statement"
    text: str        # the actual text content


@dataclass
class TargetRef:
    """Reference to a target element in the artifact under review."""
    id: str          # e.g., "checklist-item-03"
    file: str        # e.g., "spec/16a_impl_planner.json"
    path: str        # e.g., ".plan.checklist[3].description"
    text: str        # the actual text content


@dataclass
class ReviewPair:
    """A single semantic review concern pairing a source claim with a target element."""
    check_type: str      # faithfulness | acceptance_gap | seed_distillation |
                         # quantifier_weakening | scope_completeness
    description: str     # human-readable description
    source: SourceRef
    target: TargetRef
    concern: str         # heuristic-generated hint for Claude


@dataclass
class StructuralReview:
    """Results from Pass 1 structural analysis."""
    upstream_coverage: dict  # {covered: [id...], dropped: [id...]}
    reverse_trace: dict      # {unjustified: [id...], scope_creep: [id...]}
    acceptance_criteria_coverage: dict  # {fr_id: {total: N, covered: N, missing: [...]}}


@dataclass
class ReviewResult:
    """Aggregated result of both review passes."""
    structural: StructuralReview
    semantic_pairs: list          # list[ReviewPair]
    verdict: str                  # PASS | NEEDS_SEMANTIC_REVIEW | FAIL
    token_cost: dict              # {structural: 0, semantic_total: N}


# ---------------------------------------------------------------------------
# Helpers — JSON traversal
# ---------------------------------------------------------------------------

def _collect_id_values(obj: Any, suffix: str = "_id") -> list[str]:
    """Recursively collect all string values whose key ends with `suffix`."""
    results: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k.endswith(suffix) and isinstance(v, str):
                results.append(v)
            results.extend(_collect_id_values(v, suffix))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(_collect_id_values(item, suffix))
    return results


def _collect_trace_ids(obj: Any) -> list[str]:
    """Recursively collect all IDs found inside 'trace' arrays.

    Handles both:
      - trace: [{id: "...", ...}, ...]          (list of objects with an 'id' key)
      - trace: ["fr-foo", "api-bar"]             (list of plain strings)
    """
    results: list[str] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == "trace" and isinstance(v, list):
                for item in v:
                    if isinstance(item, str):
                        results.append(item)
                    elif isinstance(item, dict) and "id" in item:
                        results.append(item["id"])
            else:
                results.extend(_collect_trace_ids(v))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(_collect_trace_ids(item))
    return results


def _find_items_by_key(obj: Any, key: str) -> list[Any]:
    """Recursively collect all values whose dict key equals `key`."""
    results: list[Any] = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == key:
                results.append(v)
            results.extend(_find_items_by_key(v, key))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(_find_items_by_key(item, key))
    return results


def _find_dicts_with_key(obj: Any, key: str, path: str = "") -> list[tuple[str, dict]]:
    """Recursively find all dicts that contain `key`, returning (path, dict) pairs."""
    results: list[tuple[str, dict]] = []
    if isinstance(obj, dict):
        if key in obj:
            results.append((path, obj))
        for k, v in obj.items():
            results.extend(_find_dicts_with_key(v, key, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            results.extend(_find_dicts_with_key(item, key, f"{path}[{i}]"))
    return results


# ---------------------------------------------------------------------------
# Helpers — spec file loading
# ---------------------------------------------------------------------------

def _load_json_safe(path: str) -> dict | None:
    """Load a JSON file, returning None on any error."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _load_step_order(repo_root: str) -> dict:
    """Load step_order.json from tools/, returning empty dict on failure."""
    path = os.path.join(repo_root, "tools", "step_order.json")
    data = _load_json_safe(path)
    return data if isinstance(data, dict) else {}


def _get_upstream_step_ids(step_id: str, step_order: dict) -> list[str]:
    """Return all step IDs that are upstream of step_id.

    Inverts the downstream_consumers map: upstream steps are those whose
    downstream_consumers list includes step_id.
    """
    downstream_consumers: dict = step_order.get("downstream_consumers", {})
    upstream: list[str] = []
    for sid, consumers in downstream_consumers.items():
        if isinstance(consumers, list) and step_id in consumers:
            upstream.append(sid)
    return upstream


def _find_spec_file(step_id: str, spec_dir: str) -> str | None:
    """Find the spec file for step_id in spec_dir by matching NN_*.json naming."""
    try:
        entries = os.listdir(spec_dir)
    except OSError:
        return None
    prefix = f"{step_id}_"
    for entry in entries:
        if entry.startswith(prefix) and entry.endswith(".json") and ".guide." not in entry:
            return os.path.join(spec_dir, entry)
    return None


def _load_upstream_specs(step_id: str, spec_dir: str, repo_root: str) -> list[tuple[str, dict]]:
    """Return list of (filepath, parsed_json) for all upstream spec files."""
    step_order = _load_step_order(repo_root)
    upstream_ids = _get_upstream_step_ids(step_id, step_order)
    specs: list[tuple[str, dict]] = []
    for uid in upstream_ids:
        fpath = _find_spec_file(uid, spec_dir)
        if fpath is None:
            continue
        data = _load_json_safe(fpath)
        if data is not None:
            specs.append((fpath, data))
    return specs


# ---------------------------------------------------------------------------
# Pass 1 — Structural review
# ---------------------------------------------------------------------------

def _run_structural_pass(
    artifact: dict,
    artifact_path: str,
    upstream_specs: list[tuple[str, dict]],
    step_id: str = "",
) -> StructuralReview:
    """Execute Pass 1: automated structural analysis with zero LLM token cost."""
    _ = artifact_path  # currently unused

    # --- Collect upstream entity IDs ---
    all_upstream_ids: set[str] = set()
    for _, spec_data in upstream_specs:
        ids = _collect_id_values(spec_data, suffix="_id")
        all_upstream_ids.update(ids)

    # For non-checklist steps, acceptance criteria (ac-*) are child entities of
    # FRs and are covered at FR granularity via trace arrays — not individually.
    # Including them in the coverage denominator causes a false FAIL because
    # ~80% of upstream IDs would always be "dropped".  Exclude them here; the
    # AC-coverage structural check (gated on _CHECKLIST_STEPS) handles them
    # separately for steps that do need individual AC tracing.
    if step_id not in _CHECKLIST_STEPS:
        all_upstream_ids = {uid for uid in all_upstream_ids if not uid.startswith("ac-")}

    # --- Collect artifact trace IDs ---
    artifact_trace_ids: set[str] = set(_collect_trace_ids(artifact))

    # Also collect IDs referenced in scope.apis and scope.components fields.
    # Invariant-style artifacts (step 06) express API and component coverage via
    # the scope object rather than trace arrays; both are valid traceability refs.
    for scope_dict in _find_items_by_key(artifact, "scope"):
        if isinstance(scope_dict, dict):
            for scope_key in ("apis", "components"):
                for item in scope_dict.get(scope_key, []):
                    if isinstance(item, str):
                        artifact_trace_ids.add(item)

    # --- ID coverage ---
    covered = sorted(all_upstream_ids & artifact_trace_ids)
    dropped = sorted(all_upstream_ids - artifact_trace_ids)

    upstream_coverage = {
        "covered": covered,
        "dropped": dropped,
    }

    # --- Reverse trace / scope creep ---
    unjustified = sorted(artifact_trace_ids - all_upstream_ids)
    reverse_trace = {
        "unjustified": unjustified,
        "scope_creep": list(unjustified),
    }

    # --- Acceptance criteria coverage ---
    # Only meaningful for checklist-style artifacts (steps 13a, 16a–16c) that
    # have linked_test_expectations fields mapping checklist items to AC IDs.
    # Non-checklist steps (invariants, NFRs, etc.) use trace arrays instead;
    # running this check on them always reports covered=0 (false positives).
    ac_coverage: dict[str, dict] = {}

    if step_id in _CHECKLIST_STEPS:
        # Build a set of all linked_test_expectation IDs referenced in artifact checklist items.
        artifact_linked_expectations: set[str] = set()
        for lte_list in _find_items_by_key(artifact, "linked_test_expectations"):
            if isinstance(lte_list, list):
                for item in lte_list:
                    if isinstance(item, str):
                        artifact_linked_expectations.add(item)
                    elif isinstance(item, dict) and "id" in item:
                        artifact_linked_expectations.add(item["id"])

        for _, spec_data in upstream_specs:
            # Find all objects that have both a key ending in '_id' and 'acceptance_criteria'.
            fr_dicts = _find_dicts_with_key(spec_data, "acceptance_criteria")
            for path, fr_dict in fr_dicts:
                # Attempt to identify the FR id.
                fr_id = (
                    fr_dict.get("fr_id")
                    or fr_dict.get("id")
                    or fr_dict.get("requirement_id")
                    or path
                )
                ac_list = fr_dict.get("acceptance_criteria", [])
                if not isinstance(ac_list, list):
                    continue
                total = len(ac_list)
                if total == 0:
                    continue
                missing: list[str] = []
                covered_count = 0
                for criterion in ac_list:
                    if isinstance(criterion, str):
                        crit_id = criterion
                    elif isinstance(criterion, dict):
                        crit_id = criterion.get("id") or criterion.get("criterion_id") or ""
                    else:
                        continue
                    if crit_id and crit_id in artifact_linked_expectations:
                        covered_count += 1
                    else:
                        if crit_id:
                            missing.append(crit_id)
                ac_coverage[str(fr_id)] = {
                    "total": total,
                    "covered": covered_count,
                    "missing": missing,
                }

    return StructuralReview(
        upstream_coverage=upstream_coverage,
        reverse_trace=reverse_trace,
        acceptance_criteria_coverage=ac_coverage,
    )


# ---------------------------------------------------------------------------
# Pass 2 — Semantic pair generation (heuristics, no LLM)
# ---------------------------------------------------------------------------

def _tokenize(text: str) -> set[str]:
    """Lowercase word tokenization, stripping non-alphanumeric chars."""
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _jaccard(a: set[str], b: set[str]) -> float:
    """Compute Jaccard similarity between two word sets."""
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _key_nouns(text: str) -> set[str]:
    """Extract key nouns: words longer than 4 chars, not in stopwords."""
    words = re.findall(r"[a-zA-Z]{5,}", text)
    return {w.lower() for w in words if w.lower() not in _STOPWORDS}


def _check_faithfulness(
    artifact: dict,
    artifact_path: str,
    upstream_specs: list[tuple[str, dict]],
) -> list[ReviewPair]:
    """Check 1: does emitted text preserve upstream FR meaning?"""
    pairs: list[ReviewPair] = []

    # Collect (fr_id, statement, source_file, source_path) from upstream specs.
    fr_statements: list[tuple[str, str, str, str]] = []
    for fpath, spec_data in upstream_specs:
        fr_items = _find_dicts_with_key(spec_data, "statement")
        for path, d in fr_items:
            fr_id = (
                d.get("fr_id")
                or d.get("id")
                or d.get("requirement_id")
                or path
            )
            statement = d.get("statement", "")
            if statement:
                fr_statements.append((str(fr_id), statement, fpath, path))

    # Find artifact elements that reference each fr_id.
    for fr_id, statement, src_file, src_path in fr_statements:
        source_nouns = _key_nouns(statement)
        if len(source_nouns) < 3:
            continue

        # Find matching artifact elements by fr_id reference.
        artifact_matches = _find_dicts_with_key(artifact, "fr_id")
        matched_text = ""
        matched_path = ""
        matched_id = ""
        for apath, adict in artifact_matches:
            if adict.get("fr_id") == fr_id:
                matched_text = (
                    adict.get("description")
                    or adict.get("statement")
                    or adict.get("text")
                    or adict.get("title")
                    or ""
                )
                matched_id = adict.get("id") or adict.get("fr_id") or apath
                matched_path = apath
                break

        if not matched_text:
            continue

        artifact_nouns = _key_nouns(matched_text)
        missing_nouns = source_nouns - artifact_nouns

        if len(missing_nouns) > 2:
            pairs.append(ReviewPair(
                check_type="faithfulness",
                description=f"FR '{fr_id}' — key nouns absent from artifact element",
                source=SourceRef(
                    id=fr_id,
                    file=src_file,
                    path=src_path,
                    text=statement,
                ),
                target=TargetRef(
                    id=str(matched_id),
                    file=artifact_path,
                    path=matched_path,
                    text=matched_text,
                ),
                concern=f"Missing key nouns: {sorted(missing_nouns)}",
            ))

    return pairs


def _check_acceptance_gap(
    artifact: dict,
    artifact_path: str,
    upstream_specs: list[tuple[str, dict]],
) -> list[ReviewPair]:
    """Check 2: is an acceptance criterion unmatched by any checklist item?"""
    pairs: list[ReviewPair] = []

    # Collect checklist item descriptions from artifact.
    checklist_texts: list[tuple[str, str, str]] = []  # (id, path, text)
    for cpath, cdict in _find_dicts_with_key(artifact, "description"):
        cid = cdict.get("id") or cdict.get("item_id") or cpath
        ctext = cdict.get("description", "")
        if ctext:
            checklist_texts.append((str(cid), cpath, ctext))

    for fpath, spec_data in upstream_specs:
        ac_dicts = _find_dicts_with_key(spec_data, "acceptance_criteria")
        for src_path, fr_dict in ac_dicts:
            fr_id = (
                fr_dict.get("fr_id")
                or fr_dict.get("id")
                or fr_dict.get("requirement_id")
                or src_path
            )
            ac_list = fr_dict.get("acceptance_criteria", [])
            if not isinstance(ac_list, list):
                continue
            for criterion in ac_list:
                if isinstance(criterion, str):
                    crit_text = criterion
                    crit_id = criterion[:50]
                elif isinstance(criterion, dict):
                    crit_text = (
                        criterion.get("description")
                        or criterion.get("text")
                        or criterion.get("criterion")
                        or ""
                    )
                    crit_id = criterion.get("id") or criterion.get("criterion_id") or crit_text[:50]
                else:
                    continue

                if not crit_text:
                    continue

                crit_words = _tokenize(crit_text)
                if not crit_words:
                    continue

                # Find max Jaccard across all checklist items.
                max_j = 0.0
                best_item: tuple[str, str, str] | None = None
                for item_id, item_path, item_text in checklist_texts:
                    j = _jaccard(crit_words, _tokenize(item_text))
                    if j > max_j:
                        max_j = j
                        best_item = (item_id, item_path, item_text)

                if max_j < 0.25:
                    target_id = best_item[0] if best_item else "(none)"
                    target_path = best_item[1] if best_item else ""
                    target_text = best_item[2] if best_item else ""
                    pairs.append(ReviewPair(
                        check_type="acceptance_gap",
                        description=(
                            f"Acceptance criterion for '{fr_id}' has no matching checklist item "
                            f"(best Jaccard={max_j:.2f})"
                        ),
                        source=SourceRef(
                            id=str(crit_id),
                            file=fpath,
                            path=src_path,
                            text=crit_text,
                        ),
                        target=TargetRef(
                            id=target_id,
                            file=artifact_path,
                            path=target_path,
                            text=target_text,
                        ),
                        concern="No checklist item addresses this criterion",
                    ))

    return pairs


def _check_quantifier_weakening(
    artifact: dict,
    artifact_path: str,
    upstream_specs: list[tuple[str, dict]],
) -> list[ReviewPair]:
    """Check 3: was a specific metric replaced by vague language?"""
    pairs: list[ReviewPair] = []

    artifact_texts = _extract_all_strings(artifact)
    artifact_combined = " ".join(artifact_texts)

    for fpath, spec_data in upstream_specs:
        upstream_texts = _extract_all_strings(spec_data)
        for utext in upstream_texts:
            for match in _METRIC_PATTERN.finditer(utext):
                metric_str = match.group(0)
                number = match.group(1)
                unit = match.group(2)
                # Check if the artifact contains the same number+unit pattern.
                if not re.search(
                    re.escape(number) + r'\s*' + re.escape(unit),
                    artifact_combined,
                    re.IGNORECASE,
                ):
                    # Check if artifact has vague language nearby.
                    vague_matches = _VAGUE_PATTERN.findall(artifact_combined)
                    if len(set(vague_matches)) >= 2:
                        pairs.append(ReviewPair(
                            check_type="quantifier_weakening",
                            description=(
                                f"Specific metric '{metric_str}' from upstream not found in artifact"
                            ),
                            source=SourceRef(
                                id=metric_str,
                                file=fpath,
                                path="(text scan)",
                                text=utext[:200],
                            ),
                            target=TargetRef(
                                id="(artifact)",
                                file=artifact_path,
                                path="(text scan)",
                                text=artifact_combined[:200],
                            ),
                            concern=(
                                f"Upstream specifies '{metric_str}' but artifact contains vague "
                                f"language (fast/quick/acceptable/etc.) instead"
                            ),
                        ))
                        break  # one pair per upstream text snippet is enough

    return pairs


def _check_seed_distillation(
    artifact: dict,
    artifact_path: str,
    step_id: str,
    spec_dir: str,
    repo_root: str,
) -> list[ReviewPair]:
    """Check 4: were seed requirements faithfully captured? (Only steps 00–04.)"""
    if step_id not in _SEED_STEPS:
        return []

    pairs: list[ReviewPair] = []

    # Locate seed docs: seed_overview.md and seed_tech_stack.md
    seed_files: list[str] = []
    seen_seed_paths: set[str] = set()
    for candidate_dir in [spec_dir, os.path.dirname(spec_dir), repo_root]:
        for seed_name in ["seed_overview.md", "seed_tech_stack.md"]:
            seed_path = os.path.join(candidate_dir, seed_name)
            if os.path.isfile(seed_path) and seed_path not in seen_seed_paths:
                seen_seed_paths.add(seed_path)
                seed_files.append(seed_path)

    if not seed_files:
        return []

    artifact_combined = " ".join(_extract_all_strings(artifact))

    for seed_path in seed_files:
        try:
            with open(seed_path, "r", encoding="utf-8") as f:
                seed_text = f.read()
        except OSError:
            continue

        # Extract acronyms and proper nouns from seed.
        acronyms = set(_ACRONYM_PATTERN.findall(seed_text))
        proper_nouns = set(_PROPER_NOUN_PATTERN.findall(seed_text))
        key_terms = acronyms | proper_nouns

        # Filter out common English proper nouns that are not domain-specific.
        key_terms -= _COMMON_WORDS

        if not key_terms:
            continue

        missing_terms = {
            term for term in key_terms
            if term not in artifact_combined
        }

        if missing_terms:
            pairs.append(ReviewPair(
                check_type="seed_distillation",
                description=(
                    f"Seed doc '{os.path.basename(seed_path)}' terms not found in artifact"
                ),
                source=SourceRef(
                    id=os.path.basename(seed_path),
                    file=seed_path,
                    path="(full document)",
                    text=seed_text[:300],
                ),
                target=TargetRef(
                    id="(artifact)",
                    file=artifact_path,
                    path="(full document)",
                    text=artifact_combined[:200],
                ),
                concern=f"Missing key terms from seed: {sorted(missing_terms)[:20]}",
            ))

    return pairs


def _check_scope_completeness(
    artifact: dict,
    artifact_path: str,
    step_id: str,
    repo_root: str,
) -> list[ReviewPair]:
    """Check 5: are expected output fields (from schema) present in the artifact?"""
    pairs: list[ReviewPair] = []

    try:
        registry = SchemaRegistry(repo_root)
        schema_uri = _u_find_step_schema_uri(step_id, registry)
        if not schema_uri:
            # Fallback: try the artifact's own $schema field
            schema_uri = artifact.get("$schema")
        if not schema_uri:
            return []
        schema = registry.load(schema_uri)
    except (FileNotFoundError, Exception):
        return []

    boilerplate = _u_get_boilerplate_keys(registry)

    # Merge allOf branches (handles $ref resolution via SchemaRegistry).
    merged = _u_merge_allof(schema, registry)
    props = merged.get("properties", {})
    schema_required = merged.get("required", [])

    required_keys: list[str] = [
        key for key in schema_required if key not in boilerplate
    ]

    # If no explicit required list, fall back to all merged properties.
    if not required_keys:
        required_keys = [key for key in props if key not in boilerplate]

    artifact_keys = set(artifact.keys())

    for key in required_keys:
        if key not in artifact_keys:
            pairs.append(ReviewPair(
                check_type="scope_completeness",
                description=f"Required field '{key}' (from step schema) missing from artifact",
                source=SourceRef(
                    id=schema_uri,
                    file=f"schema/{step_id}_*.schema.json",
                    path=f".properties.{key}",
                    text=f"Required schema field: {key}",
                ),
                target=TargetRef(
                    id="(artifact root)",
                    file=artifact_path,
                    path=".",
                    text=f"Artifact top-level keys: {sorted(artifact_keys)}",
                ),
                concern=f"Field '{key}' is required by the step schema but absent from the artifact",
            ))

    return pairs


# ---------------------------------------------------------------------------
# Verdict computation
# ---------------------------------------------------------------------------

def _compute_verdict(structural: StructuralReview, semantic_pairs: list) -> str:
    """Determine overall verdict from structural results and semantic pairs.

    - FAIL if dropped fraction > 0.20 (more than 20% of upstream IDs dropped)
    - NEEDS_SEMANTIC_REVIEW if any semantic pairs were generated
    - PASS otherwise
    """
    dropped = structural.upstream_coverage.get("dropped", [])
    covered = structural.upstream_coverage.get("covered", [])
    total_upstream = len(dropped) + len(covered)

    if total_upstream > 0 and len(dropped) > 0:
        dropped_fraction = len(dropped) / total_upstream
        if dropped_fraction > 0.20:
            return "FAIL"

    if semantic_pairs:
        return "NEEDS_SEMANTIC_REVIEW"

    return "PASS"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def review_artifact(
    artifact_path: str,
    step_id: str,
    spec_dir: str,
    repo_root: str,
    entry_id: str | None = None,
) -> ReviewResult:
    """Run a two-pass structural + semantic review on a freshly-emitted spec artifact.

    Args:
        artifact_path: Absolute or relative path to the artifact JSON file.
        step_id:       Step identifier (e.g., "04", "16a").
        spec_dir:      Directory containing spec/*.json files.
        repo_root:     Root of the devspec_toolkit (for schema_registry, step_order).
        entry_id:      Optional entity ID to scope the review (currently informational).

    Returns:
        ReviewResult with structural analysis, semantic pairs, verdict, and token cost.
        Returns a minimal PASS result if the artifact cannot be read.
    """
    # --- Load artifact ---
    _ = entry_id  # currently informational; future: scope-filter structural pass
    artifact = _load_json_safe(artifact_path)
    if artifact is None:
        empty_structural = StructuralReview(
            upstream_coverage={"covered": [], "dropped": []},
            reverse_trace={"unjustified": [], "scope_creep": []},
            acceptance_criteria_coverage={},
        )
        return ReviewResult(
            structural=empty_structural,
            semantic_pairs=[],
            verdict="PASS",
            token_cost={"structural": 0, "semantic_total": 0},
        )

    # Load upstream specs once for both passes.
    upstream_specs = _load_upstream_specs(step_id, spec_dir, repo_root)

    # --- Pass 1: Structural ---
    structural = _run_structural_pass(
        artifact=artifact,
        artifact_path=artifact_path,
        upstream_specs=upstream_specs,
        step_id=step_id,
    )

    semantic_pairs: list[ReviewPair] = []

    semantic_pairs.extend(
        _check_faithfulness(artifact, artifact_path, upstream_specs)
    )
    # acceptance_gap compares AC scenario text to checklist item descriptions via
    # Jaccard similarity.  It is only meaningful for checklist-style steps (13a,
    # 16a–16c); for all other steps the vocabulary mismatch produces noise.
    if step_id in _CHECKLIST_STEPS:
        semantic_pairs.extend(
            _check_acceptance_gap(artifact, artifact_path, upstream_specs)
        )
    semantic_pairs.extend(
        _check_quantifier_weakening(artifact, artifact_path, upstream_specs)
    )
    semantic_pairs.extend(
        _check_seed_distillation(artifact, artifact_path, step_id, spec_dir, repo_root)
    )
    semantic_pairs.extend(
        _check_scope_completeness(artifact, artifact_path, step_id, repo_root)
    )

    # --- Verdict ---
    verdict = _compute_verdict(structural, semantic_pairs)

    # --- Token cost (estimated; structural is always 0 LLM tokens) ---
    token_cost = {
        "structural": 0,
        "semantic_total": len(semantic_pairs) * 50,
    }

    return ReviewResult(
        structural=structural,
        semantic_pairs=semantic_pairs,
        verdict=verdict,
        token_cost=token_cost,
    )
