"""``verify run``: run the commands of bindings and write the evidence.

The tool runs the commands and measures the code tree and the output; it is the only writer of run evidence, and no hash or
tree id is ever supplied by a caller.  A run passes when the commands exit 0 and the output matches the guard.  There is one
evidence file per binding and run stage (``evd-<binding suffix>-<stage>.json``) and each run overwrites the last: the latest
run is the evidence and git keeps the earlier ones.  With ``record=False`` nothing is written and the evidence comes back in
memory.
"""
from __future__ import annotations

import hashlib
import os
import signal
import subprocess
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from specdev_tools.core.errors import make_error
from specdev_tools.core.host_declarations import HostDeclarations
from specdev_tools.core.json_utils import resolve_effective_toolkit_root
from specdev_tools.graph.build import build_graph
from specdev_tools.graph.model import Graph
from specdev_tools.graph.queries import ROADMAP_MILESTONE, milestone_of, unknown_node_error
from specdev_tools.proof.stages import stage_rank
from specdev_tools.trace.hashing import compute_all
from specdev_tools.trace.lockfile import with_write_lock
from specdev_tools.trace.writing import seed_texts_for_write
from specdev_tools.verify.code_tree import code_tree_for_host, declarations_of
from specdev_tools.verify.guard import GuardError, guard_matches
from specdev_tools.verify.installed_versions import installed_versions
from specdev_tools.verify.records import BINDING_KIND, Binding, Evidence, EVIDENCE_PREFIX, all_bindings, binding_of, refusal, write_evidence

TIMEOUT_EXIT_CODE = 124
"""The exit code recorded for a command that was killed at ``--timeout`` (the code of ``timeout(1)``)."""
_TASK_CRITERION = "task-criterion"
_VERIFIED_BY = "verified_by"
_BINDING_PREFIX = "ver-"
_NO_HASH = "sha256:"


@dataclass(frozen=True)
class _Execution:
    """One execution of a command list: shared by every binding with the same commands and guard."""

    exit_code: int
    output_hash: str
    guard_matched: bool
    tested_tree: str
    tree_changed: bool


