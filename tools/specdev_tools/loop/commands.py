"""``specdev loop start|next|status``: the review-fix loop of the agent workflows, kept by the tool.

``loop next`` is the only command that advances a run. It reads what is on disk, takes in
the files that have arrived, asks the run machine (``loop.machine``) for the next action and
prints exactly that action as JSON. The session that calls it does what the action says and
calls again. Design: ``docs/architecture/agent-harness/agent_harness_design.md``.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from typing import Any

from specdev_tools.core.errors import FindingError, make_error
from specdev_tools.graph.commands import add_root_flags, roots
from specdev_tools.graph.trace import trace_node
from specdev_tools.loop import briefs, intake, machine, report, store
from specdev_tools.loop.machine import AWAITING, CONTESTED, GATE, LINK, OPEN, PARKED, REVIEW, RunState
from specdev_tools.loop.code_io import OUTSIDE_INSTRUCTION, CodeIO, FileIO, PlanIO
from specdev_tools.loop.spec_io import CanonDirFn, Roots, SpecIO

DESCRIPTION = (
    "The review-fix loop of a spec scope, kept by the tool.\n\n"
    "  start   create a run for a scope and print its id (or the id of the unfinished run of that scope)\n"
    "  next    advance the run: take in what arrived and print the one next action as JSON\n"
    "  status  list the runs, or show one\n\n"
    "An action is one of: dispatch (start one subagent per entry with the prompt 'Read and follow <brief>'),\n"
    "wait (files are missing; call 'loop next --redispatch' when no subagent is still running),\n"
    "ask (put the questions to the operator, write the answers, call 'loop next --answers FILE'),\n"
    "done (the verdict; the report path)."
)
SPEC_STEPS_END = "16"
KINDS = ("step", "plan", "code-group", "code-milestone")
AGENTS = {"reviewer": "specdev-reviewer", "fixer": "specdev-impl", "author": "specdev-impl"}
CODE_AGENTS = {"reviewer": "specdev-trinity-reviewer", "fixer": "specdev-trinity-impl", "execute": "specdev-trinity-impl"}
ANSWERS = {"Try once more": "again", "Leave as is": "leave", "Stop the run": "stop", "Stop": "stop",
           "Continue 2 more rounds": "2", "Continue 5 more rounds": "5", "Yes, it was carried out": "yes", "No": "no"}
PLAN_ITEM_ID = re.compile(r"^[A-Z][A-Z0-9_]+$")
FINDINGS_DIR = os.path.join(".specdev", "findings")
_canon_dir: CanonDirFn | None = None


def _refuse(message: str) -> FindingError:
    return FindingError(make_error("E850", message))


def add_loop_parsers(sub: Any, canon_dir: CanonDirFn | None = None) -> None:
    """Register ``loop`` and its subcommands; *canon_dir* finds a host's project canon, as for ``spec-check``."""
    global _canon_dir
    _canon_dir = canon_dir
    loop = sub.add_parser("loop", help="The review-fix loop of a spec scope: start, next, status.",
                          description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)
    loop_sub = loop.add_subparsers(dest="loop_cmd", required=True)

    start = loop_sub.add_parser("start", help="Create a run for a scope and print its id.")
    start.add_argument("--kind", required=True, choices=list(KINDS),
                       help="What is reviewed: spec steps, a milestone's plan, one plan item's code, a milestone's code.")
    start.add_argument("scope", help="step: NN, a range NN-MM, a list NN,MM or 'all' (steps 00 to 15). plan and "
                                     "code-milestone: a milestone id. code-group: <milestone id>/<plan item id>.")
    mode = start.add_mutually_exclusive_group()
    mode.add_argument("--author", action="store_true", help="Author the step's missing artifact first.")
    mode.add_argument("--extend", metavar="TEXT", help="Add content for this intent to the existing artifact first.")
    mode.add_argument("--execute", action="store_true", help="code-group: carry out the item's actions first.")
    mode.add_argument("--review-only", action="store_true", help="One round, nothing fixed; verdict CLEAN or FINDINGS.")
    mode.add_argument("--worklist", metavar="FILE", help="Begin with the findings of this findings file: a fix pass comes first.")
    start.add_argument("--seed", metavar="PATH", help="With --extend: the seed document the intent comes from.")
    start.add_argument("--batch", metavar="ID", help="With --kind plan --author: the batch id, the stem of the plan file to create.")
    start.add_argument("--about", metavar="NODE", help="Read only NODE and the nodes that link to it (what may be fixed stays the scope).")
    start.add_argument("--carry", metavar="RUN", help="Count as read what this earlier run read and has not changed since.")
    start.add_argument("--readers", type=int, help="Reviewers for a node nobody has read (default 2 for step, else 1).")
    start.add_argument("--defer", action="store_true", help="Never ask the operator: end HALT(stuck) instead.")
    start.add_argument("--cap", type=int, default=5, help="Rounds at most (default 5).")
    start.add_argument("--base-ref", help="The base of the step gate (default: as spec-check --step).")
    start.add_argument("--pass", dest="pass_id", metavar="ID", help="The pass this run belongs to.")
    add_root_flags(start)
    start.set_defaults(handler=run_start)

    nxt = loop_sub.add_parser("next", help="Advance a run and print its next action as JSON.")
    nxt.add_argument("run_id")
    nxt.add_argument("--answers", metavar="FILE", help="The operator's answers to the questions of the last 'ask'.")
    nxt.add_argument("--redispatch", action="store_true", help="Hand out the missing entries for their second try.")
    nxt.add_argument("--stop", action="store_true", help="End the run now: HALT(operator).")
    add_root_flags(nxt)
    nxt.set_defaults(handler=run_next)

    status = loop_sub.add_parser("status", help="List the runs, or show one run.")
    status.add_argument("run_id", nargs="?")
    status.add_argument("--pass", dest="pass_id", metavar="ID", help="Only the runs of this pass.")
    add_root_flags(status)
    status.set_defaults(handler=run_status)


