# RFC Amendment: vc-skills Subagent Layer — Review Response
Date: 2026-03-07
Applies to: rfc-vc-skills-subagent-layer.md + references/agent_prompts/*.md

This document responds to the in-depth review, clarifies the design, and specifies all
changes to be merged into the RFC and agent prompts before implementation.

---

## C-1: Dismissed — Reviewer Misunderstood the Runtime

The reviewer claimed the RFC provides "zero specification for the runtime dispatch
mechanism." This is incorrect. Claude Code natively resolves custom `subagent_type`
values against `.claude/agents/{name}.md` at runtime. No shim, MCP server, or hook
is required — this is the documented built-in behaviour from the Claude Code sub-agents
spec. The RFC should add one clarifying sentence:

> "Claude Code resolves custom `subagent_type` values against `.claude/agents/{name}.md`
> at runtime with the restricted tool set and system prompt defined in that file. No
> additional dispatch layer is required."

---

## Structural Change: 7 Agents (was 6)

vc-scope-explorer is split into two agents. vc-dependency-mapper is new.

| Agent | Model | Tools | maxTurns |
|---|---|---|---|
| vc-context-extractor | haiku | Read, Bash | 5 |
| vc-scope-explorer | haiku | Read, Grep, Glob, Bash | 10 |
| vc-dependency-mapper | sonnet | Read, Grep, Glob, Bash | 10 |
| vc-code-analyzer | opus | Read, Grep, Glob, Bash, WebFetch, WebSearch | 15 |
| vc-findings-consolidator | haiku | Bash | 8 |
| vc-code-fixer | sonnet | Read, Edit, Write, Bash, Grep, Glob, WebFetch | 20 |
| vc-web-researcher | sonnet | WebFetch, WebSearch | 10 |

---

## Changes by Finding

### C-2: Add origin to TASK output format (vc-context-extractor)

**Change**: Add `{origin}` as field 9 in the PARSE_PLAN TASK output line.

Current format:
```
TASK | {N} | {file} | {reads} | {action} | {test_gate} | {depends_on} | {parallel_group} | {source}
```

New format:
```
TASK | {N} | {file} | {reads} | {action} | {test_gate} | {depends_on} | {parallel_group} | {source} | {origin}
```

Use `none` when the `origin` field is absent from the task block. This preserves
end-to-end traceability through the full /vc-review → /vc-plan → /vc-parallel-fix
pipeline.

The vc-parallel-fix SKILL.md Phase 1 parsing section must document all 10 pipe positions
including `origin`, and pass `origin` through to the vc-code-fixer prompt as
`ORIGIN: {origin}`.

---

### C-3: Pipe-to-output field mapping (vc-review SKILL.md Step 3)

**Change**: Step 3 in vc-review SKILL.md must document how to parse the new
pipe-delimited output from vc-code-analyzer and map it to the findings output template.

Field position mapping (FINDING lines):
```
pos 1: prefix      → "FINDING"
pos 2: file:line   → maps to file + line fields in output template
pos 3: severity    → maps to **Severity** in output template
pos 4: category    → maps to **Category** in output template
pos 5: req_id      → maps to **Reference** in output template
pos 6: summary     → maps to **Summary** in output template
pos 7: evidence    → maps to **Evidence** in output template
pos 8: fix         → maps to **Fix** in output template
```

The `detail` field from the old JSON-style format is dropped — `summary` covers it.
The `status` field is implicit: `FINDING` prefix = finding, `PASS` prefix = passing check.

The output template **Detail** field in vc-review SKILL.md must be removed. The template
becomes: Summary / Evidence / Fix (no separate Detail).

---

### H-1: URL extraction added to vc-context-extractor

**Change**: vc-context-extractor must extract URLs as part of PARSE_REVIEW and PARSE_PLAN.
Add one additional output line after all TASK/REQ lines:

```
URLS | {url1},{url2},...
```

Use `URLS | none` when no URLs are found. The main agent reads this line to decide
whether to spawn vc-web-researcher — no document scanning required.

URL extraction rules:
- Match `http://` and `https://` patterns in the input document
- Exclude internal file paths (e.g., `file://`, relative paths)
- Deduplicate before outputting

---

### H-2: Add findings cap to vc-code-analyzer

**Change**: Add to vc-code-analyzer, after the FINDING/PASS output rules:

```
FINDINGS CAP: Return at most 15 FINDING records per invocation. If more exist,
prioritise by severity: critical → high → medium → low. After all records, append:
  CAPPED | {N_total} | {N_omitted}
If findings are within the cap, omit the CAPPED line.
```

This preserves the existing 15-finding budget guard that was present in the old inline
template. The cap applies per agent invocation — with multiple agents reviewing different
file groups, the effective cap across a full review is 15 × N_agents.

---

### H-3: Directory naming — use underscores

**Change**: All references to the agent prompt source directory use underscores:
`references/agent_prompts/` (not `references/agent-prompts/`). The agent files in
`.claude/agents/` retain hyphen-separated names (e.g., `vc-context-extractor.md`).

---

### H-4: Remove consolidation threshold — always consolidate

**Decision**: Drop the `if findings >= 25` threshold entirely. vc-findings-consolidator
runs after every review regardless of finding count. Rationale: a single code path is
more reliable; two paths with different dedup/sort logic produce non-deterministic output;
haiku overhead for a single consolidation pass is negligible.

**Change**: Remove the threshold check from vc-review SKILL.md Step 3. The text
"If total findings ≥ 25, spawn vc-findings-consolidator" becomes:

> "After collecting all FINDING lines from Step 2 agents, spawn vc-findings-consolidator
> with all findings concatenated as input text. Consolidation always runs."

---

### H-5: Model hardcoding — documented deliberate tradeoff (no change)

Model routing is intentionally fixed. Users who require Opus-quality fixes can run
subagents manually or adjust agent frontmatter directly. Add to RFC Risks & Assumptions:

> "Model routing is hardcoded: haiku for extraction/discovery, sonnet for fixing/research,
> opus for code analysis. This is a deliberate cost/quality tradeoff. Users on opus who
> want opus-quality fixes should update the `model:` field in the relevant agent files."

---

### H-6: Split vc-scope-explorer — new vc-dependency-mapper agent (Sonnet)

**Decision**: Split into two agents.

**vc-scope-explorer** (haiku, maxTurns: 10):
- Handles: `OBJECTIVE: FILE_DISCOVERY` and `OBJECTIVE: PATTERN_DISCOVERY` only
- DEPENDENCY_MAPPING objective removed

**vc-dependency-mapper** (sonnet, maxTurns: 10):
- New agent, handles: `OBJECTIVE: DEPENDENCY_MAPPING` only
- Same input/output contract as the old DEPENDENCY_MAPPING objective in vc-scope-explorer
- Tools: Read, Grep, Glob, Bash
- Rationale: dependency analysis requires reasoning about import graphs and ordering;
  haiku risks incorrect dependency direction, leading to broken parallel groups

**Change in vc-plan SKILL.md Step 1**: The dependency mapping agent call changes from
`subagent_type: "vc-scope-explorer"` to `subagent_type: "vc-dependency-mapper"`.

---

### M-2: vc-findings-consolidator tools — keep Bash, add explicit prohibition

`tools: none` is not supported by Claude Code. Keep `tools: Bash`. Add explicit rule
to the agent prompt:

> "You have Bash available but MUST NOT use it. All input is in your prompt. Process
> only the text passed to you and return your output. Do not invoke any commands."

---

### M-3: Remove "Project Conventions" sections from all three skills

**Change**: In vc-review, vc-plan, and vc-parallel-fix SKILL.md, remove or replace the
"## Project Conventions" section body with:

> "Project conventions are extracted in Step 0 via vc-context-extractor and injected
> into all agent prompts as PROJECT_CONTEXT. Do not re-read CLAUDE.md."

---

### M-4: Fix heading format in vc-code-fixer (Steps 7 and 8)

**Change**: Steps 7 and 8 in vc-code-fixer.md must use `### N. Title` format,
consistent with Steps 1–6:

```
### 7. Retry on Failure
### 8. Report
```

---

### M-5: Phase 3 self-healing in vc-parallel-fix uses vc-code-fixer

**Change**: vc-parallel-fix SKILL.md Phase 3 (self-healing) currently spawns
`subagent_type: "general-purpose"`. Update to `subagent_type: "vc-code-fixer"` for
consistency with Phase 2. The same single-file, test-gate, RESULT-line protocol applies.

---

### M-6: Define PROJECT_CONTEXT injection format

**Change**: Specify the injection format in the RFC and in all agent prompts that
reference PROJECT_CONTEXT. The format is a labeled block:

```
PROJECT_CONTEXT:
test_command: pytest tests/
venv: devspec_env
repo_root_flag: --repo-root ./devspec_toolkit
test_runner: pytest
spec_dir: devspec_toolkit/spec
```

Agent prompts reference individual fields by key name (e.g., "activate the venv named
in `venv:`"). The vc-context-extractor CLAUDE_MD objective already outputs these as
`key: value` lines — wrap them in the `PROJECT_CONTEXT:` label when injecting.

---

### L-1: Content anchors replace line number references

**Change**: Replace all "Remove lines N–M" references in the RFC with content anchors:

- vc-plan: "Remove the **Complete plan example** block, from the opening triple-backtick
  fence through the closing triple-backtick fence (the `## Complete plan example`
  subsection)."
- vc-parallel-fix: "Remove the **## Worked Example** section through the final line
  ending with `47 passed, 0 failed`."

---

### L-2: Remove Read from vc-web-researcher

**Change**: vc-web-researcher never reads local files. Remove `Read` from its tools list.
Final tools: `WebFetch, WebSearch`.

---

### L-3: references/agent_prompts/ kept as documentation

**Decision**: `references/agent_prompts/` is retained as the human-readable source of
record. The `.claude/agents/` files are the runtime source of truth. When editing agent
prompts, update both locations. Note this in the RFC repository structure section.

---

## Summary of New/Changed Files

| File | Change |
|---|---|
| `rfc-vc-skills-subagent-layer.md` | C-1 clarification, agent table updated (7 agents), threshold removed, dependency-mapper added, PROJECT_CONTEXT format defined, content anchors, M-3/M-5/L-3 notes |
| `references/agent_prompts/vc-context-extractor.md` | Add URLS output line; add origin (field 9) to TASK format |
| `references/agent_prompts/vc-scope-explorer.md` | Remove DEPENDENCY_MAPPING objective |
| `references/agent_prompts/vc-dependency-mapper.md` | New file (sonnet, DEPENDENCY_MAPPING only) |
| `references/agent_prompts/vc-code-analyzer.md` | Add 15-finding cap + CAPPED line |
| `references/agent_prompts/vc-findings-consolidator.md` | Add explicit Bash prohibition; remove threshold reference |
| `references/agent_prompts/vc-code-fixer.md` | Fix ### 7 and ### 8 headings |
| `references/agent_prompts/vc-web-researcher.md` | Remove Read tool |
| `skills/vc-review/SKILL.md` | Step 3: pipe field mapping; remove Detail from output template; always consolidate; remove Project Conventions body |
| `skills/vc-plan/SKILL.md` | Step 1: dependency-mapper agent call; remove Project Conventions body |
| `skills/vc-parallel-fix/SKILL.md` | Phase 1: add origin field (pos 10); Phase 2: pass ORIGIN to fixer; Phase 3: use vc-code-fixer; remove Project Conventions body |
