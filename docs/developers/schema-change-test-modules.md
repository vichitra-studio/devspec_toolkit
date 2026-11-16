# Schema-change test modules (M3 checklist)

This is the checklist of test modules and fixture directories under `tests/` that mention a token removed, renamed or changed in meaning by the M3 schema changes, grouped by the work item that changes the token. It was produced by the script at the end of this file (term lists from the field-fate table of the M3 pack, section 3.3), run over `tests/` with `.worktrees/`, `WIP/` and `tests/fixtures/schema_baseline/` excluded; it is a checklist to tick off, not a count.

Re-run: `awk '/^```python$/{f=1;next} /^```$/{f=0} f' docs/developers/schema-change-test-modules.md > "$TMPDIR/scm.py" && python3 "$TMPDIR/scm.py"` from the repo root; the output replaces the sections below.

Matching rules: whole-word, case-sensitive; the ordinary-English terms (`trace`, `links`, `requires`, `dependencies`, `targets`, `mitigations`, `reviewers`, `assumptions`, `deliverables`, `method`) count only as a quoted key, a `.term` path or a `term:` key. Files under `tests/fixtures/` are listed by their first directory; `tests/fixtures/step_NN/` appears only under the work items of step NN. A hit means the token appears, not that the module must change. `tests/integration/test_step_scripts_bridge.py` is listed under every step whose fixtures it pins. The field-fate table lists no removed token for steps 13 and 13a. Items are listed under the work item that removes the token, so a module hit by several work items appears under each.

## WI-M3-03: ambiguity item, all steps

Terms: `crossCycleAmbiguityItem`, `ambiguityStatus`, `emergent_ambiguities`

- [ ] `tests/fixtures/analysis/`: `crossCycleAmbiguityItem`, `emergent_ambiguities`
- [ ] `tests/fixtures/step_16/`: `emergent_ambiguities`
- [ ] `tests/integration/analysis/test_upstream_backlog_cli.py`: `crossCycleAmbiguityItem`, `emergent_ambiguities`
- [ ] `tests/integration/test_step_16.py`: `crossCycleAmbiguityItem`, `emergent_ambiguities`
- [ ] `tests/unit/analysis/test_classification.py`: `emergent_ambiguities`
- [ ] `tests/unit/analysis/test_coerce.py`: `emergent_ambiguities`
- [ ] `tests/unit/context/test_milestone_state.py`: `emergent_ambiguities`
- [ ] `tests/unit/generation/test_schema_contracts.py`: `crossCycleAmbiguityItem`
- [ ] `tests/unit/validation/linters/test_e541_structural_skip.py`: `emergent_ambiguities`

## WI-M3-04: step 06 invariants

Terms: `trace`

- [ ] `tests/fixtures/entry_key_registry/`: `trace`
- [ ] `tests/fixtures/spec_corpus/`: `trace`
- [ ] `tests/fixtures/step_06/`: `trace`
- [ ] `tests/integration/test_matrix_spec_corpus.py`: `trace`
- [ ] `tests/integration/test_step_13a.py`: `trace`
- [ ] `tests/integration/test_step_16.py`: `trace`
- [ ] `tests/integration/test_step_scripts_bridge.py`: pins step_06/ fixtures
- [ ] `tests/unit/canonical/test_canonical_integrity_drift.py`: `trace`
- [ ] `tests/unit/context/test_reviewer.py`: `trace`
- [ ] `tests/unit/core/test_entry_key_registry.py`: `trace`
- [ ] `tests/unit/core/test_resolve_pointers.py`: `trace`
- [ ] `tests/unit/generation/test_prompt_schema_sync.py`: `trace`
- [ ] `tests/unit/registry/test_annotation_schema.py`: `trace`
- [ ] `tests/unit/registry/test_generate.py`: `trace`
- [ ] `tests/unit/test_cli.py`: `trace`
- [ ] `tests/unit/test_spec_dir_walker.py`: `trace`
- [ ] `tests/unit/validation/linters/test_hallucination_lint.py`: `trace`
- [ ] `tests/unit/validation/linters/test_invariants.py`: `trace`
- [ ] `tests/unit/validation/linters/test_invariants_cel.py`: `trace`
- [ ] `tests/unit/validation/linters/test_linter_utils.py`: `trace`
- [ ] `tests/unit/validation/linters/test_matrix_rules.py`: `trace`
- [ ] `tests/unit/validation/linters/test_registry_check.py`: `trace`
- [ ] `tests/unit/validation/linters/test_traceability_closure.py`: `trace`
- [ ] `tests/unit/validation/test_legacy_shim.py`: `trace`
- [ ] `tests/unit/validation/validators/test_cross_artifact_checks.py`: `trace`
- [ ] `tests/unit/validation/validators/test_cross_step_validation.py`: `trace`
- [ ] `tests/unit/validation/validators/test_r9_cross_step.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_10_deep.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_11_deep.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_validators_03_10.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_validators_core.py`: `trace`

## WI-M3-05: step 07 NFRs

Terms: `trace`

- [ ] `tests/fixtures/entry_key_registry/`: `trace`
- [ ] `tests/fixtures/spec_corpus/`: `trace`
- [ ] `tests/fixtures/step_07/`: `trace`
- [ ] `tests/integration/test_matrix_spec_corpus.py`: `trace`
- [ ] `tests/integration/test_step_13a.py`: `trace`
- [ ] `tests/integration/test_step_16.py`: `trace`
- [ ] `tests/integration/test_step_scripts_bridge.py`: pins step_07/ fixtures
- [ ] `tests/unit/canonical/test_canonical_integrity_drift.py`: `trace`
- [ ] `tests/unit/context/test_reviewer.py`: `trace`
- [ ] `tests/unit/core/test_entry_key_registry.py`: `trace`
- [ ] `tests/unit/core/test_resolve_pointers.py`: `trace`
- [ ] `tests/unit/generation/test_prompt_schema_sync.py`: `trace`
- [ ] `tests/unit/registry/test_annotation_schema.py`: `trace`
- [ ] `tests/unit/registry/test_generate.py`: `trace`
- [ ] `tests/unit/test_cli.py`: `trace`
- [ ] `tests/unit/test_spec_dir_walker.py`: `trace`
- [ ] `tests/unit/validation/linters/test_hallucination_lint.py`: `trace`
- [ ] `tests/unit/validation/linters/test_invariants.py`: `trace`
- [ ] `tests/unit/validation/linters/test_invariants_cel.py`: `trace`
- [ ] `tests/unit/validation/linters/test_linter_utils.py`: `trace`
- [ ] `tests/unit/validation/linters/test_matrix_rules.py`: `trace`
- [ ] `tests/unit/validation/linters/test_registry_check.py`: `trace`
- [ ] `tests/unit/validation/linters/test_traceability_closure.py`: `trace`
- [ ] `tests/unit/validation/test_legacy_shim.py`: `trace`
- [ ] `tests/unit/validation/validators/test_cross_artifact_checks.py`: `trace`
- [ ] `tests/unit/validation/validators/test_cross_step_validation.py`: `trace`
- [ ] `tests/unit/validation/validators/test_r9_cross_step.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_10_deep.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_11_deep.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_validators_03_10.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_validators_core.py`: `trace`

