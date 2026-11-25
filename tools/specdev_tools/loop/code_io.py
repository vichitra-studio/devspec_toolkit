"""What ``specdev loop`` reads for the kinds of a milestone: its plan (``plan``), one plan
item's code (``code-group``) and the milestone's code (``code-milestone``).

The classes have the interface of :class:`SpecIO` that the commands use, so a run of any kind
goes through the same intake and the same machine.
"""

from __future__ import annotations

import fnmatch
import glob
import hashlib
import json
import os
import subprocess
from typing import Any

from specdev_tools.core.ambiguity_items import is_open, read_ambiguity_items
from specdev_tools.graph.model import Node
from specdev_tools.loop.spec_io import CanonDirFn, GateView, LinkView, Roots, SpecIO, _hash

PLAN_STEP = "16a"
ABSENT = "absent"
OUTSIDE_INSTRUCTION = (
    "This is outside what the code agent may edit. Record it as an open item of the plan and answer `recorded` with "
    "the item's id."
)


def _norm(path: str) -> str:
    return os.path.normpath(path).replace(os.sep, "/")


class PlanIO(SpecIO):
    """The plan of one milestone: its plan items and the plan file. The plan may not exist yet (``--author``)."""

    def __init__(self, roots: Roots, milestone: str, canon_dir: CanonDirFn | None = None) -> None:
        super().__init__(roots, [PLAN_STEP], canon_dir)
        self.milestone = milestone
        self.plan_file: str | None = None  # relative to the spec root
        for spec_file in self.graph.shape.files_by_step.get(PLAN_STEP, ()):
            document = self.graph.documents.get(spec_file) or {}
            if document.get("milestone") == milestone:
                self.plan_file = spec_file

    @property
    def plan(self) -> dict[str, Any]:
        return dict(self.graph.documents.get(self.plan_file) or {}) if self.plan_file else {}

    @property
    def batch(self) -> str:
        stem = os.path.basename(self.plan_file or "")
        return stem[len("ms_"):-len("_plan.json")] if stem.startswith("ms_") and stem.endswith("_plan.json") else stem

    def present(self) -> bool:
        return self.plan_file is not None

    def files(self) -> dict[str, str]:
        return {self.file_key(self.plan_file): PLAN_STEP} if self.plan_file else {}

    def nodes(self) -> list[Node]:
        return [n for n in self.graph.nodes if self.plan_file and n.file == self.plan_file and n.role != "record"]

    def content(self) -> dict[str, str]:
        out = {node.id: _hash(self.text_of(node.id)) for node in self.nodes()}
        if self.plan_file:
            rest = {k: v for k, v in self.plan.items() if k != "execution"}
            plan = dict(rest.get("plan") or {})
            alignment = dict(plan.get("spec_alignment") or {})
            alignment["checklist"] = [i.get("id") for i in alignment.get("checklist") or [] if isinstance(i, dict)]
            plan["spec_alignment"] = alignment
            rest["plan"] = plan
            out[self.file_key(self.plan_file)] = _hash(rest)
        return out

    def clusters(self) -> dict[str, int]:
        return {name: 0 for name in self.content()}

    def in_scope(self, target: str) -> bool:
        return target in self.content()

    def gate(self, base_ref: str | None) -> GateView:
        view = super().gate(base_ref)
        if not self.plan_file:
            return GateView()
        mine = set(self.content())
        for key in [k for k, target in view.blocking.items() if target not in mine]:
            line = f"another plan: {key} {view.messages.pop(key)}"
            del view.blocking[key]
            view.owner.pop(key, None)
            view.blocked_by.append(line)
        return view

    def links(self) -> LinkView:
        return LinkView()  # the links of a plan stay with the trinity skill (graph design 8.5)

    def open_plan_items(self) -> list[str]:
        if not self.plan_file:
            return []
        path = os.path.abspath(os.path.join(self.roots.spec, self.plan_file))
        return [i.id for i in read_ambiguity_items(self.roots.spec).items
                if os.path.abspath(i.artifact_path) == path and is_open(i)]

    def contract_paths(self, step: str = PLAN_STEP) -> list[str]:
        repo = self.roots.repo
        found = sorted(glob.glob(os.path.join(repo, "prompts", "prompt_16a_*.md")))
        found += [os.path.join(repo, "schema", "16_impl_context.schema.json"),
                  os.path.join(repo, "docs", "prompts", "shared_expectations.md")]
        return [os.path.abspath(p) for p in found if os.path.isfile(p)]


