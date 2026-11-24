"""Registry generator for entry_key_registry.json and extraction_paths.json.

``run`` (the ``registry-generate`` command) also writes step_order.json, cli_commands.json and the
schema-change checklist, each built by its own module.

Implements W3-T1: programmatically derives the entry-key registry and
extraction-paths from toolkit schemas (schema/*.schema.json), replacing the
previously hand-curated spec/entry_key_registry.json.

Output is byte-deterministic across runs (sort_keys=True, indent=2, trailing
newline).  ``registry`` keys follow step_order.json::steps[] ordering;
``arrays[]`` entries follow schema-declaration order (Python 3.7+ dict ordering
preserved by json.load).

Design constraints:
  - Sentinel arrays (canonical_refs_used, canonical_proposals) are listed only
    at the top-level _sentinels key, NOT per-file.
  - Basename overrides: schema name ≠ spec basename in two cases:
      * step 13: schema is 13_extension_manifest.schema.json
                 spec basename is 13_extension_manifest.json
      * step 16: two schemas exist (16_impl_context + 16_anchor);
                 16_impl_context.schema.json is the step host and
                 16_anchor.schema.json (``STEP_EXTRA_HOSTS``) is a second host
                 whose annotation entries register under the same spec file.
  - Steps 16b and 16c have no schema and no node kind of their own: their records are blocks
    inside the plan file, registered under step 16a.  They are listed in
    ``steps_without_entry_arrays``.  Step 16a has no schema either, but its ``plan-item`` kind is
    registered through the ``files`` glob of an ``x-node`` of step 16, so it is not listed there.

Every kind is declared by an ``x-node`` object (see registry/annotation_scan.py).  A schema file
that declares ``x-node`` at a definition site inside itself is a host: its kinds, paths and id
fields are the declared ones.  A shared ``schema/core`` node reached only by ``$ref`` is added to
the host's entries once per occurrence.  No kind or id field is guessed from a schema's shape.
"""
from __future__ import annotations

import glob
import json
import os
from pathlib import Path
from typing import Any

from specdev_tools.core.entry_key_registry import join_nested_path
from specdev_tools.core.schema_nav import effective_schema as _schema_nav_effective_schema
from specdev_tools.core.step_paths import PLAN_FILE_KEY
from specdev_tools.registry.annotation_scan import AnnotationScan, HostScan, scan_annotations
from specdev_tools.registry.annotations import (
    AnnotationDecls,
    AnnotationError,
    collect_annotations,
    lint_annotations,
)
from specdev_tools.registry.schema_checklist import generate_checklist
from specdev_tools.registry.step_order_gen import (
    StepOrderError,
    annotated_steps,
    build_step_order_document,
    declared_edge_pairs,
    derive_from_decls,
    load_hand_kept,
    load_steps,
)


# ---------------------------------------------------------------------------
# Constants / overrides
# ---------------------------------------------------------------------------

#: Sentinels: array names that appear across multiple spec files and are always
#: corpus-excluded.  Only emitted at top-level _sentinels, not per-file.
#: Also includes cross-reference arrays that need suppression in the W614
#: registry-check scanner (``out_of_scope`` lists of ids held by another step).
SENTINEL_ARRAYS: tuple[str, ...] = ("canonical_proposals", "canonical_refs_used", "out_of_scope")

#: Map step_id → spec_file_basename when schema filename ≠ spec basename.
STEP_BASENAME_OVERRIDES: dict[str, str] = {
    "13": "13_extension_manifest.json",
}

#: Schema files to skip entirely (not the canonical spec file for any step).
SCHEMA_SKIP: frozenset[str] = frozenset([
    "16_anchor.schema.json",          # a second host of step 16 (STEP_EXTRA_HOSTS), not its step schema
    "seed_manifest.schema.json",      # seed manifest, not a step spec
    "seed_requirements.schema.json",  # seed requirements, not a step spec
    "step_order.schema.json",         # step_order, not a step spec
])

