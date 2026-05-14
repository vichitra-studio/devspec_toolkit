"""loop_inner.py — Inner pointer-verification loop (plan → resolve → repair).

Implements §5.1 of docs/agents/llm_protocol.md.

The inner loop is the pointer-hallucination firewall for the local-LLM layer:
  - Iter 1 ("plan"): ask the LLM to emit a pointer bundle.
  - Subsequent iters ("repair"): re-prompt with miss set + nearest-name hints.
  - Terminates on: empty miss set, no-shrink/same-set stagnation, or max_iters.

No spec edits, no filesystem mutation, O(iterations × LLM call). Safe to run
aggressively.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING

import jsonschema

from specdev_tools.core.json_utils import resolve_pointers

if TYPE_CHECKING:
    from .adapter import LLMAdapter

# ---------------------------------------------------------------------------
# Schema loading (lazy cache)
# ---------------------------------------------------------------------------

_SCHEMA_PATH = Path(__file__).parent / "schemas" / "pointer_response.schema.json"
_SCHEMA_CACHE: dict | None = None


def _get_schema() -> dict:
    global _SCHEMA_CACHE
    if _SCHEMA_CACHE is None:
        try:
            with _SCHEMA_PATH.open("r", encoding="utf-8") as fh:
                _SCHEMA_CACHE = json.load(fh)
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Inner-loop response schema not found: {_SCHEMA_PATH}. "
                "Ensure specdev_tools is installed with package_data (llm/schemas/*.json)."
            ) from None
    assert _SCHEMA_CACHE is not None
    return _SCHEMA_CACHE


# ---------------------------------------------------------------------------
# Prompt templates (lazy cache)
# ---------------------------------------------------------------------------

_PROMPTS_DIR = Path(__file__).parent / "prompts"

_TEMPLATE_CACHE: dict[str, tuple[str, str]] = {}  # name → (system, user)


def _parse_template(template_name: str) -> tuple[str, str]:
    """Parse a prompt template file into (system, user) sections.

    Sections are delimited by lines matching ``^# (\\w+)\\s*$``.
    The ``# response_shape`` section at the end is excluded.
    """
    if template_name in _TEMPLATE_CACHE:
        return _TEMPLATE_CACHE[template_name]

    path = _PROMPTS_DIR / template_name
    try:
        with path.open("r", encoding="utf-8") as fh:
            content = fh.read()
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Inner-loop prompt template not found: {path}. "
            "Ensure specdev_tools is installed with package_data (llm/prompts/*.md)."
        ) from None

    # Split into sections
    section_pattern = re.compile(r"^# (\w+)\s*$", re.MULTILINE)
    matches = list(section_pattern.finditer(content))

    sections: dict[str, str] = {}
    for i, match in enumerate(matches):
        name = match.group(1).lower()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        sections[name] = content[start:end].strip()

    system = sections.get("system", "")
    user = sections.get("user", "")
    _TEMPLATE_CACHE[template_name] = (system, user)
    return system, user


def _render(template_str: str, vars: dict[str, str]) -> str:
    """Replace ``{{ key }}`` placeholders in *template_str* with *vars* values.

    Uses str.replace with all spacing variants. No jinja2 dependency.
    """
    result = template_str
    for key, value in vars.items():
        # Match {{ key }} with any surrounding whitespace inside the braces
        result = re.sub(r"\{\{\s*" + re.escape(key) + r"\s*\}\}", str(value), result)
    return result


# ---------------------------------------------------------------------------
# Helper: pointer fingerprint for stagnation detection
# ---------------------------------------------------------------------------


def _pointer_fingerprint(pointer: dict) -> str:
    """Return a stable string key for a pointer dict."""
    file_ = pointer.get("file", "")
    id_ = pointer.get("id")
    jq = pointer.get("jq_path")
    if id_ is not None:
        return f"{file_}::{id_}"
    if jq is not None:
        return f"{file_}::jq:{jq}"
    return repr(pointer)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def run_inner_loop(
    *,
    task: str,
    step_structure_summary: dict,
    upstream_structure: dict,
    prompt_nn: str,
    adapter: "LLMAdapter",
    spec_root: str,
    git_root: str | None = None,
    max_iters: int | None = None,
) -> dict:
    """Run the inner pointer-verification loop.

    Parameters
    ----------
    task:
        Natural-language description of what the agent is trying to do.
    step_structure_summary:
        Dict describing the current step's spec entries (from run_bundle).
    upstream_structure:
        Dict describing upstream spec entries (from run_bundle).
    prompt_nn:
        Full text of the pipeline step's prompt (``context.prompt_NN`` from
        the bundle).
    adapter:
        Injected :class:`~specdev_tools.llm.adapter.LLMAdapter` implementation.
        Never constructed internally.
    spec_root:
        Absolute path to the host project's spec directory.
    git_root:
        Absolute path to the host repo git root. Defaults to cwd.
    max_iters:
        Maximum number of inner-loop iterations.  When ``None`` (default),
        read from ``SPECDEV_LLM_INNER_MAX_ITERS`` env var (default 3).

    Returns
    -------
    dict with keys:
        ``validated_pointers``
            List of pointer dicts that resolved (exists=True).
        ``unresolved``
            List of ``{pointer, reason}`` dicts for misses that couldn't be
            fixed.  Non-empty iff ``partial`` is True.
        ``iterations``
            Number of inner-loop iterations run.
        ``partial``
            True iff ``unresolved`` is non-empty.
        ``ok``
            True iff ``unresolved`` is empty.
    """
    # Resolve max_iters from config when not explicitly provided.
    if max_iters is None:
        from specdev_tools.core.config import get_config
        max_iters = get_config().llm_inner_max_iters

    # Guard: max_iters=0 means "no LLM calls allowed" — honest partial with
    # an explicit reason (not the discard sentinel, since no calls were made).
    if max_iters <= 0:
        return {
            "validated_pointers": [],
            "unresolved": [
                {"pointer": {"file": "?", "id": "?"}, "reason": "max_iters=0; no LLM calls attempted"}
            ],
            "iterations": 0,
            "partial": True,
            "ok": False,
        }

    # Current validated (hit) pointers, carried across iterations.
    current_hits: list[dict] = []
    # Current miss set with nearest hints from resolve_pointers.
    current_misses: list[dict] = []
    # LLM-emitted unresolved entries from the most recent valid response.
    current_llm_unresolved: list[dict] = []

    # Stagnation tracking (only updated on valid — non-discarded — iterations).
    stall_count: int = 0                          # consecutive non-shrinking transitions
    prev_miss_count: int | None = None            # miss count from last valid iteration
    prev_miss_set: frozenset[str] | None = None   # fingerprints from last valid iteration

    # Track the last "good" hits so partial returns can include them (test 10).
    last_good_hits: list[dict] = []

    # Track discards so we can emit a sentinel in _partial_return when every
    # iteration was discarded (partial=True iff unresolved is non-empty contract).
    discard_count = 0

    iteration = 0

    while iteration < max_iters:
        iteration += 1

        # ------------------------------------------------------------------
        # Render prompt
        # ------------------------------------------------------------------
        if iteration == 1:
            system_tmpl, user_tmpl = _parse_template("inner_plan.md")
            render_vars = {
                "task": task,
                "step_structure_summary": json.dumps(step_structure_summary, indent=2),
                "upstream_structure": json.dumps(upstream_structure, indent=2),
                "context.prompt_NN": prompt_nn,
            }
        else:
            system_tmpl, user_tmpl = _parse_template("inner_repair.md")
            render_vars = {
                "task": task,
                "pointers": json.dumps(current_hits, indent=2),
                "unresolved": json.dumps(current_misses, indent=2),
                "nearest_suggestions": _format_nearest(current_misses),
            }

        system_msg = _render(system_tmpl, render_vars)
        user_msg = _render(user_tmpl, render_vars)

        # ------------------------------------------------------------------
        # Call LLM
        # ------------------------------------------------------------------
        raw_response = adapter.chat(system_msg, user_msg)

        # ------------------------------------------------------------------
        # Parse JSON
        # ------------------------------------------------------------------
        try:
            parsed = json.loads(raw_response)
        except (json.JSONDecodeError, ValueError):
            # Discard — count the iteration; stagnation state not touched so
            # discards don't pollute the no-shrink or same-set counters.
            discard_count += 1
            continue

        # ------------------------------------------------------------------
        # Schema validation
        # ------------------------------------------------------------------
        schema = _get_schema()
        validator = jsonschema.Draft202012Validator(schema)
        errors = list(validator.iter_errors(parsed))
        if errors:
            # Schema failure — discard response
            discard_count += 1
            continue

        # ------------------------------------------------------------------
        # Forbidden pointer shapes: content field on any pointer item
        # (belt-and-suspenders — schema's additionalProperties:false already
        # rejects these, but we want an explicit protocol-violation guard per §9)
        # ------------------------------------------------------------------
        pointer_list: list[dict] = parsed.get("pointers", [])
        if any("content" in ptr for ptr in pointer_list):
            # Protocol violation — discard response
            discard_count += 1
            continue

        # ------------------------------------------------------------------
        # Call resolve_pointers
        # ------------------------------------------------------------------
        report = resolve_pointers(pointer_list, spec_root=spec_root, git_root=git_root)
        results = report.get("results", [])

        new_hits: list[dict] = []
        new_misses: list[dict] = []
        for result in results:
            if result.get("exists"):
                new_hits.append(result["pointer"])
            else:
                new_misses.append({
                    "pointer": result["pointer"],
                    "nearest": result.get("nearest", []),
                    "reason": result.get("reason", "unresolved"),
                })

        # Capture LLM-emitted unresolved (honor them per spec)
        llm_unresolved: list[dict] = parsed.get("unresolved", [])

        # Update state
        current_hits = new_hits
        current_misses = new_misses
        current_llm_unresolved = llm_unresolved
        if new_hits:
            last_good_hits = new_hits

        # ------------------------------------------------------------------
        # Termination condition 1: miss set is empty
        # ------------------------------------------------------------------
        if not current_misses and not current_llm_unresolved:
            return {
                "validated_pointers": current_hits,
                "unresolved": [],
                "iterations": iteration,
                "partial": False,
                "ok": True,
            }

        # ------------------------------------------------------------------
        # Termination condition 2: stagnation (same miss set twice in a row,
        # OR miss set has not shrunk for 2 consecutive transitions)
        # ------------------------------------------------------------------
        current_count = len(current_misses)
        current_fingerprints = frozenset(
            _pointer_fingerprint(m["pointer"]) for m in current_misses
        )

        # 2a: Same miss set twice in a row (checked before 2b — same-set is a
        # stricter signal; no need to wait for a second non-shrink transition).
        if prev_miss_set is not None and current_fingerprints == prev_miss_set:
            return _partial_return(
                hits=last_good_hits,
                misses=current_misses,
                llm_unresolved=current_llm_unresolved,
                iteration=iteration,
                discard_count=discard_count,
            )

        # 2b: No shrink for 2 consecutive valid-iteration transitions.
        # stall_count counts transitions where miss count did not decrease.
        # A single stagnant transition (e.g. [5, 5]) is not enough — the spec
        # says "2 consecutive" to tolerate productive-but-non-monotonic paths
        # like [5, 5, 3, 1]. Exit only when stall_count reaches 2.
        if prev_miss_count is not None:
            if current_count >= prev_miss_count:
                stall_count += 1
            else:
                stall_count = 0  # shrink happened — reset counter

        if stall_count >= 2:
            return _partial_return(
                hits=last_good_hits,
                misses=current_misses,
                llm_unresolved=current_llm_unresolved,
                iteration=iteration,
                discard_count=discard_count,
            )

        prev_miss_count = current_count
        prev_miss_set = current_fingerprints

    # ------------------------------------------------------------------
    # Termination condition 3: max_iters reached
    # ------------------------------------------------------------------
    return _partial_return(
        hits=last_good_hits,
        misses=current_misses,
        llm_unresolved=current_llm_unresolved,
        iteration=iteration,
        discard_count=discard_count,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------



def _format_nearest(misses: list[dict]) -> str:
    """Format nearest-hint lists for the repair prompt."""
    if not misses:
        return "(none)"
    lines = []
    for m in misses:
        ptr = m.get("pointer", {})
        nearest = m.get("nearest", [])
        id_or_jq = ptr.get("id") or ptr.get("jq_path") or "?"
        file_ = ptr.get("file", "?")
        # nearest items may be dicts {id, score} or plain strings
        hint_parts = []
        for item in nearest:
            if isinstance(item, dict):
                hint_parts.append(item.get("id", repr(item)))
            else:
                hint_parts.append(str(item))
        hint_str = ", ".join(hint_parts) if hint_parts else "none"
        lines.append(f"- {file_}::{id_or_jq} → nearest: [{hint_str}]")
    return "\n".join(lines)


def _partial_return(
    *,
    hits: list[dict],
    misses: list[dict],
    llm_unresolved: list[dict],
    iteration: int,
    discard_count: int = 0,
) -> dict:
    """Build a partial (ok=False) return envelope.

    Merges resolve_pointers misses and LLM-emitted unresolved entries.
    Silent drops are forbidden — every miss must appear in ``unresolved``.

    Contract: ``partial`` is True iff ``unresolved`` is non-empty.
    When all iterations were discarded (parse/schema/content failures),
    a sentinel entry is injected so the contract holds.
    """
    unresolved: list[dict] = []

    # Add resolve-pointers misses
    seen_fingerprints: set[str] = set()
    for m in misses:
        fp = _pointer_fingerprint(m["pointer"])
        seen_fingerprints.add(fp)
        nearest = m.get("nearest", [])
        # nearest items may be dicts {id, score} or plain strings
        nearest_strs = []
        for item in nearest:
            if isinstance(item, dict):
                nearest_strs.append(item.get("id", repr(item)))
            else:
                nearest_strs.append(str(item))
        # Use the structured reason from resolve_pointers as the primary signal
        # (e.g. "missing_file", "invalid_shape: path_escapes_git_root") so
        # diagnostic context is not lost.  Append nearest hints when present.
        base_reason = m.get("reason", f"unresolved after {iteration} iterations")
        reason = (
            base_reason + f"; nearest: {', '.join(nearest_strs)}"
            if nearest_strs
            else base_reason
        )
        unresolved.append({"pointer": m["pointer"], "reason": reason})

    # Add LLM-emitted unresolved (avoid duplicates with misses AND with hits,
    # since a confused LLM might emit the same pointer in both pointers[] and
    # unresolved[], which would create an inconsistent envelope).
    hit_fingerprints = frozenset(_pointer_fingerprint(h) for h in hits)
    for item in llm_unresolved:
        ptr = item.get("pointer", {})
        fp = _pointer_fingerprint(ptr)
        if fp not in seen_fingerprints and fp not in hit_fingerprints:
            seen_fingerprints.add(fp)
            unresolved.append({
                "pointer": ptr,
                "reason": item.get("reason", f"unresolved after {iteration} iterations"),
            })

    # Enforce partial=True iff unresolved non-empty: when every iteration was
    # discarded (parse/schema/content failure), inject a sentinel so the caller
    # always receives an actionable reason (§5.1 "silent drops are forbidden").
    if not unresolved and discard_count > 0:
        unresolved.append({
            "pointer": {"file": "?", "id": "?"},
            "reason": (
                f"response discarded {discard_count} time(s); "
                f"no valid LLM response within {iteration} iteration(s)"
            ),
        })

    return {
        "validated_pointers": hits,
        "unresolved": unresolved,
        "iterations": iteration,
        "partial": bool(unresolved),
        "ok": not bool(unresolved),
    }
