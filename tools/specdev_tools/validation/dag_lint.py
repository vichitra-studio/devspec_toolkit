"""DAG completeness validator for step_order.json.

Checks that the step DAG is complete and consistent:
  E520 — step_order.json missing or malformed (unresolved input)
  E585 — circular dependency detected in the upstream dependency graph
  E596 — non-terminal step has zero downstream consumers (dead-end producer)
  E599 — downstream_consumers entry inconsistent with computed upstream dependency order
  W596 — prompt references undeclared artifact not in computed allowed upstream steps

Terminal step 16c is explicitly exempted from E596.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from ..core.errors import SpecError, make_error
from ..core.registry import derive_allowed_upstream
from ._extraction_intent_parser import parse_extraction_intent
from ._extraction_intent_parser import INTENT_ENTRY_RE as _INTENT_ENTRY_RE  # re-exported for tests


# Matches prompt filenames like prompt_04_functional_requirements.md -> "04"
_PROMPT_STEP_RE = re.compile(r"prompt_(\d{2}[a-z]?)_")

# Terminal steps exempted from the dead-end check (E596)
_TERMINAL_STEPS = frozenset({"16c"})


def lint_dag(repo_root: str) -> list[SpecError]:
    """Validate DAG completeness in step_order.json.

    Args:
        repo_root: Path to the toolkit root directory.

    Returns:
        List of SpecError objects (E520, E585, E596, E599, W596).
    """
    errors: list[SpecError] = []
    root = Path(os.path.abspath(repo_root))
    step_order_path = root / "tools" / "step_order.json"

    if not step_order_path.is_file():
        return [make_error("E520", "UNRESOLVED_INPUT step_order.json not found")]

    try:
        with step_order_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        return [make_error("E520", f"UNRESOLVED_INPUT step_order.json parse error: {exc}")]

    steps: list[str] = data.get("steps", [])
    downstream_consumers: dict[str, list[str]] = data.get("downstream_consumers", {})
    allowed_deps: dict[str, list[str]] = {s: derive_allowed_upstream(s, steps) for s in steps}
    step_set = set(steps)
    step_index: dict[str, int] = {s: i for i, s in enumerate(steps)}

    # ---------------------------------------------------------------
    # Check 1: Dead-end producers (E596)
    # Every non-terminal step must have >= 1 downstream consumer.
    # ---------------------------------------------------------------
    for step in steps:
        if step in _TERMINAL_STEPS:
            continue
        consumers = downstream_consumers.get(step, [])
        if len(consumers) == 0:
            errors.append(make_error(
                "E596",
                f"DAG_DEAD_END_PRODUCER step '{step}' has zero "
                f"downstream consumers",
            ))

    # ---------------------------------------------------------------
    # Check 4: Consumer consistency (E599)
    # If step X lists step Y as a downstream consumer, then Y must
    # appear after X in the ordered steps list (strict_waterfall).
    # Under derive_allowed_upstream, any prior step is always an
    # allowed upstream — so we check positional order directly.
    # ---------------------------------------------------------------
    for step, consumers in downstream_consumers.items():
        for consumer in consumers:
            if consumer not in step_set:
                errors.append(make_error(
                    "E599",
                    f"DAG_CONSUMER_INCONSISTENCY step '{step}' lists "
                    f"'{consumer}' as consumer but '{consumer}' is not a "
                    f"recognized step",
                ))
                continue
            # Consumer must come after the producer in the ordered steps list
            if step in step_index and consumer in step_index:
                if step_index[consumer] <= step_index[step]:
                    errors.append(make_error(
                        "E599",
                        f"DAG_CONSUMER_INCONSISTENCY step '{step}' lists "
                        f"'{consumer}' as consumer but '{consumer}' does not "
                        f"appear after '{step}' in the steps ordering",
                    ))

    # ---------------------------------------------------------------
    # Check 5: Circular dependencies
    # Under strict_waterfall with derive_allowed_upstream, cycles are
    # structurally impossible since allowed deps are always prior steps.
    # This check is retained for robustness.
    # ---------------------------------------------------------------
    _check_circular_dependencies(steps, allowed_deps, errors)

    # ---------------------------------------------------------------
    # Check: Undeclared upstream refs in extraction intents (W596)
    # Only run if the prompts directory exists.
    # ---------------------------------------------------------------
    prompts_dir = root / "prompts"
    if prompts_dir.is_dir():
        _check_extraction_intents(
            prompts_dir, steps, step_set, allowed_deps, downstream_consumers, errors
        )

    return errors


def _check_circular_dependencies(
    steps: list[str],
    allowed_deps: dict[str, list[str]],
    errors: list[SpecError],
) -> None:
    """Detect circular dependencies in the upstream dependency graph.

    Edges go from a step to its declared upstream dependencies.
    A cycle means step A depends on B which depends on ... which depends on A.
    """
    visited: set[str] = set()
    rec_stack: set[str] = set()
    cycles_found: list[list[str]] = []

    def _dfs(node: str, path: list[str]) -> None:
        if node in rec_stack:
            # Extract the cycle portion from path
            cycle_start = path.index(node)
            cycle = path[cycle_start:] + [node]
            cycles_found.append(cycle)
            return
        if node in visited:
            return
        visited.add(node)
        rec_stack.add(node)
        for dep in allowed_deps.get(node, []):
            _dfs(dep, path + [node])
        rec_stack.discard(node)

    for step in steps:
        if step not in visited:
            _dfs(step, [])

    for cycle in cycles_found:
        errors.append(make_error(
            "E585",
            f"DAG_CIRCULAR_DEPENDENCY cycle detected: "
            f"{' -> '.join(cycle)}",
        ))


def _check_extraction_intents(
    prompts_dir: Path,
    steps: list[str],
    step_set: set[str],
    allowed_deps: dict[str, list[str]],
    downstream_consumers: dict[str, list[str]],
    errors: list[SpecError],
) -> None:
    """Check for undeclared upstream refs in extraction intent sections (W596).

    For each prompt file that has a ``### Extraction Intent`` section:
      - Parse intent entries to identify which upstream artifacts are declared
      - Warn if a referenced artifact is not in the computed allowed upstream steps

    Note: E597, E598, and W597 checks are handled by extraction_intent_check.py.
    """
    # Build a map: step -> ParsedIntent (from shared parser)
    prompt_intents = {}

    for prompt_path in sorted(prompts_dir.glob("prompt_*.md")):
        match = _PROMPT_STEP_RE.search(prompt_path.name)
        if not match:
            continue
        step = match.group(1)
        if step not in step_set:
            continue

        intent = parse_extraction_intent(prompt_path)
        if intent is not None:
            prompt_intents[step] = intent

    # W596: Prompt references artifact not in the runtime-computed allowed upstream steps
    for step, intent in prompt_intents.items():
        upstream_deps = set(allowed_deps.get(step, []))
        for ref_step in intent.referenced_steps:
            if ref_step in step_set and ref_step not in upstream_deps:
                errors.append(make_error(
                    "W596",
                    f"UNDECLARED_UPSTREAM_REF prompt for step '{step}' "
                    f"({intent.prompt_path.name}) references artifact for "
                    f"step '{ref_step}' which is not in the "
                    f"computed allowed upstream steps",
                ))