#: Schema files that are a second host of a step: their annotation entries register under the
#: step's own spec file.  Key: step id.
STEP_EXTRA_HOSTS: dict[str, tuple[str, ...]] = {
    "16": ("16_anchor.schema.json",),
}

#: Host schemas that describe per-milestone files, not the step's own spec file: every entry of
#: such a host without its own ``files`` registers under this glob, for this step.  Key: schema
#: path relative to the toolkit root.  (``16_impl_context.schema.json`` is the plan-file schema;
#: the anchor file ``16_impl_context.json`` is ``16_anchor.schema.json``.)
PLAN_FILE_HOSTS: dict[str, tuple[str, str]] = {
    "schema/16_impl_context.schema.json": ("16a", PLAN_FILE_KEY),
}

#: Steps with no schema and no node kind of their own: their records are blocks inside the plan file.
STEPS_INSIDE_PLAN_FILE: frozenset[str] = frozenset(["16b", "16c"])

#: Rationale of a step in ``STEPS_INSIDE_PLAN_FILE``.
INSIDE_PLAN_FILE_RATIONALE = "no node kind of its own: its records are blocks inside the plan file, registered under step 16a"

#: Format version for the generated registry.
FORMAT_VERSION = "1.1.0"

#: Note embedded in _note field of generated registry.
REGISTRY_NOTE = (
    "Generated by specdev registry-generate from devspec_toolkit/schema/*.schema.json. "
    "Do not hand-edit."
)


# ---------------------------------------------------------------------------
# Schema loading and $ref resolution
# ---------------------------------------------------------------------------

