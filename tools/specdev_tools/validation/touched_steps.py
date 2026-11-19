"""Which steps of the step gate a set of touched paths puts under check (S-024, PD-10).

``spec-check --paths`` is the commit-time hook: pre-commit hands it the paths of the commit, relative to the
repository top, and this module maps them to the steps whose gate must run.  The mapping is pure (no check runs
here) and loads the graph only when a seed document was touched, so a commit that touches no spec or seed costs
nothing.

========================================  ==========================================================
Path                                      Steps
========================================  ==========================================================
``<spec>/NN_*.json``                      ``NN`` (the anchor ``16_impl_context.json`` gives ``16``)
``<spec>/impl_context/ms_*_plan.json``    ``16a``, ``16b``, ``16c``
a seed listed in the manifest             steps whose nodes ``derives_from`` it, plus the steps the
                                          manifest routes it to; step ``00`` when there are none
``<spec>/common/seed_manifest.json``      step ``00`` and every step of ``step_requirements``
anything else (``extras/``, other files)  none
========================================  ==========================================================

A step with no artifact in the spec folder is dropped.  A path that lies outside the host root (a nested spec folder
and no ``--git-root``) maps to no step and is reported by ``outside_root_note``.
"""
from __future__ import annotations

import functools
import os
import posixpath
import re
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from specdev_tools.core.ambiguity_items import STEP_FILE_RE
from specdev_tools.core.scope_helpers import as_dict, as_str, dict_items
from specdev_tools.core.seed_routing import resolve_seeds_for_step
from specdev_tools.graph.gitview import host_root_of, spec_path_in_repo
from specdev_tools.graph.model import Graph

DERIVES_FROM = "derives_from"
FIRST_STEP = "00"
PLAN_STEPS = ("16a", "16b", "16c")
PLAN_DIR = "impl_context"
SEED_MANIFEST_FILE = "common/seed_manifest.json"
SEED_EDIT_NOTE = "seed edit: dependants become suspect; run `specdev stale`"
_PLAN_FILE_RE = re.compile(r"^ms_.+_plan\.json$")
_PARENT = ".."


@dataclass(frozen=True)
class TouchedSteps:
    """The steps to gate for a set of touched paths.

    ``steps`` is in waterfall order; ``outside_root`` lists the paths (as given) that lie outside the host root;
    ``seed_edited`` is true when a listed seed document was among the paths.
    """

    steps: tuple[str, ...]
    outside_root: tuple[str, ...]
    seed_edited: bool


def outside_root_note(touched: TouchedSteps) -> str | None:
    """The one stderr line for paths outside the host root, or ``None`` when there are none."""
    count = len(touched.outside_root)
    if not count:
        return None
    noun = "path lies" if count == 1 else "paths lie"
    return (
        f"{count} {noun} outside the host root and map to no step; "
        "pass --git-root <repository root> when the spec folder is nested"
    )


def steps_for_paths(
    paths: Iterable[str],
    spec_dir: str,
    manifest: Mapping[str, Any],
    graph: Callable[[], Graph],
    *,
    step_order: Sequence[str],
    git_root: str | None = None,
) -> TouchedSteps:
    """The steps of *step_order* whose gate the touched *paths* put under check.

    Args:
        paths: touched files, relative to the current folder (the repository top for a pre-commit hook) or absolute.
        spec_dir: the spec folder.
        manifest: the parsed ``seed_manifest.json`` (an empty mapping when the host has none).
        graph: builds the graph of the spec; called at most once, and only when a listed seed document is touched.
        step_order: the steps of ``tools/step_order.json`` in waterfall order.
        git_root: the host repository root; the folder above *spec_dir* when absent (``host_root_of``).

    Raises:
        GitViewError: E708 when *spec_dir* is not inside the host root.
    """
    host_root = os.path.realpath(host_root_of(spec_dir, git_root))
    spec_prefix = spec_path_in_repo(spec_dir, host_root)
    seed_ids = _seed_ids_by_path(manifest)
    load_graph = functools.cache(graph)
    found: set[str] = set()
    outside: list[str] = []
    seed_edited = False
    for path in paths:
        relative = _relative_to(host_root, path)
        if relative is None:
            outside.append(path)
        elif relative in seed_ids:
            seed_edited = True
            found |= _seed_steps(seed_ids[relative], manifest, step_order, load_graph)
        elif (in_spec := _relative_to_spec(relative, spec_prefix)) is not None:
            found |= _spec_file_steps(in_spec, manifest)
    steps = _with_artifact(found & set(step_order), spec_dir, step_order)
    return TouchedSteps(steps, tuple(outside), seed_edited)


