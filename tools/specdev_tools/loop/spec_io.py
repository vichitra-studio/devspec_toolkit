"""What ``specdev loop`` reads from a spec: the nodes of a scope and their content hashes,
the step gate, the suspect links, the open items, and the text a quote must occur in.

Everything here calls the functions the existing commands call (``spec-check --step``,
``specdev stale``, ``specdev attest``, ``upstream-backlog``); nothing is computed a second
way. The loop writes nothing through this module.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from specdev_tools.core.ambiguity_items import read_ambiguity_items
from specdev_tools.core.errors import FindingError
from specdev_tools.graph.build import build_graph, step_order_ranks
from specdev_tools.graph.gitview import read_seed_texts
from specdev_tools.graph.model import Graph, Node
from specdev_tools.graph.queries import own_content
from specdev_tools.trace import replay
from specdev_tools.trace.attest import plan_step_attest
from specdev_tools.trace.lockfile import read_lock
from specdev_tools.trace.step_ready import check_ready, present_steps, required_spec_inputs
from specdev_tools.validation.graph_checks import install_gap_provider
from specdev_tools.validation.step_gate_run import gate_run

CLUSTER_STEPS = 6
"""Steps per reviewer cluster."""

CanonDirFn = Callable[[Optional[str], Optional[str], Optional[str]], Optional[str]]


@dataclass(frozen=True)
class Roots:
    repo: str
    spec: str
    git: str


@dataclass
class GateView:
    blocking: dict[str, str] = field(default_factory=dict)  # key -> target, owned by the scope
    messages: dict[str, str] = field(default_factory=dict)  # key -> the error's text
    owner: dict[str, str] = field(default_factory=dict)  # key -> the step that owns the error (not always its node's step)
    result: dict[str, str] = field(default_factory=dict)  # step -> clear | blocked
    blocked_by: list[str] = field(default_factory=list)  # "step NN: CODE message", outside the scope
    waiting: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class LinkView:
    listed: dict[str, tuple[str, str]] = field(default_factory=dict)  # key -> (holder, chain stamp)
    detail: dict[str, dict[str, Any]] = field(default_factory=dict)  # key -> holder, field, target, cause, roots
    waiting: list[str] = field(default_factory=list)  # holders `attest` would refuse (E764)
    gaps: list[str] = field(default_factory=list)
    suspect_steps: list[str] = field(default_factory=list)  # the steps that hold a suspect link, attestable or not


def _hash(value: Any) -> str:
    text = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def squash(text: str) -> str:
    """Text with every run of whitespace as one space: a quote is matched this way."""
    return re.sub(r"\s+", " ", text).strip()


def ordered_steps(repo_root: str, steps: list[str]) -> list[str]:
    ranks = step_order_ranks(repo_root)
    return sorted(dict.fromkeys(steps), key=lambda s: ranks.get(s, 10**6))


class SpecIO:
    """One reading of the spec, for one ``loop`` command."""

    def __init__(self, roots: Roots, steps: list[str], canon_dir: CanonDirFn | None = None) -> None:
        install_gap_provider()
        self.roots = roots
        self.steps = ordered_steps(roots.repo, steps)
        self._canon_dir = canon_dir
        self.graph: Graph = build_graph(roots.spec, roots.repo)

    # ------------------------------------------------------------ scope and content

    def file_key(self, spec_file: str) -> str:
        """A spec file as findings name it: its path from the host root."""
        return os.path.relpath(os.path.join(self.roots.spec, spec_file), self.roots.git).replace(os.sep, "/")

    def files(self) -> dict[str, str]:
        """The artifact files of the scope: file key -> step."""
        out: dict[str, str] = {}
        for step in self.steps:
            for spec_file in self.graph.shape.files_by_step.get(step, ()):
                out[self.file_key(spec_file)] = step
        return out

    def nodes(self) -> list[Node]:
        wanted = set(self.steps)
        return [n for n in self.graph.nodes if n.step in wanted]

    def content(self) -> dict[str, str]:
        """The content hash of every in-scope node and artifact file.

        A node: its own item with child collections as ids, so adding or removing a child
        changes the parent. A file: what is in it and is no node's (top-level fields and the
        open items), so recording an open item is a change of content.
        """
        out: dict[str, str] = {}
        for node in self.nodes():
            out[node.id] = _hash(own_content(self.graph, node, full=False))
        for step in self.steps:
            for spec_file in self.graph.shape.files_by_step.get(step, ()):
                document = self.graph.documents.get(spec_file) or {}
                top = {k: v for k, v in document.items() if k == "ambiguities" or not isinstance(v, (list, dict))}
                out[self.file_key(spec_file)] = _hash(top)
        return out

    def outside_content(self, inside: set[str]) -> dict[str, str]:
        """The content hash of what a fixer of this run may not change: every node that is not in *inside* (the keys
        of the run's own content), and the text of every seed document."""
        out = {n.id: _hash(own_content(self.graph, n, full=False)) for n in self.graph.nodes if n.id not in inside}
        for seed_id, text in read_seed_texts(self.graph, self.roots.git).items():
            out[f"seed document {seed_id}"] = _hash(text)
        return out

    def clusters(self) -> dict[str, int]:
        """Reviewer cluster per node and file: up to six consecutive steps each."""
        index = {step: i // CLUSTER_STEPS for i, step in enumerate(self.steps)}
        out = {n.id: index.get(n.step or "", 0) for n in self.nodes()}
        out.update({key: index.get(step, 0) for key, step in self.files().items()})
        return out

    def step_of(self, target: str) -> str | None:
        """The step a finding's target belongs to: a node's step, a scope file's step, else None."""
        node = self.graph.find(target)
        if node is not None:
            return node.step
        return self.files().get(target)

    def in_scope(self, target: str) -> bool:
        """Whether a finding about *target* is this run's to fix: a node or an artifact file of its steps."""
        return self.step_of(target) in set(self.steps)

    def exists(self, target: str) -> bool:
        if self.graph.find(target) is not None:
            return True
        return os.path.exists(os.path.join(self.roots.git, target)) or os.path.exists(target)

    def text_of(self, source: str) -> str | None:
        """The text a quote from *source* must occur in: a node's item, or a file."""
        node = self.graph.find(source)
        if node is not None:
            item = own_content(self.graph, node, full=True)
            return json.dumps(item, ensure_ascii=False) if item is not None else None
        for path in (source, os.path.join(self.roots.git, source), os.path.join(self.roots.repo, source)):
            if os.path.isfile(path):
                with open(path, encoding="utf-8", errors="replace") as handle:
                    return handle.read()
        return None

    def quote_occurs(self, source: str, text: str) -> bool:
        haystack = self.text_of(source)
        if haystack is None or not text.strip():
            return False
        needle = squash(text)
        return needle in squash(haystack) or needle in squash(haystack.replace('\\"', '"').replace("\\n", " "))

    def label(self, node_id: str) -> str:
        node = self.graph.find(node_id)
        return f"{node_id} ({node.label})" if node is not None and node.label else node_id

    # ------------------------------------------------------------ gate, links, items

    def gate(self, base_ref: str | None) -> GateView:
        view = GateView()
        present = [s for s in self.steps if self.graph.shape.files_by_step.get(s)]
        if not present:
            return view
        canon = self._canon_dir(self.roots.git, self.roots.spec, self.roots.spec) if self._canon_dir else None
        try:
            run = gate_run(
                self.roots.repo, self.roots.spec, steps=present, paths=None,
                git_root=self.roots.git, spec_root=self.roots.spec, project_canon_dir=canon, base_ref=base_ref,
            )
        except FindingError as exc:
            view.notes.append(exc.error.render())
            return view
        view.notes.extend(run.notes)
        owners = {f"step:{s}" for s in self.steps}
        for result in run.results:
            view.result[result.step] = "clear" if result.clear else "blocked"
            for err in result.blocking.errors:
                target = err.node_id or (self.file_key(err.file) if err.file else self.file_key(""))
                if err.owner in owners or err.owner is None:
                    key = f"{err.code}|{target}"
                    owner = (err.owner or f"step:{result.step}").split(":", 1)[-1]
                    view.blocking[key] = target
                    view.messages[key] = f"[step {owner}] {err.message}"
                    view.owner[key] = owner
                else:
                    line = f"{err.owner}: {err.code} {err.message}"
                    if line not in view.blocked_by:
                        view.blocked_by.append(line)
            for waiting in result.waiting:
                view.waiting.append(f"{waiting.error.code} {waiting.error.node_id or ''} waits on {', '.join(waiting.reasons)}")
        return view

    def links(self) -> LinkView:
        """The suspect links of the scope that `specdev attest` would accept now, upward first."""
        view = LinkView()
        if not os.path.isdir(self.roots.spec):
            return view
        lock = read_lock(self.roots.spec)
        seed_texts = read_seed_texts(self.graph, self.roots.git)
        for step in self.steps:
            if not self.graph.shape.files_by_step.get(step):
                continue
            plan = plan_step_attest(self.graph, lock, seed_texts, step)
            for link in plan.links:
                if link.suspect is None:
                    continue
                entry = link.new
                key = f"E763|{entry.source}|{entry.field}|{entry.target}"
                view.listed[key] = (entry.source, entry.chain_stamp)
                view.detail[key] = {
                    "holder": entry.source, "field": entry.field, "target": entry.target,
                    "cause": link.suspect.cause, "roots": list(link.suspect.roots),
                }
            view.waiting.extend(blocked.node for blocked in plan.blocked)
        whole = replay.compute_replay(self.graph, lock, seed_texts)
        for step in replay.pending_replay(whole, self.steps):
            view.gaps.extend(f"{gap.code} {gap.node}" for gap in step.coverage_gaps)
            if step.nodes and step.step:
                view.suspect_steps.append(step.step)
        return view

    def open_item_ids(self) -> set[str]:
        read = read_ambiguity_items(self.roots.spec)
        return {item.id for item in read.items if item.id}

    def open_items_about(self, node_ids: set[str]) -> list[dict[str, Any]]:
        out = []
        for item in read_ambiguity_items(self.roots.spec).items:
            if set(item.about_ids) & node_ids:
                out.append({"id": item.id, "about": list(item.about_ids), "description": item.description})
        return out

    def ready(self, step: str) -> tuple[bool, list[str]]:
        """What `specdev step ready NN` answers: ready or not, and the first blockers."""
        lock = read_lock(self.roots.spec)
        plan = replay.compute_replay(self.graph, lock, read_seed_texts(self.graph, self.roots.git))
        verdict = check_ready(self.graph, plan, step, required_spec_inputs(self.roots.repo, step),
                              present_steps(self.graph, self.roots.spec))
        return verdict.ready, [f"{b.step}: {b.reason} {b.node or ''}".strip() for b in verdict.blockers[:10]]

    # ------------------------------------------------------------ contract paths

    def contract_paths(self, step: str) -> list[str]:
        """The step's prompt, its schema and the shared expectations, as absolute paths."""
        repo = self.roots.repo
        found = sorted(glob.glob(os.path.join(repo, "prompts", f"prompt_{step}_*.md")))
        found += sorted(glob.glob(os.path.join(repo, "schema", f"{step}_*.schema.json")))
        shared = os.path.join(repo, "docs", "prompts", "shared_expectations.md")
        return [os.path.abspath(p) for p in [*found, shared] if os.path.isfile(p)]