def _load_json(path: str) -> Any:
    """Load JSON from path, raising FileNotFoundError or json.JSONDecodeError."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _get_all_properties(schema: dict[str, Any]) -> dict[str, Any]:
    """Return merged top-level properties from a schema, collapsing allOf blocks.

    Preserves insertion order (Python 3.7+), which is the schema-declaration
    order.  Later allOf entries override earlier ones if keys collide (rare).
    A property that only a ``oneOf``/``anyOf``/``then``/``else`` branch declares
    is added under the allOf-only ones; the allOf-only definition wins when both
    declare a key (a ``then`` branch of step 13 restates ``extensions`` without
    ``items``).

    Thin adapter over ``schema_nav.effective_schema`` (called with conditionals
    OFF and ON, no-op resolver).  Generate intentionally does NOT resolve the ``vc:core:step-base``
    ``$ref`` — only inline step-specific top-level properties are wanted.  The
    no-op resolver returns None (non-dict) for any ``$ref`` node, causing
    effective_schema to treat that branch as empty — same as before.

    Projects ``["properties"]`` only; ``["required"]`` is discarded (generate
    never reads required; the helper always sets ``required=[]``).
    """
    # No-op resolver: returns None (non-dict) for any $ref node so that
    # effective_schema skips bare-$ref branches without resolving them.
    # MUST return non-dict (None) — not the node itself — per the helper contract.
    def _noop_resolver(_node: dict) -> None:
        return None

    base = _schema_nav_effective_schema(schema, _noop_resolver, include_conditionals=False)
    full = _schema_nav_effective_schema(schema, _noop_resolver, include_conditionals=True)
    return {**full["properties"], **base["properties"]}


# ---------------------------------------------------------------------------
# Step → schema mapping
# ---------------------------------------------------------------------------

def _schema_file_for_step(step: str, schema_dir: str) -> str | None:
    """Return the path to the schema file for a step, or None if none exists.

    Fail-loud hardening: after the SCHEMA_SKIP filter, if >1 file remains for
    the same step, raises ``ValueError`` naming the step, the remaining files,
    and the fix instruction (add the non-spec schema to SCHEMA_SKIP).

    Today exactly 1 file remains for every step after the filter, so this raise
    is purely future-proofing — it NEVER triggers on the current schema corpus.
    Step 16 has two schema files (16_impl_context, 16_anchor) but 16_anchor is
    in SCHEMA_SKIP, so only 16_impl_context remains and the raise does not fire.

    This makes the selector ORDER-INDEPENDENT and FAIL-LOUD rather than silently
    picking the lexicographic-first when an unhandled multi-schema step is added.
    """
    pattern = os.path.join(schema_dir, f"{step}_*.schema.json")
    matches = [
        p for p in sorted(glob.glob(pattern))
        if os.path.basename(p) not in SCHEMA_SKIP
    ]
    if not matches:
        return None
    if len(matches) == 1:
        return matches[0]
    # >1 match after SCHEMA_SKIP filter: unhandled ambiguity — fail loud.
    # To fix: add the non-spec schema file(s) to SCHEMA_SKIP in generate.py.
    remaining = [os.path.basename(p) for p in matches]
    raise ValueError(
        f"_schema_file_for_step: step '{step}' has {len(matches)} schema files "
        f"remaining after SCHEMA_SKIP filter: {remaining!r}. "
        f"Add the non-spec schema(s) to SCHEMA_SKIP in "
        f"tools/specdev_tools/registry/generate.py."
    )


def _spec_basename_for_step(step: str, schema_path: str) -> str:
    """Derive the spec file basename from a schema path.

    Applies STEP_BASENAME_OVERRIDES where schema filename ≠ spec basename.
    For all other steps: strips .schema.json suffix, adds .json.
    """
    if step in STEP_BASENAME_OVERRIDES:
        return STEP_BASENAME_OVERRIDES[step]
    base = os.path.basename(schema_path)
    # e.g. 04_fr_list.schema.json → 04_fr_list.json
    if base.endswith(".schema.json"):
        return base[: -len(".schema.json")] + ".json"
    return base


# ---------------------------------------------------------------------------
# extraction_paths.json generation
# ---------------------------------------------------------------------------

def _full_array_paths(entry: dict[str, Any], full_path: str) -> list[str]:
    """Return *full_path* followed, depth first, by the full path of each nested entry of *entry*."""
    paths = [full_path]
    for nested in entry.get("nested", []):
        paths += _full_array_paths(nested, join_nested_path(full_path, nested["array_path"]))
    return paths


def _build_extraction_paths(
    registry: dict[str, dict[str, Any]],
    step_order: list[str],
) -> dict[str, Any]:
    """Build the extraction_paths.json structure from the registry.

    Format matches the existing extraction_paths.json: step-keyed dict
    (excluding _meta) with inner basename → list of array paths: each
    top-level ``array_path``, then (depth first) the full path of every nested
    or map-keyed entry (``join_nested_path``), e.g.
    ``.milestones[].tasks[].acceptance_criteria``.

    The _meta key is preserved in spirit but we emit only the structure that
    downstream consumers (registry_check._load_extraction_basenames) expect:
    a dict where values are dicts whose keys are spec file basenames.

    Note: generated_at is intentionally omitted to preserve byte-determinism
    across runs.  schema_hashes is also omitted (generated from schemas, not
    hashed here) — downstream consumers only read the step-keyed structure.

    Structure:
        {
          "_meta": { "note": "Generated by specdev registry-generate." },
          "<step>": { "<basename>": [<array_paths>] },
          ...
        }
    """
    result: dict[str, Any] = {
        "_meta": {
            "note": (
                "Generated by specdev registry-generate. "
                "Do not hand-edit. Step-keyed; inner keys are spec file basenames."
            )
        }
    }

    # Build step → {basename: [array_paths]} from registry
    # Follow step_order for deterministic ordering
    basename_to_step: dict[str, str] = {}
    for basename, entry in registry.items():
        basename_to_step[basename] = entry["step"]

    # Group basenames by step in step_order sequence
    step_basenames: dict[str, list[str]] = {}
    for basename, entry in registry.items():
        step = entry["step"]
        step_basenames.setdefault(step, []).append(basename)

    for step in step_order:
        basenames = step_basenames.get(step, [])
        if not basenames:
            continue
        step_block: dict[str, list[str]] = {}
        for basename in sorted(basenames):
            arrays = registry[basename]["arrays"]
            step_block[basename] = [path for a in arrays for path in _full_array_paths(a, a["array_path"])]
        result[step] = step_block

    return result


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

#: Registry ``step`` of every entry declared by a record host (a non-step schema).
RECORD_HOST_STEP = "extras"


def _register_glob_entry(
    registry: dict[str, dict[str, Any]], key: str, step: str, entry: dict[str, Any]
) -> None:
    """Append *entry* to the registry slot of glob *key*, creating the slot under *step*."""
    registry.setdefault(key, {"step": step, "arrays": []})["arrays"].append(entry)


def _in_slot(registry: dict[str, dict[str, Any]], key: str, entry: dict[str, Any]) -> bool:
    """True when the slot of *key* already holds an entry with the same array path and kind."""
    arrays = registry.get(key, {}).get("arrays", [])
    return any(a["array_path"] == entry["array_path"] and a["kind"] == entry["kind"] for a in arrays)


def _register_host_entries(
    registry: dict[str, dict[str, Any]],
    host: HostScan,
    step: str,
    arrays: list[dict[str, Any]],
    default_files: list[str] | None = None,
) -> tuple[list[dict[str, Any]], set[str]]:
    """Register one step host's annotation entries; return ``(arrays, claimed glob keys)``.

    An occurrence with ``files`` (or, lacking its own, *default_files*) goes under each glob key
    (step *step* unless it names its own).
    Any other occurrence is added to the returned *arrays*; when an entry of *arrays* (from an
    earlier host of the step) has its path, the declared entry replaces it in place, so a kind
    declared once carries one name in every host.  The *arrays* argument itself is not modified.
    """
    out = list(arrays)
    claimed: set[str] = set()
    for occ in host.occurrences:
        files = occ.files or default_files
        if files:
            for glob_key in files:
                _register_glob_entry(registry, glob_key, occ.step or step, occ.entry)
                claimed.add(glob_key)
            continue
        slot = next((i for i, a in enumerate(out) if a["array_path"] == occ.entry["array_path"]), None)
        if slot is None:
            out.append(occ.entry)
        else:
            out[slot] = occ.entry
    return out, claimed


def _register_step_hosts(
    registry: dict[str, dict[str, Any]],
    scan: AnnotationScan,
    step: str,
    schema_files: list[str],
    arrays: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], set[str]]:
    """Register the annotation entries of every host schema file of *step*, in *schema_files* order.

    Each file is a schema path relative to the toolkit root; a file that is no host adds nothing.
    A file in ``PLAN_FILE_HOSTS`` registers all its entries under its plan-file glob.
    Returns the step's ``(arrays, claimed glob keys)`` as ``_register_host_entries`` does.
    """
    claimed: set[str] = set()
    for rel in schema_files:
        host = scan.host(rel)
        if host is not None:
            if rel in PLAN_FILE_HOSTS:
                plan_step, glob_key = PLAN_FILE_HOSTS[rel]
                arrays, keys = _register_host_entries(registry, host, plan_step, arrays, [glob_key])
            else:
                arrays, keys = _register_host_entries(registry, host, step, arrays)
            claimed |= keys
    return arrays, claimed


def generate_registry(repo_root: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Generate the entry_key_registry and extraction_paths dicts from schemas.

    Args:
        repo_root: Absolute path to the toolkit root (contains schema/, tools/).

    Returns:
        (registry_doc, extraction_paths_doc) — two dicts ready to serialize.

    Raises:
        json.JSONDecodeError: if any schema file is malformed.
        AnnotationError: if the x-node / x-link annotation lint finds issues.
        StepOrderError: if ``steps`` of tools/step_order.json cannot be read or leaves out a step
                        that declares an ``x-node`` kind (the registry would silently lose it).
    """
    return generate_registry_from_decls(repo_root, collect_annotations(repo_root))


