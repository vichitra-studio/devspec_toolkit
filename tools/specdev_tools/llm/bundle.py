"""bundle.py — orientation bundle assembler for 'specdev llm bundle'.

Assembles a deterministic orientation context bundle for a given pipeline step.
The bundle contains always-included context artifacts, upstream structural summaries,
and (when --task is provided) pointer-only scoped entries.

No LLM calls are made here. This is entirely deterministic.
"""
from __future__ import annotations

import glob
import json
import os
import sys
from typing import Any

from specdev_tools.core.entry_key_registry import list_entries as _list_entries

_BUNDLE_VERSION = "1"

# The 11 required context slot names (in order)
_CONTEXT_SLOTS = [
    "skill_md",
    "shared_expectations",
    "prompt_NN",
    "claude_md_toolkit",
    "claude_md_host",
    "llm_protocol",
    "step_order",
    "trace_matrix",
    "step_docs",
    "canon_manifest_core",
    "canon_manifest_project",
]


def _rel_path(abs_path: str, git_root_abs: str) -> str:
    """Return *abs_path* relative to *git_root_abs*, using forward slashes."""
    try:
        return os.path.relpath(abs_path, git_root_abs).replace("\\", "/")
    except ValueError:
        # On Windows, relpath can fail across drives
        return abs_path


def _path_ref(abs_path: str, base: str) -> dict | None:
    """Return a path-pointer dict for large reference-only files.

    Returns None if the file does not exist, so the slot stays null.
    The path is relative to *base* (typically git_root_abs or repo_root_abs).
    The agent fetches the actual content on demand via 'specdev json read'.
    """
    if not os.path.isfile(abs_path):
        return None
    return {"__type": "path_ref", "path": os.path.relpath(abs_path, base).replace("\\", "/")}


def _kebab_similarity(task: str, id_val: str) -> float:
    """Token-overlap similarity: |intersection| / |union| of kebab-split tokens.

    Per llm_protocol.md §15: deterministic, LLM-free, fast.
    """
    task_tokens = set(task.lower().replace("-", " ").replace("_", " ").split())
    id_tokens = set(id_val.lower().split("-"))
    if not task_tokens or not id_tokens:
        return 0.0
    intersection = task_tokens & id_tokens
    union = task_tokens | id_tokens
    return len(intersection) / len(union)


def _read_text(path: str) -> str | None:
    """Read a text file, returning None on any error."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except Exception:
        return None


def _read_json(path: str) -> Any:
    """Parse a JSON file, returning None on any error."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return None


def _error_envelope(message: str) -> dict:
    """Return a minimal failure envelope."""
    return {"ok": False, "error": message, "bundle_version": _BUNDLE_VERSION}


def _resolve_jq_path(data: dict, array_path: str) -> list:
    """Resolve a jq-style array path on *data*.

    Supports:
    - ``.functional_requirements`` → top-level array
    - ``.milestones[].tasks`` → nested array (flattened)
    - ``milestones[].tasks`` (no leading dot) — same as above

    Returns the flattened list of matching entries.
    """
    path = array_path.lstrip(".")
    # Split on "[]." to detect nested arrays
    parts = path.split("[].")
    if len(parts) == 1:
        # Simple top-level key
        key = parts[0].strip()
        val = data.get(key, [])
        return list(val) if isinstance(val, list) else []
    else:
        # Nested: parts[0] is outer key, parts[1:] are inner keys
        outer_key = parts[0].strip()
        outer_list = data.get(outer_key, [])
        if not isinstance(outer_list, list):
            return []
        result = []
        inner_path = "[]." .join(parts[1:])
        for item in outer_list:
            if isinstance(item, dict):
                inner_entries = _resolve_jq_path(item, inner_path)
                result.extend(inner_entries)
        return result


