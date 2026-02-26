#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Template for pre-commit-config.yaml
PRE_COMMIT_TEMPLATE = """repos:
  - repo: local
    hooks:
      - id: devspec-validate
        name: DevSpec Validate
        entry: ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
        language: system
        types: [json]
        files: ^spec/
        verbose: true
        additional_dependencies: []

      - id: devspec-fixtures
        name: DevSpec Fixtures Lint
        entry: ./tools/run_specdev.sh fixtures-lint spec --repo-root ./devspec_toolkit
        language: system
        types: [json]
        files: ^spec/
        verbose: true
        additional_dependencies: []

#  - id: devspec-governance
#    name: DevSpec Governance Check
#    entry: ./tools/run_specdev.sh governance-check spec --repo-root ./devspec_toolkit --message
#    language: python
#    stages: [commit-msg]
#    # Note: commit-msg hooks require 'pre-commit install --hook-type commit-msg'
"""

CI_WORKFLOW_TEMPLATE = """name: SpecDev CI

on:
  push:
    branches: ["**"]
  pull_request:
  workflow_dispatch:

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

permissions:
  contents: read

jobs:
  validate:
    name: Schema & Spec Validation
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4
        with:
          fetch-depth: 0
          submodules: recursive
      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.x"
          cache: "pip"
      - name: Create virtualenv
        run: python -m venv dev_env
      - name: Install tooling
        run: |
          dev_env/bin/pip install --upgrade pip
          dev_env/bin/pip install -r devspec_toolkit/tools/requirements.txt
          dev_env/bin/pip install -e devspec_toolkit/tools/
      - name: Validate all specs
        run: ./tools/run_specdev.sh validate-all spec --repo-root ./devspec_toolkit
      - name: Governance check (PR Title)
        if: github.event_name == 'pull_request'
        run: ./tools/run_specdev.sh governance-check spec --message "${{ github.event.pull_request.title }}" --repo-root ./devspec_toolkit
      - name: Fixtures lint
        run: ./tools/run_specdev.sh fixtures-lint spec --repo-root ./devspec_toolkit
      - name: Build trace matrix
        run: ./tools/run_specdev.sh matrix spec --out trace_matrix.json --repo-root ./devspec_toolkit
      - name: Upload matrix
        uses: actions/upload-artifact@v4
        with:
          name: trace-matrix
          path: trace_matrix.json
          if-no-files-found: ignore
"""

def run_cmd(cmd, cwd=None, check=True):
    print(f"Running: {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=check)

def get_git_root(path):
    try:
        res = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=path, capture_output=True, text=True, check=True)
        return res.stdout.strip()
    except subprocess.CalledProcessError:
        return None

def _find_seed_templates(toolkit_path, script_dir):
    # Priority 1: direct (standard submodule checkout)
    direct = os.path.join(toolkit_path, "seed_templates")
    if os.path.isdir(direct):
        return direct
    # Priority 2: nested (repo has inner devspec_toolkit/ folder)
    nested = os.path.join(toolkit_path, "devspec_toolkit", "seed_templates")
    if os.path.isdir(nested):
        return nested
    # Priority 3: relative to script location (running from source)
    source = os.path.abspath(os.path.join(script_dir, "..", "seed_templates"))
    if os.path.isdir(source):
        return source
    return None

def _get_toolkit_root(toolkit_path, script_dir):
    seed_dir = _find_seed_templates(toolkit_path, script_dir)
    if seed_dir:
        return os.path.dirname(seed_dir)
    return toolkit_path