## WI-M3-06: step 08 fixtures

Terms: `targets`, `out_of_scope`

- [ ] `tests/fixtures/entry_key_registry_golden.json`: `out_of_scope`
- [ ] `tests/fixtures/entry_key_registry_pre_m1.json`: `out_of_scope`
- [ ] `tests/fixtures/spec_corpus/`: `targets`
- [ ] `tests/fixtures/step_08/`: `out_of_scope`, `targets`
- [ ] `tests/integration/test_step_scripts_bridge.py`: pins step_08/ fixtures
- [ ] `tests/unit/generation/test_schema_differ.py`: `out_of_scope`
- [ ] `tests/unit/registry/test_generate.py`: `out_of_scope`
- [ ] `tests/unit/test_cli.py`: `out_of_scope`
- [ ] `tests/unit/validation/linters/test_fixtures_lint.py`: `targets`
- [ ] `tests/unit/validation/linters/test_matrix_rules.py`: `out_of_scope`, `targets`
- [ ] `tests/unit/validation/linters/test_traceability_closure.py`: `out_of_scope`, `targets`
- [ ] `tests/unit/validation/validators/test_cross_step_validation.py`: `out_of_scope`, `targets`
- [ ] `tests/unit/validation/validators/test_r9_cross_step.py`: `targets`
- [ ] `tests/unit/validation/validators/test_step_10_deep.py`: `targets`
- [ ] `tests/unit/validation/validators/test_step_validators_core.py`: `targets`

## WI-M3-07: step 09 impl plan

Terms: `deliverables`, `tech_stack`, `tech_stack_ref`, `trace`, `depends_on`, `dependencies`, `dependency_ref`

- [ ] `tests/fixtures/entry_key_registry/`: `deliverables`, `trace`
- [ ] `tests/fixtures/entry_key_registry_golden.json`: `dependencies`, `depends_on`
- [ ] `tests/fixtures/entry_key_registry_pre_m1.json`: `dependencies`
- [ ] `tests/fixtures/graph/`: `depends_on`
- [ ] `tests/fixtures/spec_corpus/`: `deliverables`, `dependencies`, `trace`
- [ ] `tests/fixtures/step_09/`: `deliverables`, `dependencies`, `depends_on`, `tech_stack`, `trace`
- [ ] `tests/integration/test_matrix_spec_corpus.py`: `trace`
- [ ] `tests/integration/test_step_04.py`: `depends_on`
- [ ] `tests/integration/test_step_13a.py`: `trace`
- [ ] `tests/integration/test_step_14.py`: `deliverables`, `tech_stack`
- [ ] `tests/integration/test_step_16.py`: `trace`
- [ ] `tests/integration/test_step_16_anchor.py`: `deliverables`
- [ ] `tests/integration/test_step_scripts_bridge.py`: pins step_09/ fixtures
- [ ] `tests/unit/canonical/test_canonical_integrity_drift.py`: `trace`
- [ ] `tests/unit/context/test_reviewer.py`: `trace`
- [ ] `tests/unit/context/test_reviewer_seed_distillation.py`: `tech_stack`
- [ ] `tests/unit/core/test_entry_key_registry.py`: `deliverables`, `dependencies`, `trace`
- [ ] `tests/unit/core/test_merge_allof_preservation.py`: `tech_stack`, `tech_stack_ref`
- [ ] `tests/unit/core/test_resolve_pointers.py`: `deliverables`, `dependencies`, `trace`
- [ ] `tests/unit/generation/test_prompt_schema_sync.py`: `dependencies`, `trace`
- [ ] `tests/unit/generation/test_schema_contracts.py`: `dependencies`, `tech_stack`
- [ ] `tests/unit/registry/test_annotation_scan.py`: `depends_on`
- [ ] `tests/unit/registry/test_annotation_schema.py`: `depends_on`, `trace`
- [ ] `tests/unit/registry/test_annotations.py`: `depends_on`
- [ ] `tests/unit/registry/test_generate.py`: `deliverables`, `dependencies`, `trace`
- [ ] `tests/unit/registry/test_step_order_gen.py`: `depends_on`
- [ ] `tests/unit/test_cli.py`: `dependencies`, `dependency_ref`, `tech_stack`, `tech_stack_ref`, `trace`
- [ ] `tests/unit/test_spec_dir_walker.py`: `trace`
- [ ] `tests/unit/test_update_command.py`: `dependencies`
- [ ] `tests/unit/toolkit_invariants/test_m2_graph_declarations.py`: `depends_on`
- [ ] `tests/unit/validation/linters/test_e541_structural_skip.py`: `deliverables`
- [ ] `tests/unit/validation/linters/test_hallucination_lint.py`: `trace`
- [ ] `tests/unit/validation/linters/test_invariants.py`: `trace`
- [ ] `tests/unit/validation/linters/test_invariants_cel.py`: `trace`
- [ ] `tests/unit/validation/linters/test_linter_utils.py`: `trace`
- [ ] `tests/unit/validation/linters/test_matrix_rules.py`: `trace`
- [ ] `tests/unit/validation/linters/test_registry_check.py`: `trace`
- [ ] `tests/unit/validation/linters/test_spec_quality_lint.py`: `tech_stack`
- [ ] `tests/unit/validation/linters/test_traceability_closure.py`: `deliverables`, `trace`
- [ ] `tests/unit/validation/test_legacy_shim.py`: `trace`
- [ ] `tests/unit/validation/validators/test_cross_artifact_checks.py`: `trace`
- [ ] `tests/unit/validation/validators/test_cross_step_validation.py`: `deliverables`, `trace`
- [ ] `tests/unit/validation/validators/test_r9_cross_step.py`: `deliverables`, `trace`
- [ ] `tests/unit/validation/validators/test_step_10_deep.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_11_deep.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_validators_03_10.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_validators_core.py`: `dependencies`, `trace`

## WI-M3-08: step 10 governance

Terms: `pr_rules`, `spec_first_policy`, `review_policy`, `verdict_requirements`, `required_metadata`, `evidence_source_by_phase`, `reviewers`, `trace`, `links`

