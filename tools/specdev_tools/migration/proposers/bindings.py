"""``specdev align propose --kind bindings``: which command verified each legacy fixture, and the ``verify bind`` that records it.

A 1.1.1 host ran its fixtures by commands it wrote down in its plans (a checklist item's ``linked_test_expectation`` and
``fixture_ref``, kept by the capture) and in its CI workflows.  1.2.0 wants each fixture bound to the command and the output
guard that prove it (``specdev verify bind``).  For every step-08 fixture the proposer

1. collects the commands the legacy record names for it.  A plan item whose legacy status was ``deferred`` or ``wont_do`` is
   not trusted (its test may not exist) and is only named in the evidence.  An expectation that is a sentence, not a command,
   is no command; it becomes the reason of a ``manual`` fixture.  When no plan names a command, the host's CI workflow
   lines that name a word of the fixture are listed as candidates (never certain);
2. groups the fixtures that run the same commands (one binding binds one verifier, but ``verify run`` runs identical commands
   once, so the fixtures of a group share one run);
3. derives the guard from the test path the command names, escaped; and says why;
4. gives each fixture one ``verify bind`` line per stage its targets need (``--proves`` and ``--stage`` when more than one);
5. classes the case.

Classes (a person or ``align bind-legacy`` acts only on ``certain``):

* ``certain``: the fixture's targets are known, the trusted commands are exactly one, it runs a test runner whose report
  names the test file (``jest``, ``vitest``, ``pytest``, ``playwright``), names exactly one test file, the repository tracks
  that file, and the guard is that path.  The binding still proves nothing until ``specdev verify run`` ran it;
* ``needs-judgement``: a command or a guard is a reading, not a fact (several commands, a runner whose output may not name
  the file, a path the repository does not track, a command only CI names, a fixture that proves no node);
* ``manual``: the legacy record names no command: proposed as a ``manual`` fixture, attested by a person;
* ``bound``: the fixture already has the bindings its targets need.

A proposer runs no command and writes no spec file: it adds worklist items (``migration.worklist``) and returns the
proposals.  ``migration.legacy_bindings`` is the driver that writes bindings, through the one writer of ``verify bind``.
"""

from __future__ import annotations

import json
import os
import re
import shlex
from collections import Counter
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

from specdev_tools.graph.contract import item_of
from specdev_tools.graph.model import NOT_APPLICABLE, Graph, Node
from specdev_tools.graph.names import FIXTURE, MANUAL_MODE
from specdev_tools.graph.stages import DEFAULT_STAGE, STAGES, UnknownStageForEnvironment, bindings_of, is_retired_binding
from specdev_tools.host_install import host_workflow_files
from specdev_tools.migration.context import GitReadError
from specdev_tools.migration.proposers import KIND_BINDINGS, MigratedTree, Proposal, ProposeResult
from specdev_tools.migration.worklist import AUDIENCE_AGENT, WorklistItem, item_id, make_item
from specdev_tools.verify.bind import BindRequest, computed_stage, proved_ids, targets_of
from specdev_tools.verify.records import binding_of

STEP = "08"
KIND_GROUP = "legacy-binding"
KIND_FIXTURE = "legacy-fixture"
CERTAIN = "certain"
JUDGEMENT = "needs-judgement"
MANUAL = "manual"
BOUND = "bound"
CLASSES = (CERTAIN, JUDGEMENT, MANUAL, BOUND)
UNTRUSTED_STATUSES = ("deferred", "wont_do")
PROSE_LIMIT = 120
PROVES_NOTHING_NOTE = "a binding proves nothing until `specdev verify run` has run it on the migrated tree and the guard matched real output"