def _relative_to(host_root: str, path: str) -> str | None:
    """*path* relative to *host_root*, ``/``-separated; ``None`` when it lies outside."""
    relative = os.path.relpath(os.path.realpath(path), host_root)
    if relative == _PARENT or relative.startswith(_PARENT + os.sep):
        return None
    return relative.replace(os.sep, "/")


def _relative_to_spec(relative: str, spec_prefix: str) -> str | None:
    """*relative* (to the host root) as a path inside the spec folder, ``None`` when it is not inside."""
    inside = posixpath.relpath(relative, spec_prefix)
    return None if inside == _PARENT or inside.startswith(_PARENT + "/") else inside


def _seed_ids_by_path(manifest: Mapping[str, Any]) -> dict[str, str]:
    """``{normalised seed path (relative to the host root): seed id}`` of the listed seeds."""
    return {
        posixpath.normpath(path): seed_id
        for seed in dict_items(manifest.get("seeds"))
        if (path := as_str(seed.get("path"))) and (seed_id := as_str(seed.get("seed_id")))
    }


def _spec_file_steps(relative: str, manifest: Mapping[str, Any]) -> set[str]:
    """The steps of a file inside the spec folder (*relative* to it); empty for a file no step owns."""
    if relative == SEED_MANIFEST_FILE:
        return {FIRST_STEP, *as_dict(manifest.get("step_requirements"))}
    directory, name = posixpath.split(relative)
    if directory == PLAN_DIR and _PLAN_FILE_RE.match(name):
        return set(PLAN_STEPS)
    match = None if directory else STEP_FILE_RE.match(name)
    return {match.group(1)} if match else set()


def _seed_steps(
    seed_id: str, manifest: Mapping[str, Any], step_order: Sequence[str], graph: Callable[[], Graph]
) -> set[str]:
    """Steps whose nodes link *seed_id* with ``derives_from``, plus the steps the manifest routes it to; step 00 if none."""
    routed = {step for step in step_order if seed_id in resolve_seeds_for_step(step, dict(manifest))[1]}
    steps = _linking_steps(graph(), seed_id) | routed
    return steps or {FIRST_STEP}


def _linking_steps(graph: Graph, seed_id: str) -> set[str]:
    """The steps of the nodes that link the seed *seed_id* with ``derives_from``."""
    sources = (graph.by_id.get(link.source) for link in graph.incoming.get(seed_id, ()) if link.field == DERIVES_FROM)
    return {node.step for node in sources if node is not None and node.step}


def _with_artifact(steps: Collection[str], spec_dir: str, step_order: Sequence[str]) -> tuple[str, ...]:
    """*steps* that have an artifact in *spec_dir*, in waterfall order."""
    if not steps:
        return ()
    present = _present_steps(spec_dir)
    return tuple(step for step in step_order if step in steps and step in present)


def _present_steps(spec_dir: str) -> set[str]:
    """Steps with a file in *spec_dir*: a root ``NN_*.json``, or (for 16a to 16c) a milestone plan."""
    present = {match.group(1) for name in os.listdir(spec_dir) if (match := STEP_FILE_RE.match(name))}
    plans = os.path.join(spec_dir, PLAN_DIR)
    if os.path.isdir(plans) and any(_PLAN_FILE_RE.match(name) for name in os.listdir(plans)):
        present.update(PLAN_STEPS)
    return present