def _handled(function: Any) -> Any:
    def wrapper(args: argparse.Namespace) -> int:
        try:
            return function(args)
        except FindingError as exc:
            print(json.dumps({"type": "error", "code": exc.error.code, "message": exc.error.message}, indent=2))
            return 1
    return wrapper


def _spec_steps(repo_root: str) -> list[str]:
    with open(os.path.join(repo_root, "tools", "step_order.json"), encoding="utf-8") as handle:
        steps = json.load(handle)["steps"]
    return steps[: steps.index(SPEC_STEPS_END)]


def parse_scope(repo_root: str, scope: str) -> list[str]:
    known = _spec_steps(repo_root)
    if scope == "all":
        return known
    if "-" in scope and "," not in scope:
        first, last = scope.split("-", 1)
        if first in known and last in known and known.index(first) <= known.index(last):
            return known[known.index(first): known.index(last) + 1]
        raise _refuse(f"{scope!r} is not a range of steps 00 to 15")
    steps = [s.strip() for s in scope.split(",") if s.strip()]
    unknown = [s for s in steps if s not in known]
    if unknown or not steps:
        raise _refuse(f"{unknown[0] if unknown else scope!r} is not a step of 00 to 15")
    return [s for s in known if s in steps]


def _wave() -> int:
    try:
        return max(1, int(os.environ.get("SPECDEV_REVIEW_CONCURRENCY", "6")))
    except ValueError:
        return 6


# --------------------------------------------------------------------------- start


def _label(steps: list[str]) -> str:
    return store.slug("-".join(steps) if len(steps) <= 2 else f"{steps[0]}-{steps[-1]}")


def about_set(io: SpecIO, node_id: str) -> set[str]:
    """NODE and every node that links to it, directly or through other nodes: what ``specdev trace NODE --down`` reaches."""
    result = trace_node(io.graph, node_id, ("down",))
    return {n.id for n in result.reached}


def _unfinished(git_root: str, kind: str, steps: list[str], scope: dict[str, Any] | None = None) -> tuple[str, dict[str, Any]] | None:
    for run_id in reversed(store.list_runs(git_root)):
        state, meta = store.load(os.path.join(store.runs_root(git_root), run_id))
        if state.verdict is None and meta["kind"] == kind and meta["steps"] == steps and meta.get("scope") == scope:
            return run_id, meta
    return None


def make_io(rts: Roots, kind: str, steps: list[str], scope: dict[str, Any] | None) -> SpecIO:
    """The reader of a run's scope, by kind."""
    if kind == "step" and scope is None:
        return SpecIO(rts, steps, _canon_dir)
    assert scope is not None
    if kind == "step":
        return FileIO(rts, scope["file"], _canon_dir)
    if kind == "plan":
        return PlanIO(rts, scope["milestone"], _canon_dir)
    return CodeIO(rts, scope["milestone"], scope.get("group"), _canon_dir)


def parse_milestone_scope(kind: str, text: str, batch: str | None = None) -> dict[str, Any]:
    milestone, _, group = text.partition("/")
    if not milestone or (kind == "code-group") != bool(group):
        form = "<milestone id>/<plan item id>" if kind == "code-group" else "<milestone id>"
        raise _refuse(f"the scope of kind {kind} is {form}")
    scope: dict[str, Any] = {"milestone": milestone, "group": group or None}
    if batch:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", batch):
            raise _refuse(f"{batch!r} is not a batch id (letters, digits, '_' and '-')")
        scope["batch"] = batch
    return scope


def _earlier_execution(git_root: str, scope: dict[str, Any]) -> dict[str, Any] | None:
    """The executor's outcome of the newest earlier run of a group, when it holds no refusal and no action held by an open item."""
    for run_id in reversed(store.list_runs(git_root)):
        _, meta = store.load(os.path.join(store.runs_root(git_root), run_id))
        if meta["kind"] != "code-group" or meta.get("scope") != scope:
            continue
        outcome = meta.get("author") or {}
        if outcome.get("result") == "executed" and not outcome.get("refusal") and not outcome.get("held_by_open_item"):
            return outcome
        return None
    return None


