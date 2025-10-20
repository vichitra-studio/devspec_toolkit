from __future__ import annotations
import yaml


def generate_ci_yaml(toolkit_path: str) -> str:
    """Return a GitHub Actions workflow that validates specs and scaffolds code."""

    install_cmd = f"pip install -r \"{toolkit_path}/tools/requirements.txt\""
    export_pythonpath = f"export PYTHONPATH=\"{toolkit_path}/tools\""

    validate_cmd = (
        f"{export_pythonpath} && "
        f"python -m specdev_tools.cli validate-all spec --repo-root \"{toolkit_path}\""
    )
    scaffold_cmd = (
        f"{export_pythonpath} && "
        f"python -m specdev_tools.cli scaffold spec --repo-root \"{toolkit_path}\" --out scaffold_out"
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