def _run_command(command: str, cwd: str, timeout: float | None) -> tuple[int, bytes]:
    """Run *command* in a shell in *cwd*; ``(exit code, stdout then stderr)``.

    At *timeout* seconds the whole process group is killed, the output captured so far is kept and the exit code is
    ``TIMEOUT_EXIT_CODE``.
    """
    process = subprocess.Popen(command, shell=True, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
    try:
        out, err = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        out, err = process.communicate()
        return TIMEOUT_EXIT_CODE, out + err
    return process.returncode, out + err


def _run_commands(commands: Sequence[str], cwd: str, timeout: float | None) -> tuple[int, bytes]:
    """Run *commands* in order, stopping at the first that fails; ``(that exit code or 0, the output of every command run)``."""
    output = b""
    for command in commands:
        exit_code, out = _run_command(command, cwd, timeout)
        output += out
        if exit_code != 0:
            return exit_code, output
    return 0, output


def _execute(binding: Binding, spec_dir: str, git_root: str, timeout: float | None) -> _Execution:
    """Run the commands of *binding* between two measurements of the code tree; the evidence records the tree after the run."""
    before = code_tree_for_host(git_root, spec_dir)
    exit_code, output = _run_commands(binding.commands, git_root, timeout)
    after = code_tree_for_host(git_root, spec_dir)
    try:
        matched = exit_code != TIMEOUT_EXIT_CODE and guard_matches(binding.guard, output)
    except GuardError as exc:
        raise refusal("E332", f"binding '{binding.id}': {exc}") from exc
    return _Execution(exit_code, _NO_HASH + hashlib.sha256(output).hexdigest(), matched, after, after != before)


def evidence_id(binding_id: str, stage: str) -> str:
    """The id of the evidence of *binding_id* run at *stage*: ``evd-`` and the binding id without ``ver-``, then the stage."""
    return f"{EVIDENCE_PREFIX}{binding_id.removeprefix(_BINDING_PREFIX)}-{stage}"


def _tree_note(binding_id: str) -> str:
    return make_error(
        "W351", f"the run of '{binding_id}' changed the code tree; add the generated paths to code_tree_exclusions or .gitignore"
    ).render()


def _binding(graph: Graph, binding_id: str) -> Binding:
    node = graph.find(binding_id)
    if node is None:
        raise unknown_node_error(graph, binding_id)
    if node.kind != BINDING_KIND:
        raise refusal("E706", f"'{node.id}' is of kind {node.kind}, not a binding (a verification record)")
    return binding_of(node, graph)


def _selected(bindings: Sequence[Binding], stage: str, only_stage: bool, *, explicit: bool) -> list[Binding]:
    """The *bindings* a run at *stage* takes: those of that stage or below; with *only_stage* those of exactly that stage.

    A binding named by the caller (*explicit*) above the run stage is refused (E767); a binding found by ``--all`` or
    ``--milestone`` above it is left out.
    """
    above = next((binding for binding in bindings if stage_rank(binding.stage) > stage_rank(stage)), None)
    if explicit and above is not None:
        raise refusal("E767", f"binding '{above.id}' is a {above.stage} binding and this run is at {stage}; run with --stage {above.stage}")
    wanted = [binding for binding in bindings if stage_rank(binding.stage) <= stage_rank(stage)]
    return [binding for binding in wanted if binding.stage == stage] if only_stage else wanted


def milestone_binding_ids(graph: Graph, milestone: str) -> list[str]:
    """The ids of the bindings of the verifiers that the task criteria of *milestone* name in ``verified_by``, in graph order.

    Raises:
        FindingError: E706 when *milestone* is not a roadmap milestone.
    """
    found = graph.find(milestone)
    if found is None or found.kind != ROADMAP_MILESTONE:
        raise unknown_node_error(graph, milestone) if found is None else refusal("E706", f"'{found.id}' is not a roadmap milestone")
    verifiers = {
        graph.canonical_id(link.target)
        for node in graph.by_kind.get(_TASK_CRITERION, ()) if milestone_of(graph, node) == found.id
        for link in node.links if link.field == _VERIFIED_BY
    }
    return [binding.id for binding in all_bindings(graph) if binding.verifier in verifiers]


def selected_ids(graph: Graph, *, every: bool, milestone: str | None, stage: str, only_stage: bool) -> list[str]:
    """The ids ``verify run --all`` or ``--milestone`` takes at *stage*."""
    candidates = all_bindings(graph) if every else [_binding(graph, binding_id) for binding_id in milestone_binding_ids(graph, milestone or "")]
    return [binding.id for binding in _selected(candidates, stage, only_stage, explicit=False)]


@dataclass(frozen=True)
class _Context:
    """What every binding of one invocation shares."""

    graph: Graph
    spec_dir: str
    evidence_dir: str
    git_root: str
    repo_root: str
    stage: str
    declarations: HostDeclarations
    hashes: Mapping[str, tuple[str, str]]
    timeout: float | None
    overrides: Mapping[str, str]


def _evidence_for(binding: Binding, execution: _Execution, context: _Context) -> Evidence:
    proved = [node for node_id in binding.proves if (node := context.graph.find(node_id)) is not None]
    versions, notes = installed_versions(proved, context.graph, context.declarations, context.git_root, context.overrides)
    hashed = {node_id: context.hashes[node_id][0] for node_id in (binding.verifier, *binding.proves) if node_id in context.hashes}
    return Evidence(
        evidence_id=evidence_id(binding.id, context.stage),
        about=(binding.id,),
        stage=context.stage,
        tested_tree=execution.tested_tree,
        exit_code=execution.exit_code,
        guard_matched=execution.guard_matched,
        output_hash=execution.output_hash,
        installed_versions=versions,
        recorded_hashes=hashed,
        notes=(*([_tree_note(binding.id)] if execution.tree_changed else []), *notes),
    )


def _run_group(group: Sequence[Binding], context: _Context, record: bool) -> list[Evidence]:
    """Run the commands of the first binding of *group* once, and make (and write) the evidence of every binding in it."""
    execution = _execute(group[0], context.spec_dir, context.git_root, context.timeout)
    results = [_evidence_for(binding, execution, context) for binding in group]
    if record:
        for evidence in results:
            with with_write_lock(context.spec_dir):
                write_evidence(context.evidence_dir, context.repo_root, evidence.to_item())
    return results


def _groups(bindings: Sequence[Binding]) -> list[list[Binding]]:
    """The bindings grouped by (commands, guard), in order of first appearance: a group is run once."""
    groups: dict[tuple[tuple[str, ...], str], list[Binding]] = {}
    for binding in bindings:
        groups.setdefault((binding.commands, binding.guard), []).append(binding)
    return list(groups.values())


def run_bindings(
    binding_ids: Sequence[str],
    spec_dir: str,
    evidence_dir: str,
    git_root: str,
    record: bool = True,
    stage: str = "dev",
    only_stage: bool = False,
    *,
    timeout: float | None = None,
    installed: Mapping[str, str] | None = None,
    repo_root: str | None = None,
    graph: Graph | None = None,
) -> list[Evidence]:
    """Run the bindings *binding_ids* at *stage* and return their evidence, in the order given.

    The commands run in a shell in *git_root*; the evidence is written to *evidence_dir* unless *record* is false (the
    merge check: the run is the proof and nothing is stored).  *only_stage* leaves out the named bindings of a lower stage.
    Bindings with the same commands and guard run once.  *timeout* is per command, in seconds; *installed* names the
    version of third parties as installed (it wins over the working tree).  *graph* and *repo_root* are used when given
    (the toolkit root is found otherwise).

    Raises:
        FindingError: E706 for an id that is not a binding; E767 for a named binding above *stage*; E520 for an unreadable
            declarations file or a seed document that was not found; E332 for a guard that is not a regular expression;
            E769 when another write holds the lock; E708 when git fails.
    """
    spec_root, host_root = os.path.abspath(spec_dir), os.path.abspath(git_root)
    toolkit = repo_root if repo_root is not None else resolve_effective_toolkit_root(None)
    known = graph if graph is not None else build_graph(spec_root, toolkit)
    named = [_binding(known, binding_id) for binding_id in dict.fromkeys(binding_ids)]
    chosen = _selected(named, stage, only_stage, explicit=True)
    context = _Context(
        known, spec_root, evidence_dir, host_root, toolkit, stage, declarations_of(spec_root),
        compute_all(known, seed_texts_for_write(known, host_root)), timeout, installed or {},
    )
    results: dict[str, Evidence] = {}
    for group in _groups(chosen):
        for evidence in _run_group(group, context, record):
            results[evidence.about[0]] = evidence
    return [results[binding.id] for binding in chosen]
