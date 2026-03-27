# P4 Deep Review: User Concerns Round 3

Date: 2026-03-19

---

## Q1: generation_quality.assumptions -- what purpose does it solve?

### Evidence from files

**Schema definition** (`schema/core/collections.schema.json`, lines 380-392):
```json
"generationQuality": {
  "type": "object",
  "additionalProperties": false,
  "required": ["assumptions"],
  "properties": {
    "assumptions": {
      "$ref": "https://specdev.local/schema/core/collections/1#stringArray"
    }
  }
}
```

The schema enforces `generation_quality: { assumptions: [...] }` on every spec artifact. The `assumptions` field is a simple string array with no minimum items -- empty arrays are valid.

**Prompt instructions** (consistent across all 5 prompts examined: 00, 01, 02, 03, 04):

Every prompt contains this instruction under "Self-Audit Gate":
> Populate `generation_quality.assumptions` with specific, testable claims about decisions made during generation.

And under "Canonical Binding Rules":
> `generation_quality` is REQUIRED. Populate `generation_quality.assumptions` with specific, testable claims about decisions made during generation.

So yes, every prompt instructs the LLM to populate assumptions. The instruction is clear: "specific, testable claims about decisions made during generation."

**Actual spec files** (`spec/05_interface_contracts.json` -- the only spec file in the repo):
```json
"generation_quality": {
    "assumptions": []
}
```

Assumptions are empty in the only real spec file. The output contract examples in ALL five prompts also show `"assumptions": []` (empty).

**Migration script** (`tools/specdev_tools/migration/scripts/strip_generation_quality.py`):
A migration script exists to strip `generation_quality` down to `{"assumptions": <existing>}`, suggesting the field previously contained more sub-fields that were removed. The field was actively pared down, yet `assumptions` survived the cut.

**Consumption**: No validator, linter, or downstream tool reads or acts on `generation_quality.assumptions`. The `prompt_schema_sync.py` lists it in a skip-list of "metadata fields" that are excluded from prompt-schema drift checks. No lint checks whether assumptions are empty or non-empty.

### Analysis

**Intended purpose**: (a) audit trail + (b) quality signal. The prompts frame it as part of the "Self-Audit Gate" -- the LLM is supposed to list what it assumed so a human reviewer can spot problematic reasoning.

**Is asking an LLM "what did you assume?" actually useful?**

No, not reliably. There are fundamental problems:

1. **Post-hoc rationalization**: LLMs do not have genuine introspective access to their "reasoning process." When asked "what did you assume?", they produce plausible-sounding statements about what they might have assumed, but these are generated the same way as any other text -- they are not a faithful readout of an internal decision log.

2. **Completeness gap**: The assumptions an LLM lists will be the obvious, surface-level ones. The dangerous assumptions -- the ones that cause subtle bugs -- are precisely the ones the LLM will fail to identify, because if it recognized them as assumptions, it would have flagged them already.

3. **Empty in practice**: The only real spec file has `assumptions: []`. The output contract examples in every prompt also show `[]`. This means either (a) LLMs are not populating it despite being told to, or (b) the example trains the LLM to leave it empty. Either way, the field is not serving its stated purpose.

4. **No downstream consumer**: Nothing reads assumptions. No lint warns on empty assumptions. No CI gate checks them. They are write-only data.

### Verdict

The field is **ceremonial overhead**. It adds schema complexity, prompt verbosity (the instruction appears twice per prompt across 17+ prompts), and validation surface area -- all for a field that is empty in practice and consumed by nothing.

The concept of "document your assumptions" is sound for human authors but breaks down for LLMs because LLMs cannot reliably introspect on their own decision-making.

### Recommended action

**Remove `generation_quality` entirely from all schemas.** Rationale:
- No validator consumes it
- Empty in all real artifacts
- LLM introspection on assumptions is unreliable
- The migration script already stripped it down once; finish the job
- If assumption tracking is needed, it should be a human review field in guide files, not a schema-enforced LLM output

If removal is too aggressive, at minimum: (1) make `generation_quality` optional, not required, (2) remove the prompt instructions about it, (3) let it die naturally.

---

## Q2: seed_refs for steps 00-04 -- can we hardwire in prompts instead?

### Evidence from files

**seed_manifest.json** (`spec/common/seed_manifest.json`) step_requirements:
```json
"step_requirements": {
    "00": ["seed-overview", "seed-tech-stack"],
    "01": ["seed-overview"],
    "02": ["seed-tech-stack"],
    "02a": ["seed-tech-stack"],
    "03": ["seed-overview"],
    "04": ["seed-overview"]
}
```

