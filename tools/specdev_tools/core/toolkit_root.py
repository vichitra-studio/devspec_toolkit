"""Find the toolkit root of a submodule deployment from the current directory."""
from __future__ import annotations

from pathlib import Path

DEFAULT_REPO_ROOT = "."
_TOOLKIT_MARKER = Path("tools") / "specdev_tools" / "__init__.py"


def detect_toolkit_root(repo_root: str, cwd: str | Path = ".") -> str:
    """The toolkit root a command should use for the ``--repo-root`` value *repo_root*.

    Only the default value ``"."`` is looked up: the first immediate subdirectory of *cwd* that holds the toolkit's
    package (``tools/specdev_tools/__init__.py``) is returned as a path (a host repo that vendors the toolkit as a
    submodule).  Any other value, and ``"."`` when no subdirectory holds the package, is returned unchanged.
    """
    if repo_root != DEFAULT_REPO_ROOT:
        return repo_root
    for child in Path(cwd).iterdir():
        if child.is_dir() and (child / _TOOLKIT_MARKER).exists():
            return str(child)
    return repo_root
