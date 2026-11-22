"""The host installer library behind ``specdev update`` and ``init``.

A *piece* is one thing the toolkit puts into a host repository (a hook file, a git setting, a workflow, a wrapper...).
This module is the core every piece stands on: the registry of pieces, the context a piece reads, the result a piece
returns, the dry-run rule, the marker helpers and the warning codes.  Real pieces are added by later work items, each
by one function and one line in :data:`PIECES`.

The rules every piece follows (the report of a run says which one applied):

* it never overwrites a host's own content outside a block it marked (``# >>> specdev-managed`` to
  ``# <<< specdev-managed``) or a file whose first line is its header (``# specdev-managed: <piece> toolkit=<version>``);
* with ``ctx.dry_run`` it writes nothing and runs no command, and returns :data:`WOULD_INSTALL` for what it would do;
* a second run changes nothing and returns :data:`CURRENT`.

The module sits beside ``update.py`` outside the layer chain: only ``update.py`` and ``cli.py`` import it.
"""
from __future__ import annotations

import difflib
import json
import os
import posixpath
import re
import shlex
import subprocess
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import NamedTuple

import yaml

from .core.changelog_parser import get_toolkit_version
from .core.constants import REMOVED_COMMANDS
from .core.errors import ERROR_CODES
from .core.host_declarations import HOST_DECLARATIONS_FILE, HostDeclarationsError, load_host_declarations
from .graph.gitview import GitViewError, git_top_level, run_git, spec_path_in_repo
from .trace.merge_driver import ATTRIBUTES_GIT_PATH, DRIVER_ARGUMENTS, DRIVER_NAME, LockMergeError, attribute_line, install_driver

W_TEMPLATE_DRIFT = "W930"
W_INSTALL_REFUSED = "W931"
W_RETIRED_COMMAND = "W932"
W_SETUP_UNDECLARED = "W935"

CREATED = "created"
REFRESHED = "refreshed"
CURRENT = "current"
DRIFT = "drift"
REFUSED = "refused"
WOULD_INSTALL = "would_install"

DEFAULT_VENV_NAME = "devspec_env"
MARKER_BEGIN = "# >>> specdev-managed"
MARKER_END = "# <<< specdev-managed"
_HEADER_PATTERN = re.compile(r"^# specdev-managed: (?P<piece>\S+) toolkit=(?P<version>\S+)\s*$")

NOT_A_GIT_REPOSITORY = "the spec folder is not inside a git repository (pass --git-root to name the host)"
TOOLKIT_IS_NOT_A_HOST = "the toolkit checkout is not a host"
NO_TOOLKIT_INPUTS = "the toolkit version or its templates folder was not found, so nothing is installed"
NO_INSTALL_REQUESTED = "--no-install"


class HostInstallError(Exception):
    """A piece cannot do its work; the message is the reason printed with W931."""


@dataclass(frozen=True)
class Finding:
    """One thing a piece found in a host: a drift, a refusal, a retired command, an undeclared setup.

    ``code`` is one of the four host warning codes; ``file`` is relative to the host root (empty when no file is
    meant); ``line`` is 1-based; ``command`` is the command the finding is about (empty when none); ``text`` is the
    exact replacement or the pointer the person needs.
    """

    code: str
    file: str = ""
    line: int | None = None
    command: str = ""
    text: str = ""

    def render(self) -> str:
        """The warning string ``UpdateResult.warnings`` carries: the code and name, then where, then what."""
        where = self.file if self.line is None else f"{self.file}:{self.line}"
        return f"{self.code} {ERROR_CODES[self.code]}: {f'{where}: ' if where else ''}{self.text}".rstrip()


@dataclass(frozen=True)
class PieceResult:
    """What one piece did: a status constant, a short detail, and the findings it raised."""

    status: str
    detail: str = ""
    findings: tuple[Finding, ...] = ()


def refused(reason: str, *, file: str = "") -> PieceResult:
    """The result of a piece that wrote nothing and says why (a W931 finding carries the reason)."""
    return PieceResult(REFUSED, reason, (Finding(W_INSTALL_REFUSED, file=file, text=reason),))


@dataclass(frozen=True)
class InstallContext:
    """Everything a piece may read; built once per run, never mutated.

    ``spec_rel`` is the spec folder relative to ``git_root``; ``venv_prefix`` is ``sys.prefix`` of the interpreter
    that runs the command; ``venv_name`` is :func:`venv_name_for` of that prefix.
    """

    spec_dir: Path
    spec_rel: str
    git_root: Path
    toolkit_root: Path
    templates_dir: Path
    toolkit_version: str
    venv_prefix: Path
    venv_name: str
    dry_run: bool
    adopt: bool
    force_claude: bool

    @property
    def venv_bin(self) -> Path:
        """The ``bin`` folder of the running interpreter's venv (the console scripts and ``pre-commit`` live here)."""
        return self.venv_prefix / "bin"

    @property
    def toolkit_rel(self) -> str:
        """The toolkit folder relative to the host root, ``/``-separated (``.`` when they are one folder)."""
        # ``git_root`` is resolved; resolve the toolkit's parent folder too, so a symlinked path to the same folder
        # (``/tmp`` for ``/private/tmp`` on macOS) does not turn ``devspec_toolkit`` into ``../../..``.
        toolkit = self.toolkit_root.parent.resolve() / self.toolkit_root.name
        return Path(os.path.relpath(toolkit, self.git_root)).as_posix()


class HostPiece(NamedTuple):
    """One line of the registry: the piece's name (the JSON key) and the function that installs it."""

    name: str
    install: Callable[[InstallContext], PieceResult]




@dataclass(frozen=True)
class InstallReport:
    """The outcome of one install run: a result per piece, or the reason nothing ran at all."""

    pieces: tuple[tuple[str, PieceResult], ...] = ()
    skipped: str = ""

    def warnings(self) -> list[str]:
        """The warning strings of the findings of the pieces, in piece order; a finding every piece repeats (the host could not be resolved) is listed once."""
        return list(dict.fromkeys(finding.render() for _, result in self.pieces for finding in result.findings))

    def summary(self) -> str:
        """The lines printed for a person: the skip reason, or one line per piece."""
        if self.skipped:
            return f"Host install skipped: {self.skipped}."
        if not self.pieces:
            return "Host install: no pieces to install."
        lines = [f"  {name}: {result.status}" + (f" ({result.detail})" if result.detail else "") for name, result in self.pieces]
        return "\n".join(["Host install:", *lines])

    def to_dict(self) -> dict:
        """The ``host_install`` JSON value: ``skipped`` (reason or null) and ``pieces`` (name to status, detail, findings)."""
        return {
            "skipped": self.skipped or None,
            "pieces": {
                name: {"status": result.status, "detail": result.detail, "findings": [asdict(f) for f in result.findings]}
                for name, result in self.pieces
            },
        }


def venv_name_for(host_root: Path, prefix: str | Path | None = None) -> str:
    """The name of the venv the host's wrappers and hooks should use (ruling N5).

    It is the folder name of *prefix* (default ``sys.prefix``, the interpreter that runs the command) when that folder
    lies directly under *host_root*, else :data:`DEFAULT_VENV_NAME`.
    """
    venv = Path(sys.prefix if prefix is None else prefix)
    return venv.name if venv.parent.resolve() == Path(host_root).resolve() else DEFAULT_VENV_NAME


def managed_header(piece: str, toolkit_version: str) -> str:
    """The first line of a file the toolkit fully owns."""
    return f"# specdev-managed: {piece} toolkit={toolkit_version}"


def read_managed_header(text: str) -> tuple[str, str] | None:
    """``(piece, toolkit_version)`` of the header on the first line of *text*, ``None`` when the file is not marked."""
    match = _HEADER_PATTERN.match(text.partition("\n")[0])
    return (match["piece"], match["version"]) if match else None