**Prompt instructions** -- every prompt (00-04) contains:

1. A "Seed Order & Mandatory Sources" section:
   > Read `spec/common/seed_manifest.json` first; follow `global_seed_order` and `step_requirements["00"]`.
   > Populate `seed_refs` with the seeds actually used.

2. A "Context To Ingest" section that explicitly names the seed files:
   - prompt_00: "Primary Source: `docs/seed/seed_overview.md` (required)" and "Constraints Source: `docs/seed/seed_tech_stack.md` (required)"
   - prompt_01: "Primary Source: `docs/seed/seed_overview.md` (required)"
   - prompt_02: "Primary Source: `docs/seed/seed_tech_stack.md` (required)"
   - prompt_03: Charter is primary; seed_overview is in step_requirements
   - prompt_04: Charter/capabilities primary; seed_overview is in step_requirements

3. A "Seed Ingestion Protocol" section with a 4-step process telling the LLM to read seed_manifest.json, ingest seeds, extract fields, and "Populate `seed_refs[]` with actually-used seed IDs and content hashes."

4. Coverage Closure checklist includes: "`seed_refs` only contains seeds actually referenced in the output"

**seed_lint.py** (`tools/specdev_tools/validation/seed_lint.py`) -- this is the critical consumer:

The `lint_seeds()` function validates seed_refs by:
- Loading seed_manifest.json
- For each spec JSON file, reading its `seed_refs` array
- Collecting required seeds via `_collect_required_seeds()` (which unions step_requirements + global_seed_order)
- Checking that all required seeds appear in the artifact's `seed_refs`
- Emitting `E520` if required seed_refs are missing

This means **seed_refs is consumed by a post-hoc validator**, not just by the LLM.

**The redundancy pattern**:

The information flows through THREE channels:
1. **seed_manifest.json** `step_requirements` -- authoritative mapping of which seeds each step needs
2. **Prompts** -- hardwire the same information in "Context To Ingest" and "Seed Ingestion Protocol"
3. **seed_refs in artifact** -- the LLM echoes back which seeds it used, validated by seed_lint

### Analysis

The prompt already tells the LLM exactly which seeds to use. The LLM then echoes this back in seed_refs. The seed_lint then checks that the echo matches seed_manifest.json. This is a triple-redundancy loop.

However, there is a meaningful distinction: seed_lint validates that the **generated artifact** claims to have used the right seeds. This is a CI-checkable assertion. Without seed_refs in the artifact, seed_lint would have to trust that the LLM followed the prompt instructions, which cannot be verified post-hoc.

The real question is: **does verifying the LLM's self-report add value?** The LLM will include whatever seed_refs the prompt tells it to include. It is not an independent verification -- it is asking the LLM "did you do what I told you?" and the LLM will always say yes.

The content_overlap check in seed_lint (lines 129-170) is more meaningful -- it tokenizes the spec and the seed file and checks that they share vocabulary. This check does NOT depend on seed_refs; it uses seed_refs only to know which seed-artifact pairs to compare.

### Verdict

**seed_refs is partially useful but over-engineered for steps 00-04.**

- The mapping is already fully determined by seed_manifest.json `step_requirements`
- The prompts already hardwire which seeds to use
- The LLM echoing back seed_refs is not an independent verification
- The content_overlap check is useful but could derive seed-step mappings from seed_manifest.json directly

### Recommended action

**Option A (conservative)**: Keep seed_refs but simplify. Remove the "Seed Ingestion Protocol" boilerplate from prompts. Instead, have seed_lint derive the expected seed_refs directly from seed_manifest.json `step_requirements` + the artifact's step number. The LLM still populates seed_refs (for the content_overlap check), but the prompt instruction shrinks to one line: "Populate seed_refs with seeds listed in step_requirements."

**Option B (aggressive)**: Remove seed_refs from schemas for steps 00-04 entirely. The seed_lint should derive expected seeds from seed_manifest.json without needing the artifact to self-report. The content_overlap check can use step_requirements directly. This eliminates:
- ~15 lines of boilerplate per prompt (across 6 prompts = 90 lines)
- A schema field that adds no independent information
- A validation loop that checks the LLM's self-report against the source it was told to copy from

**Option B is recommended.** The seed_manifest.json is already the single source of truth. The artifact echoing it back is ceremony.

---

## Q3: docs_policy in seed_manifest.json -- what purpose does it solve?

### Evidence from files

