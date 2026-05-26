# Changelog

All notable changes to the orchemist-skills pack are recorded here. The pipeline YAML version (`pipelines/coding-pipeline-standard.yaml :: version`) tracks structural pipeline changes; the package version (`package.json :: version`) tracks distribution releases.

This changelog uses [Semantic Versioning](https://semver.org/) for the pipeline YAML version field.

## [4.3.0] — 2026-05-26

### Added — producer-side 7d enforcement family (closes [#6](https://github.com/ToscanAI/orchemist-skills/issues/6))

- **`### 7e` sub-check in SPEC_ADVERSARY** — intra-symbol duplication audit (producer-side complement to 7d). Catches the case where a newly-created exported symbol's body contains byte-identical sub-blocks (e.g. identical SQL projections across a fixture-stub short-circuit). Two acceptable resolutions: (a) factor the duplicate sub-block into a private helper; (b) document a per-branch divergence justification in §B.5.x with the same concreteness bar as 7d (sealed string / sort order / precision / type narrowing / environment boundary — not bare "different use case").
- **`### HARD RULE — 7e-implement` in IMPLEMENT** — implementer self-check before file output. Inspects each `return` / `throw` arm of newly-created exported functions for byte-identical-modulo-whitespace duplicates; refactors to a private helper inline OR returns `BLOCKED: 7e-intra-symbol-duplication`. Sibling of the existing 7d HARD RULE.
- **`### HARD RULE — §7.2 byte-identical added-block diff lint` in IMPLEMENT** — pure static grep at post-commit, pre-push. Surfaces multi-line byte-identical added blocks across the diff via `git diff main...HEAD | grep '^+' | sort | uniq -c | awk '$1 >= 2 && length($0) > 50'`; contiguous-3-line gate FAILS the lint and routes to inline refactor OR `BLOCKED: 7e-seal-diff-lint`. Non-LLM lint; tunable thresholds. Inserted as IMPLEMENT task step 8, between commit and push.
- **`### §3a` sub-section in Phase 0 inventory** — pre-existing dual-path helpers inventory via regex heuristic (`grep -B 8 "return [^;]*;" <file> | grep "if ("`). SPEC reads this list and considers EXTEND-ing an existing multi-branch helper before authoring a new one. Acknowledged false-positive rate; consumer is human-in-the-loop. EXTEND verdict in §5 now explicitly references §3a.
- **`Sub-check 7d-producer` in REVIEW** — intra-symbol return-arm comparison (pragmatic verbatim-quote form, not normalized-hash α-conversion per audit R1 downgrade). Quotes each arm verbatim in `review.md`, asserts ≥1 non-whitespace-non-identifier token differs; SPEC §B.5.x divergence justification short-circuits the comparison (and the §B.5.x justification itself must meet the 7d concreteness bar).
- **Regression test scaffold** — `tests/test_spec_adversary_7e_intra_symbol.py` + `tests/fixtures/spec-with-intra-duplication.md` (reconstructed value-investing#449 fixture) + minimal `pyproject.toml` + `tests/conftest.py` + `tests/README.md`. Prompt-rendering-only assertions (no live Opus call per CI-cost note). Manual integration-reproduction protocol documented in `tests/README.md`.

### Motivation — value-investing Wave 7 audit (2026-05-26)

ToscanAI/value-investing#449 (lift commit `11db4eb`) shipped `findCompanyByTicker` with two byte-identical `await db<…>` SQL blocks separated by a fixture-stub short-circuit. The PR's 7d enumeration listed callers of a pre-existing symbol (`loadAnnualFactsFromDb`) and APPROVED — the new symbol's own intra-file duplication was never inspected. 7d's caller-enumeration audit is import-side reuse; this issue's 7e family is producer-side intra-symbol duplication. The two are complementary defense-in-depth layers, not redundancy.

Five-phase defense in depth (SPEC_ADVERSARY 7e ⇒ Phase 0 §3a EXTEND hint ⇒ IMPLEMENT 7e-implement ⇒ IMPLEMENT §7.2 diff lint ⇒ REVIEW 7d-producer) gives the producer-side smell the same multi-layer treatment 7d-consumer received in v4.x.

### Notes

- Follow-up issue for the retro-loop process operationalization (audit R1 deferred Improvement 4) — filed separately; see PR body for link. The follow-up names concrete cadence, owner, and output format.
- All five sub-checks are ADDITIVE; existing 7d enforcement language is unchanged byte-for-byte. No breaking change to consumers; consumer pipelines that don't trigger the new producer-side patterns see no behavioral change.
- Structural-pipeline version line bumped from `4.2.0` → `4.3.0` (minor — additive sub-checks). The `version` field in `pipelines/coding-pipeline-standard.yaml` (distribution-layer) is unchanged at `"2.0.0"` per the two-axis version scheme.
- Skip-spec pipeline (`pipelines/coding-pipeline-skip-spec.yaml`) is NOT touched in this release — by design, skip-spec assumes the consumer pre-places SPEC + behavioral and accepts duplication responsibility upstream.

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