def _marker_lines(lines: list[str]) -> tuple[int, int] | None:
    """The indexes of the begin and end marker lines, ``None`` when there are none.

    Raises:
        HostInstallError: a begin without an end, an end without a begin, or a second pair.
    """
    begins = [i for i, line in enumerate(lines) if line.strip().startswith(MARKER_BEGIN)]
    ends = [i for i, line in enumerate(lines) if line.strip().startswith(MARKER_END)]
    if not begins and not ends:
        return None
    if len(begins) != 1 or len(ends) != 1 or ends[0] < begins[0]:
        raise HostInstallError(f"the managed block is damaged: expected one '{MARKER_BEGIN}' line followed by one '{MARKER_END}' line")
    return begins[0], ends[0]


def split_marked_block(text: str) -> tuple[str, str, str] | None:
    """``(before, inside, after)`` around the marked block of *text*, ``None`` when it has none.

    ``before`` ends with the begin marker line and ``after`` starts with the end marker line, so
    ``before + inside + after == text``.

    Raises:
        HostInstallError: the markers are damaged.
    """
    lines = text.splitlines(keepends=True)
    found = _marker_lines(lines)
    if found is None:
        return None
    begin, end = found
    return "".join(lines[: begin + 1]), "".join(lines[begin + 1 : end]), "".join(lines[end:])


def replace_marked_block(text: str, body: str) -> str | None:
    """*text* with the lines between the markers replaced by *body*; ``None`` when *text* has no marked block.

    Every byte outside the markers is kept.  *body* is written as given, with a newline added when it lacks one.

    Raises:
        HostInstallError: the markers are damaged.
    """
    parts = split_marked_block(text)
    if parts is None:
        return None
    before, _, after = parts
    if body and not body.endswith("\n"):
        body += "\n"
    if not before.endswith("\n"):
        before += "\n"
    return before + body + after


def write_if_changed(path: Path, text: str, *, dry_run: bool) -> str:
    """Write *text* to *path* only when it differs; the status says what happened.

    ``CURRENT`` when the file already holds *text*; ``WOULD_INSTALL`` for a dry run that would write; else ``CREATED``
    (the file was absent; its folder is made) or ``REFRESHED``.  The caller decides that the file is the toolkit's to write.
    """
    existing = path.read_text(encoding="utf-8") if path.is_file() else None
    if existing == text:
        return CURRENT
    if dry_run:
        return WOULD_INSTALL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return CREATED if existing is None else REFRESHED


def _host_context(
    spec_dir: Path, repo_root: Path, git_root: Path | None, version: str, *, dry_run: bool, adopt: bool, force_claude: bool
) -> InstallContext:
    """Resolve the host a run installs into.

    Raises:
        HostInstallError: no git repository holds the spec folder, the spec folder is outside the named root, or the
            toolkit checkout is the host.
    """
    try:
        top = str(git_root) if git_root is not None else git_top_level(str(spec_dir))
        if top is None or not Path(top).is_dir():
            raise HostInstallError(NOT_A_GIT_REPOSITORY)
        spec_rel = spec_path_in_repo(str(spec_dir), top)
    except GitViewError as exc:
        raise HostInstallError(str(exc)) from exc
    host_root = Path(top).resolve()
    if host_root == repo_root.resolve():
        raise HostInstallError(TOOLKIT_IS_NOT_A_HOST)
    prefix = Path(sys.prefix)
    return InstallContext(
        spec_dir=spec_dir,
        spec_rel=spec_rel,
        git_root=host_root,
        toolkit_root=repo_root,
        templates_dir=repo_root / "templates",
        toolkit_version=version,
        venv_prefix=prefix,
        venv_name=venv_name_for(host_root, prefix),
        dry_run=dry_run,
        adopt=adopt,
        force_claude=force_claude,
    )


def _run_piece(piece: HostPiece, ctx: InstallContext) -> PieceResult:
    """Run one piece; a piece that raises is a W931 result and never stops the others or the version stamp."""
    try:
        return piece.install(ctx)
    except Exception as exc:  # boundary: one piece must not stop the others or the core of ``update``
        return refused(f"{piece.name} failed: {type(exc).__name__}: {exc}")


def run_host_install(
    spec_dir: Path,
    repo_root: Path,
    *,
    git_root: Path | None = None,
    dry_run: bool = False,
    adopt: bool = False,
    force_claude: bool = False,
    pieces: tuple[HostPiece, ...] | None = None,
) -> InstallReport:
    """Install every registered piece into the host that holds *spec_dir*.

    *git_root* wins when given, else it is the git top folder of *spec_dir*.  Nothing is written when the toolkit
    version or its ``templates`` folder is missing (``skipped``), and every piece is ``refused`` with W931 when the
    spec folder is not in a git repository or the toolkit checkout is itself the host.  *pieces* defaults to
    :data:`PIECES`.  Never raises for a piece.
    """
    registry = PIECES if pieces is None else pieces
    version = get_toolkit_version(repo_root)
    if version is None or not (repo_root / "templates").is_dir():
        return InstallReport(skipped=NO_TOOLKIT_INPUTS)
    try:
        ctx = _host_context(spec_dir, repo_root, git_root, version, dry_run=dry_run, adopt=adopt, force_claude=force_claude)
    except HostInstallError as exc:
        return InstallReport(pieces=tuple((piece.name, refused(str(exc))) for piece in registry))
    return InstallReport(pieces=tuple((piece.name, _run_piece(piece, ctx)) for piece in registry))


# --------------------------------------------------------------------------------------------------------------------
# Piece "pre-commit": the host's ``.pre-commit-config.yaml``.
#
# The toolkit's hooks live between two marker lines in the host's own file.  The file is read with ``yaml.compose`` for
# the hooks' line spans and never loaded and dumped again (a round trip drops comments), so every line outside the block
# is kept byte for byte.
# --------------------------------------------------------------------------------------------------------------------

PRE_COMMIT_FILE = ".pre-commit-config.yaml"
PRE_COMMIT_TEMPLATE = "pre-commit-config.host.yaml"
PRE_COMMIT_PIECE = "pre-commit"
_TEMPLATE_TOOLKIT = "devspec_toolkit"
_CLI_SUBCOMMAND = re.compile(r"specdev_tools\.cli\s+(\S+)")
_COMPARED_FIELDS = ("entry", "files", "pass_filenames", "require_serial", "types")
_PRE_COMMIT_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class PreCommitHook:
    """One hook of a ``repo: local`` entry: the fields the installer compares and where it sits in the file.

    ``start`` and ``end`` are 1-based line numbers (the line of the ``- `` and the last line with content of the hook;
    comment lines between two hooks belong to neither); ``col`` is the 0-based column of the ``-``.  Absent fields hold
    pre-commit's defaults, so a hook that leaves ``pass_filenames`` out equals one that says ``true``.
    """

    id: str
    entry: str
    files: str | None
    pass_filenames: bool
    require_serial: bool
    types: tuple[str, ...]
    start: int
    end: int
    col: int

    @property
    def subcommand(self) -> str | None:
        """The ``specdev_tools.cli <subcommand>`` the entry runs, ``None`` for a hook that does not run the toolkit."""
        match = _CLI_SUBCOMMAND.search(self.entry)
        return match[1] if match else None

    def differences(self, other: PreCommitHook) -> list[str]:
        """The names of the compared fields in which *other* differs from this hook."""
        return [name for name in _COMPARED_FIELDS if getattr(self, name) != getattr(other, name)]


@dataclass(frozen=True)
class _ConfigShape:
    """What the installer needs to know of a pre-commit config: the local hooks and where hooks or a repo can be added."""

    hooks: tuple[PreCommitHook, ...] = ()
    local_lists: tuple[tuple[int, int], ...] = ()  # per local repo with hooks: (last content line, column of the dashes)
    repos_end: int | None = None  # last content line of the ``repos`` list, when it is a block list
    repos_col: int = 0


def _template_file(templates_dir: Path | None) -> Path | None:
    """The hook template of the toolkit, ``None`` when the folder or the file is missing."""
    path = None if templates_dir is None else templates_dir / PRE_COMMIT_TEMPLATE
    return path if path is not None and path.is_file() else None


