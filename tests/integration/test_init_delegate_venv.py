"""The command `init` runs to install the host files, run for real in a real venv (WI-M9-11a).

The venv is created by the standard library without pip and borrows the packages of the interpreter that runs the
test through a ``.pth`` file, so nothing is downloaded; its ``bin/specdev`` is the console-script shim the package
install would write.  The command under test is the one `init_project` builds.
"""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
import sysconfig
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import init_project  # noqa: E402


def _make_venv(host: Path, name: str) -> Path:
    venv = host / name
    subprocess.run([sys.executable, "-m", "venv", "--without-pip", str(venv)], check=True)
    site_packages = next((venv / "lib").glob("python*/site-packages"))
    (site_packages / "borrowed.pth").write_text(f"{sysconfig.get_paths()['purelib']}\n{REPO_ROOT / 'tools'}\n", encoding="utf-8")
    shim = venv / "bin" / "specdev"
    shim.write_text(
        f"#!{venv / 'bin' / 'python'}\nimport sys\nfrom specdev_tools.cli import main\nsys.exit(main())\n", encoding="utf-8"
    )
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR)
    return venv


@pytest.mark.parametrize("venv_name", ["devspec_env", "custom_env"])
def test_init_delegate_command_runs_in_temp_venv(tmp_path, venv_name):
    host = tmp_path / "host"
    (host / "spec").mkdir(parents=True)
    subprocess.run(["git", "init", "-q", str(host)], check=True)
    venv = _make_venv(host, venv_name)
    rel_toolkit = os.path.relpath(REPO_ROOT, host)

    command = init_project.build_install_delegate(str(venv), rel_toolkit, force_claude=True)
    env = {k: v for k, v in os.environ.items() if k not in ("VIRTUAL_ENV", "PYTHONPATH")}
    done = subprocess.run(command, cwd=host, capture_output=True, text=True, env=env, timeout=120)
    assert done.returncode == 0, done.stderr
    assert "Host install" in done.stdout

    as_json = subprocess.run([*command, "--json"], cwd=host, capture_output=True, text=True, env=env, timeout=120)
    assert as_json.returncode == 0, as_json.stderr
    payload = json.loads(as_json.stdout)
    assert payload["update_status"] == "installed"
    assert payload["host_install"] == {"skipped": None, "pieces": {}}
