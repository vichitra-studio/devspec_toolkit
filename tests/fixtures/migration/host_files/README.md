# Host files for the p7 host-file report (invented)

Overlays copied onto a git copy of `../mini_host_1_1_1` by `tests/unit/migration/test_host_files.py`. The mini host already
carries `spec_validation.yml` (`validate-all` on line 11, `matrix` on line 12) and a clean `.pre-commit-config.yaml`; the
overlays add the shapes it lacks.

| Folder | File | Shape |
|---|---|---|
| `retired/` | `.pre-commit-config.yaml` | the wrapper form (`./tools/run_specdev.sh matrix`, line 6); a command inside a longer line (`bash -c "specdev traceability-check ..."`, line 10); a commented line that is NOT reported (line 12); a command on the line after a backslash (lines 15 to 16: the detector misses it, pinned as it is today); `dag-lint` (not retired); a clean `spec-check` hook |
| `retired/` | `.github/workflows/ci.yml` | `validate-all` (line 12); `matrix` and `trace_matrix.json` on one line (line 13); a `matrix:` job strategy (not a command); a commented retired command; `dag-lint` and `spec-check` (not reported); the install step `npm ci` (line 11) |
| `pins/` | `package-lock.json` | one package, `argon2` at 0.41.1 (the pointer `/packages/node_modules~1argon2/version`) |
| `pins/` | `.github/workflows/build.yml` | the toolkit's own install (left out of the setup evidence), `npm ci --ignore-scripts`, `npm test` |
