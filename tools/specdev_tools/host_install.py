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
import sys
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import NamedTuple

from .core.changelog_parser import get_toolkit_version
from .core.errors import ERROR_CODES
from .graph.gitview import GitViewError, git_top_level, spec_path_in_repo

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
        return Path(os.path.relpath(self.toolkit_root, self.git_root)).as_posix()


class HostPiece(NamedTuple):
    """One line of the registry: the piece's name (the JSON key) and the function that installs it."""

    name: str
    install: Callable[[InstallContext], PieceResult]


PIECES: tuple[HostPiece, ...] = ()
"""The registry of pieces, in install order.  A new piece adds a function and one ``HostPiece(name, function)`` line."""


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
