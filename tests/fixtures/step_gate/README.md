# Step gate fixtures

Deltas over the worked example (`tests/fixtures/graph_example`), applied at test time by
`tests/integration/_step_gate_support.py`.  A delta is a JSON file under `deltas/` with a `description` and a list of
`ops`: `append` (add `value` to the array at `path` of `file`, `create` makes the array when it is absent) and `write`
(a new file `file` holding `value`).  There is no second copy of the example here.
