# AI Spec Driven Development CLI (v3 Full)

Deterministic, schema-first utilities for the AI Spec Driven Development Toolkit.

## Install

```bash
# adjust tools/ai-spec-toolkit if the submodule lives elsewhere
python -m venv .venv && . .venv/bin/activate
pip install -r tools/ai-spec-toolkit/tools/requirements.txt
export PYTHONPATH="${PWD}/tools/ai-spec-toolkit/tools"
```

Run these commands from the root of your host repository; adjust the paths if you invoke them from inside the submodule. Python 3.10+ recommended.

---

## What is **toolkit root**?

The toolkit root is the directory that contains this submodule (for example, `tools/ai-spec-toolkit`). That folder ships with:

```
<toolkit-root>/
├─ tools/
│  ├─ schema_registry.json
│  └─ specdev_tools/...
├─ schema/
├─ prompts/
├─ docs/
├─ template/
└─ tests/
```

The CLI resolves `$schema` URIs via `tools/schema_registry.json`. When you run commands from your product repository, pass `--repo-root <toolkit-root>` so those paths resolve correctly.

Examples (assuming `tools/ai-spec-toolkit`):

- Host repo root:
  ```bash
  python -m specdev_tools.cli validate spec/00_charter.json --repo-root tools/ai-spec-toolkit
  ```
- Inside the toolkit directory:
  ```bash
  python -m specdev_tools.cli validate ../spec/00_charter.json --repo-root .
  ```
- Arbitrary location:
  ```bash
  python -m specdev_tools.cli validate /abs/path/spec/00_charter.json --repo-root /abs/path/tools/ai-spec-toolkit
  ```

If you vend the toolkit elsewhere, substitute that path in the commands above and below.

---

## CLI overview

Show help:

```bash
python -m specdev_tools.cli --help
```

Subcommands (all arguments documented; nothing hidden):

### 1) `validate`
```
python -m specdev_tools.cli validate <file> [--repo-root <toolkit-root>]
```
Validate a single JSON artifact. Exit code `0` means success.

**Example**
```bash
python -m specdev_tools.cli validate spec/00_charter.json --repo-root tools/ai-spec-toolkit
```

### 2) `validate-all`
```
python -m specdev_tools.cli validate-all <spec_dir> [--repo-root <toolkit-root>]
```
Validate every `*.json` recursively.

**Example**
```bash
python -m specdev_tools.cli validate-all spec --repo-root tools/ai-spec-toolkit
```

### 3) `matrix`
```
python -m specdev_tools.cli matrix <spec_dir> [--repo-root <toolkit-root>] [--out -]
```
Emit the FR→API→Fixture→NFR coverage matrix.

**Example**
```bash
python -m specdev_tools.cli matrix spec --repo-root tools/ai-spec-toolkit --out tools/trace_matrix.json
```

### 4) `fixtures-lint`
```
python -m specdev_tools.cli fixtures-lint <spec_dir> [--repo-root <toolkit-root>]
```
Static lint for fixture structure and targets.

**Example**
```bash
python -m specdev_tools.cli fixtures-lint spec --repo-root tools/ai-spec-toolkit
```

### 5) `invariants-check`
```
python -m specdev_tools.cli invariants-check <spec_dir> --sample <file> [--repo-root <toolkit-root>]
```
Evaluate invariant expressions against a sample JSON context.

**Example**
```bash
echo '{ "password": { "length": 12 } }' > /tmp/sample.json
python -m specdev_tools.cli invariants-check spec --repo-root tools/ai-spec-toolkit --sample /tmp/sample.json
```

### 6) `governance-check`
```
python -m specdev_tools.cli governance-check <spec_dir> --message "<text>" [--repo-root <toolkit-root>]
```
Verify commit messages against Step 10.

**Example**
```bash
python -m specdev_tools.cli governance-check spec --repo-root tools/ai-spec-toolkit --message "feat(spec): add login [fr-initial-login]"
```

### 7) `gen-ci`
```
python -m specdev_tools.cli gen-ci <spec_dir> [--repo-root <toolkit-root>] [--toolkit-path <toolkit-root>] [--out -]
```
Generate a baseline CI workflow aligned with Step 12.

**Example**
```bash
python -m specdev_tools.cli gen-ci spec --repo-root tools/ai-spec-toolkit --toolkit-path tools/ai-spec-toolkit --out .github/workflows/ci.yml
```

### 8) `scaffold`
```
python -m specdev_tools.cli scaffold <spec_dir> --out <dir> [--repo-root <toolkit-root>]
```
Create a minimal HTTP scaffold from Steps 05 + 13 contracts.

**Example**
```bash
python -m specdev_tools.cli scaffold spec --repo-root tools/ai-spec-toolkit --out scaffold_out
```

---

## How schema resolution works

- Artifacts embed `$schema` URIs (e.g., `https://specdev.local/schema/04_fr_list.schema.json`).
- The CLI maps that URI via `tools/schema_registry.json` under the toolkit root.
- If you move files, update the registry accordingly.

---

## CI integration (quick start)

A minimal workflow (via `gen-ci`) typically runs:

1. `python -m specdev_tools.cli validate-all spec --repo-root tools/ai-spec-toolkit`
2. `python -m specdev_tools.cli scaffold spec --repo-root tools/ai-spec-toolkit --out scaffold_out`

Extend with unit tests, fixture execution, red-team loops, deploy, and drift audit steps as your pipeline matures.

---

## FAQ

- **Do I always need `--repo-root`?** From inside the toolkit root it defaults correctly; otherwise pass the path to your toolkit checkout.
- **Can I vendor the toolkit elsewhere?** Yes—update the paths in the commands above (and when running `gen-ci --toolkit-path <path>`).