- [ ] `tests/fixtures/entry_key_registry/`: `trace`
- [ ] `tests/fixtures/entry_key_registry_golden.json`: `links`
- [ ] `tests/fixtures/spec_corpus/`: `trace`
- [ ] `tests/fixtures/step_10/`: `pr_rules`, `reviewers`, `spec_first_policy`, `trace`
- [ ] `tests/integration/test_annotation_pipeline.py`: `links`
- [ ] `tests/integration/test_graph_example_steps_00_05.py`: `links`
- [ ] `tests/integration/test_matrix_spec_corpus.py`: `trace`
- [ ] `tests/integration/test_step_13a.py`: `trace`
- [ ] `tests/integration/test_step_16.py`: `trace`
- [ ] `tests/integration/test_step_scripts_bridge.py`: pins step_10/ fixtures
- [ ] `tests/unit/canonical/test_canonical_integrity_drift.py`: `trace`
- [ ] `tests/unit/context/test_reviewer.py`: `trace`
- [ ] `tests/unit/core/test_entry_key_registry.py`: `trace`
- [ ] `tests/unit/core/test_json_output.py`: `pr_rules`
- [ ] `tests/unit/core/test_resolve_pointers.py`: `trace`
- [ ] `tests/unit/generation/test_prompt_schema_sync.py`: `trace`
- [ ] `tests/unit/registry/test_annotation_scan.py`: `links`
- [ ] `tests/unit/registry/test_annotation_schema.py`: `trace`
- [ ] `tests/unit/registry/test_annotations.py`: `links`
- [ ] `tests/unit/registry/test_generate.py`: `trace`
- [ ] `tests/unit/registry/test_step_order_gen.py`: `links`
- [ ] `tests/unit/test_cli.py`: `trace`
- [ ] `tests/unit/test_spec_dir_walker.py`: `trace`
- [ ] `tests/unit/toolkit_invariants/test_m2_graph_declarations.py`: `links`
- [ ] `tests/unit/toolkit_invariants/test_m2_prerequisites.py`: `links`
- [ ] `tests/unit/validation/linters/test_hallucination_lint.py`: `pr_rules`, `trace`
- [ ] `tests/unit/validation/linters/test_invariants.py`: `trace`
- [ ] `tests/unit/validation/linters/test_invariants_cel.py`: `trace`
- [ ] `tests/unit/validation/linters/test_linter_utils.py`: `trace`
- [ ] `tests/unit/validation/linters/test_matrix_rules.py`: `trace`
- [ ] `tests/unit/validation/linters/test_registry_check.py`: `trace`
- [ ] `tests/unit/validation/linters/test_traceability_closure.py`: `pr_rules`, `trace`
- [ ] `tests/unit/validation/test_legacy_shim.py`: `trace`
- [ ] `tests/unit/validation/validators/test_cross_artifact_checks.py`: `trace`
- [ ] `tests/unit/validation/validators/test_cross_step_validation.py`: `trace`
- [ ] `tests/unit/validation/validators/test_r9_cross_step.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_10_deep.py`: `pr_rules`, `trace`
- [ ] `tests/unit/validation/validators/test_step_11_deep.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_validators_03_10.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_validators_core.py`: `trace`

## WI-M3-09: step 11 red team

Terms: `trace`, `target_ids`, `mitigations`

- [ ] `tests/fixtures/entry_key_registry/`: `trace`
- [ ] `tests/fixtures/entry_key_registry_golden.json`: `mitigations`
- [ ] `tests/fixtures/entry_key_registry_pre_m1.json`: `mitigations`
- [ ] `tests/fixtures/spec_corpus/`: `mitigations`, `target_ids`, `trace`
- [ ] `tests/fixtures/step_11/`: `mitigations`, `target_ids`, `trace`
- [ ] `tests/integration/test_matrix_spec_corpus.py`: `trace`
- [ ] `tests/integration/test_step_11.py`: `mitigations`, `target_ids`
- [ ] `tests/integration/test_step_13a.py`: `trace`
- [ ] `tests/integration/test_step_16.py`: `trace`
- [ ] `tests/integration/test_step_scripts_bridge.py`: pins step_11/ fixtures
- [ ] `tests/unit/canonical/test_canonical_integrity.py`: `mitigations`, `target_ids`
- [ ] `tests/unit/canonical/test_canonical_integrity_drift.py`: `trace`
- [ ] `tests/unit/context/test_reviewer.py`: `trace`
- [ ] `tests/unit/core/test_entry_key_registry.py`: `trace`
- [ ] `tests/unit/core/test_resolve_pointers.py`: `trace`
- [ ] `tests/unit/generation/test_prompt_schema_sync.py`: `trace`
- [ ] `tests/unit/generation/test_schema_contracts.py`: `mitigations`, `target_ids`
- [ ] `tests/unit/registry/test_annotation_scan.py`: `mitigations`
- [ ] `tests/unit/registry/test_annotation_schema.py`: `trace`
- [ ] `tests/unit/registry/test_generate.py`: `trace`
- [ ] `tests/unit/test_cli.py`: `trace`
- [ ] `tests/unit/test_spec_dir_walker.py`: `trace`
- [ ] `tests/unit/validation/linters/test_hallucination_lint.py`: `trace`
- [ ] `tests/unit/validation/linters/test_invariants.py`: `trace`
- [ ] `tests/unit/validation/linters/test_invariants_cel.py`: `trace`
- [ ] `tests/unit/validation/linters/test_linter_utils.py`: `target_ids`, `trace`
- [ ] `tests/unit/validation/linters/test_matrix_rules.py`: `target_ids`, `trace`
- [ ] `tests/unit/validation/linters/test_registry_check.py`: `trace`
- [ ] `tests/unit/validation/linters/test_traceability_closure.py`: `trace`
- [ ] `tests/unit/validation/test_legacy_shim.py`: `trace`
- [ ] `tests/unit/validation/test_matrix_invariant_coverage.py`: `mitigations`
- [ ] `tests/unit/validation/validators/test_cross_artifact_checks.py`: `trace`
- [ ] `tests/unit/validation/validators/test_cross_step_validation.py`: `trace`
- [ ] `tests/unit/validation/validators/test_r9_cross_step.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_10_deep.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_11_deep.py`: `mitigations`, `target_ids`, `trace`
- [ ] `tests/unit/validation/validators/test_step_validators_03_10.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_validators_core.py`: `mitigations`, `target_ids`, `trace`

## WI-M3-10: step 12 CI gates

Terms: `trace`, `requires`

- [ ] `tests/fixtures/entry_key_registry/`: `trace`
- [ ] `tests/fixtures/spec_corpus/`: `trace`
- [ ] `tests/fixtures/step_12/`: `requires`, `trace`
- [ ] `tests/integration/test_matrix_spec_corpus.py`: `trace`
- [ ] `tests/integration/test_step_12.py`: `requires`
- [ ] `tests/integration/test_step_13a.py`: `trace`
- [ ] `tests/integration/test_step_16.py`: `trace`
- [ ] `tests/integration/test_step_scripts_bridge.py`: pins step_12/ fixtures
- [ ] `tests/unit/canonical/test_canonical_integrity_drift.py`: `trace`
- [ ] `tests/unit/context/test_reviewer.py`: `trace`
- [ ] `tests/unit/core/test_entry_key_registry.py`: `trace`
- [ ] `tests/unit/core/test_resolve_pointers.py`: `trace`
- [ ] `tests/unit/generation/test_prompt_schema_sync.py`: `trace`
- [ ] `tests/unit/registry/test_annotation_schema.py`: `trace`
- [ ] `tests/unit/registry/test_generate.py`: `trace`
- [ ] `tests/unit/test_cli.py`: `trace`
- [ ] `tests/unit/test_spec_dir_walker.py`: `trace`
- [ ] `tests/unit/validation/linters/test_hallucination_lint.py`: `requires`, `trace`
- [ ] `tests/unit/validation/linters/test_invariants.py`: `trace`
- [ ] `tests/unit/validation/linters/test_invariants_cel.py`: `trace`
- [ ] `tests/unit/validation/linters/test_linter_utils.py`: `requires`, `trace`
- [ ] `tests/unit/validation/linters/test_matrix_rules.py`: `trace`
- [ ] `tests/unit/validation/linters/test_registry_check.py`: `trace`
- [ ] `tests/unit/validation/linters/test_traceability_closure.py`: `trace`
- [ ] `tests/unit/validation/test_legacy_shim.py`: `trace`
- [ ] `tests/unit/validation/validators/test_cross_artifact_checks.py`: `trace`
- [ ] `tests/unit/validation/validators/test_cross_step_validation.py`: `trace`
- [ ] `tests/unit/validation/validators/test_r9_cross_step.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_10_deep.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_11_deep.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_validators_03_10.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_validators_core.py`: `requires`, `trace`