def render_pre_commit_template(rel_toolkit_root: str, venv_name: str, templates_dir: Path | None = None) -> str:
    """The toolkit's hook template with the host's toolkit folder and venv name put in.

    Text substitution only: ``./devspec_toolkit`` and ``devspec_toolkit/`` become the toolkit folder relative to the
    host root, ``devspec_env`` becomes *venv_name*.  A missing template gives a minimal config with the one step-gate
    hook, so a host never ends up with none.
    """
    template = _template_file(templates_dir)
    if template is not None:
        content = template.read_text(encoding="utf-8")
        content = content.replace(f"./{_TEMPLATE_TOOLKIT}", f"./{rel_toolkit_root}")
        content = content.replace(f"{_TEMPLATE_TOOLKIT}/", f"{rel_toolkit_root}/")
        return content.replace(DEFAULT_VENV_NAME, venv_name)
    return f"""# Pre-commit hooks: template not found, minimal config generated.
repos:
  - repo: local
    hooks:
      - id: spec-check
        name: Step gate for touched steps and seed paths
        entry: {venv_name}/bin/python -m specdev_tools.cli spec-check spec --repo-root ./{rel_toolkit_root} --spec-root ./spec --git-root . --paths
        language: system
        pass_filenames: true
        require_serial: true
        types: [file]
"""


def _content_end_line(node: yaml.Node) -> int:
    """The 0-based last line of *node* that holds content (a block ends where the next token starts, so step back)."""
    while isinstance(node, yaml.MappingNode | yaml.SequenceNode) and node.value:
        last = node.value[-1]
        node = last[1] if isinstance(node, yaml.MappingNode) else last
    mark = node.end_mark
    return mark.line - 1 if mark.column == 0 and mark.line > node.start_mark.line else mark.line


def _dash_position(lines: list[str], node: yaml.Node) -> tuple[int, int]:
    """``(0-based line, column)`` of the ``-`` that opens the sequence item *node*."""
    line = node.start_mark.line
    for candidate in (line, line - 1):
        if candidate < 0:
            break
        prefix = lines[candidate][: node.start_mark.column] if candidate == line else lines[candidate]
        stripped = prefix.rstrip()
        if stripped.endswith("-") and not stripped[:-1].strip():
            return candidate, len(stripped) - 1
    raise HostInstallError(f"line {line + 1}: a hook list item is not in the block form '- id: ...'")


def _mapping_value(node: yaml.Node, key: str) -> yaml.Node | None:
    if not isinstance(node, yaml.MappingNode):
        return None
    return next((value for k, value in node.value if getattr(k, "value", None) == key), None)


def _as_list(value: object) -> tuple[str, ...]:
    return tuple(str(v) for v in value) if isinstance(value, list) else ()


def _parse_pre_commit(text: str) -> _ConfigShape:
    """The local hooks of a config and the places to add hooks, read with ``yaml.compose`` (no rewrite of anything).

    Raises:
        HostInstallError: the text is not YAML, or its ``repos`` is not a list of mappings.
    """
    try:
        root = yaml.compose(text)
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise HostInstallError(f"{PRE_COMMIT_FILE} is not valid YAML: {' '.join(str(exc).split())}") from exc
    if root is None:
        return _ConfigShape()
    repos = _mapping_value(root, "repos")
    if not isinstance(root, yaml.MappingNode) or not isinstance(data, dict) or not isinstance(data.get("repos"), list):
        raise HostInstallError(f"{PRE_COMMIT_FILE} has no 'repos' list")
    lines = text.splitlines()
    repos_end, repos_col = None, 0
    if isinstance(repos, yaml.SequenceNode) and not repos.flow_style and repos.value:
        repos_end = _content_end_line(repos) + 1
        repos_col = _dash_position(lines, repos.value[0])[1]
    hooks: list[PreCommitHook] = []
    lists: list[tuple[int, int]] = []
    for repo_node, repo in zip(repos.value if isinstance(repos, yaml.SequenceNode) else [], data["repos"], strict=False):
        hooks_node = _mapping_value(repo_node, "hooks")
        if not isinstance(repo, dict) or repo.get("repo") != "local" or not isinstance(hooks_node, yaml.SequenceNode):
            continue
        if hooks_node.flow_style or not hooks_node.value:
            continue
        for hook_node, hook in zip(hooks_node.value, repo["hooks"], strict=False):
            if not isinstance(hook, dict) or not isinstance(hook.get("id"), str):
                continue
            start, col = _dash_position(lines, hook_node)
            hooks.append(
                PreCommitHook(
                    id=hook["id"],
                    entry=str(hook.get("entry", "")),
                    files=None if hook.get("files") is None else str(hook["files"]),
                    pass_filenames=hook.get("pass_filenames", True) is not False,
                    require_serial=hook.get("require_serial", False) is True,
                    types=_as_list(hook.get("types", ["file"])),
                    start=start + 1,
                    end=_content_end_line(hook_node) + 1,
                    col=col,
                )
            )
        last_node = hooks_node.value[-1]
        lists.append((_content_end_line(last_node) + 1, _dash_position(lines, hooks_node.value[0])[1]))
    return _ConfigShape(tuple(hooks), tuple(lists), repos_end, repos_col)


def enumerate_pre_commit_hooks(text: str) -> tuple[PreCommitHook, ...]:
    """The hooks of the local repos of a pre-commit config, in file order (the one reader of a template's hooks)."""
    return _parse_pre_commit(text).hooks


def _indent(lines: list[str], delta: int) -> list[str]:
    """*lines* moved right by *delta* columns (left when negative, never past column 0); blank lines are kept as they are."""
    moved = []
    for line in lines:
        if not line.strip():
            moved.append(line)
        elif delta >= 0:
            moved.append(" " * delta + line)
        else:
            moved.append(line[min(-delta, len(line) - len(line.lstrip(" "))) :])
    return moved


def _with_newline(lines: list[str]) -> list[str]:
    return [*lines[:-1], lines[-1] + "\n"] if lines and not lines[-1].endswith("\n") else lines


@dataclass(frozen=True)
class _Template:
    """The rendered hook template cut into its head (up to the first hook) and the hook block (first hook to the end)."""

    head: list[str]
    body: list[str]
    col: int
    hooks: tuple[PreCommitHook, ...]

    def block(self, col: int) -> list[str]:
        """The hook lines moved to the column *col*, ready to sit between two marker lines."""
        return _with_newline(_indent(self.body, col - self.col))

    def hook_text(self, hook: PreCommitHook) -> str:
        """The exact lines of one template hook, as a person would paste them."""
        return "".join(self.body[hook.start - len(self.head) - 1 : hook.end - len(self.head)]).rstrip()


def _read_template(ctx: InstallContext) -> _Template:
    rendered = render_pre_commit_template(ctx.toolkit_rel, ctx.venv_name, ctx.templates_dir)
    hooks = enumerate_pre_commit_hooks(rendered)
    if not hooks:
        raise HostInstallError(f"the hook template {PRE_COMMIT_TEMPLATE} has no hook")
    lines = rendered.splitlines(keepends=True)
    start = hooks[0].start - 1
    if any(line.strip() and not line.lstrip().startswith("#") for line in lines[hooks[-1].end :]):
        raise HostInstallError(f"the hook template {PRE_COMMIT_TEMPLATE} must end with its hook list")
    return _Template(lines[:start], lines[start:], hooks[0].col, hooks)


def _marker_pair(col: int) -> tuple[str, str]:
    pad = " " * col
    return f"{pad}{MARKER_BEGIN} (the toolkit rewrites the lines between the markers on 'specdev update')\n", f"{pad}{MARKER_END}\n"


def _marked_block(template: _Template, col: int) -> list[str]:
    begin, end = _marker_pair(col)
    return [begin, *template.block(col), end]


def _new_config(template: _Template) -> str:
    return "".join([*template.head, *_marked_block(template, template.col)])


def _marker_column(before: str) -> int:
    last = before.rstrip("\n").rsplit("\n", 1)[-1]
    return len(last) - len(last.lstrip(" "))