_PLAN_ITEMS = "plan_items"
_EXPECTATION = "legacy_linked_test_expectation"
_FIXTURE_REF = "legacy_fixture_ref"
_STATUS = "legacy_checklist_status"
_PATH_ECHOING_RUNNERS = frozenset({"jest", "vitest", "pytest", "py.test", "playwright"})
_RUNNABLE = frozenset(
    {"npx", "npm", "yarn", "pnpm", "bun", "node", "pytest", "py.test", "python", "python3", "bash", "sh", "make", "go", "cargo", "dotnet", "mvn", "gradle", "uv", "poetry", "ruby", "bundle", "php", "composer"}
)
_FILE_TOKEN = re.compile(r"^[\w./@+-]+\.(?:[cm]?[jt]sx?|py|sh|rb|go|php)$")
_ENV_ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
_WORDS = re.compile(r"[a-z0-9]+")
_GENERIC_WORDS = frozenset({"npm", "npx", "run", "jest", "test", "tests", "spec", "src", "bash", "python", "pytest", "node", "yarn", "pnpm", "make", "bun", "poetry", "vitest", "playwright", "the", "and"})


# --- reading one command ------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CommandReading:
    """What the proposer can tell about one command line: whether it is a command, its test files, and the guard it suggests.

    ``guard`` is the escaped test path (or, for a command that selects by a word after ``--``, that word); ``None`` when the
    command names neither.  ``certain`` is the one condition under which the guard is more than a suggestion.
    """

    command: str
    runnable: bool
    echoes_path: bool
    paths: tuple[str, ...]
    untracked: tuple[str, ...]
    guard: str | None

    @property
    def certain(self) -> bool:
        return self.runnable and self.echoes_path and len(self.paths) == 1 and not self.untracked

    def why(self) -> str:
        """The sentence that says where the guard comes from and how far it can be trusted."""
        if not self.runnable:
            return "not a command"
        if self.guard is None:
            return "the command names no test file or selector, so no guard can be derived: give a line a real run prints"
        source = f"the escaped test path {self.paths[0]}" if self.paths else "the escaped selector the command passes after --"
        if self.certain:
            return f"guard is {source}; the runner prints the path of each test file it runs and the repository tracks the file"
        reasons = []
        if not self.echoes_path:
            reasons.append("this runner's report is not known to name the test file")
        if len(self.paths) > 1:
            reasons.append(f"the command names {len(self.paths)} test files and a guard names one")
        if self.untracked:
            reasons.append(f"the repository does not track {', '.join(self.untracked)}")
        return f"guard is {source}, a suggestion only: {'; '.join(reasons) or 'confirm it with a run'}"


def normalise(command: str) -> str:
    """The command with its white space collapsed (two plan items that differ only there name one command)."""
    return " ".join(command.split())


def _tokens(command: str) -> list[str]:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return []
    while tokens and _ENV_ASSIGNMENT.match(tokens[0]):
        tokens.pop(0)
    return tokens


def _is_command(tokens: list[str]) -> bool:
    return bool(tokens) and (os.path.basename(tokens[0]) in _RUNNABLE or tokens[0].startswith("./") or _FILE_TOKEN.match(tokens[0]) is not None)


def _test_paths(tokens: list[str]) -> tuple[str, ...]:
    found = (token.split("::")[0].removeprefix("./") for token in tokens if not token.startswith("-"))
    return tuple(dict.fromkeys(path for path in found if _FILE_TOKEN.match(path)))


def _selector(tokens: list[str]) -> str | None:
    if "--" not in tokens:
        return None
    return next((token for token in tokens[tokens.index("--") + 1 :] if not token.startswith("-")), None)


def read_command(command: str, tracked: frozenset[str] | None) -> CommandReading:
    """Read *command*; *tracked* is the set of files the repository tracks (``None`` when git could not say, which leaves every path untracked)."""
    text = normalise(command)
    tokens = _tokens(text)
    runnable = _is_command(tokens)
    paths = _test_paths(tokens) if runnable else ()
    echoes = any(os.path.basename(token) in _PATH_ECHOING_RUNNERS for token in tokens)
    untracked = tuple(path for path in paths if tracked is None or path not in tracked)
    selector = _selector(tokens) if runnable else None
    chosen = paths[0] if paths else selector
    return CommandReading(text, runnable, echoes, paths, untracked, re.escape(chosen) if chosen else None)


# --- where a command comes from -----------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CiLine:
    """A test command of one of the host's own CI workflows: the command and where it stands (file, job, step number)."""

    command: str
    where: str