## WI-M3-11: step 13 and 13a

Terms: (none: no removed token)

- [ ] `tests/integration/test_step_scripts_bridge.py`: pins step_13/ fixtures

## WI-M3-12: step 14 roadmap

Terms: `milestone_status_reason`, `status_reason`, `source_milestones`, `deliverables`, `fr_refs`, `capability_refs`, `tech_stack`, `tech_stack_ref`, `trace`, `assumptions`, `exit_conditions`, `invariant_refs`, `fixture_ref`, `dependencies`, `dependency_ref`, `W602`, `W605`

- [ ] `tests/fixtures/entry_key_registry/`: `deliverables`, `trace`
- [ ] `tests/fixtures/entry_key_registry_golden.json`: `assumptions`, `dependencies`
- [ ] `tests/fixtures/entry_key_registry_pre_m1.json`: `dependencies`
- [ ] `tests/fixtures/graph_example/`: `assumptions`
- [ ] `tests/fixtures/spec_corpus/`: `capability_refs`, `deliverables`, `dependencies`, `fr_refs`, `source_milestones`, `trace`
- [ ] `tests/fixtures/step_14/`: `assumptions`, `capability_refs`, `deliverables`, `dependencies`, `exit_conditions`, `fr_refs`, `invariant_refs`, `source_milestones`, `tech_stack`, `trace`
- [ ] `tests/integration/_anchor_factories.py`: `fixture_ref`, `fr_refs`
- [ ] `tests/integration/test_matrix_spec_corpus.py`: `fr_refs`, `trace`
- [ ] `tests/integration/test_step_13a.py`: `trace`
- [ ] `tests/integration/test_step_14.py`: `deliverables`, `source_milestones`, `status_reason`, `tech_stack`
- [ ] `tests/integration/test_step_16.py`: `fixture_ref`, `fr_refs`, `status_reason`, `trace`
- [ ] `tests/integration/test_step_16_anchor.py`: `deliverables`, `fr_refs`
- [ ] `tests/unit/canonical/test_canonical_integrity_drift.py`: `trace`
- [ ] `tests/unit/context/test_milestone_state.py`: `fixture_ref`
- [ ] `tests/unit/context/test_reviewer.py`: `trace`
- [ ] `tests/unit/context/test_reviewer_seed_distillation.py`: `tech_stack`
- [ ] `tests/unit/core/test_entry_key_registry.py`: `deliverables`, `dependencies`, `trace`
- [ ] `tests/unit/core/test_error_code_coverage.py`: `W602`, `W605`
- [ ] `tests/unit/core/test_json_utils_dry_run.py`: `fixture_ref`
- [ ] `tests/unit/core/test_merge_allof_preservation.py`: `tech_stack`, `tech_stack_ref`
- [ ] `tests/unit/core/test_resolve_pointers.py`: `deliverables`, `dependencies`, `trace`
- [ ] `tests/unit/generation/test_prompt_schema_sync.py`: `dependencies`, `trace`
- [ ] `tests/unit/generation/test_schema_contracts.py`: `dependencies`, `tech_stack`
- [ ] `tests/unit/registry/test_annotation_schema.py`: `trace`
- [ ] `tests/unit/registry/test_generate.py`: `deliverables`, `dependencies`, `trace`
- [ ] `tests/unit/test_cli.py`: `dependencies`, `dependency_ref`, `tech_stack`, `tech_stack_ref`, `trace`
- [ ] `tests/unit/test_spec_dir_walker.py`: `trace`
- [ ] `tests/unit/test_update_command.py`: `dependencies`
- [ ] `tests/unit/validation/linters/test_e541_structural_skip.py`: `capability_refs`, `deliverables`, `fr_refs`
- [ ] `tests/unit/validation/linters/test_hallucination_lint.py`: `fr_refs`, `trace`
- [ ] `tests/unit/validation/linters/test_invariants.py`: `trace`
- [ ] `tests/unit/validation/linters/test_invariants_cel.py`: `trace`
- [ ] `tests/unit/validation/linters/test_linter_utils.py`: `trace`
- [ ] `tests/unit/validation/linters/test_matrix_rules.py`: `fr_refs`, `trace`
- [ ] `tests/unit/validation/linters/test_quality_lint_rules.py`: `assumptions`
- [ ] `tests/unit/validation/linters/test_registry_check.py`: `trace`
- [ ] `tests/unit/validation/linters/test_spec_quality_assumption_nodes.py`: `assumptions`
- [ ] `tests/unit/validation/linters/test_spec_quality_lint.py`: `assumptions`, `tech_stack`
- [ ] `tests/unit/validation/linters/test_traceability_closure.py`: `deliverables`, `fr_refs`, `status_reason`, `trace`
- [ ] `tests/unit/validation/test_legacy_shim.py`: `fr_refs`, `trace`
- [ ] `tests/unit/validation/validators/test_cross_artifact_checks.py`: `trace`
- [ ] `tests/unit/validation/validators/test_cross_step_validation.py`: `capability_refs`, `deliverables`, `trace`
- [ ] `tests/unit/validation/validators/test_r9_cross_step.py`: `capability_refs`, `deliverables`, `trace`
- [ ] `tests/unit/validation/validators/test_step_07_deep.py`: `fr_refs`
- [ ] `tests/unit/validation/validators/test_step_10_deep.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_11_deep.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_validators_03_10.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_validators_core.py`: `dependencies`, `trace`

## WI-M3-13: step 15 scaffold

Terms: `trace`, `links`, `interface_ref`, `method`