def _load_worklist(path: str, io: SpecIO, state: RunState, meta: dict[str, Any], run_dir: str) -> str | None:
    """Put the findings of a worklist file into a new run; returns the run to carry the read-record from, if the file names one."""
    document = intake.load_json(path)
    if not isinstance(document, dict) or not isinstance(document.get("findings"), list):
        raise _refuse(f"{path} is not a findings file")
    folder = os.path.dirname(os.path.abspath(path))
    prior: dict[str, dict[str, Any]] = {}
    settled: dict[str, tuple[machine.Finding, dict[str, Any]]] = {}
    carry = None
    sidecar = intake.load_json(path + ".state.json")
    beside = os.path.join(folder, "run.json")
    if isinstance(sidecar, dict):
        prior = sidecar
    elif os.path.basename(path) in ("final.json", "handoffs.json") and os.path.isfile(beside):
        old_state, old_meta = store.load(folder)
        carry = old_meta["run_id"]
        for key, f in old_state.findings.items():
            prior[key] = {"status": f.status, "attempts": f.attempts, "instruction": f.instruction,
                          "fixer": old_meta.get("detail", {}).get(key, {}).get("fixer", "")}
            if f.source == REVIEW and f.status == machine.SETTLED:
                settled[key] = (f, old_meta.get("detail", {}).get(key, {}))
    by_tool = isinstance(sidecar, dict) or carry is not None
    rejected: list[dict[str, Any]] = []
    for finding in document["findings"]:
        if not isinstance(finding, dict) or not finding.get("kind") or not finding.get("location"):
            rejected.append({"finding": finding, "reason": "no kind or no location"})
            continue
        key, target = intake.key_of(finding), intake.target_of(finding["location"])
        reason = None
        if not io.exists(target):
            reason = f"the target {target!r} no longer exists"
        elif not io.in_scope(target):
            reason = f"the target {target!r} is outside this run's scope"
        elif not by_tool:
            reason = intake.check_finding(finding, io)
        if reason is not None:
            rejected.append({"finding": finding, "reason": reason})
            continue
        was = prior.get(key, {})
        status = str(was["status"]) if was.get("status") in (AWAITING, CONTESTED) else OPEN
        attempts = min(int(was.get("attempts", 0)), machine.MAX_ATTEMPTS - 1)
        carried = str(finding.get("suggested_fix") or "")
        instruction = str(was.get("instruction") or "") or (carried if carried.startswith(report.GUIDANCE) else "")
        state.findings[key] = machine.Finding(key=key, source=REVIEW, status=status, attempts=attempts, target=target,
                                              instruction=instruction)
        meta["detail"][key] = {
            "kind": finding["kind"], "location": finding["location"], "severity": finding.get("severity", "P1"),
            "messages": [finding.get("message", key)], "evidence_quotes": list(finding.get("evidence_quotes") or []),
            "target": target, "in_scope": True, "fixer": was.get("fixer", ""),
            "evidence": list(finding.get("evidence") or []), "origin": finding.get("origin"),
            "upstream_refs": list(finding.get("upstream_refs") or []),
        }
    for key, (old, detail) in settled.items():
        # what the earlier run settled (a decline a reviewer upheld, a finding the operator left as is) is known to
        # this run too: a reviewer that raises it again on unchanged text does not open it again
        if key not in state.findings and io.in_scope(old.target) and io.exists(old.target):
            state.findings[key] = machine.Finding(key=key, source=REVIEW, status=machine.SETTLED, target=old.target,
                                                  settled_hash=old.settled_hash, left_as_is=old.left_as_is)
            meta["detail"][key] = dict(detail)
    if rejected:
        store.write_json(os.path.join(run_dir, "rejected.json"), rejected)
        meta["rejected"] += len(rejected)
    return carry


