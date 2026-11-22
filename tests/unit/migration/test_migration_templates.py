"""The migration templates in prompts/migration/ (WI-M10-16a).

A template is the text an agent or a person follows in ONE step's judgement pass of a 1.1.1 to 1.2.0 migration: the item
kinds the mechanical scripts and the proposers leave for that step, the command that answers each, how an item is closed
and the step's check.  The tests pin facts, never wording:

* the files exist, are not empty, name their schema and the step-base fields, and render without an unresolved placeholder;
* every ``specdev`` line parses with the real parser of its command (flags included), a line with a ``<placeholder>`` after
  the placeholder is filled with a sample, and no line calls a retired command or reads or writes a spec file by hand;
* every error or warning code a template names is registered;
* the worklist kinds: every kind a template names is one a script or proposer writes (collected from the modules and from a run
  of the chain and the three proposers on a copy of the mini host), every kind written at step NN is named in step NN's
  template, and every kind there is is named somewhere;
* every field the "Shape in 1.2.0" sections name is a property of the step's schema.
"""

from __future__ import annotations

import contextlib
import importlib
import io
import json
import pkgutil
import re
import shlex
import warnings

import pytest

from specdev_tools.cli import build_parser
from specdev_tools.core.constants import REMOVED_COMMANDS, STEP_TO_TEMPLATE
from specdev_tools.core.errors import ERROR_CODES
from specdev_tools.core.json_utils import build_json_parser
from specdev_tools.generation.prompt_generator import PromptContext, render_template
from specdev_tools.graph.commands import build_node_parser
from specdev_tools.migration import proposers, runner
from specdev_tools.migration.scripts.v1_2_0 import p3_ordering
from specdev_tools.migration.worklist import WORKLIST_FILE
from specdev_tools.trace.id_write_commands import build_id_write_parser, is_id_write

from ._support import REAL_ROOT, make_host, make_toolkit

EXPECTED_TEMPLATES = [
    "template_capabilities.md",
    "template_charter.md",
    "template_ci_gates.md",
    "template_delivery_baseline.md",
    "template_extension_manifest.md",
    "template_fixtures.md",
    "template_frs.md",
    "template_glossary.md",
    "template_governance.md",
    "template_impl_coder.md",
    "template_impl_context.md",
    "template_impl_plan.md",
    "template_impl_planner.md",
    "template_impl_reviewer.md",
    "template_interfaces.md",
    "template_invariants.md",
    "template_nfrs.md",
    "template_redteam.md",
    "template_roadmap.md",
    "template_scaffold.md",
    "template_system_sketch.md",
]

STEP_OF_TEMPLATE = {template: step for step, template in STEP_TO_TEMPLATE.items()}
TEMPLATE_DIR = REAL_ROOT / "prompts" / "migration"
SAMPLES = {"stage": "dev", "NN": "04"}
CODE = re.compile(r"\b[EW]\d{3}\b")
INLINE_COMMAND = re.compile(r"`(specdev [^`]+)`")
KIND_ROW = re.compile(r"(?m)^\| `([a-z][a-z-]*)` \|")
FIELD = re.compile(r"`([a-z_][a-z0-9_]*)`")
# Fields a Shape section may name that are not properties of the step's schema (none today; a name goes here with its reason).
SHAPE_EXCEPTIONS: dict[str, set[str]] = {
    "template_delivery_baseline.md": {"log_level"},  # an example key of a `config` map, not a field of the schema
}


def _text(name: str) -> str:
    return (TEMPLATE_DIR / name).read_text(encoding="utf-8")


@pytest.fixture
def templates_dir(repo_root):
    """Return the migration templates directory."""
    return repo_root / "prompts" / "migration"