def _build_step_structure_summary(
    step: str,
    spec_root: str,
    git_root_abs: str,
) -> dict:
    """Build step_structure_summary for the current step.

    Returns a dict keyed by relative path → {entry_count, ids}.
    Returns {} if registry missing or spec file not yet generated.
    """
    registry_path = os.path.join(spec_root, "entry_key_registry.json")
    if not os.path.isfile(registry_path):
        return {}

    # Find the current step's spec file
    spec_file = None
    prefix = f"{step}_"
    try:
        for fname in os.listdir(spec_root):
            if fname.startswith(prefix) and fname.endswith(".json"):
                spec_file = os.path.join(spec_root, fname)
                break
    except OSError:
        return {}

    if spec_file is None or not os.path.isfile(spec_file):
        return {}

    # Load spec data
    spec_data = _read_json(spec_file)
    if spec_data is None or not isinstance(spec_data, dict):
        return {}

    # Use entry_key_registry to get registered arrays
    try:
        entries = _list_entries(os.path.basename(spec_file), spec_root=spec_root)
    except FileNotFoundError:
        return {}
    except Exception:
        return {}

    if entries is None:
        # Unknown file to registry — return empty
        return {}

    # Build ids across all registered arrays
    all_ids: list[str] = []
    for reg_entry in entries:
        array_entries = _resolve_jq_path(spec_data, reg_entry.array_path)
        for item in array_entries:
            if isinstance(item, dict):
                id_val = item.get(reg_entry.id_field)
                if id_val is not None:
                    all_ids.append(str(id_val))

    rel_path = _rel_path(spec_file, git_root_abs)
    return {
        rel_path: {
            "entry_count": len(all_ids),
            "ids": all_ids,
        }
    }


def _build_upstream_structure(
    step: str,
    spec_root: str,
    repo_root: str,
    git_root_abs: str,
) -> dict:
    """Build upstream_structure using context.structure.get_step_structure."""
    try:
        from ..context.structure import get_step_structure
        structure = get_step_structure(step, spec_root, repo_root)
    except Exception:
        return {}

    required_inputs = structure.get("required_inputs", [])
    upstream: dict[str, Any] = {}

    for inp in required_inputs:
        basename = inp.get("file")
        if not basename:
            continue

        # Reconstruct full path for the spec file
        spec_file_abs = os.path.join(os.path.abspath(spec_root), basename)
        if not os.path.isfile(spec_file_abs):
            continue

        keys = inp.get("keys", [])
        array_counts = inp.get("array_counts", {})

        # entry_count: sum of all array counts (deterministic)
        entry_count = sum(array_counts.values()) if array_counts else 0

        rel_path = _rel_path(spec_file_abs, git_root_abs)
        upstream[rel_path] = {
            "entry_count": entry_count,
            "top_level_keys": keys,
        }

    return upstream


def _build_scoped_entries(
    task: str,
    step_structure_summary: dict,
    spec_root: str,
    git_root_abs: str,
) -> tuple[list, list]:
    """Build scoped_entries and unresolved using kebab-token overlap similarity.

    Returns (scoped_entries, unresolved).
    scoped_entries items have ONLY {file, id, jq_path} — no content field.
    """
    # Gather all ids with their file and index
    candidate_pool: list[tuple[str, str, int]] = []  # (id, file_rel_path, index)
    for file_rel_path, summary in step_structure_summary.items():
        for idx, id_val in enumerate(summary.get("ids", [])):
            candidate_pool.append((id_val, file_rel_path, idx))

    if not candidate_pool:
        unresolved = [{
            "pointer": {"file": "", "id": task},
            "reason": "no match",
            "nearest": [],
        }]
        return [], unresolved

    # Compute kebab token-overlap similarity (IoU over kebab-split tokens)
    scored: list[tuple[float, str, str, int]] = []
    for id_val, file_rel, idx in candidate_pool:
        ratio = _kebab_similarity(task, id_val)
        scored.append((ratio, id_val, file_rel, idx))

    scored.sort(key=lambda x: -x[0])

    threshold = 0.25
    matches = [(r, id_val, file_rel, idx) for r, id_val, file_rel, idx in scored if r > threshold]

    if not matches:
        top3 = [id_val for _, id_val, _, _ in scored[:3]]
        first_file = scored[0][2] if scored else ""
        unresolved = [{
            "pointer": {"file": first_file, "id": task},
            "reason": "no match",
            "nearest": top3,
        }]
        return [], unresolved

    # Build a per-file array_path lookup to construct accurate jq_paths.
    # Map file_rel_path → list of (array_path, id_field) from registry.
    file_array_paths: dict[str, list[tuple[str, str]]] = {}
    for file_rel_path, summary in step_structure_summary.items():
        abs_path = os.path.join(git_root_abs, file_rel_path)
        basename = os.path.basename(abs_path)
        try:
            entries = _list_entries(basename, spec_root=spec_root)
            if entries:
                file_array_paths[file_rel_path] = [
                    (e.array_path, e.id_field) for e in entries
                ]
        except Exception:
            pass

    scoped_entries = []
    for _, id_val, file_rel, global_idx in matches:
        # Try to compute an accurate jq_path using the registry
        jq_path = _compute_jq_path(
            id_val=id_val,
            file_rel=file_rel,
            global_idx=global_idx,
            file_array_paths=file_array_paths,
            git_root_abs=git_root_abs,
        )
        scoped_entries.append({
            "file": file_rel,
            "id": id_val,
            "jq_path": jq_path,
        })

    return scoped_entries, []