- [ ] `tests/fixtures/entry_key_registry/`: `trace`
- [ ] `tests/fixtures/entry_key_registry_golden.json`: `interface_ref`, `links`, `method`
- [ ] `tests/fixtures/graph_example/`: `interface_ref`, `method`
- [ ] `tests/fixtures/spec_corpus/`: `trace`
- [ ] `tests/fixtures/step_15/`: `interface_ref`, `links`, `method`, `trace`
- [ ] `tests/integration/test_annotation_pipeline.py`: `links`
- [ ] `tests/integration/test_graph_example_steps_00_05.py`: `links`
- [ ] `tests/integration/test_matrix_spec_corpus.py`: `trace`
- [ ] `tests/integration/test_step_13a.py`: `trace`
- [ ] `tests/integration/test_step_16.py`: `trace`
- [ ] `tests/integration/test_step_scripts_bridge.py`: pins step_15/ fixtures
- [ ] `tests/unit/canonical/test_canonical_integrity_drift.py`: `trace`
- [ ] `tests/unit/context/test_reviewer.py`: `trace`
- [ ] `tests/unit/core/test_entry_key_registry.py`: `trace`
- [ ] `tests/unit/core/test_resolve_pointers.py`: `trace`
- [ ] `tests/unit/generation/test_prompt_schema_sync.py`: `trace`
- [ ] `tests/unit/registry/test_annotation_scan.py`: `links`
- [ ] `tests/unit/registry/test_annotation_schema.py`: `trace`
- [ ] `tests/unit/registry/test_annotations.py`: `links`
- [ ] `tests/unit/registry/test_generate.py`: `trace`
- [ ] `tests/unit/registry/test_step_order_gen.py`: `links`
- [ ] `tests/unit/test_cli.py`: `interface_ref`, `trace`
- [ ] `tests/unit/test_spec_dir_walker.py`: `trace`
- [ ] `tests/unit/toolkit_invariants/test_m2_graph_declarations.py`: `links`
- [ ] `tests/unit/toolkit_invariants/test_m2_prerequisites.py`: `links`
- [ ] `tests/unit/validation/linters/test_hallucination_lint.py`: `trace`
- [ ] `tests/unit/validation/linters/test_invariants.py`: `trace`
- [ ] `tests/unit/validation/linters/test_invariants_cel.py`: `trace`
- [ ] `tests/unit/validation/linters/test_linter_utils.py`: `trace`
- [ ] `tests/unit/validation/linters/test_matrix_rules.py`: `trace`
- [ ] `tests/unit/validation/linters/test_registry_check.py`: `trace`
- [ ] `tests/unit/validation/linters/test_traceability_closure.py`: `interface_ref`, `trace`
- [ ] `tests/unit/validation/test_legacy_shim.py`: `trace`
- [ ] `tests/unit/validation/validators/test_cross_artifact_checks.py`: `trace`
- [ ] `tests/unit/validation/validators/test_cross_step_validation.py`: `interface_ref`, `method`, `trace`
- [ ] `tests/unit/validation/validators/test_r9_cross_step.py`: `interface_ref`, `method`, `trace`
- [ ] `tests/unit/validation/validators/test_step_05_e311.py`: `method`
- [ ] `tests/unit/validation/validators/test_step_05_route_fix.py`: `method`
- [ ] `tests/unit/validation/validators/test_step_10_deep.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_11_deep.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_validators_03_10.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_validators_core.py`: `method`, `trace`

## WI-M3-14: step 16 anchor

Terms: `context_path`, `fr_refs`, `W607`, `W612`

- [ ] `tests/fixtures/spec_corpus/`: `fr_refs`
- [ ] `tests/fixtures/step_16/`: `context_path`, `fr_refs`
- [ ] `tests/integration/_anchor_factories.py`: `context_path`, `fr_refs`
- [ ] `tests/integration/test_matrix_spec_corpus.py`: `fr_refs`
- [ ] `tests/integration/test_step_16.py`: `fr_refs`
- [ ] `tests/integration/test_step_16_anchor.py`: `W607`, `W612`, `context_path`, `fr_refs`
- [ ] `tests/unit/core/test_error_code_coverage.py`: `W607`, `W612`, `context_path`
- [ ] `tests/unit/validation/linters/test_e541_structural_skip.py`: `fr_refs`
- [ ] `tests/unit/validation/linters/test_hallucination_lint.py`: `fr_refs`
- [ ] `tests/unit/validation/linters/test_matrix_rules.py`: `fr_refs`
- [ ] `tests/unit/validation/linters/test_traceability_closure.py`: `W607`, `context_path`, `fr_refs`
- [ ] `tests/unit/validation/test_legacy_shim.py`: `fr_refs`
- [ ] `tests/unit/validation/validators/test_step_07_deep.py`: `fr_refs`

## WI-M3-15: step 16 plan, execution, review

Terms: `coverage_status`, `spec_ref`, `milestone_ref`, `nfr_refs`, `fixture_ref`, `checklist_status`, `deferred_reason`, `wont_do_reason`, `linked_test_expectation`, `spec_refs`, `new_fixtures`, `spec_mutations`, `evidence_binding`, `critical_evidence`, `review_state`, `line_range`, `commit_hash`, `emergent_ambiguities`

- [ ] `tests/fixtures/analysis/`: `emergent_ambiguities`
- [ ] `tests/fixtures/step_16/`: `checklist_status`, `commit_hash`, `critical_evidence`, `deferred_reason`, `emergent_ambiguities`, `evidence_binding`, `fixture_ref`, `line_range`, `linked_test_expectation`, `milestone_ref`, `nfr_refs`, `spec_ref`, `spec_refs`, `wont_do_reason`
- [ ] `tests/integration/_anchor_factories.py`: `commit_hash`, `fixture_ref`, `line_range`, `linked_test_expectation`, `milestone_ref`, `nfr_refs`, `spec_ref`
- [ ] `tests/integration/analysis/test_upstream_backlog_cli.py`: `emergent_ambiguities`
- [ ] `tests/integration/test_step_16.py`: `checklist_status`, `commit_hash`, `critical_evidence`, `deferred_reason`, `emergent_ambiguities`, `evidence_binding`, `fixture_ref`, `line_range`, `linked_test_expectation`, `milestone_ref`, `nfr_refs`, `spec_ref`, `wont_do_reason`
- [ ] `tests/integration/test_step_16_anchor.py`: `milestone_ref`, `spec_ref`
- [ ] `tests/unit/analysis/test_classification.py`: `emergent_ambiguities`
- [ ] `tests/unit/analysis/test_coerce.py`: `emergent_ambiguities`
- [ ] `tests/unit/context/test_milestone_state.py`: `checklist_status`, `emergent_ambiguities`, `fixture_ref`
- [ ] `tests/unit/context/test_reviewer.py`: `checklist_status`
- [ ] `tests/unit/core/test_json_output.py`: `linked_test_expectation`
- [ ] `tests/unit/core/test_json_utils_dry_run.py`: `checklist_status`, `commit_hash`, `deferred_reason`, `evidence_binding`, `fixture_ref`, `line_range`, `linked_test_expectation`, `nfr_refs`, `spec_ref`
- [ ] `tests/unit/validation/linters/test_e541_structural_skip.py`: `critical_evidence`, `emergent_ambiguities`
- [ ] `tests/unit/validation/linters/test_hallucination_lint.py`: `linked_test_expectation`, `nfr_refs`
- [ ] `tests/unit/validation/linters/test_linter_utils.py`: `nfr_refs`
- [ ] `tests/unit/validation/linters/test_traceability_closure.py`: `checklist_status`, `critical_evidence`, `spec_ref`
- [ ] `tests/unit/validation/validators/test_cross_step_validation.py`: `spec_refs`
- [ ] `tests/unit/validation/validators/test_r9_cross_step.py`: `spec_refs`
- [ ] `tests/unit/validation/validators/test_step_16a_deep.py`: `checklist_status`, `deferred_reason`, `spec_ref`, `wont_do_reason`