class TestAllTemplatesExist:
    """All expected template files exist on disk, and no other template is there."""

    def test_all_templates_exist(self, templates_dir):
        missing = [name for name in EXPECTED_TEMPLATES if not (templates_dir / name).exists()]
        assert missing == [], f"Missing template files: {missing}"

    def test_expected_count(self):
        assert len(EXPECTED_TEMPLATES) == 21

    def test_no_template_outside_the_list(self, templates_dir):
        assert sorted(p.name for p in templates_dir.glob("template_*.md")) == sorted(EXPECTED_TEMPLATES)

    def test_every_step_that_has_a_template_in_the_step_table_is_listed(self):
        assert sorted(STEP_TO_TEMPLATE.values()) == sorted(EXPECTED_TEMPLATES)


class TestTemplatesReadable:
    """Each template can be read without error."""

    @pytest.mark.parametrize("template_name", EXPECTED_TEMPLATES)
    def test_template_readable(self, templates_dir, template_name):
        path = templates_dir / template_name
        if not path.exists():
            pytest.skip(f"{template_name} does not exist")
        assert isinstance(path.read_text(encoding="utf-8"), str)


class TestNoEmptyTemplates:
    """No template file is empty."""

    @pytest.mark.parametrize("template_name", EXPECTED_TEMPLATES)
    def test_template_not_empty(self, templates_dir, template_name):
        path = templates_dir / template_name
        if not path.exists():
            pytest.skip(f"{template_name} does not exist")
        assert len(path.read_text(encoding="utf-8").strip()) > 0, f"{template_name} is empty"


class TestTemplateContentValidation:
    """Templates reference canonical schema URIs and metadata fields."""

    @pytest.mark.parametrize("template_name", EXPECTED_TEMPLATES)
    def test_templates_reference_canonical_schema_uri(self, templates_dir, template_name):
        path = templates_dir / template_name
        if not path.exists():
            pytest.skip(f"{template_name} does not exist")
        assert "vc:" in path.read_text(encoding="utf-8"), f"{template_name} does not reference canonical schema URI"

    @pytest.mark.parametrize("template_name", EXPECTED_TEMPLATES)
    def test_templates_include_metadata_fields(self, templates_dir, template_name):
        path = templates_dir / template_name
        if not path.exists():
            pytest.skip(f"{template_name} does not exist")
        assert "canonical_refs_used" in path.read_text(encoding="utf-8"), f"{template_name} does not mention canonical_refs_used"

    @pytest.mark.parametrize("template_name", EXPECTED_TEMPLATES)
    def test_schema_uris_are_registered(self, template_name):
        registry = json.loads((REAL_ROOT / "tools" / "schema_registry.json").read_text(encoding="utf-8"))
        uris = set(re.findall(r"`(vc:[0-9a-z-]+)`", _text(template_name).split("## Judgement pass")[0]))
        assert uris and uris <= set(registry), f"{template_name}: {sorted(uris - set(registry))}"

    @pytest.mark.parametrize("template_name", EXPECTED_TEMPLATES)
    def test_the_title_names_the_step_of_the_template(self, template_name):
        step = STEP_OF_TEMPLATE[template_name]
        assert re.search(rf"(?m)^# Migration: .*\(Step {step}\b", _text(template_name))

    @pytest.mark.parametrize("template_name", EXPECTED_TEMPLATES)
    def test_every_placeholder_is_one_the_renderer_fills(self, template_name):
        with warnings.catch_warnings(record=True) as seen:
            warnings.simplefilter("always")
            rendered = render_template(_text(template_name), PromptContext(source_version="1.1.1", target_version="1.2.0", step_id="04"))
        assert [str(w.message) for w in seen] == []
        assert "{{" not in rendered and rendered.startswith("<!-- Migration template: step 04, 1.1.1 to 1.2.0 -->")


# --- command lines ------------------------------------------------------------------------------------------------------


def _fill(line: str) -> str:
    return re.sub(r"<([^<>]+)>", lambda m: SAMPLES.get(m.group(1), "x"), line)