class CodeIO(PlanIO):
    """The code of one plan item (*group*), or of the whole milestone (*group* is None)."""

    def __init__(self, roots: Roots, milestone: str, group: str | None, canon_dir: CanonDirFn | None = None) -> None:
        super().__init__(roots, milestone, canon_dir)
        self.group = group
        summary = dict(dict(self.plan.get("plan") or {}).get("summary") or {})
        self.patterns = [_norm(p) for p in summary.get("target_file_patterns") or [] if isinstance(p, str)]
        self.supporting = [_norm(p) for p in summary.get("milestone_supporting_files") or [] if isinstance(p, str)]

    def item(self) -> dict[str, Any] | None:
        checklist = dict(dict(self.plan.get("plan") or {}).get("spec_alignment") or {}).get("checklist") or []
        for entry in checklist:
            if isinstance(entry, dict) and entry.get("id") == self.group:
                return entry
        return None

    def actions(self) -> list[dict[str, Any]]:
        item = self.item() or {}
        found = dict(item.get("implementation") or {}).get("actions") or []
        return [a for a in found if isinstance(a, dict)]

    def _tracked(self) -> list[str]:
        done = subprocess.run(["git", "ls-files", "--cached", "--others", "--exclude-standard"], cwd=self.roots.git,
                              capture_output=True, text=True, check=False)
        return [_norm(line) for line in done.stdout.splitlines() if line.strip()]

    def _matches(self, path: str) -> bool:
        path = _norm(path)
        return path in self.supporting or any(fnmatch.fnmatch(path, pattern) for pattern in self.patterns)

    def code_files(self) -> list[str]:
        if self.group is not None:
            item = self.item() or {}
            named = [a.get("target") for a in self.actions() if str(a.get("type", "")).startswith("file_")]
            named += list(item.get("files_touched") or [])
            return sorted({_norm(p) for p in named if isinstance(p, str) and p})
        return sorted({p for p in self._tracked() if self._matches(p)} | set(self.supporting))

    def _file_hash(self, path: str) -> str:
        full = os.path.join(self.roots.git, path)
        if not os.path.isfile(full):
            return ABSENT
        with open(full, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()[:16]

    def content(self) -> dict[str, str]:
        """Each code file, and the plan file: for a group, its item and the records of its actions; else the whole plan."""
        out = {path: self._file_hash(path) for path in self.code_files()}
        if self.plan_file:
            plan = self.plan
            if self.group is None:
                out[self.file_key(self.plan_file)] = _hash(plan)
            else:
                records = [r for r in dict(plan.get("execution") or {}).get("records") or []
                           if self.group in json.dumps(r)]
                out[self.file_key(self.plan_file)] = _hash([self.item(), records])
        return out

    def in_scope(self, target: str) -> bool:
        target = _norm(target)
        if self.plan_file and target == self.file_key(self.plan_file):
            return True
        if self.group is not None:
            return target == self.group or target in self.code_files()
        return self._matches(target) or self.graph.find(target) is not None and target in {n.id for n in self.nodes()}

    def exists(self, target: str) -> bool:
        return self.in_scope(target) or super().exists(target)

    def step_of(self, target: str) -> str | None:
        return "code" if self.in_scope(target) else super().step_of(target)

    def gate(self, base_ref: str | None) -> GateView:
        return GateView()  # the reviewer keeps the spec-check run it does today

    def recorded_actions(self) -> set[str]:
        records = dict(self.plan.get("execution") or {}).get("records") or []
        text = json.dumps(records)
        return {str(a.get("id")) for a in self.actions() if f"{self.group}/{a.get('id')}" in text}

    def contract_paths(self, step: str = PLAN_STEP) -> list[str]:
        repo = self.roots.repo
        names = ["prompt_16b_*.md"] if self.group is not None else []
        names.append("prompt_16c_*.md")
        found: list[str] = []
        for name in names:
            found += sorted(glob.glob(os.path.join(repo, "prompts", name)))
        found.append(os.path.join(repo, "docs", "prompts", "shared_expectations.md"))
        return [os.path.abspath(p) for p in found if os.path.isfile(p)]


class FileIO(SpecIO):
    """One non-step file of ``spec/common/`` (today's ``manifest_artifact`` scope): read-only, with no step gate."""

    def __init__(self, roots: Roots, spec_file: str, canon_dir: CanonDirFn | None = None) -> None:
        super().__init__(roots, [], canon_dir)
        self.spec_file = spec_file  # relative to the spec root

    def files(self) -> dict[str, str]:
        return {self.file_key(self.spec_file): "common"}

    def nodes(self) -> list[Node]:
        return [n for n in self.graph.nodes if n.file == self.spec_file]

    def content(self) -> dict[str, str]:
        with open(os.path.join(self.roots.spec, self.spec_file), "rb") as handle:
            return {self.file_key(self.spec_file): hashlib.sha256(handle.read()).hexdigest()[:16]}

    def clusters(self) -> dict[str, int]:
        return {name: 0 for name in self.content()}

    def in_scope(self, target: str) -> bool:
        return target in self.content() or any(n.id == target for n in self.graph.nodes if n.step == "seed")

    def gate(self, base_ref: str | None) -> GateView:
        return GateView()

    def links(self) -> LinkView:
        return LinkView()

    def contract_paths(self, step: str = "") -> list[str]:
        shared = os.path.join(self.roots.repo, "docs", "prompts", "shared_expectations.md")
        return [os.path.abspath(shared)] if os.path.isfile(shared) else []