def main():
    parser = argparse.ArgumentParser(description="Initialize DevSpec Toolkit in a project")
    parser.add_argument("--target", default=".", help="Target project directory")
    parser.add_argument("--toolkit-url", default="https://github.com/vichitra-studio/devspec_toolkit.git", help="URL of the devspec_toolkit repo")
    parser.add_argument("--toolkit-root", help="Explicit path to devspec_toolkit source directory")
    parser.add_argument("--strict", action="store_true", help="Enable strict governance (commit-msg hooks)")
    args = parser.parse_args()

    target_dir = os.path.abspath(args.target)
    
    if not os.path.exists(target_dir):
        print(f"Error: Target directory {target_dir} does not exist.")
        sys.exit(1)

    # 1. Check if git repo
    git_root = get_git_root(target_dir)
    if not git_root:
        print("Initializing git repo...")
        run_cmd(["git", "init"], cwd=target_dir)
        git_root = target_dir
    else:
        # Ensure we are at root if possible, or just work relative
        pass

    # 2. Add Submodule
    toolkit_path = os.path.abspath(args.toolkit_root) if args.toolkit_root else os.path.join(target_dir, "devspec_toolkit")
    
    if args.toolkit_root:
        print(f"Using explicit toolkit root at {toolkit_path}. Skipping submodule add.")
    elif os.path.exists(toolkit_path):
        print("devspec_toolkit directory already exists. Skipping submodule add.")
    else:
        print(f"Adding submodule from {args.toolkit_url}...")
        try:
            run_cmd(["git", "submodule", "add", args.toolkit_url, "devspec_toolkit"], cwd=target_dir)
            run_cmd(["git", "submodule", "update", "--init", "--recursive"], cwd=target_dir)
        except subprocess.CalledProcessError as e:
            print(f"Failed to add submodule: {e}")
            print("Please check the URL, your network connection, or if 'devspec_toolkit' matches .gitignore.")
            print("If a partial directory exists, try: rm -rf devspec_toolkit")
            sys.exit(1)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    actual_toolkit_root = _get_toolkit_root(toolkit_path, script_dir)

    # 3. Init spec/ directory
    spec_dir = os.path.join(target_dir, "spec")
    if not os.path.exists(spec_dir):
        print("Creating spec/ directory...")
        os.makedirs(spec_dir)
        # Create .gitkeep
        with open(os.path.join(spec_dir, ".gitkeep"), "w") as f:
            f.write("")
    else:
        print("spec/ directory already exists.")

    # 3a. Init spec/common/ directory and seed manifest
    spec_common_dir = os.path.join(spec_dir, "common")
    if not os.path.exists(spec_common_dir):
        print("Creating spec/common/ directory...")
        os.makedirs(spec_common_dir)
    else:
        print("spec/common/ directory already exists.")

    seed_manifest_target = os.path.join(spec_common_dir, "seed_manifest.json")
    if not os.path.exists(seed_manifest_target):
        manifest_src = os.path.join(actual_toolkit_root, "spec", "common", "seed_manifest.json")
        if os.path.exists(manifest_src):
            print("Copying seed_manifest.json to spec/common/...")
            shutil.copy2(manifest_src, seed_manifest_target)
        else:
            print("Warning: seed_manifest.json template not found. Please add it manually to spec/common/.")
    else:
        print("spec/common/seed_manifest.json already exists.")

    # 3b. Init spec/impl_context/ directory
    impl_context_dir = os.path.join(spec_dir, "impl_context")
    if not os.path.exists(impl_context_dir):
        print("Creating spec/impl_context/ directory...")
        os.makedirs(impl_context_dir)
        # Create .gitkeep
        with open(os.path.join(impl_context_dir, ".gitkeep"), "w") as f:
            f.write("")
    else:
        print("spec/impl_context/ directory already exists.")

    # 4. Init docs/seed directory and copy templates
    docs_seed_dir = os.path.join(target_dir, "docs", "seed")
    if not os.path.exists(docs_seed_dir):
        print("Creating docs/seed/ directory...")
        os.makedirs(docs_seed_dir)

    # 4a. Emit wrapper scripts for venv-enforced CLI usage
    tools_dir = os.path.join(target_dir, "tools")
    if not os.path.exists(tools_dir):
        print("Creating tools/ directory...")
        os.makedirs(tools_dir)

    script_dir = os.path.dirname(os.path.abspath(__file__))
    wrapper_templates_dir = os.path.join(script_dir, "templates")
    run_specdev_src = os.path.join(wrapper_templates_dir, "run_specdev.sh")
    ensure_venv_src = os.path.join(wrapper_templates_dir, "ensure_venv.py")

    run_specdev_target = os.path.join(tools_dir, "run_specdev.sh")
    ensure_venv_target = os.path.join(tools_dir, "ensure_venv.py")

    if os.path.exists(run_specdev_src) and not os.path.exists(run_specdev_target):
        print("Creating tools/run_specdev.sh...")
        shutil.copy2(run_specdev_src, run_specdev_target)
        os.chmod(run_specdev_target, 0o755)
    elif os.path.exists(run_specdev_target):
        print("tools/run_specdev.sh already exists.")
    else:
        print("Warning: run_specdev.sh template not found; skipping.")

    if os.path.exists(ensure_venv_src) and not os.path.exists(ensure_venv_target):
        print("Creating tools/ensure_venv.py...")
        shutil.copy2(ensure_venv_src, ensure_venv_target)
    elif os.path.exists(ensure_venv_target):
        print("tools/ensure_venv.py already exists.")
    else:
        print("Warning: ensure_venv.py template not found; skipping.")
    
    seed_templates_dir = _find_seed_templates(toolkit_path, script_dir)
    if seed_templates_dir:
        print(f"Found seed templates at {seed_templates_dir}")
        for item in os.listdir(seed_templates_dir):
            s = os.path.join(seed_templates_dir, item)
            d = os.path.join(docs_seed_dir, item)
            if os.path.isfile(s):
                if not os.path.exists(d):
                    print(f"Copying {item} to docs/seed/...")
                    shutil.copy2(s, d)
                else:
                    print(f"Skipping {item} (already exists)")
    else:
        print("Warning: Seed templates not found. Could not copy seed templates to docs/seed/.")
    
    rel_toolkit_root = os.path.relpath(actual_toolkit_root, target_dir).replace("\\", "/")
    
    # 5. Hook setup (Pre-commit)
    pre_commit_file = os.path.join(target_dir, ".pre-commit-config.yaml")
    if not os.path.exists(pre_commit_file):
        print("Creating .pre-commit-config.yaml...")
        config_content = PRE_COMMIT_TEMPLATE.replace("./devspec_toolkit", f"./{rel_toolkit_root}" if rel_toolkit_root != "." else ".")
        with open(pre_commit_file, "w") as f:
            f.write(config_content)
        print("Note: You need to install pre-commit (pip install pre-commit) and run 'pre-commit install'")
    else:
        print(".pre-commit-config.yaml exists. Please manually ensure devspec hooks are configured.")

    # 6. Setup Virtual Environment
    venv_dir = os.path.join(target_dir, "dev_env")
    if not os.path.exists(venv_dir):
        print("Creating virtual environment 'dev_env'...")
        run_cmd([sys.executable, "-m", "venv", "dev_env"], cwd=target_dir)
        
        # Determine pip path (bin vs Scripts for cross-platform compatibility, though likely unix here)
        venv_bin = os.path.join(venv_dir, "bin")
        if sys.platform == "win32":
            venv_bin = os.path.join(venv_dir, "Scripts")
        
        pip_cmd = os.path.join(venv_bin, "pip")

        print("Upgrading pip...")
        run_cmd([pip_cmd, "install", "--upgrade", "pip"], cwd=target_dir)

        print("Installing pre-commit...")
        run_cmd([pip_cmd, "install", "pre-commit"], cwd=target_dir)

        print("Installing toolkit dependencies...")
        
        # requirements.txt path relative to actual toolkit root
        reqs_path = os.path.join(actual_toolkit_root, "tools", "requirements.txt")
        if os.path.exists(reqs_path):
             run_cmd([pip_cmd, "install", "-r", reqs_path], cwd=target_dir)
        
        # Install toolkit in editable mode
        tools_path = os.path.join(actual_toolkit_root, "tools")
        if os.path.exists(tools_path):
            run_cmd([pip_cmd, "install", "-e", tools_path], cwd=target_dir)

    else:
        print("Virtual environment 'dev_env' already exists.")
        # We still need the bin paths for subsequent steps
        venv_bin = os.path.join(venv_dir, "bin")
        if sys.platform == "win32":
             venv_bin = os.path.join(venv_dir, "Scripts")

    # 7. Setup Git Hooks (Always run/check)
    print("Ensuring git hooks are installed...")
    pre_commit_bin = os.path.join(venv_bin, "pre-commit")
    if os.path.exists(pre_commit_bin):
        # Run pre-commit install (basic)
        run_cmd([pre_commit_bin, "install"], cwd=target_dir)
        
        # If strict mode, install commit-msg hook
        if args.strict:
            print("Strict mode enabled: Installing commit-msg hook...")
            run_cmd([pre_commit_bin, "install", "--hook-type", "commit-msg"], cwd=target_dir)
            
            # Uncomment governance check in config
            config_path = os.path.join(target_dir, ".pre-commit-config.yaml")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    config_content = f.read()
                # Simple string replacement to uncomment the governance block
                if "#  - id: devspec-governance" in config_content:
                    print("Enabling governance check in pre-commit config...")
                    new_content = config_content.replace("#  - id: devspec-governance", "  - id: devspec-governance")
                    new_content = new_content.replace("#    name: DevSpec Governance Check", "    name: DevSpec Governance Check")
                    new_content = new_content.replace("#    entry: ./tools/run_specdev.sh", "    entry: ./tools/run_specdev.sh")
                    new_content = new_content.replace("#    language: python", "    language: system") # Ensure system language here too
                    new_content = new_content.replace("#    stages: [commit-msg]", "    stages: [commit-msg]")
                    with open(config_path, "w") as f:
                        f.write(new_content)
    else:
        print("Warning: pre-commit binary not found in dev_env. Skipping hook install.")

    # 7b. Generate CI Workflow
    workflows_dir = os.path.join(target_dir, ".github", "workflows")
    if not os.path.exists(workflows_dir):
        os.makedirs(workflows_dir)
    
    ci_file = os.path.join(workflows_dir, "spec_validation.yml")
    if not os.path.exists(ci_file):
        print("Creating CI workflow .github/workflows/spec_validation.yml...")
        ci_content = CI_WORKFLOW_TEMPLATE.replace("devspec_toolkit/tools", f"{rel_toolkit_root}/tools" if rel_toolkit_root != "." else "tools")
        ci_content = ci_content.replace("./devspec_toolkit", f"./{rel_toolkit_root}" if rel_toolkit_root != "." else ".")
        with open(ci_file, "w") as f:
            f.write(ci_content)
    else:
        print("CI workflow already exists.")

    # 7. Gitignore
    gitignore_path = os.path.join(target_dir, ".gitignore")
    ignore_entry = "dev_env/"
    if os.path.exists(gitignore_path):
        with open(gitignore_path, "r") as f:
            content = f.read()
        if ignore_entry not in content:
            print("Adding dev_env/ to .gitignore...")
            with open(gitignore_path, "a") as f:
                f.write(f"\n{ignore_entry}\n")
    else:
        print("Creating .gitignore with dev_env/...")
        with open(gitignore_path, "w") as f:
            f.write(f"{ignore_entry}\n")

    # 8. Update README
    readme_path = os.path.join(target_dir, "README.md")
    setup_docs = """
## Development Setup
This project uses the [DevSpec Toolkit](https://github.com/vichitracollective/devspec_toolkit) for specification-driven development.

1. **Activate Environment**:
   ```bash
   source dev_env/bin/activate
   ```
2. **Run Toolkit Commands**:
   ```bash
   ./tools/run_specdev.sh --help
   ```
"""
    if not os.path.exists(readme_path):
        print("Creating README.md...")
        with open(readme_path, "w") as f:
            f.write(f"# Project\n{setup_docs}")
    else:
        with open(readme_path, "r") as f:
            content = f.read()
        if "## Development Setup" not in content:
            print("Appending Development Setup to README.md...")
            with open(readme_path, "a") as f:
                f.write(f"\n{setup_docs}")
        else:
             print("README.md already contains Development Setup.")

    print("\nInitialization complete!")
    print("Next steps:")
    print("1. Fill out docs/seed/seed_overview.md and seed_tech_stack.md")
    print("2. Activate your environment: source dev_env/bin/activate")
    print("3. Start your first spec or run `./tools/run_specdev.sh --help`")

if __name__ == "__main__":
    main()