def _candidates(hook: PreCommitHook, shape: _ConfigShape) -> list[PreCommitHook]:
    """The host hooks that stand for the template hook *hook*: the same id, else the same ``specdev_tools.cli`` subcommand."""
    by_id = [h for h in shape.hooks if h.id == hook.id]
    return by_id or [h for h in shape.hooks if hook.subcommand is not None and h.subcommand == hook.subcommand]


def _hook_findings(template: _Template, shape: _ConfigShape) -> tuple[list[Finding], list[PreCommitHook]]:
    """The W930 findings of a hand-written config (a template hook that is missing or differs) and the host hooks that matched."""
    matched = sorted({h for hook in template.hooks for h in _candidates(hook, shape)}, key=lambda h: h.start)
    anchor = matched[0].start if matched else None
    findings: list[Finding] = []
    missing: list[str] = []
    for hook in template.hooks:
        found = _candidates(hook, shape)
        if not found:
            missing.append(hook.id)
            continue
        different = hook.differences(found[0])
        if different:
            what = (
                f"hook '{found[0].id}' differs from the template in {', '.join(different)}; "
                "'specdev update --adopt' replaces it, or replace it by hand"
            )
            findings.append(Finding(W_TEMPLATE_DRIFT, PRE_COMMIT_FILE, found[0].start, hook.subcommand or "", f"{what} with:\n{template.hook_text(hook)}"))
    if missing:
        what = (
            f"template hooks not in the config: {', '.join(missing)}; "
            f"'specdev update --adopt' adds them, or copy them from {PRE_COMMIT_TEMPLATE}"
        )
        findings.append(Finding(W_TEMPLATE_DRIFT, PRE_COMMIT_FILE, anchor, "", what))
    return findings, matched


def _adopt(lines: list[str], template: _Template, matched: list[PreCommitHook]) -> list[str]:
    """*lines* with the spans of the matched host hooks removed and one marked block at the first of them."""
    block = _marked_block(template, matched[0].col)
    result: list[str] = []
    index = 0
    while index < len(lines):
        line_no = index + 1
        span = next((h for h in matched if h.start == line_no), None)
        if span is None:
            result.append(lines[index])
            index += 1
            continue
        if span is matched[0]:
            result.extend(block)
        index = span.end
    return result


def _append_block(lines: list[str], template: _Template, shape: _ConfigShape) -> list[str]:
    """*lines* with the marked block added after the last local hook, or as a new local repo at the end of ``repos``."""
    if shape.local_lists:
        after, col = shape.local_lists[0]
        return [*_with_newline(lines[:after]), *_marked_block(template, col), *lines[after:]]
    if shape.repos_end is None:
        raise HostInstallError(f"{PRE_COMMIT_FILE} has no block-style 'repos' list to add the hooks to")
    pad = " " * shape.repos_col
    repo = [f"{pad}- repo: local\n", f"{pad}  hooks:\n"]
    return [*_with_newline(lines[: shape.repos_end]), *repo, *_marked_block(template, shape.repos_col + 4), *lines[shape.repos_end :]]


def _plan_pre_commit(ctx: InstallContext, template: _Template, existing: str | None) -> tuple[str, list[Finding], str]:
    """``(new text, findings, detail)``: the text the file should hold (unchanged when the host's hooks are not touched)."""
    if existing is None or not existing.strip():
        return _new_config(template), [], "written with the toolkit hooks between markers"
    if "\r" in existing:
        raise HostInstallError(f"{PRE_COMMIT_FILE} uses CRLF line endings; convert it to LF first or add the hooks by hand")
    parts = split_marked_block(existing)
    if parts is not None:
        replaced = replace_marked_block(existing, "".join(template.block(_marker_column(parts[0]))))
        assert replaced is not None
        return replaced, [], "the hooks between the markers rewritten from the template"
    shape = _parse_pre_commit(existing)
    findings, matched = _hook_findings(template, shape)
    lines = existing.splitlines(keepends=True)
    if not matched:
        return "".join(_append_block(lines, template, shape)), [], "no toolkit hook found: block added after the host's own hooks"
    if ctx.adopt:
        return "".join(_adopt(lines, template, matched)), [], f"{len(matched)} hand-written hook(s) replaced by one marked block"
    return existing, findings, "hand-written toolkit hooks left as they are" + (f"; {len(findings)} differ from the template" if findings else "")


def _run_pre_commit_install(binary: Path, git_root: Path) -> tuple[int, str]:
    """Run ``<binary> install`` in the host (the one place the installer starts pre-commit; tests replace it)."""
    process = subprocess.run(
        [str(binary), "install"], cwd=git_root, capture_output=True, text=True, check=False, timeout=_PRE_COMMIT_TIMEOUT_SECONDS
    )
    return process.returncode, " ".join((process.stdout + process.stderr).split())


def _install_git_hook(ctx: InstallContext) -> list[Finding]:
    """``<venv>/bin/pre-commit install`` when pre-commit is in the venv; a failure is a W931 finding, not an exception."""
    binary = ctx.venv_bin / "pre-commit"
    if ctx.dry_run or not binary.is_file():
        return []
    try:
        code, output = _run_pre_commit_install(binary, ctx.git_root)
    except (OSError, subprocess.SubprocessError) as exc:
        code, output = 1, str(exc)
    if code == 0:
        return []
    return [Finding(W_INSTALL_REFUSED, PRE_COMMIT_FILE, text=f"'pre-commit install' failed: {output or f'exit {code}'}; run '{binary} install' by hand")]


def install_pre_commit(ctx: InstallContext) -> PieceResult:
    """Put the toolkit's hooks into the host's ``.pre-commit-config.yaml`` and install the git hook.

    No file: it is written from the template, the hooks between markers.  A file with the markers: the lines between
    them are replaced.  A file whose hooks were written by hand: they are left alone and a W930 finding per differing
    or missing hook gives the exact lines, until ``--adopt`` replaces them by one marked block at the first of them.  A
    file with no toolkit hook: the block is added after its last local hook.  Lines outside the block are never touched.
    """
    path = ctx.git_root / PRE_COMMIT_FILE
    try:
        existing = path.read_bytes().decode("utf-8") if path.is_file() else None
        template = _read_template(ctx)
        new_text, findings, detail = _plan_pre_commit(ctx, template, existing)
    except (HostInstallError, UnicodeDecodeError, OSError) as exc:
        return refused(str(exc), file=PRE_COMMIT_FILE)
    status = write_if_changed(path, new_text, dry_run=ctx.dry_run)
    if findings:
        status = DRIFT
    elif status == CURRENT:
        detail = "up to date"
    return PieceResult(status, detail, (*findings, *_install_git_hook(ctx)))


# --------------------------------------------------------------------------------------------------------------------
# Piece "merge-driver": the git merge driver of ``spec/extras/trace.lock.json`` (``trace.merge_driver.install_driver``).
# --------------------------------------------------------------------------------------------------------------------

MERGE_DRIVER_PIECE = "merge-driver"


def _git_path(ctx: InstallContext, name: str) -> Path:
    """The file git keeps for *name* (``info/attributes``, ``config``) in the clone that holds the host: worktree-safe."""
    process = run_git(str(ctx.git_root), ["rev-parse", "--git-path", name])
    if process.returncode != 0:
        raise HostInstallError(f"git rev-parse --git-path {name} failed in {ctx.git_root}")
    return ctx.git_root / process.stdout.decode("utf-8", errors="replace").strip()


def _unquote_config_value(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] == '"':
        value = re.sub(r"\\(.)", r"\1", value[1:-1])
    return value