def _compute_jq_path(
    id_val: str,
    file_rel: str,
    global_idx: int,
    file_array_paths: dict,
    git_root_abs: str,
) -> str:
    """Compute a jq-path for *id_val* in *file_rel*.

    Tries to find which registered array contains this id and its position.
    Falls back to ``.[global_idx]`` if disambiguation fails.
    """
    abs_path = os.path.join(git_root_abs, file_rel)
    if not os.path.isfile(abs_path):
        return f".[{global_idx}]"

    spec_data = _read_json(abs_path)
    if spec_data is None:
        return f".[{global_idx}]"

    array_infos = file_array_paths.get(file_rel, [])
    for array_path, id_field in array_infos:
        entries = _resolve_jq_path(spec_data, array_path)
        for i, entry in enumerate(entries):
            if isinstance(entry, dict) and entry.get(id_field) == id_val:
                # Normalize array_path for jq notation: strip leading dot
                norm = array_path.lstrip(".")
                return f".{norm}[{i}]"

    # Fallback: use global index within the combined id list
    return f".[{global_idx}]"


def run_bundle(
    *,
    step: str,
    spec_root: str,
    repo_root: str,
    git_root: str | None = None,
    task: str | None = None,
) -> dict:
    """Assemble an orientation bundle for pipeline step *step*.

    All errors are caught and returned as error envelopes (ok=false).
    Never raises.

    Parameters
    ----------
    step:
        Pipeline step ID, e.g. "04".
    spec_root:
        Absolute path to the host project's spec directory.
    repo_root:
        Absolute path to the devspec_toolkit repo root.
    git_root:
        Absolute path to the host repo git root. Defaults to repo_root.
    task:
        Optional natural-language task hint for scoped entry matching.
    """
    try:
        return _run_bundle_impl(
            step=step,
            spec_root=spec_root,
            repo_root=repo_root,
            git_root=git_root,
            task=task,
        )
    except Exception as exc:
        return _error_envelope(str(exc))