**seed_manifest.json** (`spec/common/seed_manifest.json`) docs_policy section:
```json
"docs_policy": {
    "readme_required": true,
    "root_readme_required": true,
    "readme_depth_default": 0,
    "readme_depth_by_scope": {},
    "scope": ["devspec_toolkit/"],
    "exclusions": [
        "devspec_toolkit/node_modules/",
        "devspec_toolkit/.git/",
        "devspec_toolkit/.venv/",
        "devspec_toolkit/__pycache__/",
        "devspec_toolkit/dist/",
        "devspec_toolkit/build/",
        "devspec_toolkit/coverage/",
        "devspec_toolkit/tests/fixtures/",
        "devspec_toolkit/tools/specdev_tools.egg-info/"
    ],
    "doc_paths": ["docs/**", "README.md", "CHANGELOG.md"]
}
```

**Schema** (`schema/seed_manifest.schema.json`): `docs_policy` is listed in the `required` array -- it is mandatory in every seed_manifest.json.

**Prompt consumption**: Only ONE prompt mentions docs_policy -- `prompts/prompt_16a_impl_planner.md`:
> If new directories are introduced or renamed, update `spec/common/seed_manifest.json` to set `docs_policy.readme_depth_by_scope` for those paths

This is an administrative instruction about maintaining the config, not an instruction to use docs_policy data in spec generation.

**Tool consumption**: `docs_lint.py` (`tools/specdev_tools/validation/docs_lint.py`) is the ONLY consumer. It:
1. Loads seed_manifest.json
2. Reads `docs_policy` to determine: which directories need READMEs (`scope`), how deep to check (`readme_depth_default`, `readme_depth_by_scope`), what to exclude (`exclusions`), and whether a root README is required (`root_readme_required`)
3. Walks the filesystem and emits `E520` errors for missing READMEs

No other tool, validator, or prompt consumes docs_policy.

### Analysis

**docs_policy is pure lint configuration masquerading as spec-level data.**

It does not describe the product being specified. It describes how to lint the repository's documentation structure. This is fundamentally different from the other seed_manifest fields:
- `seeds` -- describes input documents the LLM must read (spec concern)
- `step_requirements` -- maps seeds to steps (spec concern)
- `global_seed_order` -- controls ingestion order (spec concern)
- `docs_policy` -- controls which directories need README files (tooling concern)

Putting lint config in seed_manifest.json conflates two concerns:
1. **Spec pipeline metadata** (what the LLM needs to know) -- belongs in seed_manifest
2. **Repository hygiene rules** (what the linter needs to enforce) -- belongs in tool config

The fact that docs_policy is `required` in the schema means every project using this toolkit must define a docs_policy, even if they do not use docs_lint or have no opinion about README placement.

**Is the concept of "docs policy" even necessary?** The current policy (`readme_depth_default: 0`) means "only check the root and the directories explicitly listed in scope." This is a reasonable lint rule, but it could be a simpler config. The full docs_policy schema supports:
- Per-scope depth overrides (`readme_depth_by_scope`)
- Glob-based doc_paths
- Per-directory exclusion lists

This is configurable to the point of over-engineering for a feature that boils down to: "does each important directory have a README?"

### Verdict

**docs_policy is misplaced and over-engineered.** It is lint configuration that should not live in a spec-level manifest.

### Recommended action

1. **Move docs_policy out of seed_manifest.json** into a dedicated tool config file (e.g., `tools/docs_lint_config.json` or a section in a `tools/specdev_config.json`).

2. **Remove docs_policy from the seed_manifest schema's required array.** Keep it as optional for backward compatibility during migration.

3. **Simplify the config.** The current shape has 6 fields. A simpler alternative:
   ```json
   {
     "require_root_readme": true,
     "scope": ["devspec_toolkit/"],
     "exclusions": ["node_modules/", ".git/", ...],
     "max_depth": 0
   }
   ```
   The `doc_paths` field is not consumed by docs_lint.py at all -- it is dead config. `readme_depth_by_scope` is an empty object in the actual manifest -- unused complexity.

4. **If we want to keep it simple**: just always require a root README and check the top-level of scoped directories. This is what the current config effectively does (depth=0). Hard-code this behavior and eliminate the config entirely. Let projects override via an optional config file if they need custom depth.

---

## Summary Table

| Question | Verdict | Action |
|----------|---------|--------|
| Q1: generation_quality.assumptions | Ceremonial; empty in practice; no consumer; LLM introspection unreliable | Remove from all schemas |
| Q2: seed_refs for steps 00-04 | Triple redundancy; LLM self-report adds no independent value | Remove seed_refs from schemas; derive from seed_manifest |
| Q3: docs_policy in seed_manifest | Lint config masquerading as spec data; over-engineered | Move to tool config; simplify or hard-code defaults |