def _workflow_steps(host_root: str) -> Iterator[tuple[str, str, int, str]]:
    for rel, text in host_workflow_files(Path(host_root)):
        try:
            document = yaml.safe_load(text)
        except yaml.YAMLError:
            continue
        jobs = document.get("jobs") if isinstance(document, dict) else None
        if not isinstance(jobs, dict):
            continue
        for job, body in jobs.items():
            steps = body.get("steps") if isinstance(body, dict) else None
            for number, step in enumerate(steps if isinstance(steps, list) else (), start=1):
                if isinstance(step, dict) and isinstance(step.get("run"), str):
                    yield rel, str(job), number, step["run"]


def ci_test_lines(host_root: str) -> tuple[CiLine, ...]:
    """The test commands the host's own CI workflows run (a ``run:`` line, backslash continuations joined) that are not the toolkit's own calls."""
    found: list[CiLine] = []
    for rel, job, number, run in _workflow_steps(host_root):
        for line in run.replace("\\\n", " ").splitlines():
            tokens = _tokens(line.strip())
            names_test = any(os.path.basename(t) in _PATH_ECHOING_RUNNERS or t == "test" for t in tokens) or bool(_test_paths(tokens))
            if _is_command(tokens) and names_test and "specdev" not in line and "devspec" not in line:
                found.append(CiLine(normalise(line), f"{rel}, job {job}, step {number}"))
    return tuple(found)


def _words(text: str) -> frozenset[str]:
    return frozenset(word for word in _WORDS.findall(text.lower()) if len(word) >= 3 and word not in _GENERIC_WORDS)


def _tracked_files(tree: MigratedTree) -> frozenset[str] | None:
    try:
        return frozenset(tree.ctx.git("ls-files").splitlines())
    except GitReadError:
        return None


# --- the fixtures -------------------------------------------------------------------------------------------------------


@dataclass(frozen=True)
class Expectation:
    """One ``linked_test_expectation`` line of a plan item that names the fixture, with where it was written and whether it is trusted."""

    text: str
    where: str
    trusted: bool


def _expectations(tree: MigratedTree) -> dict[str, list[Expectation]]:
    """``{fixture id: its expectations}`` from the capture's plan items (a ref to a renamed fixture is mapped through the capture's renames)."""
    renames = tree.renames.get(FIXTURE, {})
    found: dict[str, list[Expectation]] = {}
    for entry in tree.capture.get(_PLAN_ITEMS, ()):
        ref = entry.get(_FIXTURE_REF)
        raw = entry.get(_EXPECTATION)
        if not isinstance(ref, str) or raw is None:
            continue
        lines = [raw] if isinstance(raw, str) else [line for line in raw if isinstance(line, str)] if isinstance(raw, list) else []
        status = entry.get(_STATUS)
        where = f"plan item {entry.get('item')} of {entry.get('file')}" + (f" ({status})" if status in UNTRUSTED_STATUSES else "")
        fixture = tree.graph.canonical_id(renames.get(ref, ref))
        found.setdefault(fixture, []).extend(Expectation(normalise(line), where, status not in UNTRUSTED_STATUSES) for line in lines if line.strip())
    return found


@dataclass(frozen=True)
class BindLine:
    """One ``verify bind``: the request, the nodes it proves and whether the tree already holds a binding that proves them all."""

    request: BindRequest
    proves: tuple[str, ...]
    stage: str
    present: bool


def bind_line(request: BindRequest, root_flags: Iterable[str] = ()) -> str:
    """The ``specdev verify bind`` line for *request*, shell-quoted; *root_flags* (already quoted words) go at the end."""
    parts = ["specdev", "verify", "bind", request.verifier]
    for command in request.commands:
        parts += ["--command", shlex.quote(command)]
    parts += ["--guard", shlex.quote(request.guard or "")]
    if request.proves:
        parts += ["--proves", *request.proves]
    if request.stage:
        parts += ["--stage", request.stage]
    return " ".join([*parts, *root_flags])


