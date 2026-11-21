"""The release cut: the one function that creates a release tag, and what it checks first.

``cut_release`` refuses, in this order, a tree that is not clean (E910), a host with no ``release_tag_pattern`` (E911) and a tag
name that does not match the pattern, is not a usable git tag name or exists already (E912); then it runs the release gate on
the checkout.  Only a gate with no error creates the tag: an annotated tag on HEAD, made through ``run_git``.  Nothing else is
written, nothing is committed and nothing is pushed (the push starts the deploy; it is the person's or the host's).
"""
from __future__ import annotations

from dataclasses import dataclass

from specdev_tools.core.errors import FindingError, make_error, refusal
from specdev_tools.graph.gitview import GitViewError, git_reason, resolve_ref, run_git
from specdev_tools.release.gate import ReleaseGateResult, run_release_gate
from specdev_tools.release.tag_state import release_tag_pattern, tag_matches
from specdev_tools.verify.code_tree import declarations_of

_SHOWN_PATHS = 3


@dataclass(frozen=True)
class CutResult:
    """What the cut did: the *commit* HEAD names, the *gate* result and whether the annotated *tag* was created (``tagged``)."""

    tag: str
    commit: str
    message: str
    gate: ReleaseGateResult
    tagged: bool


def default_message(tag: str) -> str:
    """The annotation of a tag cut without ``--message``."""
    return f"release {tag}"


def _git_text(git_root: str, args: list[str]) -> str:
    process = run_git(git_root, args)
    if process.returncode != 0:
        raise FindingError(make_error("E708", f"git {args[0]} failed: {git_reason(process)}"))
    return process.stdout.decode("utf-8", errors="replace")


def _refuse_dirty(git_root: str) -> None:
    """E910 when ``git status --porcelain`` lists anything: a changed or staged file, or an untracked one git does not ignore."""
    lines = [line for line in _git_text(git_root, ["status", "--porcelain"]).splitlines() if line.strip()]
    if lines:
        shown = ", ".join(line[3:] for line in lines[:_SHOWN_PATHS]) + (", ..." if len(lines) > _SHOWN_PATHS else "")
        raise refusal("E910", f"the working tree is not clean ({len(lines)} path(s): {shown}); commit or remove them, so the tag names the state that was checked")


def _refuse_bad_tag(git_root: str, tag: str, pattern: str) -> None:
    """E912 when *tag* does not match *pattern*, is not a name git accepts for a tag, or names a tag that exists."""
    if not tag_matches(pattern, tag):
        raise refusal("E912", f"'{tag}' does not match the release tag pattern {pattern}; name a tag the pattern accepts")
    if tag.startswith("-") or run_git(git_root, ["check-ref-format", f"refs/tags/{tag}"]).returncode != 0:
        raise refusal("E912", f"'{tag}' is not a name git accepts for a tag; name a tag the pattern accepts")
    if run_git(git_root, ["rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"]).returncode == 0:
        raise refusal("E912", f"the tag '{tag}' exists already; a release tag is cut once, name the next one")


def cut_release(git_root: str, spec_root: str, repo_root: str, tag: str, message: str | None = None, project_canon_dir: str | None = None) -> CutResult:
    """Cut the release *tag* on HEAD of the host at *git_root* when the release gate passes (see the module text).

    *message* is the annotation (``default_message`` when ``None``); *project_canon_dir* is the folder the command discovers and
    ``spec-check`` receives too.  A gate with errors is a result with ``tagged`` false, not an exception.

    Raises:
        FindingError: E910, E911, E912; E708 when git cannot answer or refuses to create the tag; E520 when the host
            declarations cannot be read.
    """
    _refuse_dirty(git_root)
    pattern = release_tag_pattern(declarations_of(spec_root))
    _refuse_bad_tag(git_root, tag, pattern)
    try:
        commit = resolve_ref("HEAD", git_root)
    except GitViewError as error:
        raise FindingError(make_error("E708", f"nothing can be tagged: {error.error.message}")) from error
    gate = run_release_gate(repo_root, spec_root, git_root, spec_root, project_canon_dir)
    text = message or default_message(tag)
    if not gate.passed:
        return CutResult(tag, commit, text, gate, False)
    _git_text(git_root, ["tag", "-a", "-m", text, "--", tag, commit])
    return CutResult(tag, commit, text, gate, True)