def _driver_command_in_config(ctx: InstallContext, key: str) -> str | None:
    """The value of ``merge.<driver>.<key>`` in the clone's config.

    A real run asks ``git config --local --get``; a dry run runs no ``git config``, so it reads the config file text.
    """
    if not ctx.dry_run:
        process = run_git(str(ctx.git_root), ["config", "--local", "--get", f"merge.{DRIVER_NAME}.{key}"])
        return process.stdout.decode("utf-8", errors="replace").strip() if process.returncode == 0 else None
    config = _git_path(ctx, "config")
    if not config.is_file():
        return None
    in_section = False
    for line in config.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            in_section = stripped.replace(" ", "").lower() == f'[merge"{DRIVER_NAME}"]'
        elif in_section and stripped.startswith(f"{key}") and "=" in stripped:
            return _unquote_config_value(stripped.split("=", 1)[1])
    return None


def install_merge_driver(ctx: InstallContext) -> PieceResult:
    """Install the lock merge driver in the host's clone: its git config and one line of ``info/attributes``.

    The work is ``trace.merge_driver.install_driver``; this piece supplies the driver command (the quoted
    ``specdev`` of the venv that runs the command, and ``lock merge``) and says whether anything changed.  The
    config and the attributes file are local to the clone and not committed, so every clone runs ``update`` once.
    """
    command = f"{shlex.quote(str(ctx.venv_bin / 'specdev'))} lock merge"
    try:
        attributes = _git_path(ctx, ATTRIBUTES_GIT_PATH)
        line = attribute_line(ctx.spec_rel)
        has_line = attributes.is_file() and line in attributes.read_text(encoding="utf-8", errors="replace").splitlines()
        configured = _driver_command_in_config(ctx, "driver")
        if has_line and configured == f"{command} {DRIVER_ARGUMENTS}":
            return PieceResult(CURRENT, "up to date")
        if ctx.dry_run:
            return PieceResult(WOULD_INSTALL, f"would set merge.{DRIVER_NAME} and add the line '{line}' to {attributes.name}")
        install_driver(str(ctx.git_root), ctx.spec_rel, command)
    except LockMergeError as exc:
        return refused(exc.error.message)
    except HostInstallError as exc:
        return refused(str(exc))
    return PieceResult(REFRESHED if has_line or configured is not None else CREATED, f"merge driver '{DRIVER_NAME}' set in the clone's git config")


# --------------------------------------------------------------------------------------------------------------------
# Piece "workflows": ``.github/workflows/specdev-merge-check.yml`` and the scan of the host's own files for retired
# commands.
#
# Only the merge-check workflow is installed; the three snippets of ``templates/workflows/`` are copied by a person.  The
# file carries the managed header, so a refresh rewrites it, and a host file of the same name without the header is
# drift and is never overwritten (``--adopt`` covers hooks and wrappers, not workflows).  The scan reads every other
# workflow and the host's pre-commit config and only reports.
# --------------------------------------------------------------------------------------------------------------------

WORKFLOWS_PIECE = "workflows"
WORKFLOWS_DIR = ".github/workflows"
MERGE_CHECK_FILE = "specdev-merge-check.yml"
MERGE_CHECK_PIECE = "merge-check"
SETUP_BEGIN = "# specdev:setup-begin"
SETUP_END = "# specdev:setup-end"
_PLACEHOLDER_VERSION = "__SPECDEV_TOOLKIT_VERSION__"
_PLACEHOLDER_SETUP = "__SPECDEV_SETUP_COMMAND__"
_PLACEHOLDER = re.compile(r"__SPECDEV_[A-Z_]+__")
_TEMPLATE_SPEC = "spec"
_DIFF_LINE_LIMIT = 40


def _without_placeholder_notes(lines: list[str]) -> list[str]:
    """*lines* without the template author's note on the placeholders: the ``# Placeholders`` comment line and the
    indented comment lines that follow it (they name the placeholders, which a rendered file must not hold)."""
    kept: list[str] = []
    inside = False
    for line in lines:
        if line.startswith("# Placeholders"):
            inside = True
        elif inside and line.startswith("#  "):
            pass
        else:
            inside = False
            kept.append(line)
    return kept


def render_merge_check_workflow(
    template: str, *, toolkit_version: str, toolkit_rel: str, venv_name: str, spec_rel: str, setup_command: str | None
) -> str:
    """The merge-check template with the host's names put in.

    The setup block (the marker lines and what lies between them, twice) is removed when *setup_command* is ``None``;
    else its placeholder is replaced by the command, one line per line, at the placeholder's indentation.  The literal
    toolkit folder, venv folder and spec folder of the template are replaced when the host's differ.

    Raises:
        HostInstallError: the setup markers are not paired, or a placeholder is left over.
    """
    lines = _without_placeholder_notes(template.splitlines(keepends=True))
    if setup_command is None:
        kept: list[str] = []
        inside = False
        for line in lines:
            mark = line.strip()
            if mark == SETUP_BEGIN:
                inside = True
            elif mark == SETUP_END:
                if not inside:
                    raise HostInstallError(f"the workflow template has '{SETUP_END}' without '{SETUP_BEGIN}'")
                inside = False
            elif not inside:
                kept.append(line)
        if inside:
            raise HostInstallError(f"the workflow template has '{SETUP_BEGIN}' without '{SETUP_END}'")
        text = "".join(kept)
    else:
        text = "".join(lines)
    if spec_rel != _TEMPLATE_SPEC:
        for pattern in (r"\./spec(?![\w/-])", r"(?<=spec-check )spec(?![\w/-])", r"(?<=governance-check )spec(?![\w/-])", r"spec(?=/extras/verification)"):
            text = re.sub(pattern, lambda _m: f"./{spec_rel}" if _m[0].startswith("./") else spec_rel, text)
    text = text.replace(_TEMPLATE_TOOLKIT, toolkit_rel).replace(DEFAULT_VENV_NAME, venv_name)
    text = text.replace(_PLACEHOLDER_VERSION, toolkit_version)
    if setup_command is not None:
        command_lines = setup_command.strip("\n").splitlines()
        out: list[str] = []
        for line in text.splitlines(keepends=True):
            if _PLACEHOLDER_SETUP in line:
                indent = line[: len(line) - len(line.lstrip())]
                out.extend(f"{indent}{part}\n" if part.strip() else "\n" for part in command_lines)
            else:
                out.append(line)
        text = "".join(out)
    left = _PLACEHOLDER.search(text)
    if left is not None:
        raise HostInstallError(f"the workflow template keeps the placeholder {left[0]}")
    return text


_VALIDATE_ALL = "validate-all"
_VALIDATE_ALL_REPLACEMENT = "superseded by `specdev spec-check` (run it with --merge on a pull request)"
_TRACE_MATRIX_FILE = "trace_matrix.json"
_TRACE_MATRIX_REPLACEMENT = "no longer produced; use `specdev coverage --by fr` for the FR view and `specdev trace --up|--down <id>` for lineage"
_INVOCATION = r"(?:\bspecdev|specdev_tools\.cli|run_specdev\.sh)"


def _scan_lines(text: str, *, skip_block: bool) -> list[tuple[int, str]]:
    """``(1-based line number, line)`` of the lines a host owns: not a comment line, not inside the toolkit's marked block."""
    kept: list[tuple[int, str]] = []
    inside = False
    for number, line in enumerate(text.splitlines(), start=1):
        mark = line.strip()
        if skip_block and mark.startswith(MARKER_BEGIN):
            inside = True
        elif skip_block and mark.startswith(MARKER_END):
            inside = False
        elif not inside and mark and not mark.startswith("#"):
            kept.append((number, line))
    return kept


