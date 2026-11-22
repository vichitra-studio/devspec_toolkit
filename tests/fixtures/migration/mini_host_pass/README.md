# mini_host_pass

The scripted judgement pass of the invented mini host (`../mini_host_1_1_1/`, "Lantern Lending"). Every answer here is
invented content about that invented host; nothing comes from a real host.

| File | What it holds |
|---|---|
| `pass.json` | the steps in the generated order (00, 01, 02, 02a, 04 ... 16a). A step is a list of commands, written as the arguments a person gives `specdev` (`json patch --id`, `json insert --id|--step`, `attest --step NN --yes`, `canonical-autofix`); `{spec}` stands for the spec folder. An object is an operation on a file of the host OUTSIDE `spec/`: `write_file`, `replace`, `commit` |
| `resolutions.json` | one note per worklist item of the mechanical stage (`align triage --resolve ID --note TEXT`): what was decided or done. The test checks that the keys are exactly the item ids, so a new item (or a vanished one) turns the test red |

`tests/integration/test_migration_then_merge_mode.py` runs it once per session on a tmp git copy of the mini host, after
`align apply --auto`, then `spec-check --merge` (zero errors) and `align validate` (exit 0).

How a careful person would have answered, in one line each: a link goes to the node the text is about (a scope item to the
need it serves, a capability to the segment and scope item, an API error to the criterion that makes it happen); two
wrong baseline links (a capability that derived from the checkout-time metric) were replaced before they were attested (`attest --step NN --yes` accepts what is left); a text that was
only a command name became one sentence; an open item got its answer written into the spec text and was then deleted; an
item the old data could not answer got a reason or a deferral (`disposition: deferred`, `scope_reason`), never a blanket
`not_applicable`; frozen plans are not touched (their items are closed with a note only).

To change an answer, edit `pass.json`; run the test; `specdev spec-check --step NN` says which step an answer broke.
