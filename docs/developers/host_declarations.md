# Host declarations

`spec/common/host_declarations.json` holds what only the host repository knows and the toolkit cannot derive: the pattern of its release tags, the command that prepares a clean checkout, the paths its code-tree id leaves out, and where its files declare the version of each third party. The file is optional. A host without it works as before: every item is empty, and a command that needs an item says so itself.

The file is written by hand. Its shape is `schema/host_declarations.schema.json` (`$schema` `vc:host-declarations`); that file is the source for what each key accepts. `spec-check` validates the file like any other spec file (E520 for a value of the wrong shape). One reader, `load_host_declarations` in `tools/specdev_tools/core/host_declarations.py`, serves every command.

## The four items

| Item | What it declares | Read today by |
|------|------------------|---------------|
| `release_tag_pattern` | The regular expression a git tag must match to count as a release tag | No command yet; the release gates of milestone M9 read it |
| `setup_command` | The command that prepares a clean checkout to run verification commands | No command yet; the gates of milestone M9 read it |
| `code_tree_exclusions` | Git pathspecs left out of the code-tree id, so a change under them does not make recorded evidence stale | `specdev verify run` (the tree it records and compares, W351); `specdev third-party check --installed` (the tree its install-check record names) |
| `pin_sources` | Where the repository declares the version of a third party, keyed by the id of its third-party node: a `json-pointer` into a JSON file, or a `regex` with one capture group over a text file | `specdev third-party check` (E337, E338); `specdev verify run` (the `installed_versions` it records) |

An item no command reads yet is still validated, so a mistake in it is found now and not at the first gate that needs it.

`code_tree_exclusions` is for what is not the product's own code: the toolkit submodule path, generated report folders. A source folder of the product does not belong there, because evidence would then outlive a change to the code. A path that a run writes into and that is not ignored gives W351 (see its entry in [error-codes.md](error-codes.md)); add the path here or to `.gitignore`.

`pin_sources` lists, for a third party, every place that must equal the node's `pin`. A third party with no entry is not checked, and it gets no stale-version check either: after a pin bump the evidence of a binding that relies on it is never `STALE_TP_VERSION` (run on the declarations fixture with the entry of `tp-argon2` removed: a bound record run once, then `third-party pin tp-argon2 0.42.0`, and `proof_errors` returned nothing). A key that names no third-party node is E338. A `regex` source is matched with MULTILINE, as the output guard of a binding is: `^` and `$` match at the start and end of each line (`^version = "(.*)"$` read `0.41.1` from a line of a `pkg.toml`, and `third-party check` printed `every pin matches its declared sources`).

## Example

The fixture `tests/fixtures/host_declarations/` holds a declarations file and the repository files its sources read. Copied into a git copy of the worked example (`tests/fixtures/graph_example`), the file is:

```json
{
  "$schema": "vc:host-declarations",
  "release_tag_pattern": "^v[0-9]+\\.[0-9]+\\.[0-9]+$",
  "setup_command": "npm ci",
  "code_tree_exclusions": ["devspec_toolkit", "test-results/"],
  "pin_sources": {
    "tp-argon2": [
      { "type": "json-pointer", "file": "package-lock.json", "pointer": "/packages/node_modules~1argon2/version" }
    ],
    "tp-mailrelay": [
      { "type": "regex", "file": "src/mail/client.ts", "pattern": "MAILRELAY_API_VERSION = \"(api-v[0-9]+)\"" },
      { "type": "regex", "file": "src/mail/client.ts", "pattern": "X-Api-Version: (api-v[0-9]+)" }
    ]
  }
}
```

Both pins of the example (`tp-argon2` at `0.41.1`, `tp-mailrelay` at `api-v3`) equal what these sources read, so `specdev third-party check` prints `every pin matches its declared sources`. With `package-lock.json` changed to `0.42.0` it prints E337 and exits 1; the entry of E337 in [error-codes.md](error-codes.md) shows the message and the ways out.

## Getting the file

No command installs the file in this release. A host that wants it copies `templates/host_declarations.host.json` to `spec/common/host_declarations.json` and edits it: the template has the four keys, with the toolkit submodule path already listed in `code_tree_exclusions` (a toolkit version bump should not make the product's evidence stale) and an empty `pin_sources`. Installing the template by `init_project.py` and `update` is milestone M9's.

Nothing has to be done for a host that does not use the file.