def create_run(
    rts: Roots, kind: str, steps: list[str], mode: str | None, *, extend: str | None = None, seed: str | None = None,
    worklist: str | None = None, carry: str | None = None, about: str | None = None, readers: int = 2,
    defer: bool = False, cap: int = 5, base_ref: str | None = None, pass_id: str | None = None,
    guidance: dict[str, str] | None = None, scope: dict[str, Any] | None = None,
) -> str:
    """Create a run and return its id. The checks of ``loop start`` that need the spec are here, so the pass tool gets them too."""
    io = make_io(rts, kind, steps, scope)
    if isinstance(io, FileIO):
        if mode != "review-only":
            raise _refuse("a spec/common/ file is reviewed with --review-only: its entries are edited by a person")
        label = store.slug(os.path.splitext(os.path.basename(scope["file"] if scope else ""))[0])
    elif kind == "step":
        present = [s for s in steps if io.graph.shape.files_by_step.get(s)]
        if mode in ("author", "extend") and len(steps) != 1:
            raise _refuse("--author and --extend take one step")
        if mode == "author" and present:
            raise _refuse(f"the artifact of step {steps[0]} exists; review it, or add to it with --extend")
        if mode != "author" and len(present) != len(steps):
            missing = [s for s in steps if s not in present]
            raise _refuse(f"step {missing[0]} has no artifact; author it with --author")
        if mode == "execute":
            raise _refuse("--execute goes with --kind code-group")
        label = _label(steps)
    else:
        assert isinstance(io, PlanIO) and scope is not None
        milestone = scope["milestone"]
        if mode == "extend" or about or (mode == "execute") != (kind == "code-group" and mode == "execute"):
            raise _refuse(f"kind {kind} does not take that mode")
        if (mode == "author") != bool(scope.get("batch")):
            raise _refuse("--batch goes with --kind plan --author, and --author needs it")
        if mode == "author" and (kind != "plan" or io.present()):
            raise _refuse(f"--author is for a plan that does not exist yet; milestone {milestone} "
                          + ("has a plan" if io.present() else "is not a plan scope"))
        if mode != "author" and not io.present():
            raise _refuse(f"no plan in impl_context/ names the milestone {milestone!r}"
                          + ("; author it with --author" if kind == "plan" else ""))
        if isinstance(io, CodeIO) and kind == "code-group" and io.item() is None:
            raise _refuse(f"the plan of {milestone} has no item {scope['group']!r}")
        label = {"plan": f"{milestone}-plan", "code-group": str(scope.get("group")), "code-milestone": milestone}[kind]
        if not re.fullmatch(r"[a-z0-9_-]+|[A-Z0-9_]+", label):
            label = store.slug(label)
    state = RunState(kind=kind, mode=mode, defer=defer, cap=cap, readers=max(1, readers), wave=_wave())
    state.content, state.cluster = io.content(), io.clusters()
    run_id = store.new_run_id(kind, label)
    run_dir = os.path.join(store.runs_root(rts.git), run_id)
    for letter in "bcdefghij":  # a second run of one scope in one second
        if not os.path.exists(run_dir):
            break
        run_id = store.new_run_id(kind, label) + letter
        run_dir = os.path.join(store.runs_root(rts.git), run_id)
    contract: list[str] = []
    for step in steps or ["16a"]:
        contract += [p for p in io.contract_paths(step) if p not in contract]
    meta: dict[str, Any] = {
        "run_id": run_id, "kind": kind, "steps": steps, "scope": scope, "scope_label": label, "mode": mode,
        "mode_arg": {"extend": extend, "seed": os.path.abspath(seed) if seed else None,
                     "worklist": os.path.abspath(worklist) if worklist else None, "about": about},
        "roots": {"repo": rts.repo, "spec": rts.spec, "git": rts.git}, "base_ref": base_ref,
        "pass_id": pass_id, "created": int(time.time()), "contract": contract, "detail": {}, "handoffs": {},
        "notes": {}, "rounds": [], "files": {}, "retry": {}, "unasked_changes": [], "noticed": [], "rejected": 0,
        "gate": {}, "links": {}, "guidance": dict(guidance or {}), "carry": None,
    }
    if mode == "extend":
        state.read = dict(state.content)  # what was there is not reviewed again
    if mode == "execute" and scope is not None:
        earlier = _earlier_execution(rts.git, scope)
        if earlier is not None:  # the group was executed by an earlier run: this one only reviews and fixes
            state.start_done, meta["author"] = True, dict(earlier, from_earlier_run=True)
    if worklist:
        named = _load_worklist(worklist, io, state, meta, run_dir)
        carry = carry or named
    if carry:
        old_dir = os.path.join(store.runs_root(rts.git), carry)
        if not os.path.isfile(os.path.join(old_dir, "run.json")):
            raise _refuse(f"no run {carry!r} to carry the read-record from")
        old_state, _ = store.load(old_dir)
        state.read.update({n: h for n, h in old_state.read.items() if n in state.content})
        meta["carry"] = carry
    if about:
        if io.graph.find(about) is None:
            raise _refuse(f"no node has the id {about!r}")
        inside = about_set(io, about)
        for name, digest in state.content.items():
            if name not in inside:
                state.read.setdefault(name, digest)  # outside the set: counts as read, so it is not handed out
    store.save(run_dir, state, meta)
    return run_id


@_handled
def run_start(args: argparse.Namespace) -> int:
    spec_root, repo_root, git_root = roots(args)
    if not os.path.isdir(spec_root):
        raise _refuse(f"{spec_root} is not a folder: name the spec with --spec-root")
    common = os.path.join(spec_root, "common", os.path.basename(args.scope))
    if args.kind == "step" and args.scope.endswith(".json") and os.path.isfile(common):
        steps, scope = [], {"file": os.path.relpath(common, spec_root).replace(os.sep, "/")}
    elif args.kind == "step":
        steps, scope = parse_scope(repo_root, args.scope), None
    else:
        steps, scope = [], parse_milestone_scope(args.kind, args.scope, args.batch)
    if args.batch and args.kind != "plan":
        raise _refuse("--batch goes with --kind plan --author")
    mode = ("author" if args.author else "extend" if args.extend else "review-only" if args.review_only
            else "worklist" if args.worklist else "execute" if args.execute else None)
    if args.seed and not args.extend:
        raise _refuse("--seed goes with --extend")
    wanted = {"extend": args.extend, "worklist": os.path.abspath(args.worklist) if args.worklist else None, "about": args.about}
    found = _unfinished(git_root, args.kind, steps, scope)
    if found is not None:
        run_id, meta = found
        had = {k: (meta.get("mode_arg") or {}).get(k) for k in wanted}
        same = mode == meta["mode"] and wanted == had
        if same or (mode is None and not args.about and meta["mode"] != "review-only"):
            print(json.dumps({"run_id": run_id, "resumed": True}, indent=2))
            return 0
        raise _refuse(
            f"run {run_id} of this scope is unfinished and was started in another mode or with another argument; "
            f"continue it with 'specdev loop next {run_id}', or end it with 'specdev loop next {run_id} --stop'"
        )
    run_id = create_run(
        Roots(repo_root, spec_root, git_root), args.kind, steps, mode, extend=args.extend, seed=args.seed,
        worklist=args.worklist, carry=args.carry, about=args.about, defer=args.defer,
        readers=args.readers or (2 if args.kind == "step" else 1),
        cap=args.cap, base_ref=args.base_ref, pass_id=args.pass_id, scope=scope,
    )
    print(json.dumps({"run_id": run_id, "resumed": False}, indent=2))
    return 0


# --------------------------------------------------------------------------- next


RESULTS = ("written", "nothing_to_add", "executed")