def command_lines(text: str) -> list[str]:
    """Every ``specdev ...`` line of a template: backticked spans anywhere (table cells included) and the lines of a code fence."""
    found = INLINE_COMMAND.findall(text)
    fenced = False
    for line in text.splitlines():
        if line.strip().startswith("```"):
            fenced = not fenced
        elif fenced and line.strip().startswith(("specdev ", "./tools/run_specdev.sh ")):
            found.append(line.strip().replace("./tools/run_specdev.sh ", "specdev ", 1))
    return found


def _parse(argv: list[str]) -> None:
    """Parse *argv* (the words after ``specdev``) with the real parser of its command; ``SystemExit`` says it does not parse."""
    if argv[0] == "json":
        words = argv[1:]
        (build_id_write_parser() if is_id_write(words) else build_json_parser()).parse_args(words)
    elif argv[0] == "node":
        build_node_parser().parse_args(argv[1:])
    else:
        build_parser().parse_args(argv)


def _fails_to_parse(line: str) -> str | None:
    err = io.StringIO()
    try:
        with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
            _parse(shlex.split(_fill(line))[1:])
    except SystemExit:
        return err.getvalue().strip().splitlines()[-1] if err.getvalue().strip() else "exit"
    return None


def test_every_template_has_command_lines():
    assert all(len(command_lines(_text(name))) >= 8 for name in EXPECTED_TEMPLATES)


@pytest.mark.parametrize("template_name", EXPECTED_TEMPLATES)
def test_every_command_line_parses_with_the_real_parser(template_name):
    bad = {line: why for line in command_lines(_text(template_name)) if (why := _fails_to_parse(line))}
    assert bad == {}


GROUPS_WITH_SUBCOMMANDS = {"align", "context", "json", "node", "step", "verify", "third-party", "plan", "review", "milestone", "release", "lock"}


def command_path(line: str) -> str:
    """The path ``tools/cli_commands.json`` lists for a ``specdev`` line: the command, and the sub-command or action of a group."""
    words = shlex.split(_fill(line))[1:]
    return " ".join(words[:2]) if words[0] in GROUPS_WITH_SUBCOMMANDS else words[0]


@pytest.mark.parametrize("template_name", EXPECTED_TEMPLATES)
def test_the_command_path_of_every_line_is_in_the_generated_command_list(template_name):
    listed = {entry["path"] for entry in json.loads((REAL_ROOT / "tools" / "cli_commands.json").read_text(encoding="utf-8"))["commands"]}
    assert {command_path(line) for line in command_lines(_text(template_name))} - listed == set()


def test_the_checker_refuses_a_line_that_does_not_parse():
    """The parse check can fail: a removed command, an unknown flag and a missing positional are each refused."""
    for line in ("specdev matrix spec", "specdev security spec", "specdev align triage spec --only 04", "specdev attest --nope", "specdev json patch --id x .a"):
        assert _fails_to_parse(line), line


def test_a_placeholder_is_filled_before_the_line_is_parsed():
    assert _fails_to_parse("specdev verify run <binding-id> --stage <stage>") is None
    assert _fails_to_parse("specdev verify run <binding-id> --stage nowhere")


@pytest.mark.parametrize("template_name", EXPECTED_TEMPLATES)
def test_the_step_of_a_step_flag_is_the_step_of_the_template(template_name):
    """``align triage --step`` and ``spec-check --step`` in a template name that template's own step."""
    step = STEP_OF_TEMPLATE[template_name]
    flags = [shlex.split(_fill(line)) for line in command_lines(_text(template_name))]
    named = [words[words.index("--step") + 1] for words in flags if "--step" in words and ("triage" in words or "spec-check" in words)]
    assert named and set(named) == {step}


@pytest.mark.parametrize("template_name", EXPECTED_TEMPLATES)
def test_no_template_calls_a_retired_command_or_touches_a_spec_file_by_hand(template_name):
    text = _text(template_name)
    retired = [name for name in (*REMOVED_COMMANDS, "validate-all", "security") if re.search(rf"\bspecdev\s+{re.escape(name)}\b", text)]
    assert retired == []
    assert "validate-all" not in text and "trace_matrix.json" not in text and "run_specdev.sh" not in text
    shell = [
        line for line in text.splitlines()
        if re.match(r"\s*(cat|jq|sed|awk|tee|vim|nano|echo|cp|mv|rm|touch)\s", line) or re.search(r"\s>>?\s*spec/", line)
    ]
    assert shell == []


