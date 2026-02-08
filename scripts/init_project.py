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

def main():
    parser = argparse.ArgumentParser(description="Initialize DevSpec Toolkit in a project")
    parser.add_argument("--target", default=".", help="Target project directory")
    parser.add_argument("--toolkit-url", default="https://github.com/vichitra-studio/devspec_toolkit.git", help="URL of the devspec_toolkit repo")
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
    toolkit_path = os.path.join(target_dir, "devspec_toolkit")
    if os.path.exists(toolkit_path):
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
        # Try to copy the seed manifest from toolkit source
        manifest_candidates = [
            os.path.join(toolkit_path, "spec", "common", "seed_manifest.json"),
            os.path.join(toolkit_path, "devspec_toolkit", "spec", "common", "seed_manifest.json"),
        ]
        script_dir = os.path.dirname(os.path.abspath(__file__))
        manifest_candidates.append(os.path.abspath(os.path.join(script_dir, "..", "spec", "common", "seed_manifest.json")))
        manifest_src = next((p for p in manifest_candidates if os.path.exists(p)), None)
        if manifest_src:
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
    
    # Check for seed templates in the *toolkit* inside the target, or assume we are running *from* a toolkit source?
    # Strategy: We assume the script is valid, but where are the templates?
    # If we just added the submodule, they are in `devspec_toolkit/seed_templates`
    
    toolkit_seed_src = os.path.join(toolkit_path, "devspec_toolkit", "seed_templates") 
    # Note: the internal structure is devspec_toolkit/devspec_toolkit/seed_templates based on my `ls` earlier?
    # Let's double check.
    # Earlier I did `list_dir devspec_toolkit/devspec_toolkit`.
    # And `seed_templates` was there.
    # So if I submodule the *repo* into `devspec_toolkit`, the path is `target/devspec_toolkit/devspec_toolkit/seed_templates`?
    # Let's checking `ls` output again usually submodule root matches repo root.
    # My `ls` was `/Users/.../devspec_toolkit/devspec_toolkit`.
    # This implies the repo name is one thing, and it has a subdir `devspec_toolkit`.
    # If the user submodules the repo, they get the root.
    # So `target/devspec_toolkit/devspec_toolkit/seed_templates` seems correct given the current workspace.
    # WAIT. The workspace is `.../vc-code/devspec_toolkit`.
    # Inside it is `devspec_toolkit` folder.
    # And `README.md` is in `devspec_toolkit/devspec_toolkit/README.md`?
    # No, Step 8 says `file:///Users/vichitracollective/vc-code/devspec_toolkit/devspec_toolkit/README.md`.
    # And Step 4 `list_dir` of `.../devspec_toolkit/devspec_toolkit` showed README.
    # So the repo has a top-level folder `devspec_toolkit`.
    # So if I submodule it, `target/devspec_toolkit` will contain `devspec_toolkit`.
    # So source is `target/devspec_toolkit/devspec_toolkit/seed_templates`.
    
    if os.path.exists(toolkit_seed_src):
        for item in os.listdir(toolkit_seed_src):
            s = os.path.join(toolkit_seed_src, item)
            d = os.path.join(docs_seed_dir, item)
            if os.path.isfile(s):
                if not os.path.exists(d):
                    print(f"Copying {item} to docs/seed/...")
                    shutil.copy2(s, d)
                else:
                    print(f"Skipping {item} (already exists)")
    else:
        # Fallback: maybe we are running *from* the toolkit source and not using the submodule copy?
        script_dir = os.path.dirname(os.path.abspath(__file__))
        fallback_src = os.path.abspath(os.path.join(script_dir, "..", "seed_templates"))
        if os.path.exists(fallback_src):
             for item in os.listdir(fallback_src):
                s = os.path.join(fallback_src, item)
                d = os.path.join(docs_seed_dir, item)
                if os.path.isfile(s) and not os.path.exists(d):
                    print(f"Copying {item} to docs/seed/ (from local source)...")
                    shutil.copy2(s, d)
    
    # 5. Hook setup (Pre-commit)
    pre_commit_file = os.path.join(target_dir, ".pre-commit-config.yaml")
    if not os.path.exists(pre_commit_file):
        print("Creating .pre-commit-config.yaml...")
        with open(pre_commit_file, "w") as f:
            f.write(PRE_COMMIT_TEMPLATE)
        print("Note: You need to install pre-commit (pip install pre-commit) and run 'pre-commit install'")
    else:
        print(".pre-commit-config.yaml exists. Please manually ensure devspec hooks are configured.")

    # 6. Setup Virtual Environment
    venv_dir = os.path.join(target_dir, "dev_env")
    if not os.path.exists(venv_dir):
        print("Creating virtual environment 'dev_env'...")
        run_cmd(["python3", "-m", "venv", "dev_env"], cwd=target_dir)
        
        # Determine pip path (bin vs Scripts for cross-platform compatibility, though likely unix here)
        venv_bin = os.path.join(venv_dir, "bin")
        if sys.platform == "win32":
            venv_bin = os.path.join(venv_dir, "Scripts")
        
        pip_cmd = os.path.join(venv_bin, "pip3")

        print("Upgrading pip...")
        run_cmd([pip_cmd, "install", "--upgrade", "pip"], cwd=target_dir)

        print("Installing pre-commit...")
        run_cmd([pip_cmd, "install", "pre-commit"], cwd=target_dir)

        print("Installing toolkit dependencies...")
        # requirements.txt path relative to target -> devspec_toolkit/tools/requirements.txt
        reqs_path = os.path.join(target_dir, "devspec_toolkit", "tools", "requirements.txt")
        if os.path.exists(reqs_path):
             run_cmd([pip_cmd, "install", "-r", reqs_path], cwd=target_dir)
        
        # Install toolkit in editable mode
        tools_path = os.path.join(target_dir, "devspec_toolkit", "tools")
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
                    new_content = new_content.replace("#    entry: ./tools/run_specdev.sh governance-check spec --repo-root ./devspec_toolkit --message", "    entry: ./tools/run_specdev.sh governance-check spec --repo-root ./devspec_toolkit --message")
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
        with open(ci_file, "w") as f:
            f.write(CI_WORKFLOW_TEMPLATE)
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