class _Run:
    """One ``loop next`` call: the state, the spec as it is now, and the folder."""

    def __init__(self, git_root: str, run_id: str) -> None:
        self.dir = os.path.join(store.runs_root(git_root), run_id)
        if not os.path.isfile(os.path.join(self.dir, "run.json")):
            raise _refuse(f"no run {run_id!r} under {store.runs_root(git_root)}")
        self.state, self.meta = store.load(self.dir)
        r = self.meta["roots"]
        self.io = make_io(Roots(r["repo"], r["spec"], r["git"]), self.meta["kind"], self.meta["steps"], self.meta.get("scope"))
        self.state.content, self.state.cluster = self.io.content(), self.io.clusters()

    # ---- arrivals

    def _dnum(self) -> int:
        return self.state.dispatches

    def _file_of(self, entry: machine.Entry) -> str | None:
        """The passing file of an entry with the lowest try number, or None."""
        d = self.state.dispatch
        assert d is not None
        for attempt in range(1, entry.tries + 1):
            path = store.entry_path(self.dir, self._dnum(), entry.id, attempt)
            if not os.path.isfile(path):
                continue
            if d.role == "review":
                checked = intake.check_review_file(
                    path, self.meta["roots"]["repo"], round_no=self.state.rounds_used + 1,
                    scope=self.meta["scope_label"], assigned=entry.nodes, contract=self.meta["contract"], judge=entry.judge,
                )
                if checked.ok and self.meta["kind"] == "code-milestone":
                    checked = self._record_shape(checked)
                if not checked.ok:
                    self.meta["retry"][entry.id] = checked.reason
                    continue
            else:
                document = intake.load_json(path)
                reason = None
                if not isinstance(document, dict):
                    reason = "the file is not a JSON object"
                elif d.role == "fix" and not isinstance(document.get("outcomes"), list):
                    reason = "the file has no `outcomes` list"
                elif d.role != "fix" and not document.get("refusal") and document.get("result") not in RESULTS:
                    reason = "the outcome names neither a result nor a refusal"
                if reason is not None:
                    self.meta["retry"][entry.id] = reason
                    continue
            return path
        return None

    def _record_shape(self, checked: intake.ReviewFile) -> intake.ReviewFile:
        """What `specdev review record` requires of a finding (lifecycle/review_record.py), asked at intake."""
        items = {n.id for n in self.io.nodes()}
        for finding in checked.document.get("findings") or []:
            if len(finding.get("message", "")) > report.MESSAGE_MAX:
                return intake.ReviewFile(False, f"a message is longer than {report.MESSAGE_MAX} characters")
            for ref in finding.get("upstream_refs") or []:
                if PLAN_ITEM_ID.match(ref) and ref not in items:
                    return intake.ReviewFile(False, f"upstream_refs names {ref}, which is no item of the plan")
        return checked

    def take_arrivals(self) -> None:
        d = self.state.dispatch
        if d is None:
            return
        files = self.meta["files"].setdefault(str(self._dnum()), {})
        for entry in d.entries:
            if entry.handed_out and not entry.arrived:
                path = self._file_of(entry)
                if path is not None:
                    entry.arrived, files[entry.id] = True, path
        if not machine.complete(d):
            return
        if d.role == "review":
            self._take_review(d, files)
        elif d.role == "fix":
            self._take_fix(d, files)
        else:
            self._take_author(d, files)

    def _hashes(self) -> dict[str, str]:
        return store.read_json(os.path.join(store.dispatch_dir(self.dir, self._dnum()), "hashes.json"))

    def _take_review(self, d: machine.Dispatch, files: dict[str, str]) -> None:
        documents = []
        for entry in d.entries:
            checked = intake.check_review_file(
                files[entry.id], self.meta["roots"]["repo"], round_no=self.state.rounds_used + 1,
                scope=self.meta["scope_label"], assigned=entry.nodes, contract=self.meta["contract"], judge=entry.judge,
            )
            documents.append(checked.document)
        merged = intake.merge_round(documents, self.io)
        folder = store.dispatch_dir(self.dir, self._dnum())
        store.write_json(os.path.join(folder, "merged.json"), merged.detail)
        store.write_json(os.path.join(folder, "rejected.json"), merged.rejected)
        self.meta["rejected"] += len(merged.rejected)
        given = self._hashes()
        read = {n: given[n] for entry in d.entries for n in entry.nodes if n in given}
        handoffs_before = set(self.state.handoffs)
        notes_before = len(self.state.notes)
        machine.apply_review(self.state, read, merged.raised, dict(merged.judgements))
        for key, entry in merged.detail.items():
            if key in self.state.findings and self.state.kind in machine.CODE_KINDS and not entry["in_scope"]:
                self.state.findings[key].instruction = OUTSIDE_INSTRUCTION
            if key in self.state.findings:
                known = self.meta["detail"].setdefault(key, entry)
                for message in entry["messages"]:
                    if message not in known["messages"]:
                        known["messages"].append(message)
            if key in self.state.handoffs and key not in handoffs_before:
                self.meta["handoffs"][key] = entry
        for key in self.state.notes[notes_before:]:
            self.meta["notes"][key] = merged.detail[key]["messages"][0]
        for key, verdict in merged.judgements.items():
            f = self.state.findings.get(key)
            if f is not None and verdict in ("finding_right", "not_resolved") and f.status == OPEN:
                f.instruction = f"The reviewer of round {self.state.rounds_used} judged this {verdict}: {merged.reasons.get(key, '')}"
        counts = {sev: sum(1 for e in merged.detail.values() if e["severity"] == sev) for sev in ("P0", "P1", "P2")}
        self.meta["rounds"].append({"round": self.state.rounds_used, **counts, "rejected": len(merged.rejected),
                                    "reviewers": len(d.entries), "read": len(read)})
        machine.close_dispatch(self.state)

    def _take_fix(self, d: machine.Dispatch, files: dict[str, str]) -> None:
        before, now = self._hashes(), self.state.content
        links = self.io.links()
        outcomes, noticed = intake.fix_checks(
            intake.load_json(files["fix"]), self.io, before=before, now=now, listed=set(links.listed),
        )
        targets = {self.state.findings[k].target for k in d.keys if k in self.state.findings}
        moved: dict[str, dict[str, Any]] = {}
        for key, checked in outcomes.items():
            raw = checked.pop("raw")
            if key in self.meta["detail"]:
                self.meta["detail"][key]["fixer"] = f"{raw.get('outcome')}: {raw.get('reason', '')}".strip()
            if checked.get("named") and key in self.meta["detail"]:
                source = self.meta["detail"][key]
                moved[checked["named"]] = dict(source, location=raw["named"]["location"], kind=raw["named"]["kind"],
                                               target=checked["target"], in_scope=checked["in_scope"], fixer="")
        if any(o.get("outcome") == "recorded" and o.get("item_exists") for o in outcomes.values()):
            self.meta["recorded_item"] = True
        handoffs_before = set(self.state.handoffs)
        machine.apply_fix(self.state, outcomes)
        for named, info in moved.items():
            if named in self.state.handoffs and named not in handoffs_before:
                self.meta["handoffs"].setdefault(named, info)
            elif named in self.state.findings:
                self.meta["detail"].setdefault(named, info)
                if self.state.kind in machine.CODE_KINDS and not info["in_scope"]:
                    self.state.findings[named].instruction = OUTSIDE_INSTRUCTION
        self._refresh(after_fix=True, links=links)
        changed = sorted(n for n in set(before) | set(now) if before.get(n) != now.get(n) and n not in targets)  # a deleted node too
        items = self.io.open_item_ids()
        recorded = [n for n in changed if n not in before and n in items]  # a new open item is what a fixer may add
        self.meta["recorded_items"] = sorted(set(self.meta.get("recorded_items", [])) | set(recorded))
        changed = [n for n in changed if n not in recorded]
        outside_path = os.path.join(store.dispatch_dir(self.dir, self._dnum()), "outside.json")
        if os.path.isfile(outside_path):  # absent in a run that was dispatched by an older toolkit
            was, is_now = store.read_json(outside_path), self.io.outside_content(set(now))
            changed += sorted(f"{n} (outside the scope)" for n in set(was) | set(is_now)
                              if was.get(n) != is_now.get(n) and n not in targets and n not in items)
        self.meta["unasked_changes"] = sorted(set(self.meta["unasked_changes"]) | set(changed))
        self.meta["noticed"] += [n for n in noticed if n not in self.meta["noticed"]]
        machine.close_dispatch(self.state)

    def _take_author(self, d: machine.Dispatch, files: dict[str, str]) -> None:
        document = intake.load_json(files[d.entries[0].id]) or {}
        if document.get("refusal"):
            self.state.refusal = str(document["refusal"])
            return  # row 2 ends the run
        if document.get("result") not in RESULTS:
            entry = d.entries[0]
            entry.arrived = False  # names neither a result nor a refusal: a failed try
            self.meta["retry"][entry.id] = "the outcome names neither a result nor a refusal"
            return
        self.meta["author"] = document
        self.state.start_done = True
        if d.role == "execute" and isinstance(self.io, CodeIO):
            done = self.io.recorded_actions()
            self.state.confirmations = {str(a): None for a in document.get("awaiting_confirmation") or [] if str(a) not in done}
        machine.close_dispatch(self.state)

    # ---- gate and links

    def _refresh(self, after_fix: bool = False, links: Any = None) -> None:
        if isinstance(self.io, CodeIO):
            open_items = self.io.open_plan_items()
            held = (self.meta.get("author") or {}).get("held_by_open_item") or []
            in_the_way = bool(held) or bool(self.meta.get("recorded_item")) if self.state.kind == "code-group" else True
            self.state.plan_blocked = bool(open_items) and in_the_way
            self.meta["plan_open_items"] = open_items
        gate = self.io.gate(self.meta.get("base_ref"))
        machine.apply_gate(self.state, gate.blocking, after_fix=after_fix)
        links = links or self.io.links()
        machine.apply_links(self.state, links.listed)
        for key, target in gate.blocking.items():
            self.meta["detail"].setdefault(key, {"kind": "gate", "location": target, "target": target, "severity": "P0",
                                                 "messages": [gate.messages[key]], "evidence_quotes": []})
        for key, d in links.detail.items():
            text = f"suspect link: {d['holder']}.{d['field']} -> {d['target']} ({d['cause']}; changed above: {', '.join(d['roots']) or 'the target'})"
            self.meta["detail"].setdefault(key, {"kind": "link", "location": d["holder"], "target": d["holder"],
                                                 "severity": "P1", "messages": [text], "evidence_quotes": []})
        for key, text in self.meta.get("guidance", {}).items():
            f = self.state.findings.get(key)
            if f is not None and not f.instruction:
                f.instruction = f"The operator: {text}"
        self.meta["gate"] = {"result": gate.result, "blocked_by": gate.blocked_by, "waiting": gate.waiting, "notes": gate.notes}
        self.meta["links"] = {"waiting": links.waiting, "gaps": links.gaps}

    # ---- actions

    def _write_briefs(self, action: machine.Action, first: bool) -> list[dict[str, str]]:
        d = self.state.dispatch
        assert d is not None
        folder = store.dispatch_dir(self.dir, self._dnum())
        if first:
            store.write_json(os.path.join(folder, "hashes.json"), self.state.content)
            if d.role == "fix":  # what the fixer may not change, to list what it changed all the same
                store.write_json(os.path.join(folder, "outside.json"), self.io.outside_content(set(self.state.content)))
        out = []
        for entry in action.entries:
            expect = store.entry_path(self.dir, self._dnum(), entry.id, entry.tries)
            brief = os.path.join(self.dir, "briefs", f"d{self._dnum()}.{entry.id}.t{entry.tries}.md")
            store.write_text(brief, self._brief(d, entry, expect))
            agents = CODE_AGENTS if self.state.kind in machine.CODE_KINDS else AGENTS
            out.append({"agent": agents[entry.agent], "brief": brief, "expect": expect})
        return out

    def _brief(self, d: machine.Dispatch, entry: machine.Entry, expect: str) -> str:
        detail, state = self.meta["detail"], self.state
        if d.role == "review":
            context: list[str] = []
            for node_id in entry.nodes:
                node = self.io.graph.find(node_id)
                for link in (node.links if node is not None else ()):
                    if link.target not in context and link.target not in entry.nodes:
                        context.append(link.target)
            judge = [{"key": k, "status": state.findings[k].status, "message": (detail.get(k, {}).get("messages") or [k])[0],
                      "fixer": detail.get(k, {}).get("fixer", "") or "no outcome was given"} for k in entry.judge]
            scope_ids = set(state.content)
            known = {
                "Settled in this run": [f"{f.key}: {detail.get(f.key, {}).get('fixer', 'settled')}" for f in machine.with_status(state, machine.SETTLED)],
                "Parked for the operator": [f.key for f in machine.with_status(state, PARKED)],
                "Handoffs recorded": list(state.handoffs),
                "Open items about these nodes": [f"{i['id']} (about {', '.join(i['about'])})" for i in self.io.open_items_about(scope_ids)],
            }
            return briefs.reviewer(self.meta, round_no=state.rounds_used + 1, nodes=entry.nodes, context=context[:60],
                                   judge=judge, known=known, expect=expect, retry_reason=self.meta["retry"].get(entry.id, ""))
        if d.role == "fix":
            findings = []
            for key in d.keys:
                f, info = state.findings[key], detail.get(key, {})
                findings.append({"key": key, "source": f.source, "location": info.get("location", f.target),
                                 "message": " / ".join(info.get("messages", [])), "quotes": info.get("evidence_quotes", []),
                                 "instruction": f.instruction})
            diffs = None
            if any(state.findings[k].source == LINK for k in d.keys):
                diffs = "run `specdev stale --diff` with the roots above before you accept a link"
            return briefs.fixer(self.meta, findings=findings, expect=expect, diffs_path=diffs)
        if d.role == "execute":
            assert isinstance(self.io, CodeIO)
            return briefs.executor(self.meta, expect=expect, actions=self.io.actions(), files=self.io.code_files(),
                                   plan_file=self.io.file_key(self.io.plan_file or ""))
        return briefs.author(self.meta, expect=expect)

    def _questions(self, action: machine.Action) -> list[dict[str, Any]]:
        questions = []
        if action.ask == "cap":
            return [{"id": "cap", "question": f"The run used its {self.state.cap} rounds and findings are open. Continue?",
                     "options": [{"label": "Continue 2 more rounds"}, {"label": "Continue 5 more rounds"}, {"label": "Stop"}]}]
        if action.ask == "confirm":
            group, flags = (self.meta.get("scope") or {}).get("group"), briefs.roots_text(self.meta["roots"])
            for action_id in action.keys:
                command = f'specdev plan record {group}/{action_id} --outcome done --note "operator confirmed" {flags}'
                questions.append({"id": action_id, "question": f"Was the manual-verification action {group}/{action_id} carried out?",
                                  "options": [{"label": "Yes, it was carried out", "command": command}, {"label": "No"}]})
            return questions
        held = self.meta.get("answers_held", {})
        for key in action.keys:
            if key in held:
                continue  # answered in an earlier call of this batch
            info = self.meta["detail"].get(key, {})
            f = self.state.findings[key]
            no_leave = f.source in (GATE, LINK) or (self.state.kind in machine.CODE_KINDS and info.get("severity") == "P0")
            options = ["Try once more", "Stop the run"] if no_leave else ["Try once more", "Leave as is"]
            questions.append({
                "id": key,
                "question": f"Two fixes failed for {self.io.label(f.target)}: {' / '.join(info.get('messages', [key]))}",
                "options": [{"label": o} for o in options],
            })
        return questions

    def finish(self, verdict: str) -> dict[str, Any]:
        paths = report.write(self.dir, self.state, self.meta, verdict)
        out = {"type": "done", "run_id": self.meta["run_id"], "verdict": verdict, **paths}
        if isinstance(self.io, CodeIO):
            copy = self._milestone_state_copy(verdict, paths["final"])
            if copy:
                out["milestone_state_file"] = copy
            if verdict == "HALT(blocked)":
                out["open_items"] = self.meta.get("plan_open_items", [])
        return out

    def _milestone_state_copy(self, verdict: str, final: str) -> str | None:
        """Write the copy of ``final.json`` that `specdev milestone-state` reads; None when the run says nothing about convergence."""
        assert isinstance(self.io, CodeIO)
        document = store.read_json(final)
        if verdict == "HALT(blocked)" or (verdict != "CONVERGED" and not document["findings"]):
            return None
        folder = os.path.join(self.meta["roots"]["git"], FINDINGS_DIR)
        stem = f"findings_{self.io.group}_" if self.io.group else f"findings_{self.io.batch}_review_"
        used = [0]
        for name in os.listdir(folder) if os.path.isdir(folder) else []:
            match = re.fullmatch(re.escape(stem) + r"(\d+)(?:_.*)?\.json", name)
            if match:
                used.append(int(match.group(1)))
        path = os.path.join(folder, f"{stem}{max(used) + 1}.json")
        store.write_json(path, document)
        return path