def _covered(node: Node, graph: Graph) -> set[str]:
    return {target for binding in bindings_of(node, graph) if not is_retired_binding(binding, graph) for target in proved_ids(binding_of(binding, graph), graph)}


def is_covered(node: Node, graph: Graph) -> bool:
    """Whether the fixture *node* has the bindings its targets need: every target proved; a fixture with no target, any binding at all."""
    targets = targets_of(node, graph)
    return set(targets) <= _covered(node, graph) if targets else bool(bindings_of(node, graph))


def _stage_split(node: Node, targets: tuple[str, ...], graph: Graph) -> dict[str, tuple[str, ...]]:
    """``{stage: the targets that need it}`` in stage order; raises ``UnknownStageForEnvironment`` for a target whose environment is no stage."""
    by_stage: dict[str, list[str]] = {}
    for target in targets:
        by_stage.setdefault(computed_stage((target,), node, graph), []).append(target)
    return {stage: tuple(by_stage[stage]) for stage in STAGES if stage in by_stage}


def _lines(node: Node, commands: tuple[str, ...], guard: str, graph: Graph) -> tuple[BindLine, ...]:
    targets = targets_of(node, graph)
    split = _stage_split(node, targets, graph)
    covered = _covered(node, graph)
    many = len(split) > 1
    return tuple(
        BindLine(BindRequest(node.id, commands, guard, proves if many else (), stage if many else None), proves, stage, covered.issuperset(proves))
        for stage, proves in split.items()
    )


@dataclass(frozen=True)
class Member:
    """A fixture of a group: its id, its ``verify bind`` lines (all of them, bound or not) and the evidence for its commands."""

    fixture: str
    lines: tuple[BindLine, ...]
    evidence: str

    @property
    def bound(self) -> bool:
        """Whether the fixture has lines to bind and the tree holds every one of them."""
        return bool(self.lines) and all(line.present for line in self.lines)


@dataclass(frozen=True)
class BindGroup:
    """Fixtures that run the same commands, with the guard suggested for them; ``category`` is ``certain`` or ``needs-judgement``."""

    commands: tuple[str, ...]
    guard: str | None
    category: str
    why: str
    members: tuple[Member, ...]

    @property
    def complete(self) -> bool:
        return all(member.bound for member in self.members)


@dataclass(frozen=True)
class Single:
    """A fixture the proposer cannot put in a group: it has no command (``manual``), proves no node, or its stages cannot be told."""

    fixture: str
    category: str
    reason: str
    proposal: str


@dataclass(frozen=True)
class BindingsPlan:
    """The proposals of the whole tree: the groups, the single cases and the fixtures that already hold their bindings."""

    groups: tuple[BindGroup, ...]
    singles: tuple[Single, ...]
    bound: tuple[str, ...]


def _fixtures(graph: Graph) -> list[Node]:
    """The fixtures a binding could cover: not ``not_applicable``, not ``manual`` (a manual fixture is attested), in id order."""
    nodes = [node for node in graph.by_kind.get(FIXTURE, ()) if node.lifecycle != NOT_APPLICABLE and (item_of(graph, node) or {}).get("mode") != MANUAL_MODE]
    return sorted(nodes, key=lambda node: node.id)


def _manual_reason(prose: list[str]) -> str:
    saying = f"; the plan said only: {prose[0][:PROSE_LIMIT]}" if prose else ""
    return f"the legacy plans name no command that runs this check{saying}"


def _manual_proposal(fixture: str, reason: str) -> str:
    return (
        f"class: {MANUAL}. A person carries the check out; a command cannot. Record it: "
        f"specdev json patch --id {fixture} .manual_reason {shlex.quote(json.dumps(reason, ensure_ascii=False))}; "
        f"specdev json patch --id {fixture} .mode '\"manual\"'; a person then runs `specdev verify attest {fixture}`"
    )


