# Contributing

Thanks for your interest in improving the **AI Spec Driven Development Toolkit**. This document explains how to propose changes.

## Ground rules

- This repository uses a **fork-based** workflow. Only the maintainer has write access; all external contributions arrive as pull requests from forks.
- The default branch `main` is protected: every change requires a pull request, passing CI, and maintainer (code-owner) review.
- The **release cycle is managed solely by the maintainer**. Please do not open PRs that bump the version or create release branches/tags.

## Workflow

1. **Fork** the repository to your own account.
2. **Clone** your fork and create a topic branch:
   ```bash
   git clone https://github.com/<your-username>/devspec_toolkit.git
   cd devspec_toolkit
   git checkout -b my-change
   ```
3. **Set up the environment** (see [docs/developers/getting_started.md](docs/developers/getting_started.md) for full details):
   ```bash
   python3 -m venv devspec_env
   source devspec_env/bin/activate
   pip install -r tools/requirements.txt
   pip install -e ./tools
   ```
4. **Make your change.** Keep it focused — one logical change per pull request.
5. **Validate locally** before pushing:
   ```bash
   pytest tests/                       # full test suite
   specdev spec-check spec             # if you changed spec artifacts
   /devspec_pr_audit                   # toolkit drift audit (run in Claude Code)
   ```
6. **Push** to your fork and **open a pull request** against `main`. Fill out the pull request template.

## Spec-driven workflow

This toolkit is itself spec-driven, and the pipeline is a **forward-only waterfall**: any upstream edit (steps `00`–`16`) requires replaying every downstream step. Never fix a downstream failure by silently rewriting an upstream artifact. See [CLAUDE.md](CLAUDE.md) and [docs/developers/reference.md](docs/developers/reference.md) for the full command catalog and conventions.

## Commit messages

Use conventional-commit prefixes (`feat:`, `fix:`, `docs:`, `chore:`, `test:`). Commit-message governance is enforced by `specdev governance-check`.

## Reporting bugs, requesting features, asking questions

Use the GitHub issue templates (Bug Report, Feature Request, Question). For **security vulnerabilities**, follow [SECURITY.md](.github/SECURITY.md) — do not open a public issue.

## Code of conduct

Be respectful and constructive. Harassment, abuse, or discrimination will not be tolerated.