def _apply_answers(run: _Run, path: str) -> None:
    answers = intake.load_json(path)
    if not isinstance(answers, dict):
        raise _refuse(f"{path} is not a JSON object of answers")
    plain: dict[str, str] = {}
    for key, value in answers.items():
        label = value.get("label") if isinstance(value, dict) else value
        notes = value.get("notes", "") if isinstance(value, dict) else ""
        plain[key] = ANSWERS.get(str(label), str(label))
        if plain[key] == "again" and notes and key in run.state.findings:
            run.state.findings[key].instruction = f"The operator: {notes}"
    if run.state.pending_ask == "confirm":
        answered = (run.meta.get("author") or {}).setdefault("confirmed", {})
        answered.update(plain)
    if run.state.pending_ask == "parked":
        plain = {**run.meta.get("answers_held", {}), **plain}
        waiting = {f.key for f in machine.with_status(run.state, PARKED)}
        if not waiting <= set(plain):
            run.meta["answers_held"] = plain  # applied together, when the last question of the batch is answered
            return
        run.meta["answers_held"] = {}
    machine.apply_answers(run.state, plain)


@_handled
def run_next(args: argparse.Namespace) -> int:
    _, _, git_root = roots(args)
    run = _Run(git_root, args.run_id)
    state = run.state
    if state.verdict is None:
        if args.stop:
            state.stop = True
        if args.answers:
            _apply_answers(run, args.answers)
        run.take_arrivals()
        if state.dispatch is None:
            run._refresh()
    before = state.dispatches
    action = machine.decide(state, redispatch=args.redispatch)
    if action.type == "dispatch":
        if state.dispatches != before:
            run.meta["retry"] = {}  # entry ids repeat in every dispatch: a refusal belongs to the dispatch it happened in
        out: dict[str, Any] = {"type": "dispatch", "run_id": args.run_id,
                               "entries": run._write_briefs(action, first=state.dispatches != before)}
    elif action.type == "wait":
        d = state.dispatch
        assert d is not None
        out = {"type": "wait", "run_id": args.run_id, "missing": [
            store.entry_path(run.dir, state.dispatches, e.id, e.tries) for e in d.entries if e.id in action.missing]}
        refused = {e.id: run.meta["retry"][e.id] for e in d.entries if e.id in action.missing and e.id in run.meta.get("retry", {})}
        if refused:
            out["refused"] = refused  # a file arrived and failed its checks: `--redispatch` hands the entry out again
    elif action.type == "ask":
        out = {"type": "ask", "run_id": args.run_id, "questions": run._questions(action),
               "answers_path": os.path.join(run.dir, "answers.json")}
    elif run.meta.get("done"):
        out = run.meta["done"]
    else:
        out = run.meta["done"] = run.finish(action.verdict or "")
    store.save(run.dir, state, run.meta)
    print(json.dumps(out, indent=2))
    return 0