def _case_of(node: Node, expectations: list[Expectation], ci: tuple[CiLine, ...], graph: Graph, tracked: frozenset[str] | None) -> tuple[tuple[str, ...], CommandReading | None, str]:
    """``(commands, the reading when there is exactly one, the evidence)`` for one fixture; commands come from trusted plan items, else from CI lines naming a word of the fixture."""
    trusted = [e for e in expectations if e.trusted and _is_command(_tokens(e.text))]
    commands = tuple(dict.fromkeys(e.text for e in trusted))
    skipped = [f"{e.text!r} ({e.where})" for e in expectations if not e.trusted]
    note = f"; not used (a deferred or dropped plan item may name a test that does not exist): {'; '.join(skipped)}" if skipped else ""
    if commands:
        origins = "; ".join(dict.fromkeys(f"{e.text!r} from {e.where}" for e in trusted))
        return commands, read_command(commands[0], tracked) if len(commands) == 1 else None, origins + note
    words = _words(f"{node.id} {' '.join(e.text for e in expectations)} {(item_of(graph, node) or {}).get('description', '')}")
    candidates = [line for line in ci if words & _words(line.command)]
    if candidates:
        found_commands = tuple(dict.fromkeys(c.command for c in candidates))
        return found_commands, read_command(found_commands[0], tracked) if len(found_commands) == 1 else None, "from CI: " + "; ".join(f"{c.command!r} ({c.where})" for c in candidates) + note
    return (), None, "no plan item names a command for it" + note


def plan_bindings(tree: MigratedTree) -> BindingsPlan:
    """Classify every fixture of the tree and group those that share commands (the whole judgement of the proposer, with no write)."""
    graph = tree.graph
    expectations, tracked, ci = _expectations(tree), _tracked_files(tree), ci_test_lines(tree.ctx.host_root)
    grouped: dict[tuple[str, ...], list[tuple[Node, CommandReading | None, str, bool]]] = {}
    singles: list[Single] = []
    bound: list[str] = []
    for node in _fixtures(graph):
        found = expectations.get(node.id, [])
        commands, reading, evidence = _case_of(node, found, ci, graph, tracked)
        from_plan = any(e.trusted and e.text in commands for e in found)
        targets = targets_of(node, graph)
        if not (commands and targets) and is_covered(node, graph):
            bound.append(node.id)
            continue
        if not commands:
            reason = _manual_reason([e.text for e in found if e.trusted])
            singles.append(Single(node.id, MANUAL, f"{evidence}; manual_reason: {reason}", _manual_proposal(node.id, reason)))
            continue
        if not targets:
            singles.append(Single(node.id, JUDGEMENT, f"{evidence}; it verifies no node, so a binding would prove nothing", f"class: {JUDGEMENT}. Link the fixture to the criteria it checks, then bind it to {', '.join(commands)}"))
            continue
        grouped.setdefault(commands, []).append((node, reading, evidence, from_plan))
    groups = [_group(commands, members, graph, singles, bound) for commands, members in grouped.items()]
    return BindingsPlan(tuple(sorted((g for g in groups if g), key=lambda g: (CLASSES.index(g.category), g.commands))), tuple(sorted(singles, key=lambda s: s.fixture)), tuple(sorted(bound)))


def _group(commands: tuple[str, ...], members: list[tuple[Node, CommandReading | None, str, bool]], graph: Graph, singles: list[Single], bound: list[str]) -> BindGroup | None:
    reading = members[0][1]
    guard = reading.guard if reading else None
    certain = reading is not None and reading.certain and all(from_plan for *_, from_plan in members)
    if len(commands) > 1 or reading is None:
        why = f"{len(commands)} different commands are recorded: say whether the fixture needs all of them (one --command each) or one"
    elif not all(from_plan for *_, from_plan in members):
        why = f"the command comes from a CI workflow, not from a plan, and a CI line may run a whole suite; {reading.why()}"
    else:
        why = reading.why()
    built: list[Member] = []
    for node, _reading, evidence, _from_plan in members:
        try:
            lines = _lines(node, commands, guard, graph) if guard and len(commands) == 1 else ()
        except UnknownStageForEnvironment as error:
            singles.append(Single(node.id, JUDGEMENT, f"{evidence}; {error}", f"class: {JUDGEMENT}. Give the environment of {node.id}'s targets a stage name, then bind it"))
            continue
        member = Member(node.id, lines, evidence)
        if lines and member.bound:
            bound.append(node.id)
        built.append(member)
    if not built:
        return None
    return BindGroup(commands, guard, CERTAIN if certain and all(m.lines for m in built) else JUDGEMENT, why, tuple(built))