## WI-M3-17: legacy-consumer shim (matrix guard fields)

Terms: `trace`, `targets`, `target_ids`, `mitigations`, `fr_refs`, `source_milestones`, `deliverables`, `out_of_scope`

- [ ] `tests/fixtures/entry_key_registry/`: `deliverables`, `trace`
- [ ] `tests/fixtures/entry_key_registry_golden.json`: `mitigations`, `out_of_scope`
- [ ] `tests/fixtures/entry_key_registry_pre_m1.json`: `mitigations`, `out_of_scope`
- [ ] `tests/fixtures/spec_corpus/`: `deliverables`, `fr_refs`, `mitigations`, `source_milestones`, `target_ids`, `targets`, `trace`
- [ ] `tests/fixtures/step_00/`: `out_of_scope`
- [ ] `tests/fixtures/step_06/`: `trace`
- [ ] `tests/fixtures/step_07/`: `trace`
- [ ] `tests/fixtures/step_08/`: `out_of_scope`, `targets`, `trace`
- [ ] `tests/fixtures/step_09/`: `deliverables`, `trace`
- [ ] `tests/fixtures/step_10/`: `trace`
- [ ] `tests/fixtures/step_11/`: `mitigations`, `target_ids`, `trace`
- [ ] `tests/fixtures/step_12/`: `trace`
- [ ] `tests/fixtures/step_14/`: `deliverables`, `fr_refs`, `source_milestones`, `trace`
- [ ] `tests/fixtures/step_15/`: `trace`
- [ ] `tests/fixtures/step_16/`: `fr_refs`
- [ ] `tests/integration/_anchor_factories.py`: `fr_refs`
- [ ] `tests/integration/test_matrix_spec_corpus.py`: `fr_refs`, `trace`
- [ ] `tests/integration/test_step_11.py`: `mitigations`, `target_ids`
- [ ] `tests/integration/test_step_13a.py`: `trace`
- [ ] `tests/integration/test_step_14.py`: `deliverables`, `source_milestones`
- [ ] `tests/integration/test_step_16.py`: `fr_refs`, `trace`
- [ ] `tests/integration/test_step_16_anchor.py`: `deliverables`, `fr_refs`
- [ ] `tests/unit/canonical/test_canonical_integrity.py`: `mitigations`, `target_ids`
- [ ] `tests/unit/canonical/test_canonical_integrity_drift.py`: `trace`
- [ ] `tests/unit/context/test_reviewer.py`: `trace`
- [ ] `tests/unit/core/test_entry_key_registry.py`: `deliverables`, `trace`
- [ ] `tests/unit/core/test_resolve_pointers.py`: `deliverables`, `trace`
- [ ] `tests/unit/generation/test_prompt_schema_sync.py`: `trace`
- [ ] `tests/unit/generation/test_schema_contracts.py`: `mitigations`, `target_ids`
- [ ] `tests/unit/generation/test_schema_differ.py`: `out_of_scope`
- [ ] `tests/unit/registry/test_annotation_scan.py`: `mitigations`
- [ ] `tests/unit/registry/test_annotation_schema.py`: `trace`
- [ ] `tests/unit/registry/test_generate.py`: `deliverables`, `out_of_scope`, `trace`
- [ ] `tests/unit/test_cli.py`: `out_of_scope`, `trace`
- [ ] `tests/unit/test_spec_dir_walker.py`: `trace`
- [ ] `tests/unit/validation/linters/test_e541_structural_skip.py`: `deliverables`, `fr_refs`
- [ ] `tests/unit/validation/linters/test_fixtures_lint.py`: `targets`
- [ ] `tests/unit/validation/linters/test_hallucination_lint.py`: `fr_refs`, `trace`
- [ ] `tests/unit/validation/linters/test_invariants.py`: `trace`
- [ ] `tests/unit/validation/linters/test_invariants_cel.py`: `trace`
- [ ] `tests/unit/validation/linters/test_linter_utils.py`: `target_ids`, `trace`
- [ ] `tests/unit/validation/linters/test_matrix_rules.py`: `fr_refs`, `out_of_scope`, `target_ids`, `targets`, `trace`
- [ ] `tests/unit/validation/linters/test_registry_check.py`: `trace`
- [ ] `tests/unit/validation/linters/test_traceability_closure.py`: `deliverables`, `fr_refs`, `out_of_scope`, `targets`, `trace`
- [ ] `tests/unit/validation/test_legacy_shim.py`: `fr_refs`, `trace`
- [ ] `tests/unit/validation/test_matrix_invariant_coverage.py`: `mitigations`
- [ ] `tests/unit/validation/validators/test_cross_artifact_checks.py`: `trace`
- [ ] `tests/unit/validation/validators/test_cross_step_validation.py`: `deliverables`, `out_of_scope`, `targets`, `trace`
- [ ] `tests/unit/validation/validators/test_r9_cross_step.py`: `deliverables`, `targets`, `trace`
- [ ] `tests/unit/validation/validators/test_step_07_deep.py`: `fr_refs`
- [ ] `tests/unit/validation/validators/test_step_10_deep.py`: `targets`, `trace`
- [ ] `tests/unit/validation/validators/test_step_11_deep.py`: `mitigations`, `target_ids`, `trace`
- [ ] `tests/unit/validation/validators/test_step_validators_03_10.py`: `trace`
- [ ] `tests/unit/validation/validators/test_step_validators_core.py`: `mitigations`, `target_ids`, `targets`, `trace`

## WI-M3-18: registry cutover

Terms: `traceRef`, `traceId`, `TRACE_REF_REFS`, `specRefIngested`, `specRefIngestedArray`, `seedRef`, `seedRefArray`, `techStack`, `dependencyItem`, `dependencyList`, `dependencyObjectList`, `spec_refs_ingested`, `seed_refs_ingested`

- [ ] `tests/fixtures/step_08/`: `traceRef`
- [ ] `tests/integration/test_matrix_registry_agreement.py`: named by the pack
- [ ] `tests/unit/canonical/test_canon_schema_alignment.py`: named by the pack
- [ ] `tests/unit/core/test_entry_key_registry.py`: named by the pack
- [ ] `tests/unit/generation/test_prompt_schema_sync.py`: `dependencyList`, `traceRef`
- [ ] `tests/unit/generation/test_schema_contracts.py`: `dependencyItem`, `dependencyList`, `dependencyObjectList`, `techStack`
- [ ] `tests/unit/registry/test_annotation_scan.py`: `traceRef`
- [ ] `tests/unit/registry/test_generate.py`: `traceRef`
- [ ] `tests/unit/toolkit_invariants/test_extraction_paths_registry_agreement.py`: named by the pack
- [ ] `tests/unit/toolkit_invariants/test_registry_generation.py`: named by the pack
- [ ] `tests/unit/toolkit_invariants/test_step_registry_coverage.py`: named by the pack
- [ ] `tests/unit/validation/linters/test_registry_check.py`: `traceRef`