def retired_command_findings(host_root: Path, *, removed_commands: dict[str, str] | None = None) -> list[Finding]:
    """W932 findings for the host's own files that still call a command 1.2.0 retired (ruling N9).

    Read: every ``.github/workflows/*.yml`` and ``*.yaml`` whose first line is not the toolkit's header, and
    ``.pre-commit-config.yaml`` outside the marked block.  A finding is made for the four commands of
    ``core.constants.REMOVED_COMMANDS`` and for ``validate-all`` when they stand as the command after ``specdev``,
    ``specdev_tools.cli`` or ``run_specdev.sh`` (so a ``matrix:`` job strategy is not one), and for any mention of
    ``trace_matrix.json``; a comment line is not read.  ``dag-lint`` is not a retired command.  Nothing is rewritten.
    *removed_commands* replaces the table ``core.constants.REMOVED_COMMANDS``.
    """
    table = REMOVED_COMMANDS if removed_commands is None else removed_commands
    replacements = {**table, _VALIDATE_ALL: _VALIDATE_ALL_REPLACEMENT}
    patterns = {name: re.compile(rf"{_INVOCATION}\s+{re.escape(name)}(?![\w-])") for name in replacements}
    workflows = host_root / WORKFLOWS_DIR
    files = sorted(p for pattern in ("*.yml", "*.yaml") for p in workflows.glob(pattern)) if workflows.is_dir() else []
    files.append(host_root / PRE_COMMIT_FILE)
    findings: list[Finding] = []
    for path in files:
        try:
            text = path.read_text(encoding="utf-8") if path.is_file() else ""
        except (OSError, UnicodeDecodeError):
            continue
        if not text or (path.parent == workflows and read_managed_header(text) is not None):
            continue
        rel = path.relative_to(host_root).as_posix()
        for number, line in _scan_lines(text, skip_block=path.name == PRE_COMMIT_FILE):
            for name, pattern in patterns.items():
                if pattern.search(line):
                    findings.append(Finding(W_RETIRED_COMMAND, rel, number, name, f"'{name}' was removed in 1.2.0; {replacements[name]}"))
            if _TRACE_MATRIX_FILE in line:
                findings.append(Finding(W_RETIRED_COMMAND, rel, number, _TRACE_MATRIX_FILE, f"'{_TRACE_MATRIX_FILE}' is {_TRACE_MATRIX_REPLACEMENT}"))
    return findings


def _workflow_result(ctx: InstallContext) -> PieceResult:
    """The merge-check workflow alone (no scan): written, refreshed, current, drift (a host file of that name) or refused."""
    rel = f"{WORKFLOWS_DIR}/{MERGE_CHECK_FILE}"
    target = ctx.git_root / rel
    template_path = ctx.templates_dir / "workflows" / MERGE_CHECK_FILE
    try:
        existing = target.read_bytes().decode("utf-8") if target.is_file() else None
        header = None if existing is None else read_managed_header(existing)
        if existing is not None and (header is None or header[0] != MERGE_CHECK_PIECE):
            note = (
                f"{rel} is not the toolkit's (its first line is not '{managed_header(MERGE_CHECK_PIECE, ctx.toolkit_version)}'), "
                "so the merge-check workflow is not installed; move your file aside and run 'specdev update' again "
                "(--adopt does not touch workflows)"
            )
            return PieceResult(DRIFT, "a host file of that name is left as it is", (Finding(W_TEMPLATE_DRIFT, rel, 1, "", note),))
        if not template_path.is_file():
            raise HostInstallError(f"the workflow template {template_path.name} was not found in {template_path.parent}")
        declarations = load_host_declarations(ctx.spec_dir)
    except (HostInstallError, HostDeclarationsError, UnicodeDecodeError, OSError) as exc:
        return refused(str(exc), file=rel)
    text = render_merge_check_workflow(
        template_path.read_text(encoding="utf-8"),
        toolkit_version=ctx.toolkit_version,
        toolkit_rel=ctx.toolkit_rel,
        venv_name=ctx.venv_name,
        spec_rel=ctx.spec_rel,
        setup_command=declarations.setup_command if declarations.setup_command and declarations.setup_command.strip() else None,
    )
    findings: tuple[Finding, ...] = ()
    if declarations.setup_command is None or not declarations.setup_command.strip():
        where = f"{ctx.spec_rel}/{HOST_DECLARATIONS_FILE}"
        note = f"no setup_command is declared, so the workflow runs without a host setup step; declare 'setup_command' in {where} to add one"
        findings = (Finding(W_SETUP_UNDECLARED, where, text=note),)
    status = write_if_changed(target, text, dry_run=ctx.dry_run)
    detail = {CURRENT: "up to date", CREATED: "written from the template", REFRESHED: "rewritten from the template"}.get(
        status, f"would write {rel}"
    )
    return PieceResult(status, detail, findings)


def install_workflows(ctx: InstallContext) -> PieceResult:
    """Install the merge-check workflow and report the host's own files that call retired commands.

    The scan's W932 findings ride on the result of the workflow and never change its status.
    """
    own = _workflow_result(ctx)
    return PieceResult(own.status, own.detail, (*own.findings, *retired_command_findings(ctx.git_root)))


# --------------------------------------------------------------------------------------------------------------------
# Piece "wrappers": ``tools/run_specdev.sh`` and ``tools/ensure_venv.py``, rendered with the venv name (ruling N10).
#
# A wrapper has no header (the first line of a script is its shebang): the file is the toolkit's when it equals the
# rendered template, or the unrendered template that ``init`` copies before the venv name is known.  Any other content
# is the host's: drift (W930) until ``--adopt``.
# --------------------------------------------------------------------------------------------------------------------

WRAPPERS_PIECE = "wrappers"
WRAPPERS_TEMPLATE_DIR = ("scripts", "templates")
WRAPPERS: tuple[tuple[str, int | None], ...] = (("run_specdev.sh", 0o755), ("ensure_venv.py", None))
WRAPPERS_TARGET_DIR = "tools"


def render_wrapper(template: str, *, toolkit_rel: str, venv_name: str) -> str:
    """A wrapper template with the host's toolkit folder and venv name put in (plain text replacement)."""
    return template.replace(_TEMPLATE_TOOLKIT, toolkit_rel).replace(DEFAULT_VENV_NAME, venv_name)


def _wrapper_diff(existing: str, rendered: str) -> str:
    diff = list(difflib.unified_diff(existing.splitlines(), rendered.splitlines(), "the host's file", "the toolkit's wrapper", lineterm="", n=1))
    if len(diff) > _DIFF_LINE_LIMIT:
        diff = [*diff[:_DIFF_LINE_LIMIT], "..."]
    return "\n".join(diff)


def _install_one_wrapper(ctx: InstallContext, name: str, mode: int | None) -> PieceResult:
    rel = f"{WRAPPERS_TARGET_DIR}/{name}"
    target = ctx.git_root / rel
    source = ctx.toolkit_root.joinpath(*WRAPPERS_TEMPLATE_DIR, name)
    try:
        if not source.is_file():
            raise HostInstallError(f"the wrapper template {name} was not found in {source.parent}")
        template = source.read_text(encoding="utf-8")
        existing = target.read_bytes().decode("utf-8") if target.is_file() else None
    except (HostInstallError, UnicodeDecodeError, OSError) as exc:
        return refused(str(exc), file=rel)
    rendered = render_wrapper(template, toolkit_rel=ctx.toolkit_rel, venv_name=ctx.venv_name)
    if existing is not None and existing not in (rendered, template) and not ctx.adopt:
        note = (
            f"{rel} differs from the toolkit's wrapper; 'specdev update --adopt' rewrites it, or replace it by hand "
            f"with {ctx.toolkit_rel}/{'/'.join(WRAPPERS_TEMPLATE_DIR)}/{name} (venv folder '{ctx.venv_name}'):\n{_wrapper_diff(existing, rendered)}"
        )
        return PieceResult(DRIFT, "a host-edited file is left as it is", (Finding(W_TEMPLATE_DRIFT, rel, 1, "", note),))
    status = write_if_changed(target, rendered, dry_run=ctx.dry_run)
    if status in (CREATED, REFRESHED) and mode is not None:
        target.chmod(mode)
    return PieceResult(status, {CURRENT: "up to date", CREATED: "written", REFRESHED: "rewritten"}.get(status, f"would write {rel}"))