@pytest.mark.parametrize("template_name", EXPECTED_TEMPLATES)
def test_no_template_names_a_field_or_file_1_2_0_retired_as_if_it_were_current(template_name):
    """``matrix`` (the stored trace matrix) and ``fr_refs`` are named nowhere; ``execution_results`` only where a template says an open plan lost it."""
    text = _text(template_name)
    assert not re.search(r"\bmatrix\b|\bfr_refs\b", text)
    for line in (l for l in text.splitlines() if "execution_results" in l):
        assert template_name == "template_impl_coder.md" and "lost its old progress fields" in line


@pytest.mark.parametrize("template_name", EXPECTED_TEMPLATES)
def test_the_proposers_are_run_before_the_step_pass(template_name):
    """``refines``, ``prose-ids`` and ``legacy-*`` items exist only after ``align propose``: every template's first step runs the three proposers."""
    lines = [shlex.split(_fill(line)) for line in command_lines(_text(template_name))]
    kinds = {words[words.index("--kind") + 1] for words in lines if words[1:3] == ["align", "propose"]}
    assert kinds == set(proposers.KINDS)


@pytest.mark.parametrize("template_name", EXPECTED_TEMPLATES)
def test_every_code_a_template_names_is_registered(template_name):
    unknown = sorted({code for code in CODE.findall(_text(template_name)) if code not in ERROR_CODES})
    assert unknown == []


# --- worklist kinds -----------------------------------------------------------------------------------------------------


def _static_kinds() -> set[str]:
    """The item kinds the modules declare: the ``KIND`` / ``KIND_*`` constants of the scripts, and the proposers' four."""
    import specdev_tools.migration.scripts.v1_2_0 as scripts

    kinds: set[str] = set()
    for info in pkgutil.iter_modules(scripts.__path__):
        module = importlib.import_module(f"{scripts.__name__}.{info.name}")
        kinds |= {value for name, value in vars(module).items() if re.fullmatch(r"KIND(_[A-Z0-9_]+)?", name) and isinstance(value, str)}
    refines = importlib.import_module("specdev_tools.migration.proposers.refines")
    prose = importlib.import_module("specdev_tools.migration.proposers.prose_ids")
    bindings = importlib.import_module("specdev_tools.migration.proposers.bindings")
    return kinds | {refines.KIND_REFINES, prose.KIND_PROSE_IDS, bindings.KIND_GROUP, bindings.KIND_FIXTURE}


@pytest.fixture(scope="module")
def written(tmp_path_factory) -> set[tuple[str, str]]:
    """``(step, kind)`` of every item the chain and the three proposers write on a git copy of the mini host (a temp 1.2.0 toolkit root)."""
    tmp = tmp_path_factory.mktemp("kinds")
    toolkit, host = make_toolkit(tmp), make_host(tmp)
    report = runner.run_migration(host / "spec", toolkit_root=toolkit, git_root=host)
    assert report.status == "ok", report.errors
    for kind in proposers.KINDS:
        proposers.propose(host / "spec", kind=kind, toolkit_root=REAL_ROOT, git_root=host, dry_run=False)
    items = json.loads((host / "spec" / WORKLIST_FILE).read_text(encoding="utf-8"))["items"]
    return {(item["step"], item["kind"]) for item in items}


def named_kinds(template_name: str) -> set[str]:
    return set(KIND_ROW.findall(_text(template_name).split("## Judgement pass", 1)[1].split("### Procedure", 1)[0]))


def test_the_mini_host_run_writes_kinds_at_many_steps(written):
    assert len({step for step, _ in written}) >= 15 and len({kind for _, kind in written}) >= 30


