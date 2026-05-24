# Changelog

All notable changes to the orchemist-skills pack are recorded here. The pipeline YAML version (`pipelines/coding-pipeline-standard.yaml :: version`) tracks structural pipeline changes; the package version (`package.json :: version`) tracks distribution releases.

This changelog uses [Semantic Versioning](https://semver.org/) for the pipeline YAML version field.

## [4.2.0] — 2026-05-24

### Added

- **`EXTEND` verdict** as a first-class output label in Phase 0 (`existing_symbols_inventory`) §5 + §6, with parallel recognition in SPEC + SPEC_ADVERSARY prompts. EXTEND names the "parameterize the existing symbol so the existing call site AND the new call site both consume the same source" pattern — previously masked under CONSUME, where it was frequently missed when the existing helper had a slightly narrower signature than the new use site needed. The four-verdict schema (CONSUME / EXTEND / DIVERGENT / NEW-OK) replaces the previous three-mode prose (consume / Divergence justification / new symbol).
- **`phase0_hard_gate` config flag** (`boolean`, default `false`). Documents the policy intent: when `false`, Phase 0 degrades gracefully (transitions.exhausted: spec); when `true`, consumers signal stricter intent. The YAML's default transitions are unchanged for backwards-compat; consumers who want true HALT can fork-override `transitions.exhausted: null` in their config, or use a wrapper-orchestrator pattern.
- **Verdict-label cross-check** in SPEC_ADVERSARY: verdict label mismatch (e.g. EXTEND claimed but Files-to-Create lists a new file) is now a `[divergence]` finding with `[verdict-mismatch]` qualifier.

### Motivation — Wave 5/6 retrospective from ToscanAI/value-investing

The ToscanAI/value-investing consumer measured 32 PRs across 19 days (2026-05-04 → 2026-05-23) producing **13 new duplication groups** — Wave 5 (7 groups, all from EPIC-16 hi-fi UI sweep + EPIC-10 dashboard) and Wave 6 (6 groups, from EPIC-10/11 follow-up children). Root-cause: fresh-context IMPLEMENT subagents kept re-implementing helpers that already lived in `_shared/` because no phase enforced a behavioural grep before SPEC committed to a file plan. Phase 0 (v4) moved the catch from REVIEW → SPEC, but ~40% of the surfaced cases were "parameterize the existing helper to fit both call sites" — a pattern under-served by the v4 binary CONSUME / divergent framing.

v4.2 adds EXTEND as the explicit verdict for that pattern. The expectation, based on the value-investing N5-1 ship (PR #436, 2026-05-24), is that explicit EXTEND naming will reduce post-spec-time refactor churn by surfacing parameterization opportunities at SPEC drafting time, not at PR review time.

### Notes

- Pipeline-version bumped from `2.0.0` (skills-pack distribution version) is independent of the YAML structural revision (v4 → v4.1 → v4.2). The YAML's `version: "2.0.0"` field tracks distribution-layer compatibility; the v4.x line tracks structural pipeline maturity.
- Skip-spec pipeline (`pipelines/coding-pipeline-skip-spec.yaml`) does not have Phase 0 — by design, skip-spec assumes the consumer pre-places `spec.md` + `behavioral.md` and accepts duplication responsibility upstream.
- Memory files in the value-investing consumer's `/home/toscan/.claude/projects/.../memory/` directory may still reference v4 / pre-v4.2 verdict shapes. They are downstream artifacts; updating them is a consumer-side task, not blocking on this PR.

## [4.1.0] — 2026-05-22

### Fixed (adversary R1 follow-up to v4)

- 9 surgical fixes across 11 findings from the v4 adversary review. See merge commit `787b555` and predecessor `a47ac90`.

## [4.0.0] — 2026-05-22

### Added

- **Phase 0: `existing_symbols_inventory`** as a sticky pre-pipeline artifact. Greps the consumer's UI primitives / shared libraries / adjacent actions+hooks / workspace barrels (driven by 4 config inputs: `ui_primitive_paths`, `lib_paths`, `action_dirs`, `workspace_barrels`). Writes `{output_dir}/existing_symbols.md` with 6 sections; read by SPEC, BEHAVIORAL, SPEC_ADVERSARY, IMPLEMENT, REVIEW. Resolves the late-catch problem for sub-check 7d (re-implementation of existing symbol).

### Motivation (v4 pre-history)

The v3 yaml caught sub-check 7d at three late checkpoints (SPEC_ADVERSARY R1 / IMPLEMENT BLOCKED / REVIEW MAJOR), each requiring backtrack. Two consecutive feature PRs in a downstream consumer each shipped a 7d-duplication-then-fix cycle. Phase 0 moves catch to authoring time.