# --- proposals ----------------------------------------------------------------------------------------------------------


def stage_note(later: list[str]) -> str:
    """The sentence for bindings above ``dev`` (empty when there are none): ``verify run`` cannot exercise them on the current tree."""
    if not later:
        return ""
    return f". {'; '.join(later)}: `specdev verify run` runs bindings of stage dev or below, so the guard is not exercised until that stage is reached"


def group_item_id(group: BindGroup) -> str:
    """The id of the worklist item of *group* (it depends on the commands only, so it does not change when a fixture is bound)."""
    return item_id(STEP, KIND_GROUP, " && ".join(group.commands))


def _group_item(group: BindGroup) -> WorklistItem:
    listed = ", ".join(member.fixture for member in group.members)
    evidence = f"fixtures {listed}: " + " | ".join(f"{member.fixture}: {member.evidence}" for member in group.members)
    todo = [bind_line(line.request) for member in group.members for line in member.lines if not line.present]
    guard = f"guard {group.guard!r}" if group.guard else "no guard derived"
    later = [f"{line.request.verifier} needs stage {line.stage}" for member in group.members for line in member.lines if line.stage != DEFAULT_STAGE]
    action = f"To confirm: {'; '.join(todo)}" if todo else "Nothing to run: every line is bound already" if group.members[0].lines else "Give the guard and bind each fixture"
    proposal = f"class: {group.category}. command {' && '.join(group.commands)!r}, {guard} ({group.why}). {action}. Then run `specdev verify run`: {PROVES_NOTHING_NOTE}" + stage_note(later)
    return make_item(STEP, KIND_GROUP, " && ".join(group.commands), audience=AUDIENCE_AGENT, blocking=False, evidence=evidence, proposal=proposal)


def _group_proposal(group: BindGroup) -> Proposal:
    lines = [{"fixture": m.fixture, "line": bind_line(line.request), "stage": line.stage, "proves": list(line.proves), "bound": line.present} for m in group.members for line in m.lines]
    data = {"about": " && ".join(group.commands), "commands": list(group.commands), "guard": group.guard, "why": group.why, "fixtures": [m.fixture for m in group.members], "lines": lines}
    pending = sum(not line.present for m in group.members for line in m.lines)
    summary = f"{group.category:<15} {' && '.join(group.commands)}  ({len(group.members)} fixture(s), {pending} line(s) to bind; {group.why})"
    return Proposal(_group_item(group), group.category, data, summary)


def _single_proposal(single: Single) -> Proposal:
    item = make_item(STEP, KIND_FIXTURE, single.fixture, audience=AUDIENCE_AGENT, blocking=False, evidence=single.reason, proposal=single.proposal)
    return Proposal(item, single.category, {"about": single.fixture, "reason": single.reason}, f"{single.category:<15} {single.fixture}  ({single.reason})")


def propose(tree: MigratedTree) -> ProposeResult:
    """One proposal per group of fixtures that run the same commands and one per fixture that has no command or proves nothing; counts are by fixture."""
    plan = plan_bindings(tree)
    proposals = [_group_proposal(group) for group in plan.groups] + [_single_proposal(single) for single in plan.singles]
    done = set(plan.bound)
    by_class: Counter[str] = Counter({BOUND: len(done)})
    by_class.update(group.category for group in plan.groups for member in group.members if member.fixture not in done)
    by_class.update(single.category for single in plan.singles)
    counts: Mapping[str, int] = {"fixtures": sum(by_class.values()), **{name: by_class[name] for name in CLASSES}, "groups": len(plan.groups)}
    return ProposeResult(KIND_BINDINGS, tuple(proposals), counts, (PROVES_NOTHING_NOTE,))