@pytest.mark.parametrize("template_name", EXPECTED_TEMPLATES)
def test_every_kind_a_template_names_is_one_a_script_or_proposer_writes(template_name, written):
    real = _static_kinds() | {kind for _, kind in written}
    assert named_kinds(template_name) - real == set()


@pytest.mark.parametrize("template_name", EXPECTED_TEMPLATES)
def test_every_kind_written_at_a_step_is_named_in_the_template_of_that_step(template_name, written):
    step = STEP_OF_TEMPLATE[template_name]
    assert {kind for s, kind in written if s == step} - named_kinds(template_name) == set()


def test_every_kind_there_is_is_named_in_a_template(written):
    named = set().union(*(named_kinds(name) for name in EXPECTED_TEMPLATES))
    assert (_static_kinds() | {kind for _, kind in written}) - named == set()


def test_a_kind_named_for_one_step_is_written_at_that_step(written):
    """A kind in a step's own table (not the any-step table) is written at that step, or is a kind whose step the data decides."""
    common = set.intersection(*(named_kinds(name) for name in EXPECTED_TEMPLATES))
    by_kind: dict[str, set[str]] = {}
    for step, kind in written:
        by_kind.setdefault(kind, set()).add(step)
    # p3_ordering writes the step of the first FR or API a pair names (04, 05) and 09 when nothing is known.
    by_kind.setdefault("milestone-order", set()).update(set(p3_ordering._STEP_OF_KIND.values()) | {"09"})
    wrong = {
        (STEP_OF_TEMPLATE[name], kind)
        for name in EXPECTED_TEMPLATES
        for kind in named_kinds(name) - common
        if kind in by_kind and STEP_OF_TEMPLATE[name] not in by_kind[kind]
    }
    assert wrong == set()


def test_the_any_step_table_is_the_same_in_every_template():
    rows = {name: sorted(named_kinds(name) & set.intersection(*(named_kinds(n) for n in EXPECTED_TEMPLATES))) for name in EXPECTED_TEMPLATES}
    assert len({tuple(r) for r in rows.values()}) == 1 and len(next(iter(rows.values()))) >= 8


# --- shape ----------------------------------------------------------------------------------------------------------------


def _properties(uri: str) -> set[str]:
    """Every property name of a schema, through ``$ref`` and every composition branch."""
    registry = json.loads((REAL_ROOT / "tools" / "schema_registry.json").read_text(encoding="utf-8"))
    cache: dict[str, dict] = {}

    def load(base: str) -> dict:
        if base not in cache:
            cache[base] = json.loads((REAL_ROOT / registry[base]).read_text(encoding="utf-8"))
        return cache[base]

    names: set[str] = set()
    seen: set[tuple[str, str]] = set()

    def walk(node, doc: dict, base: str) -> None:
        if isinstance(node, list):
            for item in node:
                walk(item, doc, base)
        elif isinstance(node, dict):
            ref = node.get("$ref")
            if isinstance(ref, str):
                target_base, _, fragment = ref.partition("#")
                target_base = target_base or base
                if (target_base, fragment) not in seen:
                    seen.add((target_base, fragment))
                    target_doc = load(target_base)
                    target = target_doc
                    for part in (p for p in fragment.split("/") if p):
                        target = target[part] if part in target else target.get("$defs", {}).get(part, target.get("definitions", {}).get(part, {}))
                    walk(target, target_doc, target_base)
            for key, value in node.items():
                if key == "properties" and isinstance(value, dict):
                    for name, sub in value.items():
                        names.add(name)
                        walk(sub, doc, base)
                elif key == "required" and isinstance(value, list):
                    names.update(x for x in value if isinstance(x, str))
                elif key != "$ref":
                    walk(value, doc, base)

    walk(load(uri), load(uri), uri)
    return names