## WI-M3-20: error codes, guides, catalog

Terms: `E142`, `W574`, `W581`, `W582`, `E581`, `E582`, `W602`, `W605`, `W607`, `W612`, `W616`, `LINKED_TEST_FILE_NOT_FOUND`, `linked_test_expectation`

- [ ] `tests/fixtures/step_16/`: `linked_test_expectation`
- [ ] `tests/integration/_anchor_factories.py`: `linked_test_expectation`
- [ ] `tests/integration/test_step_14.py`: `E142`
- [ ] `tests/integration/test_step_16.py`: `E582`, `W581`, `W582`, `W616`, `linked_test_expectation`
- [ ] `tests/integration/test_step_16_anchor.py`: `W581`, `W582`, `W607`, `W612`
- [ ] `tests/unit/core/test_error_code_coverage.py`: `E142`, `E581`, `E582`, `W574`, `W581`, `W582`, `W602`, `W605`, `W607`, `W612`, `W616`
- [ ] `tests/unit/core/test_error_code_registry.py`: `E581`
- [ ] `tests/unit/core/test_guide.py`: `LINKED_TEST_FILE_NOT_FOUND`
- [ ] `tests/unit/core/test_json_output.py`: `LINKED_TEST_FILE_NOT_FOUND`, `linked_test_expectation`
- [ ] `tests/unit/core/test_json_utils_dry_run.py`: `linked_test_expectation`
- [ ] `tests/unit/validation/linters/test_hallucination_lint.py`: `LINKED_TEST_FILE_NOT_FOUND`, `linked_test_expectation`
- [ ] `tests/unit/validation/linters/test_spec_quality_lint.py`: `W574`
- [ ] `tests/unit/validation/linters/test_traceability_closure.py`: `W607`
- [ ] `tests/unit/validation/test_regression_bugs.py`: `E142`

## WI-M3-21: worked-example corpus

Terms: `graph_example`, `W570`

- [ ] `tests/integration/test_graph_example_steps_00_05.py`: `W570`, `graph_example`
- [ ] `tests/integration/test_step_16.py`: `W570`
- [ ] `tests/unit/core/test_ensure_spec_errors.py`: `W570`
- [ ] `tests/unit/core/test_error_code_coverage.py`: `W570`
- [ ] `tests/unit/core/test_error_code_registry.py`: `W570`
- [ ] `tests/unit/generation/test_schema_contracts.py`: `W570`
- [ ] `tests/unit/validation/linters/test_hallucination_lint.py`: `W570`
- [ ] `tests/unit/validation/linters/test_traceability_closure.py`: `W570`
- [ ] `tests/unit/validation/test_legacy_shim.py`: `graph_example`
- [ ] `tests/unit/validation/validators/test_step_02_deep.py`: `graph_example`
- [ ] `tests/unit/validation/validators/test_step_16a_deep.py`: `W570`

## WI-M3-22: M2 leftovers

Terms: `tech_stack`, `wont-have`, `out_of_scope`, `is_parked`, `is_parked_any_shape`, `wont_have_fr_ids`

- [ ] `tests/fixtures/entry_key_registry_golden.json`: `out_of_scope`
- [ ] `tests/fixtures/entry_key_registry_pre_m1.json`: `out_of_scope`
- [ ] `tests/fixtures/step_00/`: `out_of_scope`
- [ ] `tests/fixtures/step_02/`: `tech_stack`
- [ ] `tests/fixtures/step_08/`: `out_of_scope`
- [ ] `tests/fixtures/step_09/`: `tech_stack`
- [ ] `tests/fixtures/step_14/`: `tech_stack`
- [ ] `tests/integration/test_step_14.py`: `tech_stack`
- [ ] `tests/unit/context/test_reviewer_seed_distillation.py`: `tech_stack`
- [ ] `tests/unit/core/test_merge_allof_preservation.py`: `tech_stack`
- [ ] `tests/unit/generation/test_schema_contracts.py`: `tech_stack`
- [ ] `tests/unit/generation/test_schema_differ.py`: `out_of_scope`
- [ ] `tests/unit/registry/test_generate.py`: `out_of_scope`
- [ ] `tests/unit/test_cli.py`: `is_parked`, `is_parked_any_shape`, `out_of_scope`, `tech_stack`, `wont-have`
- [ ] `tests/unit/validation/linters/test_matrix_rules.py`: `out_of_scope`, `wont-have`
- [ ] `tests/unit/validation/linters/test_spec_quality_lint.py`: `tech_stack`
- [ ] `tests/unit/validation/linters/test_traceability_closure.py`: `out_of_scope`, `wont-have`
- [ ] `tests/unit/validation/test_legacy_shim.py`: `is_parked`, `is_parked_any_shape`, `wont-have`
- [ ] `tests/unit/validation/validators/test_cross_step_validation.py`: `out_of_scope`
- [ ] `tests/unit/validation/validators/test_step_11_deep.py`: `wont-have`

## Script

