"""What a migration run reports: per script counts, the diff of a dry run, residue, and the errors that stopped it."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from specdev_tools.core.errors import SpecError
from specdev_tools.core.constants import STAMP_FILE

STATUS_OK = "ok"
STATUS_NOOP = "noop"
STATUS_REFUSED = "refused"  # E880: the runner did not start
STATUS_FAILED = "failed"  # E881: a script broke an invariant, nothing was written

_TIMESTAMP = re.compile(r"\d{4}-\d\d-\d\dT[\d:.]+Z?")


@dataclass(frozen=True)
class ScriptReport:
    """One script's part of a run: the edits ``detect`` found, those ``apply`` made, worklist items and residue."""

    id: str
    phase: int
    detected: int
    edits: int
    worklist_items: int = 0
    residue: tuple[str, ...] = ()


@dataclass
class MigrationReport:
    """The outcome of ``run_migration``; ``to_json`` and ``render`` are the two ways it is printed."""

    status: str
    dry_run: bool
    from_version: str | None = None
    to_version: str | None = None
    scripts: list[ScriptReport] = field(default_factory=list)
    errors: list[SpecError] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    not_run: list[str] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    diff: str = ""
    spec_dir: str = "spec"

    @property
    def edits_by_script(self) -> dict[str, int]:
        return {script.id: script.edits for script in self.scripts}

    @property
    def worklist_items(self) -> int:
        return sum(script.worklist_items for script in self.scripts)

    @property
    def residue(self) -> list[str]:
        return [line for script in self.scripts for line in script.residue]

    @property
    def total_edits(self) -> int:
        return sum(script.edits for script in self.scripts)

    def to_json(self) -> dict[str, Any]:
        """``{status, dry_run, edits_by_script, worklist_items, residue, errors}``; an error is ``{code, message}``."""
        return {
            "status": self.status,
            "dry_run": self.dry_run,
            "edits_by_script": self.edits_by_script,
            "worklist_items": self.worklist_items,
            "residue": self.residue,
            "errors": [{"code": error.code, "message": error.message} for error in self.errors],
        }

    def render(self) -> str:
        """The text a person reads: the errors, or the script lines, the notes and (dry run) the diff."""
        lines: list[str] = [error.render() for error in self.errors]
        if self.status in (STATUS_REFUSED, STATUS_FAILED):
            return "\n".join(lines)
        if self.from_version and self.to_version:
            lines.append(f"migration {self.from_version} -> {self.to_version}" + (" (dry run, nothing written)" if self.dry_run else ""))
        lines.extend(self.notes)
        for script in self.scripts:
            lines.append(
                f"  p{script.phase} {script.id}: {script.edits} edit(s), {script.worklist_items} worklist item(s)"
                if script.detected
                else f"  p{script.phase} {script.id}: nothing to do"
            )
        if self.scripts:
            lines.append(f"total: {self.total_edits} edit(s), {self.worklist_items} worklist item(s), {len(self.changed_files)} file(s) changed")
        lines.extend(f"residue: {line}" for line in self.residue)
        if self.not_run and self.changed_files:
            lines.append("not run by the runner (do these by hand):")
            lines.extend(f"  - {entry}" for entry in self.not_run)
        if self.dry_run:
            lines.append(self.diff if self.diff else "no change")
        elif self.changed_files:
            lines.append(f"review: git diff --stat {self.spec_dir}")
            lines.append(f"undo:   git checkout -- {self.spec_dir} && git clean -fd {self.spec_dir}  (the second removes the files the run created)")
            version = f" to toolkit v{self.to_version}" if self.to_version else ""
            lines.append(
                f'commit: git add {self.spec_dir} && git commit --no-verify -m "Migrate the spec{version}"'
                "  (--no-verify: your old hooks still name commands the new release removed)"
            )
            lines.append(f"next:   specdev align triage {self.spec_dir}  (the decisions the run left for a person)")
        return "\n".join(lines)


def mask_stamp_timestamps(diff: str) -> str:
    """*diff* with every timestamp inside the diff of ``spec/specdev_version`` replaced by ``<timestamp>``.

    The stamp's dates are clock values; a dry run prints and compares them masked.  Other files are left as they are.
    """
    out: list[str] = []
    in_stamp = False
    for line in diff.splitlines(keepends=True):
        if line.startswith("+++ "):
            in_stamp = line.rstrip("\n").endswith(f"/{STAMP_FILE}")
        out.append(_TIMESTAMP.sub("<timestamp>", line) if in_stamp and not line.startswith(("--- ", "+++ ")) else line)
    return "".join(out)