def _shape_sections(text: str) -> list[tuple[str, str]]:
    """``(schema uri, section text)`` of each '## Shape in 1.2.0' section; the anchor's section names the anchor schema."""
    out = []
    for match in re.finditer(r"(?ms)^## Shape in 1\.2\.0( \((?P<label>[^)]*)\))?\n(?P<body>.*?)(?=^## |\Z)", text):
        out.append((match.group("label") or "", match.group("body")))
    return out


@pytest.mark.parametrize("template_name", EXPECTED_TEMPLATES)
def test_every_field_a_shape_section_names_is_a_property_of_the_schema(template_name):
    text = _text(template_name)
    sections = _shape_sections(text)
    if not sections:
        pytest.skip("this template keeps the older field lists of steps 00 to 05, checked by the next test")
    uri = re.search(r"`(vc:[0-9a-z-]+)`", text).group(1)
    unknown: set[str] = set()
    for label, body in sections:
        schema_uri = "vc:16-anchor" if label == "anchor" else uri if label != "milestone plan" else "vc:16-impl-context"
        known = _properties(schema_uri) | SHAPE_EXCEPTIONS.get(template_name, set())
        listed = [line for line in body.splitlines() if line.startswith("- `")]
        unknown |= {name for line in listed for name in FIELD.findall(line) if name not in known}
    assert unknown == set()


@pytest.mark.parametrize("template_name", [n for n in EXPECTED_TEMPLATES if STEP_OF_TEMPLATE[n] in ("00", "01", "02", "02a", "03", "04", "05")])
def test_the_field_lists_of_steps_00_to_05_name_fields_of_their_schema(template_name):
    """The bullets of 'Required Changes' name fields the step's schema has, except the 1.1.1 names a bullet says it replaces."""
    text = _text(template_name)
    uri = re.search(r"`(vc:[0-9a-z-]+)`", text).group(1)
    known = _properties(uri)
    body = re.search(r"(?ms)^## Required Changes\n(.*?)(?=^## )", text).group(1)
    unknown = set()
    for line in body.splitlines():
        if not line.lstrip().startswith("- "):
            continue
        replaced = set(FIELD.findall(line.split("Replaces", 1)[1])) if "Replaces" in line else set()
        names = FIELD.findall(line.split("Replaces", 1)[0])
        # the field a bullet is about (its first name) and any name with an underscore; a bare word later in the bullet is an enum value
        fields = {n for i, n in enumerate(names) if i == 0 or "_" in n}
        unknown |= {n for n in fields if n not in known and n not in replaced and n not in SHAPE_EXCEPTIONS.get(template_name, set())}
    assert unknown == set()


def test_open_item_rows_say_the_merge_check_wants_the_item_deleted() -> None:
    """A row that offers an `about` or raising an item again says E631 and the deletion: neither finishes the migration."""
    for name in ("template_impl_context.md", "template_impl_coder.md", "template_impl_planner.md"):
        rows = [line for line in _text(name).splitlines() if re.match(r"\| `(ambiguity-about|anchor-open-item|legacy-open-item|duplicate-promoted-item)`", line)]
        assert rows, name
        for row in rows:
            assert "E631" in row, row
    assert "json delete --id <item-id>" in _text("template_impl_context.md")


def test_status_conflict_row_reopens_in_the_1_1_1_spec() -> None:
    """A milestone closed by mistake is reopened by undoing the migration and correcting the 1.1.1 sources, not in the migrated spec."""
    row = next(line for line in _text("template_roadmap.md").splitlines() if line.startswith("| `status-conflict`"))
    assert "git revert" in row and "align apply spec --auto" in row and ".review.verdict" in row
    assert "delete the row's `close`" not in row


def test_connection_external_rows_patch_the_first_destination() -> None:
    """A connection with no `connects_to` takes its first destination by `json patch`: `json insert` refuses there (E767)."""
    rows = [line for line in _text("template_system_sketch.md").splitlines() if line.startswith(("| `external-dependency`", "| `connection-external`"))]
    assert len(rows) == 2
    assert all(".connects_to '[\"<third-party-id>\"]'" in row for row in rows)
