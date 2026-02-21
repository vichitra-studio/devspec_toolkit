# Batch B0 Baseline Lock

Date (UTC): 2026-02-21T16:33:43Z
Repo: `/Users/vichitracollective/vc-code/vc_wesbite`
Toolkit: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit`

## Scope Lock
- Active spec directory: `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/spec`
- Repository root spec directory `/Users/vichitracollective/vc-code/vc_wesbite/spec` is absent in this workspace.

## Runtime Lock
- Canonical execution entrypoint in host repo: `./tools/run_specdev.sh ... --repo-root ./devspec_toolkit`
- Direct `python -m specdev_tools.cli ...` is not assumed valid in host shell context.

## Baseline Command Results
All commands executed from `/Users/vichitracollective/vc-code/vc_wesbite`.

1. CLI availability
```bash
./tools/run_specdev.sh --help
```
Result: PASS

2. Schema validation
```bash
./tools/run_specdev.sh validate-all devspec_toolkit/spec --repo-root ./devspec_toolkit
```
Result: PASS (`OK`)

3. Fixture lint
```bash
./tools/run_specdev.sh fixtures-lint devspec_toolkit/spec --repo-root ./devspec_toolkit
```
Result: PASS (`OK`)

4. Trace matrix generation
```bash
./tools/run_specdev.sh matrix devspec_toolkit/spec --repo-root ./devspec_toolkit --out devspec_toolkit/tools/trace_matrix.json
```
Result: PASS (`devspec_toolkit/tools/trace_matrix.json` generated)

5. Seed lint
```bash
./tools/run_specdev.sh seed-lint devspec_toolkit/spec --repo-root ./devspec_toolkit
```
Result: PASS (`OK`)

6. Docs lint
```bash
./tools/run_specdev.sh docs-lint devspec_toolkit/spec --repo-root ./devspec_toolkit
```
Result: PASS (`OK`)

## B0 Exit Criteria
- [x] baseline command log captured
- [x] active `spec_dir` fixed for this repo

## Next Batch
- Proceed to `B1` per execution sequence in:
  - `/Users/vichitracollective/vc-code/vc_wesbite/devspec_toolkit/docs/audit/review_report_04_canonical_drift_and_implementation_plan.md`
