# legacy_bindings

Invented files for the tests of the legacy binding pass (`align propose --kind bindings`, `align bind-legacy`). Nothing
here comes from a real host.

`ci/` is copied over a git copy of `mini_host_1_1_1` (the folder's own files are never changed): a host CI workflow whose
test lines name a word of a fixture that no plan item gives a command (`fix-return-closes-loan`: `pytest
tests/test_return.py -q`), a line the plans already name (`npx jest tests/fee.spec.ts`) and a line of the toolkit's own
(`specdev spec-check`, which the proposer ignores), and the test file the first one names.
