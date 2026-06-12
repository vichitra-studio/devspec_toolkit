## [unreleased]

### Fixed

- **Removed orphaned host-coupled integration test `test_matrix_registry_refactor.py`.**
  `TestMatrixRegistryRefactorGolden` reached out of the toolkit submodule into
  the host repo's `spec/` directory and depended on a golden fixture
  (`tests/fixtures/trace_matrix_pre_refactor.json`) deleted in commit 99afe72.
  This caused a permanent "golden missing" failure on every CI run. The two
  non-golden methods were byte-identical duplicates of assertions already present
  in the self-contained `TestMatrixSpecCorpus` (corpus test). Coverage is fully
  retained in `tests/integration/test_matrix_spec_corpus.py`.