def _run_bundle_impl(
    *,
    step: str,
    spec_root: str,
    repo_root: str,
    git_root: str | None,
    task: str | None,
) -> dict:
    """Inner implementation — may raise; wrapped by run_bundle."""
    repo_root_abs = os.path.abspath(repo_root)
    spec_root_abs = os.path.abspath(spec_root)
    git_root_abs = os.path.abspath(git_root) if git_root else repo_root_abs

    # ------------------------------------------------------------------
    # 1. Load step_order and validate step (fail fast before any I/O).
    # ------------------------------------------------------------------
    step_order_path = os.path.join(repo_root_abs, "tools", "step_order.json")
    if not os.path.isfile(step_order_path):
        # Try root level fallback
        step_order_path = os.path.join(repo_root_abs, "step_order.json")
    if not os.path.isfile(step_order_path):
        return _error_envelope(f"step_order.json not found under {repo_root_abs!r}")

    step_order_data = _read_json(step_order_path)
    if step_order_data is None:
        return _error_envelope("step_order.json could not be parsed")

    valid_steps: list = step_order_data.get("steps", [])
    if step not in valid_steps:
        return _error_envelope(f"unknown step '{step}'")

    # ------------------------------------------------------------------
    # 2. Assemble context slots (always-included artifacts).
    # ------------------------------------------------------------------
    context: dict[str, Any] = {slot: None for slot in _CONTEXT_SLOTS}

    # skill_md: devspec_toolkit/.claude/skills/specdev-context/SKILL.md (path-ref; agent has this in bridge mode)
    skill_md_path = os.path.join(repo_root_abs, ".claude", "skills", "specdev-context", "SKILL.md")
    context["skill_md"] = _path_ref(skill_md_path, git_root_abs)
    if context["skill_md"] is None:
        print(f"[bundle] WARNING: SKILL.md not found at {skill_md_path!r}", file=sys.stderr)

    # shared_expectations: check docs/prompts/ then prompts/ under repo_root
    se_candidates = [
        os.path.join(repo_root_abs, "docs", "prompts", "shared_expectations.md"),
        os.path.join(repo_root_abs, "prompts", "shared_expectations.md"),
    ]
    for se_path in se_candidates:
        if os.path.isfile(se_path):
            context["shared_expectations"] = _read_text(se_path)
            break

    # prompt_NN: glob prompts/prompt_{step}_*.md under repo_root
    prompt_glob = os.path.join(repo_root_abs, "prompts", f"prompt_{step}_*.md")
    prompt_matches = glob.glob(prompt_glob)
    if not prompt_matches:
        return _error_envelope(f"prompt file not found for step '{step}' (glob: {prompt_glob!r})")
    context["prompt_NN"] = _read_text(sorted(prompt_matches)[0])

    # claude_md_toolkit: CLAUDE.md under repo_root
    toolkit_claude_path = os.path.join(repo_root_abs, "CLAUDE.md")
    if os.path.isfile(toolkit_claude_path):
        context["claude_md_toolkit"] = _read_text(toolkit_claude_path)

    # claude_md_host: CLAUDE.md under git_root (only if different from repo_root)
    if git_root_abs != repo_root_abs:
        host_claude_path = os.path.join(git_root_abs, "CLAUDE.md")
        if os.path.isfile(host_claude_path):
            context["claude_md_host"] = _read_text(host_claude_path)

    # llm_protocol: docs/agents/llm_protocol.md under repo_root (path-ref; 49 KB reference doc)
    protocol_path = os.path.join(repo_root_abs, "docs", "agents", "llm_protocol.md")
    context["llm_protocol"] = _path_ref(protocol_path, git_root_abs)

    # step_order: already loaded — embed as dict
    context["step_order"] = step_order_data

    # trace_matrix: tools/trace_matrix.json under repo_root (path-ref; can be large at runtime)
    trace_matrix_path = os.path.join(repo_root_abs, "tools", "trace_matrix.json")
    context["trace_matrix"] = _path_ref(trace_matrix_path, git_root_abs)

    # step_docs: tools/step_docs.json under repo_root (path-ref; supplementary reference)
    step_docs_path = os.path.join(repo_root_abs, "tools", "step_docs.json")
    context["step_docs"] = _path_ref(step_docs_path, git_root_abs)

    # canon_manifest_core: canon/manifest.json under repo_root (path-ref; 25 KB; fetched on E110 hits)
    core_manifest_path = os.path.join(repo_root_abs, "canon", "manifest.json")
    context["canon_manifest_core"] = _path_ref(core_manifest_path, git_root_abs)

    # canon_manifest_project: spec/canon/manifest.json relative to git_root or spec_root parent
    # (path-ref; 142 KB; biggest offender — fetched only on canon lookups)
    project_manifest_candidates = [
        os.path.join(git_root_abs, "spec", "canon", "manifest.json"),
        os.path.join(spec_root_abs, "canon", "manifest.json"),
        os.path.join(os.path.dirname(spec_root_abs), "spec", "canon", "manifest.json"),
    ]
    for pm_path in project_manifest_candidates:
        if os.path.isfile(pm_path):
            context["canon_manifest_project"] = _path_ref(pm_path, git_root_abs)
            break

    # ------------------------------------------------------------------
    # 3. upstream_structure
    # ------------------------------------------------------------------
    upstream_structure = _build_upstream_structure(
        step=step,
        spec_root=spec_root_abs,
        repo_root=repo_root_abs,
        git_root_abs=git_root_abs,
    )

    # ------------------------------------------------------------------
    # 4. step_structure_summary
    # ------------------------------------------------------------------
    step_structure_summary = _build_step_structure_summary(
        step=step,
        spec_root=spec_root_abs,
        git_root_abs=git_root_abs,
    )

    # ------------------------------------------------------------------
    # 5. scoped_entries (only when --task provided)
    # ------------------------------------------------------------------
    scoped_entries: list = []
    unresolved: list = []
    ok = True
    partial = False

    if task is not None:
        scoped_entries, unresolved = _build_scoped_entries(
            task=task,
            step_structure_summary=step_structure_summary,
            spec_root=spec_root_abs,
            git_root_abs=git_root_abs,
        )
        if unresolved:
            ok = False
            partial = bool(scoped_entries)

    return {
        "step": step,
        "task": task,
        "bundle_version": _BUNDLE_VERSION,
        "context": context,
        "upstream_structure": upstream_structure,
        "step_structure_summary": step_structure_summary,
        "scoped_entries": scoped_entries,
        "unresolved": unresolved,
        "iterations": {"inner": 0},
        "partial": partial,
        "ok": ok,
    }