# --------------------------------------------------------------------------- status


@_handled
def run_status(args: argparse.Namespace) -> int:
    _, _, git_root = roots(args)
    rows = []
    for run_id in store.list_runs(git_root):
        if args.run_id and run_id != args.run_id:
            continue
        state, meta = store.load(os.path.join(store.runs_root(git_root), run_id))
        if args.pass_id and meta.get("pass_id") != args.pass_id:
            continue
        counts: dict[str, int] = {}
        for f in state.findings.values():
            counts[f.status] = counts.get(f.status, 0) + 1
        row: dict[str, Any] = {"run_id": run_id, "kind": meta["kind"], "steps": meta["steps"], "mode": meta["mode"],
                               "pass": meta.get("pass_id"), "rounds": state.rounds_used, "cap": state.cap,
                               "verdict": state.verdict, "findings": counts}
        if args.run_id:
            d = state.dispatch
            row["dispatch"] = None if d is None else {
                "role": d.role, "expected": [e.id for e in d.entries if e.handed_out],
                "received": [e.id for e in d.entries if e.arrived]}
            row["waiting_for"] = state.pending_ask
            row["handoffs"], row["notes"] = len(state.handoffs), len(state.notes)
            row["awaiting_review"] = [f.key for f in machine.with_status(state, AWAITING, CONTESTED)]
            row["sources"] = {s: sum(1 for f in state.findings.values() if f.source == s) for s in (REVIEW, GATE, LINK)}
        rows.append(row)
    if args.run_id and not rows:
        raise _refuse(f"no run {args.run_id!r}")
    print(json.dumps({"runs": rows}, indent=2))
    return 0