```python
#!/usr/bin/env python3
"""Print the per-work-item sections of the M3 schema-change test-module checklist (markdown) to stdout.

Run from the repo root: python3 schema_change_modules.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path.cwd()
TESTS = ROOT / "tests"
BRIDGE = "tests/integration/test_step_scripts_bridge.py"
SKIP_PARTS = {"__pycache__", ".worktrees", "WIP", "schema_baseline"}
SKIP_SUFFIXES = {".pyc", ".png", ".jpg", ".gz", ".zip"}

# Ordinary English words: a hit counts only as a quoted key, a `.term` path or a `term:` key.
GENERIC = {"trace", "links", "requires", "dependencies", "targets", "mitigations",
           "reviewers", "assumptions", "deliverables", "method"}

# Work item -> (title, terms). Terms come from the field-fate table of packs/M3/_shared.md 3.3.
WORK_ITEMS: dict[str, tuple[str, list[str]]] = {
    "WI-M3-03": ("ambiguity item, all steps", ["crossCycleAmbiguityItem", "ambiguityStatus", "emergent_ambiguities"]),
    "WI-M3-04": ("step 06 invariants", ["trace"]),
    "WI-M3-05": ("step 07 NFRs", ["trace"]),
    "WI-M3-06": ("step 08 fixtures", ["targets", "out_of_scope"]),
    "WI-M3-07": ("step 09 impl plan", ["deliverables", "tech_stack", "tech_stack_ref", "trace",
                                       "depends_on", "dependencies", "dependency_ref"]),
    "WI-M3-08": ("step 10 governance", ["pr_rules", "spec_first_policy", "review_policy", "verdict_requirements",
                                        "required_metadata", "evidence_source_by_phase", "reviewers",
                                        "trace", "links"]),
    "WI-M3-09": ("step 11 red team", ["trace", "target_ids", "mitigations"]),
    "WI-M3-10": ("step 12 CI gates", ["trace", "requires"]),
    "WI-M3-11": ("step 13 and 13a", []),
    "WI-M3-12": ("step 14 roadmap", ["milestone_status_reason", "status_reason", "source_milestones",
                                     "deliverables", "fr_refs", "capability_refs", "tech_stack", "tech_stack_ref",
                                     "trace", "assumptions", "exit_conditions", "invariant_refs", "fixture_ref",
                                     "dependencies", "dependency_ref", "W602", "W605"]),
    "WI-M3-13": ("step 15 scaffold", ["trace", "links", "interface_ref", "method"]),
    "WI-M3-14": ("step 16 anchor", ["context_path", "fr_refs", "W607", "W612"]),
    "WI-M3-15": ("step 16 plan, execution, review",
                 ["coverage_status", "spec_ref", "milestone_ref", "nfr_refs", "fixture_ref", "checklist_status",
                  "deferred_reason", "wont_do_reason", "linked_test_expectation", "spec_refs", "new_fixtures",
                  "spec_mutations", "evidence_binding", "critical_evidence", "review_state", "line_range",
                  "commit_hash", "emergent_ambiguities"]),
    "WI-M3-17": ("legacy-consumer shim (matrix guard fields)",
                 ["trace", "targets", "target_ids", "mitigations", "fr_refs", "source_milestones",
                  "deliverables", "out_of_scope"]),
    "WI-M3-18": ("registry cutover",
                 ["traceRef", "traceId", "TRACE_REF_REFS", "specRefIngested", "specRefIngestedArray", "seedRef",
                  "seedRefArray", "techStack", "dependencyItem", "dependencyList", "dependencyObjectList",
                  "spec_refs_ingested", "seed_refs_ingested"]),
    "WI-M3-20": ("error codes, guides, catalog",
                 ["E142", "W574", "W581", "W582", "E581", "E582", "W602", "W605", "W607", "W612", "W616",
                  "LINKED_TEST_FILE_NOT_FOUND", "linked_test_expectation"]),
    "WI-M3-21": ("worked-example corpus", ["graph_example", "W570"]),
    "WI-M3-22": ("M2 leftovers", ["tech_stack", "wont-have", "out_of_scope", "is_parked", "is_parked_any_shape",
                                  "wont_have_fr_ids"]),
}

# Pack-named registry-pinning modules for WI-M3-18 (listed even when the grep misses them).
PACK_NAMED = {
    "WI-M3-18": [
        "tests/unit/registry/test_generate.py",
        "tests/unit/toolkit_invariants/test_registry_generation.py",
        "tests/unit/toolkit_invariants/test_extraction_paths_registry_agreement.py",
        "tests/unit/toolkit_invariants/test_step_registry_coverage.py",
        "tests/integration/test_matrix_registry_agreement.py",
        "tests/unit/validation/linters/test_registry_check.py",
        "tests/unit/core/test_entry_key_registry.py",
        "tests/unit/canonical/test_canon_schema_alignment.py",
    ],
}

# Fixture step number -> work items that own that step's fixtures (for the bridge test).
STEP_TO_WI = {"06": "WI-M3-04", "07": "WI-M3-05", "08": "WI-M3-06", "09": "WI-M3-07", "10": "WI-M3-08",
              "11": "WI-M3-09", "12": "WI-M3-10", "13": "WI-M3-11", "14": "WI-M3-12", "15": "WI-M3-13"}


# Per-step fixture directories (tests/fixtures/step_NN/) are listed only under the work items of that step.
STEP_DIR_OWNERS = {**{f"step_{n}": [w] for n, w in STEP_TO_WI.items()}, "step_16": ["WI-M3-14", "WI-M3-15"],
                   "step_16a": ["WI-M3-15"]}
STEP_SCOPED = {w for w in WORK_ITEMS if "WI-M3-04" <= w <= "WI-M3-15"}


def in_scope(wi: str, unit: str) -> bool:
    m = re.fullmatch(r"tests/fixtures/(step_\w+)/", unit)
    if not m or wi not in STEP_SCOPED:
        return True
    return wi in STEP_DIR_OWNERS.get(m.group(1), [])


def term_regex(term: str) -> re.Pattern[str]:
    t = re.escape(term)
    whole = rf"(?<![\w-]){t}(?![\w-])" if "-" in term else rf"(?<!\w){t}(?!\w)"
    if term not in GENERIC:
        return re.compile(whole)
    keyed = rf"""["']{t}["']|\.{t}\b|^\s*-?\s*{t}\s*:"""
    return re.compile(keyed, re.MULTILINE)


def test_files() -> list[Path]:
    out = []
    for p in sorted(TESTS.rglob("*")):
        rel = p.relative_to(ROOT).parts
        if p.is_file() and not (SKIP_PARTS & set(rel)) and p.suffix not in SKIP_SUFFIXES:
            out.append(p)
    return out


def read(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ""


def unit_of(p: Path) -> str:
    """A module is its own unit; files under tests/fixtures group by their first directory (tests/fixtures/<dir>/)."""
    rel = p.relative_to(ROOT)
    parts = rel.parts
    if parts[:2] == ("tests", "fixtures") and len(parts) > 3:
        return "/".join(parts[:3]) + "/"
    return rel.as_posix()


def main() -> None:
    files = test_files()
    texts = {p: read(p) for p in files}
    bridge_steps = set(re.findall(r"step_(\d\d)\b", texts.get(ROOT / BRIDGE, "")))
    lines: list[str] = []
    for wi, (title, terms) in WORK_ITEMS.items():
        hits: dict[str, set[str]] = {}
        for term in terms:
            rx = term_regex(term)
            for p, txt in texts.items():
                if rx.search(txt) and in_scope(wi, unit_of(p)):
                    hits.setdefault(unit_of(p), set()).add(term)
        for named in PACK_NAMED.get(wi, []):
            if (ROOT / named).exists():
                hits.setdefault(named, set())
        step_no = next((s for s, w in STEP_TO_WI.items() if w == wi), None)
        if step_no and step_no in bridge_steps:
            hits.setdefault(BRIDGE, set()).add(f"pins step_{step_no}/ fixtures")
        lines += [f"## {wi}: {title}", "", f"Terms: {', '.join(f'`{t}`' for t in terms) or '(none: no removed token)'}", ""]
        if not hits:
            lines += ["No module or fixture directory hits.", ""]
            continue
        for unit in sorted(hits):
            note = ", ".join(f"`{t}`" if not t.startswith("pins ") else t for t in sorted(hits[unit]))
            lines.append(f"- [ ] `{unit}`" + (f": {note}" if note else ": named by the pack"))
        lines.append("")
    sys.stdout.write("\n".join(lines))


if __name__ == "__main__":
    main()
```
