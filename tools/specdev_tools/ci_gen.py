from __future__ import annotations
import yaml
import shlex


def generate_ci_yaml(spec_dir: str, repo_root: str, toolkit_path: str) -> str:
    """Return a GitHub Actions workflow that validates specs and scaffolds code."""

    requirements_path = shlex.quote(f"{toolkit_path}/tools/requirements.txt")
    pythonpath_value = shlex.quote(f"{toolkit_path}/tools")
    spec_dir_arg = shlex.quote(spec_dir)
    repo_root_arg = shlex.quote(repo_root)
    install_cmd = f"pip install -r {requirements_path}"
    export_pythonpath = f"export PYTHONPATH={pythonpath_value}"

    validate_cmd = (
        f"{export_pythonpath} && "
        f"python -m specdev_tools.cli validate-all {spec_dir_arg} --repo-root {repo_root_arg}"
    )
    scaffold_cmd = (
        f"{export_pythonpath} && "
        f"python -m specdev_tools.cli scaffold {spec_dir_arg} --repo-root {repo_root_arg} --out scaffold_out"
    )

    return yaml.safe_dump({
        "name": "AI Spec Driven Development CI",
        "on": ["push", "pull_request"],
        "jobs": {
            "validate": {
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {"uses": "actions/setup-python@v5", "with": {"python-version": "3.x"}},
                    {"name": "Install", "run": install_cmd},
                    {"name": "Validate specs", "run": validate_cmd},
                ],
            },
            "scaffold": {
                "needs": ["validate"],
                "runs-on": "ubuntu-latest",
                "steps": [
                    {"uses": "actions/checkout@v4"},
                    {"uses": "actions/setup-python@v5", "with": {"python-version": "3.x"}},
                    {"name": "Install", "run": install_cmd},
                    {"name": "Scaffold", "run": scaffold_cmd},
                ],
            },
        },
    }, sort_keys=False)