def generate_registry_from_decls(
    repo_root: str, decls: AnnotationDecls, steps: list[str] | None = None
) -> tuple[dict[str, Any], dict[str, Any]]:
    """``generate_registry`` over annotation declarations the caller already collected.

    Args:
        repo_root: Absolute path to the toolkit root.
        decls: ``collect_annotations(repo_root)``; the lint runs here.
        steps: ``steps`` of tools/step_order.json when the caller already read the file (default: read here).

    Returns and raises as ``generate_registry``.
    """
    schema_dir = os.path.join(repo_root, "schema")
    tools_dir = os.path.join(repo_root, "tools")

    # Annotation lint (x-node / x-link): a no-op when the toolkit has no
    # vc:core:graph entry or no schema carries an annotation.
    annotation_issues = lint_annotations(decls)
    if annotation_issues:
        raise AnnotationError(annotation_issues)
    scan = scan_annotations(repo_root, decls)

    # Load step order
    if steps is None:
        steps = load_steps(os.path.join(tools_dir, "step_order.json"))
    unlisted = sorted(annotated_steps(decls) - set(steps))
    if unlisted:  # the loop below would leave these steps out of the registry without a message
        raise StepOrderError(f"tools/step_order.json: steps: annotated step(s) {', '.join(unlisted)} are not listed")

    # Accumulators
    registry: dict[str, dict[str, Any]] = {}  # basename → entry
    steps_without: list[dict[str, str]] = []

    for step in steps:
        if step in STEPS_INSIDE_PLAN_FILE:
            steps_without.append({"step": step, "rationale": INSIDE_PLAN_FILE_RATIONALE})
            continue

        schema_path = _schema_file_for_step(step, schema_dir)
        if schema_path is None and any(e["step"] == step for e in registry.values()):
            continue  # no schema of its own: an annotation of an earlier step registered it
        if schema_path is None:
            steps_without.append({
                "step": step,
                "rationale": "no schema file",
            })
            continue

        spec_basename = _spec_basename_for_step(step, schema_path)

        step_hosts = [os.path.relpath(schema_path, repo_root)]
        step_hosts += [os.path.join("schema", name) for name in STEP_EXTRA_HOSTS.get(step, ())]
        arrays, extra_keys = _register_step_hosts(registry, scan, step, step_hosts, [])

        if not arrays and extra_keys:
            continue  # the step's entries all live under glob keys
        if not arrays:
            steps_without.append({
                "step": step,
                "rationale": "no top-level array properties with id fields",
            })
            # Still emit a registry entry with empty arrays so basename coverage
            # matches extraction_paths; omit if you don't want empty entries.
            # Decision: skip empty entries — keep registry clean and match plan.
            continue

        registry[spec_basename] = {
            "step": step,
            "arrays": arrays,
        }

    # Record hosts: registered non-step schemas whose own x-node sets ``files``.  Their entries
    # belong to no step: they register under ``RECORD_HOST_STEP``.
    for occ in scan.record_hosts():
        for glob_key in occ.files or []:
            if _in_slot(registry, glob_key, occ.entry):
                registry[glob_key]["step"] = RECORD_HOST_STEP  # a step schema reached it via $ref first
            else:
                _register_glob_entry(registry, glob_key, RECORD_HOST_STEP, occ.entry)

    # Sentinels are a hardcoded constant list: these array names appear across
    # multiple spec files at write-time (appended by canonical-lint tooling) and
    # are never declared in any schema's properties.  We do NOT discover them
    # via schema walk — they are always emitted from the SENTINEL_ARRAYS constant.
    all_sentinels = sorted(SENTINEL_ARRAYS)

    # Build output document
    registry_doc: dict[str, Any] = {
        "$schema": "vc:entry-key-registry",
        "_format_version": FORMAT_VERSION,
        "_note": REGISTRY_NOTE,
        "registry": registry,
        "_sentinels": all_sentinels,
        "steps_without_entry_arrays": steps_without,
    }
    external_kinds = scan.external_kinds
    if external_kinds:
        registry_doc["external_kinds"] = external_kinds

    # Build extraction_paths
    extraction_paths_doc = _build_extraction_paths(registry, steps)

    return registry_doc, extraction_paths_doc


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------