def install_wrappers(ctx: InstallContext) -> PieceResult:
    """Render the two wrappers of ``tools/`` with the venv name of the run; a host-edited wrapper is drift until ``--adopt``."""
    results = [(name, _install_one_wrapper(ctx, name, mode)) for name, mode in WRAPPERS]
    statuses = [result.status for _, result in results]
    status = next((s for s in (REFUSED, DRIFT, WOULD_INSTALL, REFRESHED, CREATED) if s in statuses), CURRENT)
    detail = "up to date" if status == CURRENT else "; ".join(f"{WRAPPERS_TARGET_DIR}/{name}: {result.status}" for name, result in results)
    return PieceResult(status, detail, tuple(f for _, result in results for f in result.findings))


# --------------------------------------------------------------------------------------------------------------------
# Piece "claude-links": the symlinks of the host's ``.claude/skills`` and ``.claude/agents`` into the toolkit.
#
# Symlinks, not copies, so the toolkit stays the one source of the skills and a submodule bump reaches the host.  A link
# that already points at the toolkit is current; a stale one (it points elsewhere or is broken) is replaced only with
# ``--force-claude`` (ruling N8) and is drift otherwise; a real file or folder at the name is never replaced.
# --------------------------------------------------------------------------------------------------------------------

CLAUDE_LINKS_PIECE = "claude-links"
CLAUDE_DIR = ".claude"
KNOWN_SKILLS = frozenset({"specdev-context", "specdev-step", "specdev-review", "specdev-trinity", "devspec_pr_audit"})
"""The skills of the toolkit that a host gets.  A new toolkit skill that hosts should have is one more name here."""
KNOWN_AGENT_PREFIXES = ("specdev-", "pr-audit-")
"""The name prefixes of the toolkit's agent files that a host gets."""

_LINK_CREATED = "created"
_LINK_REFRESHED = "refreshed"
_LINK_IN_SYNC = "in_sync"
_LINK_STALE = "stale"
_LINK_REAL = "real"
_LINK_ERROR = "error"
_LINK_WOULD_CREATE = "would_create"
_LINK_WOULD_REFRESH = "would_refresh"


def _install_one_symlink(dst: Path, rel_target: str, *, force: bool, dry_run: bool) -> tuple[str, str]:
    """Make *dst* a symlink to *rel_target*; ``(outcome, note)`` where the outcome is one of the ``_LINK_*`` names.

    Nothing is printed.  A link that points elsewhere is replaced only with *force*; a real file or folder is never
    replaced; with *dry_run* nothing is written and a link that would be made says ``would_create`` / ``would_refresh``.
    """
    if os.path.lexists(dst):
        if not dst.is_symlink():
            return _LINK_REAL, "is a real file or folder, not a link into the toolkit"
        existing = os.readlink(dst)
        if existing == rel_target:
            return _LINK_IN_SYNC, ""
        if not force:
            return _LINK_STALE, f"points to '{existing}' (expected '{rel_target}')"
        if dry_run:
            return _LINK_WOULD_REFRESH, ""
        try:
            dst.unlink()
            dst.symlink_to(rel_target)
        except OSError as exc:
            return _LINK_ERROR, f"could not replace the link: {exc}"
        return _LINK_REFRESHED, ""
    if dry_run:
        return _LINK_WOULD_CREATE, ""
    try:
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.symlink_to(rel_target)
    except OSError as exc:
        return _LINK_ERROR, f"could not create the link: {exc}"
    return _LINK_CREATED, ""


def _link_candidates(ctx: InstallContext) -> tuple[list[tuple[str, str]], list[str]]:
    """``([(kind, name)...], [names the allowlists leave out])``: what the toolkit offers, skills first."""
    offered: list[tuple[str, str]] = []
    unlisted: list[str] = []
    skills = ctx.toolkit_root / CLAUDE_DIR / "skills"
    if skills.is_dir():
        for entry in sorted(skills.iterdir()):
            if entry.name.startswith(".") or not entry.is_dir():
                continue
            if entry.name in KNOWN_SKILLS:
                offered.append(("skills", entry.name))
            else:
                unlisted.append(entry.name)
    agents = ctx.toolkit_root / CLAUDE_DIR / "agents"
    if agents.is_dir():
        for entry in sorted(agents.iterdir()):
            if entry.name.startswith(".") or entry.suffix != ".md" or not entry.is_file():
                continue
            if entry.name.startswith(KNOWN_AGENT_PREFIXES):
                offered.append(("agents", entry.name))
            else:
                unlisted.append(entry.name)
    return offered, unlisted


def install_claude_links(ctx: InstallContext) -> PieceResult:
    """Link the toolkit's skills and agents into the host's ``.claude`` folder (relative links through ``toolkit_rel``).

    ``--force-claude`` (``ctx.force_claude``) replaces a stale link; a real file or folder is never replaced.  A stale
    link without the flag and a real file are drift (W930); a link that cannot be made is a refusal (W931).
    """
    offered, unlisted = _link_candidates(ctx)
    counts: dict[str, int] = {}
    findings: list[Finding] = []
    for kind, name in offered:
        rel = f"{CLAUDE_DIR}/{kind}/{name}"
        target = posixpath.relpath(posixpath.join("/host", ctx.toolkit_rel, CLAUDE_DIR, kind, name), posixpath.join("/host", CLAUDE_DIR, kind))
        outcome, note = _install_one_symlink(ctx.git_root / rel, target, force=ctx.force_claude, dry_run=ctx.dry_run)
        counts[outcome] = counts.get(outcome, 0) + 1
        if outcome == _LINK_STALE:
            findings.append(Finding(W_TEMPLATE_DRIFT, rel, None, "", f"{note}; 'specdev update --force-claude' replaces it"))
        elif outcome == _LINK_REAL:
            findings.append(Finding(W_TEMPLATE_DRIFT, rel, None, "", f"{note}, so it is left as it is; move it aside and run 'specdev update' to link the toolkit's"))
        elif outcome == _LINK_ERROR:
            findings.append(Finding(W_INSTALL_REFUSED, rel, None, "", note))
    if counts.get(_LINK_ERROR):
        status = REFUSED
    elif counts.get(_LINK_STALE) or counts.get(_LINK_REAL):
        status = DRIFT
    elif counts.get(_LINK_WOULD_CREATE) or counts.get(_LINK_WOULD_REFRESH):
        status = WOULD_INSTALL
    elif counts.get(_LINK_REFRESHED):
        status = REFRESHED
    elif counts.get(_LINK_CREATED):
        status = CREATED
    else:
        status = CURRENT
    parts = [f"{counts[name]} {label}" for name, label in _LINK_LABELS if counts.get(name)]
    detail = ", ".join(parts) if parts else "nothing to link"
    if status == CURRENT and offered:
        detail = "up to date"
    if unlisted:
        detail += f"; not linked (not in the allowlist): {', '.join(unlisted)}"
    return PieceResult(status, detail, tuple(findings))


_LINK_LABELS = (
    (_LINK_CREATED, "linked"),
    (_LINK_WOULD_CREATE, "to link"),
    (_LINK_REFRESHED, "replaced"),
    (_LINK_WOULD_REFRESH, "to replace"),
    (_LINK_IN_SYNC, "already in place"),
    (_LINK_STALE, "stale (left)"),
    (_LINK_REAL, "real file or folder (left)"),
    (_LINK_ERROR, "failed"),
)


# --------------------------------------------------------------------------------------------------------------------
# Piece "ask-rules": the Claude Code ask rules of the commands a person decides, in the host's local settings.
#
# ``.claude/settings.local.json`` is per clone and not committed.  The piece only ever APPENDS missing entries to
# ``permissions.ask``: every other key, every ``allow`` and ``deny`` entry and their order stay, it never adds an
# ``allow``, removes a ``deny`` or touches ``settings.json``.  A rule an earlier toolkit installed and this one no longer
# lists is left in place.  The file is written with 2-space indentation and a final newline, and only when a rule is
# missing.
# --------------------------------------------------------------------------------------------------------------------

