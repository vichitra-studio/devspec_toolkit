# Step gate fixtures

Deltas over the worked example (`tests/fixtures/graph_example`), applied at test time by
`tests/integration/_step_gate_support.py`.  A delta is a JSON file under `deltas/` with a `description` and a list of
`ops`: `append` (add `value` to the array at `path` of `file`, `create` makes the array when it is absent), `write`
(a new file `file` holding `value`), `set` (put `value` at `path`: an object key, or an array position given as an integer) and
`remove` (delete the object key or array position at `path`).  A path is a list of object keys (strings) and array positions
(integers).  The variants of the graph checks are in `tests/fixtures/graph_checks/deltas/` (same format; `apply_delta(..., folder=GRAPH_CHECK_DELTAS)`).  There is no second copy of the example here.
