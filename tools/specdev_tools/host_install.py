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

import os
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
from .core.errors import ERROR_CODES
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
        """The warning strings of every finding of every piece, in piece order."""
        return [finding.render() for _, result in self.pieces for finding in result.findings]

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


PIECES: tuple[HostPiece, ...] = (
    HostPiece(PRE_COMMIT_PIECE, install_pre_commit),
    HostPiece(MERGE_DRIVER_PIECE, install_merge_driver),
)
"""The registry of pieces, in install order.  A new piece adds a function and one ``HostPiece(name, function)`` line."""