def _serialize(doc: Any) -> str:
    """Serialize to deterministic JSON string with trailing newline."""
    return json.dumps(doc, sort_keys=True, indent=2) + "\n"


def _write_text(path: str, text: str) -> None:
    """Write *text* to *path* (creating its directory) and report it."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    print(f"registry-generate: wrote {path}")


def _write_doc(path: str, doc: Any) -> None:
    """Write *doc* serialized to *path* (creating its directory) and report it."""
    _write_text(path, _serialize(doc))


def run(
    repo_root: str,
    out_path: str,
    extraction_paths_out: str,
    step_order_out: str | None = None,
    cli_commands_out: str | None = None,
    checklist_out: str | None = None,
) -> None:
    """Generate registry and extraction_paths files and write them to disk.

    Args:
        repo_root: Absolute or relative path to the toolkit root.
        out_path: Destination path for entry_key_registry.json.
        extraction_paths_out: Destination path for extraction_paths.json.
        step_order_out: Optional destination for the step order derived from the annotations
            and the hand-carried keys of ``tools/step_order.json`` (``None`` writes nothing; the
            command line defaults it to ``tools/step_order.json`` when ``out_path`` is defaulted).
        cli_commands_out: Optional destination for cli_commands.json (``None`` writes nothing).
        checklist_out: Optional destination for the schema-change checklist rendered from
            ``tools/schema_changes.json`` (``None`` writes nothing).

    Raises:
        AnnotationError: if the annotation lint fails or no annotated step gives a step order.
        ChecklistError: if ``tools/schema_changes.json`` is not well formed.
        StepOrderError: if ``steps`` of ``tools/step_order.json`` cannot be used or leaves out an annotated
            step; with *step_order_out*, also if another hand-kept key cannot be used.
    """
    repo_root = os.path.abspath(repo_root)
    decls = collect_annotations(repo_root)
    # Read the hand-kept keys once; the registry generation takes ``steps`` from the same read.
    hand_path = os.path.join(repo_root, "tools", "step_order.json")
    step_order = (os.path.abspath(step_order_out), load_hand_kept(hand_path)) if step_order_out else None
    registry_doc, extraction_paths_doc = generate_registry_from_decls(
        repo_root, decls, step_order[1]["steps"] if step_order else None
    )
    outputs: list[tuple[str, Any]] = [
        (out_path, registry_doc),
        (extraction_paths_out, extraction_paths_doc),
    ]

    # Derive everything first (the checklist too), so a failure writes no output file.
    if step_order:
        step_order_path, hand = step_order
        if not annotated_steps(decls):
            raise AnnotationError(
                ["registry-generate --step-order-out: no annotated step to derive an order from"]
            )
        derived = derive_from_decls(decls, declared_edge_pairs(hand))
        outputs.append((step_order_path, build_step_order_document(derived, hand)))
    if cli_commands_out:
        # Lazy: generate_cli_commands builds the full CLI parser (specdev_tools.cli), which loads
        # this module lazily in turn; a local import keeps loading generate from loading cli.
        from specdev_tools.registry.cli_commands import generate_cli_commands

        outputs.append((os.path.abspath(cli_commands_out), generate_cli_commands()))

    checklist = (os.path.abspath(checklist_out), generate_checklist(Path(repo_root))) if checklist_out else None

    for path, doc in outputs:
        _write_doc(path, doc)
    if checklist:
        _write_text(*checklist)
