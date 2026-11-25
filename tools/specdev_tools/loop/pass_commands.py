"""``specdev pass start|next``: several steps, top down, once.

A pass names the next run and creates it; the session pumps that run with ``specdev loop
next`` and calls ``pass next`` again. What a step still has to do is computed from the spec
and the run folders at every call (``pass_machine.View``); the pass keeps only the pool of
reviewer findings, the operator's answers, and where its walk is. Design: section 8.3.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
import time
from dataclasses import asdict
from typing import Any

from specdev_tools.core.ambiguity_items import is_open, read_ambiguity_items
from specdev_tools.core.errors import FindingError
from specdev_tools.graph.commands import add_root_flags, roots
from specdev_tools.loop import commands as loop_commands
from specdev_tools.loop import intake, pass_machine, report, store
from specdev_tools.loop.commands import _handled, _refuse, _spec_steps, about_set, create_run, parse_scope
from specdev_tools.loop.machine import AWAITING, CONTESTED, GATE, LINK, OPEN, PARKED, REVIEW
from specdev_tools.loop.pass_machine import PassState, RunRef, StepView, View
from specdev_tools.loop.spec_io import Roots, SpecIO

PASSES_DIR = os.path.join(".specdev", "passes")
CLOSED = "closed"
DESCRIPTION = (
    "Take a spec through several steps, top down, once.\n\n"
    "  start   create a pass and print its id (or the id of the unfinished pass with the same entry)\n"
    "  next    advance the pass and print the one next action as JSON\n\n"
    "An action is one of: run (pump that run with 'specdev loop next <run_id>' until it prints done, then call\n"
    "'pass next' again), ask (put the questions to the operator, write the answers, call 'pass next --answers FILE'),\n"
    "done (COMPLETE, INCOMPLETE, or the HALT(operator) or HALT(agent_failed) a run or --stop ended with; the report path)."
)


def add_pass_parsers(sub: Any) -> None:
    """Register ``pass`` and its subcommands."""
    parser = sub.add_parser("pass", help="Several spec steps, top down, once: start, next.",
                            description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter)
    pass_sub = parser.add_subparsers(dest="pass_cmd", required=True)
    start = pass_sub.add_parser("start", help="Create a pass and print its id.")
    start.add_argument("scope", nargs="?", help="A step range NN-MM, a step, or 'all': author what is missing, review the rest.")
    start.add_argument("--extend", metavar="TEXT", help="Add content for this intent to every step from --from (or 00) to 15.")
    start.add_argument("--seed", metavar="PATH", help="With --extend: the seed document the intent comes from.")
    start.add_argument("--from", dest="from_step", metavar="NN", help="With --extend: the first step (default 00).")
    start.add_argument("--review", action="store_true", help="With --about: review one feature through the steps that hold it.")
    start.add_argument("--about", metavar="NODE", help="With --review: the node the review is about.")
    start.add_argument("--replay", action="store_true", help="Take what earlier runs left: handoffs, open findings, suspect links, answered items.")
    start.add_argument("--readers", type=int, default=2, help="Reviewers for a node nobody has read (default 2).")
    start.add_argument("--cap", type=int, default=5, help="Rounds at most in each run (default 5).")
    start.add_argument("--base-ref", help="The base of the step gate (default: as spec-check --step).")
    add_root_flags(start)
    start.set_defaults(handler=run_pass_start)
    nxt = pass_sub.add_parser("next", help="Advance a pass and print its next action as JSON.")
    nxt.add_argument("pass_id")
    nxt.add_argument("--answers", metavar="FILE", help="The operator's answers to the batch.")
    nxt.add_argument("--retry", action="store_true", help="Start anew the run that failed or was stopped, and go on.")
    nxt.add_argument("--stop", action="store_true", help="End the pass now: HALT(operator).")
    add_root_flags(nxt)
    nxt.set_defaults(handler=run_pass_next)


def _dir(git_root: str, pass_id: str) -> str:
    return os.path.join(git_root, PASSES_DIR, pass_id)


def _load(folder: str) -> tuple[PassState, dict[str, Any], dict[str, dict[str, Any]]]:
    document = store.read_json(os.path.join(folder, "pass.json"))
    raw = dict(document["state"])
    runs = [RunRef(**r) for r in raw.pop("runs", [])]
    state = PassState(**raw)
    state.runs = runs
    pool_path = os.path.join(folder, "pool.json")
    return state, document["meta"], store.read_json(pool_path) if os.path.isfile(pool_path) else {}


def _save(folder: str, state: PassState, meta: dict[str, Any], pool: dict[str, dict[str, Any]]) -> None:
    store.write_json(os.path.join(folder, "pass.json"), {"state": asdict(state), "meta": meta})
    store.write_json(os.path.join(folder, "pool.json"), pool)


# --------------------------------------------------------------------------- start


@_handled
def run_pass_start(args: argparse.Namespace) -> int:
    spec_root, repo_root, git_root = roots(args)
    if not os.path.isdir(spec_root):
        raise _refuse(f"{spec_root} is not a folder: name the spec with --spec-root")
    chosen = [bool(args.scope), bool(args.extend), bool(args.review), bool(args.replay)]
    if sum(chosen) != 1:
        raise _refuse("give one entry: a step range, --extend TEXT, --review --about NODE, or --replay")
    known = _spec_steps(repo_root)
    entry_args: dict[str, Any] = {}
    if args.scope:
        entry, entry_args = "range", {"steps": parse_scope(repo_root, args.scope)}
    elif args.extend:
        first = args.from_step or known[0]
        if first not in known:
            raise _refuse(f"{first!r} is not a step of 00 to 15")
        entry = "extend"
        entry_args = {"steps": known[known.index(first):], "extend": args.extend,
                      "seed": os.path.abspath(args.seed) if args.seed else None}
    elif args.review:
        if not args.about:
            raise _refuse("--review takes --about NODE")
        entry, entry_args = "review", {"about": args.about}
    else:
        entry = "replay"
    if (args.seed or args.from_step) and not args.extend:
        raise _refuse("--seed and --from go with --extend")
    if args.about and not args.review:
        raise _refuse("--about goes with --review")
    root = os.path.join(git_root, PASSES_DIR)
    for name in sorted(os.listdir(root)) if os.path.isdir(root) else []:
        if os.path.isfile(os.path.join(root, name, "pass.json")):
            state, meta, _ = _load(os.path.join(root, name))
            if state.verdict is None and meta["entry"] == entry and meta["entry_args"] == entry_args:
                print(json.dumps({"pass_id": name, "resumed": True}, indent=2))
                return 0
    rts = Roots(repo_root, spec_root, git_root)
    pool: dict[str, dict[str, Any]] = {}
    if entry == "review":
        io = SpecIO(rts, known, loop_commands._canon_dir)
        if io.graph.find(args.about) is None:
            raise _refuse(f"no node has the id {args.about!r}")
    pass_id = f"pass-{entry}-{time.strftime('%Y%m%dT%H%M%SZ', time.gmtime())}"
    stamp = pass_id
    for letter in "bcdefghijklmnopqrstuvwxyz":  # a second pass of this entry in the same second: its folder exists
        if not os.path.exists(os.path.join(git_root, PASSES_DIR, pass_id)):
            break
        pass_id = stamp + letter
    meta = {
        "pass_id": pass_id, "entry": entry, "entry_args": entry_args, "roots": asdict(rts), "readers": args.readers,
        "cap": args.cap, "base_ref": args.base_ref, "created": int(time.time()), "kept": [], "guidance": {},
        "absorbed": [], "parked_gate": {}, "outside": [], "asked": [], "first_run": None,
    }
    if entry == "replay":
        _absorb_earlier_runs(git_root, pool, SpecIO(rts, known, loop_commands._canon_dir))
    _save(_dir(git_root, pass_id), PassState(entry=entry), meta, pool)
    print(json.dumps({"pass_id": pass_id, "resumed": False}, indent=2))
    return 0


# --------------------------------------------------------------------------- the pool


def _pool_entry(info: dict[str, Any], step: str | None, run_id: str, **over: Any) -> dict[str, Any]:
    entry = {
        "kind": info.get("kind", "bug"), "location": info.get("location", info.get("target", "")),
        "severity": info.get("severity", "P1"), "messages": list(info.get("messages") or []),
        "evidence_quotes": list(info.get("evidence_quotes") or []), "target": info.get("target", ""),
        "step": step, "status": OPEN, "attempts": 0, "instruction": "", "fixer": info.get("fixer", ""), "run": run_id,
        "evidence": list(info.get("evidence") or []), "origin": info.get("origin"),
        "upstream_refs": list(info.get("upstream_refs") or []),
    }
    entry.update(over)
    return entry


def _absorb(run_id: str, git_root: str, pool: dict[str, dict[str, Any]], io: SpecIO, meta: dict[str, Any] | None) -> None:
    """Take a finished run into the pool: what it closed is closed, what it left or handed off is there to do."""
    state, run_meta = store.load(os.path.join(store.runs_root(git_root), run_id))
    detail = run_meta.get("detail", {})
    for key, f in state.findings.items():
        if f.source != REVIEW:
            if f.status == PARKED and meta is not None:
                meta["parked_gate"][key] = {"step": run_meta["steps"][0], "target": f.target,
                                            "message": " / ".join(detail.get(key, {}).get("messages", [key]))}
            elif meta is not None:
                meta["parked_gate"].pop(key, None)
            continue
        if f.status in report.CLOSED:
            if key in pool:
                pool[key]["status"] = CLOSED
                pool[key]["left_as_is"] = f.left_as_is
            continue
        was = pool.get(key, {})
        pool[key] = _pool_entry(detail.get(key, was), io.step_of(f.target), run_id, status=f.status,
                                attempts=f.attempts, instruction=f.instruction or was.get("instruction", ""))
    for key, info in run_meta.get("handoffs", {}).items():
        if pool.get(key, {}).get("status") != CLOSED:
            pool.setdefault(key, _pool_entry(info, io.step_of(info.get("target", "")), run_id))


def _absorb_earlier_runs(git_root: str, pool: dict[str, dict[str, Any]], io: SpecIO) -> None:
    for run_id in store.list_runs(git_root):
        state, run_meta = store.load(os.path.join(store.runs_root(git_root), run_id))
        if state.verdict is not None and run_meta["kind"] == "step":  # a plan's or a code run's findings are no step's work
            _absorb(run_id, git_root, pool, io, None)
    for key in [k for k, e in pool.items() if e["status"] == CLOSED or not io.exists(e["target"])]:
        del pool[key]  # closed by a later run, or about something that is gone


def _item_findings(pool: dict[str, dict[str, Any]], io: SpecIO, steps: list[str], meta: dict[str, Any]) -> None:
    """Every answered open item gives two steps work: the step of its ``about`` node, and the step that holds it."""
    for item in read_ambiguity_items(io.roots.spec).items:
        if not item.id or not is_open(item) or item.decision is None or item.step not in steps:
            continue
        holder_file = io.file_key(os.path.relpath(item.artifact_path, io.roots.spec))
        abouts = [(a, io.step_of(a)) for a in item.about_ids]
        above = [a for a, step in abouts if step != "seed" and step not in steps]
        if above:
            line = f"open item {item.id} has a decision, and its node {above[0]} is in a step outside the pass"
            if line not in meta["outside"]:
                meta["outside"].append(line)
            continue
        for about, step in abouts:
            if step == "seed":
                continue
            text = f"Open item {item.id} was answered: {item.decision!r}. Apply this decision to {about}."
            pool.setdefault(f"ambiguity|{about}#{item.id}", _pool_entry(
                {"kind": "ambiguity", "location": f"{about}#{item.id}", "messages": [text], "target": about},
                step, "", instruction=text))
        text = (f"Open item {item.id} is answered: {item.decision!r}. Do what waited on it in this step, then delete "
                "the item.")
        pool.setdefault(f"ambiguity|{holder_file}#{item.id}", _pool_entry(
            {"kind": "ambiguity", "location": f"{holder_file}#{item.id}", "messages": [text], "target": holder_file},
            item.step, "", instruction=text))


def _unclosed(pool: dict[str, dict[str, Any]], step: str | None = None) -> list[str]:
    return sorted(k for k, e in pool.items() if e["status"] != CLOSED and (step is None or e["step"] == step))


# --------------------------------------------------------------------------- the view


class _Pass:
    def __init__(self, git_root: str, pass_id: str) -> None:
        self.dir = _dir(git_root, pass_id)
        if not os.path.isfile(os.path.join(self.dir, "pass.json")):
            raise _refuse(f"no pass {pass_id!r} under {os.path.join(git_root, PASSES_DIR)}")
        self.state, self.meta, self.pool = _load(self.dir)
        r = self.meta["roots"]
        self.roots = Roots(r["repo"], r["spec"], r["git"])
        self.known = _spec_steps(self.roots.repo)
        self.io = SpecIO(self.roots, self.known, loop_commands._canon_dir)

    def reload(self) -> None:
        self.io = SpecIO(self.roots, self.known, loop_commands._canon_dir)

    def sync_runs(self) -> None:
        for ref in self.state.runs:
            if ref.verdict is None:
                state, _ = store.load(os.path.join(store.runs_root(self.roots.git), ref.run_id))
                if state.verdict is not None:
                    ref.verdict = state.verdict
                    if state.verdict not in pass_machine.FAILED and ref.run_id not in self.meta["absorbed"]:
                        _absorb(ref.run_id, self.roots.git, self.pool, self.io, self.meta)
                        self.meta["absorbed"].append(ref.run_id)

    def present(self) -> list[str]:
        return [s for s in self.known if self.io.graph.shape.files_by_step.get(s)]

    def steps(self, work: dict[str, bool]) -> list[str]:
        entry, args = self.meta["entry"], self.meta["entry_args"]
        if entry in ("range", "extend"):
            return list(args["steps"])
        if entry == "review":
            inside = about_set(self.io, args["about"])
            held = {n.step for n in self.io.graph.nodes if n.id in inside}
            return [s for s in self.known if s in held]
        named = [s for s in self.known if work.get(s)]
        if not named:
            return []
        return self.known[self.known.index(named[0]): self.known.index(named[-1]) + 1]

    def view(self) -> tuple[View, dict[str, dict[str, Any]]]:
        kept = set(self.meta["kept"])
        gate = self.io.gate(self.meta.get("base_ref"))
        links = self.io.links()
        present = set(self.present())
        gate_keys: dict[str, list[str]] = {}
        for key, target in gate.blocking.items():
            if key not in kept:
                gate_keys.setdefault(gate.owner.get(key) or self.io.step_of(target) or "", []).append(key)
        link_keys: dict[str, list[str]] = {}
        for key, (holder, _) in links.listed.items():
            if key not in kept:
                link_keys.setdefault(self.io.step_of(holder) or "", []).append(key)
        open_items: dict[str, list[Any]] = {}
        kept_steps: set[str] = set()
        answered: set[str] = set()  # the steps an answered open item gives work: its holder, and its about nodes
        for item in read_ambiguity_items(self.roots.spec).items:
            if not is_open(item):
                continue
            if item.decision is not None:
                answered.add(item.step)
                answered.update(s for s in (self.io.step_of(a) for a in item.about_ids) if s in self.known)
            elif item.id in kept:
                kept_steps.add(item.step)
            else:
                open_items.setdefault(item.step, []).append(item)
        kept_steps.update(gate.owner.get(k) or self.io.step_of(t) or "" for k, t in gate.blocking.items() if k in kept)
        kept_steps.update(self.io.step_of(holder) or "" for k, (holder, _) in links.listed.items() if k in kept)
        facts: dict[str, dict[str, Any]] = {}
        for step in self.known:
            facts[step] = {
                "pool": _unclosed(self.pool, step), "gate": gate_keys.get(step, []), "links": link_keys.get(step, []),
                "items": open_items.get(step, []), "suspect": step in links.suspect_steps, "has": step in present,
            }
        work = {s: bool(f["pool"] or f["gate"] or f["links"] or f["items"] or f["suspect"] or s in answered)
                for s, f in facts.items()}
        steps = self.steps(work)
        _item_findings(self.pool, self.io, steps, self.meta)
        for step in steps:
            facts[step]["pool"] = _unclosed(self.pool, step)
        views = []
        for step in steps:
            f = facts[step]
            ready = True
            if not f["has"]:
                ready, blockers = self.io.ready(step)
                f["blockers"] = blockers
            views.append(StepView(step=step, has_artifact=f["has"], ready=ready, pool_open=bool(f["pool"]),
                                  link_work=bool(f["links"]), gate_work=bool(f["gate"]), item_work=False,
                                  open_items=bool(f["items"]), suspect=f["suspect"], kept=step in kept_steps,
                                  rank=self.known.index(step)))
        view = View(steps=views, to_ask=bool(self.batch(steps, facts)),
                    pool_unclosed=any(e["status"] != CLOSED for e in self.pool.values()))
        return view, facts

    # ---- the batch

    def batch(self, steps: list[str], facts: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
        questions: list[dict[str, Any]] = []
        inside = set(steps)
        for step in steps:
            for item in facts[step]["items"]:
                about = ", ".join(self.io.label(a) for a in item.about_ids) or "nothing named"
                seed = any(self.io.step_of(a) == "seed" for a in item.about_ids)
                proposal = item.raw.get("proposed_assumption")
                if seed:
                    options = [{"label": "I have edited the seed"}, {"label": "Leave open"}]
                else:
                    options = [{"label": "Leave open"}]
                    if isinstance(proposal, str) and proposal.strip():
                        options.insert(0, {"label": "Accept the proposal", "description": proposal})
                questions.append({
                    "id": f"item:{item.id}", "step": step, "options": options, "free_text": not seed,
                    "question": f"Step {step}, open item {item.id} (about {about}): {item.description}",
                })
        for key, entry in sorted(self.pool.items()):
            if entry["status"] == CLOSED or entry["step"] not in inside and entry["step"] in self.known:
                continue  # a finding of a step outside the pass stays in the pool: a replay takes it
            text = " / ".join(entry["messages"]) or key
            if entry["step"] not in self.known:  # a seed, or a file no step owns: no run can work it
                questions.append({"id": f"seed:{key}", "question": f"A finding about {entry['target']}, which no step owns (a seed or another file): {text}",
                                  "options": [{"label": "I have edited it"}, {"label": "Leave as is"}]})
            elif entry["status"] == PARKED:
                questions.append({"id": f"finding:{key}", "step": entry["step"],
                                  "question": f"Step {entry['step']}: two fixes failed for {self.io.label(entry['target'])}: {text}",
                                  "options": [{"label": "Try once more", "description": "Put your guidance in the notes"},
                                              {"label": "Leave as is"}]})
        for key, info in sorted(self.meta["parked_gate"].items()):
            if key not in self.meta["kept"] and key not in self.meta["guidance"] and info["step"] in inside:
                questions.append({"id": f"gate:{key}", "step": info["step"],
                                  "question": f"Step {info['step']}: two fixes failed for the tool's finding {info['message']}",
                                  "options": [{"label": "Try once more", "description": "Put your guidance in the notes"},
                                              {"label": "Leave it to me"}]})
        return questions

    def apply_answers(self, path: str) -> None:
        answers = intake.load_json(path)
        if not isinstance(answers, dict):
            raise _refuse(f"{path} is not a JSON object of answers")
        for qid, value in answers.items():
            label = str(value.get("label") if isinstance(value, dict) else value)
            notes = str(value.get("notes", "")) if isinstance(value, dict) else ""
            sort, _, key = qid.partition(":")
            if sort == "item":
                self._answer_item(key, label, notes)
            elif sort == "seed" and key in self.pool:
                self.pool[key].update(status=CLOSED, left_as_is=label == "Leave as is")
            elif sort == "finding" and key in self.pool:
                if label == "Try once more":
                    self.pool[key].update(status=OPEN, attempts=1, instruction=f"The operator: {notes}" if notes else "")
                else:
                    self.pool[key].update(status=CLOSED, left_as_is=True)
            elif sort == "gate":
                if label == "Try once more":
                    self.meta["guidance"][key] = notes or "try once more"
                else:
                    self.meta["kept"].append(key)
            self.meta["asked"].append({"id": qid, "answer": label, "notes": notes})

    def _answer_item(self, item_id: str, label: str, notes: str) -> None:
        if label == "Leave open":
            self.meta["kept"].append(item_id)
            return
        decision = notes or label
        if label == "Accept the proposal":
            for item in read_ambiguity_items(self.roots.spec).items:
                if item.id == item_id:
                    decision = str(item.raw.get("proposed_assumption") or decision)
        elif label == "I have edited the seed":
            decision = "seed edited"
        done = subprocess.run(
            [sys.executable, "-m", "specdev_tools.cli", "json", "patch", "--id", item_id, ".decision", json.dumps(decision),
             "--repo-root", self.roots.repo, "--spec-root", self.roots.spec, "--git-root", self.roots.git],
            capture_output=True, text=True, check=False,
        )
        if done.returncode != 0:
            raise _refuse(f"the decision of {item_id} was not written: {(done.stdout + done.stderr).strip()[-400:]}")

    # ---- runs

    def carry_for(self, step: str) -> str | None:
        for ref in reversed(self.state.runs):
            if ref.verdict is not None and ref.verdict not in pass_machine.FAILED and (ref.step in (None, step)):
                if step in store.load(os.path.join(store.runs_root(self.roots.git), ref.run_id))[1]["steps"]:
                    return ref.run_id
        return None

    def worklist(self, step: str) -> str:
        keys = _unclosed(self.pool, step)
        path = os.path.join(self.dir, "worklists", f"w{self.state.walk}-{step}.json")
        findings = [report.as_finding(k, self.pool[k]) for k in keys]
        store.write_json(path, report.findings_document(step, 1, findings))
        store.write_json(path + ".state.json", {
            k: {"status": self.pool[k]["status"] if self.pool[k]["status"] in (AWAITING, CONTESTED) else OPEN,
                "attempts": self.pool[k]["attempts"], "instruction": self.pool[k]["instruction"],
                "fixer": self.pool[k].get("fixer", "")} for k in keys})
        return path

    def start_run(self, action: pass_machine.PassAction) -> str:
        m, args = self.meta, self.meta["entry_args"]
        common: dict[str, Any] = {"readers": m["readers"], "cap": m["cap"], "base_ref": m.get("base_ref"),
                                  "pass_id": m["pass_id"], "about": args.get("about")}
        if action.step is None:
            return create_run(self.roots, "step", action.steps, "review-only", **common)
        step, common["defer"], common["guidance"] = action.step, True, m["guidance"]
        if action.mode == "author":
            return create_run(self.roots, "step", [step], "author", **common)
        if action.mode == "extend":
            return create_run(self.roots, "step", [step], "extend", extend=args["extend"], seed=args.get("seed"), **common)
        return create_run(self.roots, "step", [step], "worklist", worklist=self.worklist(step),
                          carry=self.carry_for(step), **common)

    def finish(self, verdict: str, view: View, facts: dict[str, dict[str, Any]]) -> dict[str, Any]:
        lines = [f"# Pass `{self.meta['pass_id']}`: {verdict}", "", f"Entry: {self.meta['entry']} {json.dumps(self.meta['entry_args'])}", "",
                 "| Run | Step | Walk | Verdict |", "|---|---|---|---|",
                 *[f"| {r.run_id} | {r.step or 'survey'} | {r.walk} | {r.verdict} |" for r in self.state.runs]]
        left: list[str] = []
        for sv in view.steps:
            f = facts[sv.step]
            parts = []
            if not sv.has_artifact:
                parts.append("no artifact" + (f" (not ready: {'; '.join(f.get('blockers', []))})" if not sv.ready else ""))
            parts += [f"finding {k} ({self.pool[k]['status']})" for k in f["pool"]]
            parts += [f"gate {k}" for k in f["gate"]] + [f"suspect link {k}" for k in f["links"]]
            parts += [f"open item {i.id}" for i in f["items"]]
            if sv.suspect and not f["links"]:
                parts.append("suspect links that wait on a step above")
            left += [f"- step {sv.step}: {p}" for p in parts]
        steps = {sv.step for sv in view.steps}
        outside = list(self.meta["outside"])
        outside += [f"finding {k} about step {e['step'] or '?'} ({e['target']})" for k, e in sorted(self.pool.items())
                    if e["status"] != CLOSED and e["step"] not in steps]
        outside += [f"step {s}: suspect links" for s in self.known if facts[s]["suspect"] and s not in steps]
        kept = [f"- {k}" for k in self.meta["kept"]]
        for title, values in (("Left, by step", left), ("Outside the pass", [f"- {o}" for o in outside]),
                              ("Kept by the operator", kept)):
            if values:
                lines += ["", f"## {title}", *values]
        if verdict == "INCOMPLETE":
            lines += ["", "Go on with: `/specdev-pass --replay`"]
        path = os.path.join(self.dir, "report.md")
        store.write_text(path, "\n".join(lines) + "\n")
        return {"type": "done", "pass_id": self.meta["pass_id"], "verdict": verdict, "report": path,
                "left": len(left), "outside": len(outside)}


@_handled
def run_pass_next(args: argparse.Namespace) -> int:
    _, _, git_root = roots(args)
    p = _Pass(git_root, args.pass_id)
    state = p.state
    if args.stop:
        state.stop = True
    p.sync_runs()
    if args.answers:
        p.apply_answers(args.answers)
        p.reload()
    view, facts = p.view()
    if args.answers and not view.to_ask:
        pass_machine.record_answered(state)
    before = copy.deepcopy(state)
    try:
        action = pass_machine.decide(state, view, retry=args.retry and not args.stop)  # with both, the stop wins
        if action.type == "run" and action.run_id is None:
            run_id = p.start_run(action)
            pass_machine.record_run(state, run_id, action.step)
            action.run_id = run_id
    except FindingError:
        _save(p.dir, before, p.meta, p.pool)  # the run was not started: the pass has not moved
        raise
    if action.type == "run":
        out: dict[str, Any] = {"type": "run", "pass_id": args.pass_id, "run_id": action.run_id,
                               "step": action.step or "survey", "walk": state.walk if action.step else 0}
    elif action.type == "ask":
        out = {"type": "ask", "pass_id": args.pass_id, "questions": p.batch([sv.step for sv in view.steps], facts),
               "answers_path": os.path.join(p.dir, "answers.json")}
    else:
        out = p.finish(action.verdict or "", view, facts)
    _save(p.dir, state, p.meta, p.pool)
    print(json.dumps(out, indent=2))
    return 0