ASK_RULES_PIECE = "ask-rules"
SETTINGS_LOCAL = ".claude/settings.local.json"
ASK_LAUNCH_FORMS = ("specdev", "./tools/run_specdev.sh")
"""How a host starts the CLI.  ``python -m specdev_tools.cli`` and a venv path are not listed; a form is one more row here."""
ASK_COMMAND_PATTERNS = ("milestone sign-off *", "milestone defer *", "release", "release -*", "verify attest *")
"""The commands a person decides: sign-off, defer, the release cut (bare and with options) and ``verify attest``.  ``release
check``, ``release prep`` and ``release rollback`` do not ask (rollback is a plain record command)."""


def ask_rules_for() -> list[str]:
    """The Claude Code ``ask`` rules a host gets: every command pattern in every launch form, in a fixed order."""
    return [f"Bash({form} {pattern})" for form in ASK_LAUNCH_FORMS for pattern in ASK_COMMAND_PATTERNS]


def _ask_fragment(rules: list[str]) -> str:
    return json.dumps({"permissions": {"ask": rules}}, ensure_ascii=False)


def _read_settings(path: Path) -> dict | None:
    """The settings object of *path*, ``None`` when the file is absent.

    Raises:
        HostInstallError: the file cannot be read, is not JSON, or its ``permissions.ask`` is not what Claude Code reads.
    """
    if not path.exists():
        return None
    if not path.is_file():
        raise HostInstallError(f"{SETTINGS_LOCAL} is not a file")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError) as exc:
        raise HostInstallError(f"{SETTINGS_LOCAL} cannot be read ({exc})") from exc
    except json.JSONDecodeError as exc:
        raise HostInstallError(f"{SETTINGS_LOCAL} is not valid JSON ({exc.msg}, line {exc.lineno})") from exc
    if not isinstance(data, dict):
        raise HostInstallError(f"{SETTINGS_LOCAL} is not a JSON object")
    permissions = data.get("permissions", {})
    if not isinstance(permissions, dict):
        raise HostInstallError(f"'permissions' in {SETTINGS_LOCAL} is not an object")
    if not isinstance(permissions.get("ask", []), list):
        raise HostInstallError(f"'permissions.ask' in {SETTINGS_LOCAL} is not a list")
    return data


def _settings_ignored(ctx: InstallContext) -> bool:
    """Whether git already ignores the settings file (by a ``.gitignore``, the clone's exclude file or a global ignore)."""
    process = run_git(str(ctx.git_root), ["check-ignore", "-q", "--no-index", SETTINGS_LOCAL])
    if process.returncode not in (0, 1):
        raise HostInstallError(f"git check-ignore failed in {ctx.git_root}")
    return process.returncode == 0


def _append_line(path: Path, line: str) -> bool:
    """Append *line* to *path* (created when absent) unless a line of it already is *line*; ``True`` when it wrote."""
    existing = path.read_bytes().decode("utf-8", errors="replace") if path.is_file() else ""
    if line in existing.splitlines():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    separator = "" if not existing or existing.endswith("\n") else "\n"
    with path.open("ab") as handle:
        handle.write(f"{separator}{line}\n".encode())
    return True


def install_ask_rules(ctx: InstallContext) -> PieceResult:
    """Add the missing ask rules of :func:`ask_rules_for` to the host's ``.claude/settings.local.json``.

    The file is kept out of version control first (a line in the clone's ``info/exclude`` when no ignore rule covers
    it), then written.  An unreadable or malformed file is refused (W931) and left as it is, with the fragment to merge
    by hand; a write that the system refuses is W931 with the command the person runs themselves.
    """
    rules = ask_rules_for()
    path = ctx.git_root / SETTINGS_LOCAL
    fragment = _ask_fragment(rules)
    try:
        data = _read_settings(path)
        asked = [] if data is None else list(data.get("permissions", {}).get("ask", []))
        missing = [rule for rule in rules if rule not in asked]
        needs_exclude = not _settings_ignored(ctx)  # a read-only question: a dry run asks it as the real run does
    except HostInstallError as exc:
        return refused(f"{exc}; merge this by hand: {fragment}", file=SETTINGS_LOCAL)
    if not missing and not needs_exclude:
        return PieceResult(CURRENT, "up to date")
    if ctx.dry_run:
        would = ([f"would add {len(missing)} ask rule(s) to {SETTINGS_LOCAL}"] if missing else []) + ([f"would exclude {SETTINGS_LOCAL} from git"] if needs_exclude else [])
        return PieceResult(WOULD_INSTALL, "; ".join(would))
    try:
        if needs_exclude:
            _append_line(_git_path(ctx, "info/exclude"), SETTINGS_LOCAL)
        if missing:
            document = {"permissions": {"ask": list(missing)}} if data is None else data
            if data is not None:
                document.setdefault("permissions", {}).setdefault("ask", []).extend(missing)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    except OSError as exc:
        again = f"! ./tools/run_specdev.sh update {ctx.spec_rel} --repo-root {ctx.toolkit_rel} --install-only"
        return refused(f"cannot write {SETTINGS_LOCAL} ({exc.strerror or exc}); run this yourself: {again} (or merge this by hand: {fragment})", file=SETTINGS_LOCAL)
    except HostInstallError as exc:
        return refused(f"{exc}; merge this by hand: {fragment}", file=SETTINGS_LOCAL)
    detail = f"{len(missing)} ask rule(s) added to {SETTINGS_LOCAL}" if missing else f"{SETTINGS_LOCAL} excluded from git"
    return PieceResult(CREATED if data is None and missing else REFRESHED, detail)


# --------------------------------------------------------------------------------------------------------------------
# Piece "gitignore": the ``.specdev/`` line.  The findings and drafts agents write there are untracked files; unless
# they are ignored they are part of the code tree and a findings file written after ``verify run`` makes the evidence
# stale.
# --------------------------------------------------------------------------------------------------------------------

GITIGNORE_PIECE = "gitignore"
GITIGNORE_FILE = ".gitignore"
SPECDEV_IGNORE = ".specdev/"


def _names_specdev_folder(line: str) -> bool:
    return line.strip().removeprefix("/").removesuffix("/") == SPECDEV_IGNORE.removesuffix("/")


def install_gitignore(ctx: InstallContext) -> PieceResult:
    """Add ``.specdev/`` to the host's ``.gitignore`` unless a line of it already names the folder.

    The other lines and their order stay byte for byte; a missing file is created with the one line; the entry starts
    on a new line and uses the file's own line ending.
    """
    path = ctx.git_root / GITIGNORE_FILE
    existed = path.is_file()
    try:
        text = path.read_bytes().decode("utf-8") if existed else ""
    except (OSError, UnicodeDecodeError) as exc:
        return refused(f"{GITIGNORE_FILE} cannot be read ({exc})", file=GITIGNORE_FILE)
    if any(_names_specdev_folder(line) for line in text.splitlines()):
        return PieceResult(CURRENT, "up to date")
    if ctx.dry_run:
        return PieceResult(WOULD_INSTALL, f"would add '{SPECDEV_IGNORE}' to {GITIGNORE_FILE}")
    newline = "\r\n" if "\r\n" in text else "\n"
    lead = "" if not text or text.endswith("\n") else newline
    try:
        path.write_bytes(f"{text}{lead}{SPECDEV_IGNORE}{newline}".encode())
    except OSError as exc:
        return refused(f"{GITIGNORE_FILE} cannot be written ({exc.strerror or exc})", file=GITIGNORE_FILE)
    return PieceResult(REFRESHED if existed else CREATED, f"'{SPECDEV_IGNORE}' added to {GITIGNORE_FILE}")


PIECES: tuple[HostPiece, ...] = (
    HostPiece(PRE_COMMIT_PIECE, install_pre_commit),
    HostPiece(MERGE_DRIVER_PIECE, install_merge_driver),
    HostPiece(WORKFLOWS_PIECE, install_workflows),
    HostPiece(WRAPPERS_PIECE, install_wrappers),
    HostPiece(CLAUDE_LINKS_PIECE, install_claude_links),
    HostPiece(ASK_RULES_PIECE, install_ask_rules),
    HostPiece(GITIGNORE_PIECE, install_gitignore),
)
"""The registry of pieces, in install order.  A new piece adds a function and one ``HostPiece(name, function)`` line."""
