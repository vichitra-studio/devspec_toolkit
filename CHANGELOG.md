# Changelog

All changes to the DevSpec AI Toolkit are documented here. This project is based on
[Keep a Changelog](https://keepachangelog.com/en/1.0.0/) and
[Semantic Versioning](https://semver.org/).

Each release has two files in [`changelog/`](./changelog/): a human-readable
entry (`vX.Y.Z.md`) and a machine-readable migration spec (`vX.Y.Z.yaml`)
consumed by `specdev align`.

## Version Index

| Version | Documentation | Migration Spec |
| :--- | :--- | :--- |
| **[1.1.1]** | [v1.1.1.md](changelog/v1.1.1.md) | [v1.1.1.yaml](changelog/v1.1.1.yaml) |
| **[1.1.0]** | [v1.1.0.md](changelog/v1.1.0.md) | [v1.1.0.yaml](changelog/v1.1.0.yaml) |
| **[1.0.0]** | [v1.0.0.md](changelog/v1.0.0.md) | [v1.0.0.yaml](changelog/v1.0.0.yaml) |

---

## Contribution Guide

### When to write a changelog entry

Write an entry when the change affects how someone uses the toolkit:

| Change type | Entry required |
| :--- | :---: |
| New CLI command or flag | Yes |
| Schema field added, removed, or renamed | Yes |
| Validation behavior change (new/changed E or W code) | Yes |
| Prompt contract change — required fields or Extraction Intent sections | Yes |
| Bug fix that changes observable output | Yes |
| Internal refactor with no behavior change | No |
| Test additions | No |
| Prompt wording or clarity edits | No |
| CI / build changes | No |
| Docs prose edits | No |

### Format rules

- **One entry per capability, not per commit.** Group related commits into
  one bullet.
- **Experimental features** get an *(experimental)* suffix. Remove it when
  the feature is validated.
- Never edit a released version entry.

### Sections

Use only the sections that apply. Standard order:
`Breaking Changes` → `Added` → `Changed` → `Deprecated` → `Removed` → `Fixed` → `Security`

- **Breaking Changes** — use when a release removes schema fields under
  `additionalProperties: false`, adds hard validation that fails
  previously-passing specs, or removes shipped CLI surface. Each bullet must
  be self-contained: state the impact and the remediation in one paragraph.
  Breaking items also appear under their categorical section (`Removed`,
  `Changed`, etc.) — `Breaking Changes` is the alarm; the categorical
  sections are the record.

Do not add a `Removed` section unless something from a prior changelog
entry is being removed.

### Dual format — human + machine

Every release has two files in `changelog/`:

**`vX.Y.Z.md`** — human-readable entry following this guide.

**`vX.Y.Z.yaml`** — machine-readable migration spec consumed by `specdev align`.
Required when any schema field is added, removed, renamed, or type-changed, or
when a pipeline step is added or removed. Use `changes: []` for releases with
no schema changes.

Common change types (see [`changelog/format.yaml`](changelog/format.yaml) for
the authoritative list):
`add_field`, `remove_field`, `rename_field`, `change_type`, `add_constraint`,
`add_step`, `remove_step`, `rename_step`, `change_schema`, `paradigm_shift`.

Each change entry takes a `migration` block with an `action` of
`none`, `auto`, `ai_assisted`, `merge`, or `archive`:

```yaml
migration:
  action: auto          # Mechanical — applied automatically
  # action: ai_assisted # Requires an AI prompt to infer values
  # action: archive     # Unmappable data moved aside, not lost
  note: "Brief description of what to do"
```

### Validating the YAML

```bash
specdev changelog --validate <version>   # e.g. 1.0.0
```

Validates `changelog/v<version>.yaml` against `changelog/format.yaml` —
required fields, field types, semver `version` matching the filename,
no unknown top-level keys, and valid `change` types and `migration`
actions. Run before cutting a release.

### Release process

1. **Promote the unreleased files.** Copy `changelog/unreleased.md` to
   `changelog/vX.Y.Z.md` and `changelog/unreleased.yaml` to
   `changelog/vX.Y.Z.yaml`. In the YAML set `version: "X.Y.Z"` (was
   `"unreleased"`). Strip all ticket references and internal notes from both
   files following the Format rules above. Use `changes: []` if no schema
   changes were accumulated.
2. Add the new version to the Version Index table above.
3. Bump `version` in `tools/pyproject.toml` — the single source of truth.
4. Confirm no doc hardcodes the version — `CLAUDE.md` references
   `tools/pyproject.toml`; `docs/developers/getting_started.md` uses a
   `<current toolkit version>` placeholder.
5. Validate: `specdev changelog --validate X.Y.Z`.
6. Run the full test suite (`pytest tests/`).
7. Commit: `chore(release): vX.Y.Z`.
8. Tag `vX.Y.Z` and create a GitHub Release — release notes = the
   changelog entry for that version.
9. **Reset the unreleased files** for the next cycle. `changelog/unreleased.md`
   → `## [unreleased]`. `changelog/unreleased.yaml` → `version: "unreleased" /
   breaking: false / changes: []`.
