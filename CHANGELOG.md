# Changelog

All notable changes to the orchemist-skills pack are recorded here. The pipeline YAML version (`pipelines/coding-pipeline-standard.yaml :: version`) tracks structural pipeline changes; the package version (`package.json :: version`) tracks distribution releases.

This changelog uses [Semantic Versioning](https://semver.org/) for the pipeline YAML version field.

## [comic-strip-pipeline 0.1.0] — 2026-06-14

### Added — first creative pipeline: `pipelines/comic-strip-pipeline.yaml`

The pack's first non-coding pipeline. It ports the standard pipeline's spine — ground-truth spec → adversarial contract review → sealed acceptance → engine-verified gate → fix loop — to character-consistent multi-panel comic-strip generation. **Markdown-only purity preserved**: the render + judge tools live in the consumer's comic repo (like pytest in the coding pipeline), referenced via `render_command` / `judge_command`; nothing Python ships here.

- **10 phases**, mirroring the coding standard's tiers: `asset_inventory → strip_spec → panel_contracts → strip_adversary (opus) → acceptance_criteria → render → acceptance_run (engine) → art_review (opus) → fix → continuity_check (engine)`. One artifact per phase under `.orchemist/runs/<id>/`.
- **Behavioral contracts for images** — `panel_contracts` asserts WHAT is visible (characters + canonical traits, verbatim bubble text, absent props, continuity, dims), never the prompt wording. The WHAT-not-HOW rule transfers intact.
- **The adversary hunts known image failure modes** — unpinned character state → drift, reference text-leakage, back-of-head shots, design-from-description gaps, non-verbatim dialogue, trivial satisfaction. Derived from a real session where a therapist rendered as three different people, a prior post's caption leaked into a panel, and a prop appeared/vanished between panels.
- **"What is an image acceptance test?"** — `acceptance_criteria` emits a sealed JSON (from contracts alone) of deterministic PIL checks (dims/aspect/count/file) + per-panel binary vision-judge criteria; the engine `acceptance_run` runs the consumer's `judge_panels.py` (N-vote majority) and writes `acceptance_results.json`, branching on exit code exactly like pytest.
- **Consistency invariant** — `anchor_panel_id` is rendered + approved first; panels 2..N re-frame a caption-cropped copy of it, locking identity, room, and lighting (the reframe technique that took a drifting scene to a consistent one in the source session).

Reference consumer tools (live in the comic repo, not here): `scripts/generate-comic-panels.py` (render — Gemini `gemini-3-pro-image-preview`, 4:5→1080×1350, reference-image consistency) and `scripts/judge_panels.py` (the acceptance engine). Example input: `examples/example-strip.md`.

Pipeline YAML version `0.1.0` — **alpha**. One end-to-end manual pilot (a 10-panel couples-therapist strip) validated the phase logic; the judge gate was smoke-tested standalone (3-vote majority, deterministic exit code).

## [4.4.0] — 2026-06-11

### Added — process upgrades from the engine campaign (closes [#21](https://github.com/ToscanAI/orchemist-skills/issues/21))

This release encodes operating lessons earned across a multi-run standard-pipeline campaign against the engine repo (six full runs in 24h) into the skills pack, so every future operator inherits the tuned pipeline instead of re-deriving it from session memory. **Process-only release — ZERO `pipelines/*.yaml` changes** (the engine cross-repo parity surface is untouched); all content lands in `skills/*.md` + `agents/*.md` + this changelog. All additions are ADDITIVE: the two load-bearing fresh-subagent anchor sentences in the 7 pinned wrapper files remain byte-verbatim.

- **Sealed-test harness rules** (`agents/orchemist-tester.md` + `skills/orchemist-acceptance-test.md`) — six repo-agnostic rules, each of which cost a sealed-test round in the campaign: (1) module-level imports = today-real names only, `[NEW]` symbols asserted/imported lazily and `[DELETED]` modules probed in-body so collection succeeds against current code; (2) every runner-stub/fake callable ends its signature with `**kwargs` (sequencers call workers with keyword args; a bare positional stub raises a swallowed `TypeError`); (3) copy the contract-named real helper, never hand-roll its construction (phantom kwargs dropped by permissive `extra="ignore"` models; enum/plain-object wrapping mistakes); (4) keyword-filtered log/warning counting scoped to the contract's family, never raw `== []` over a logger; (5) env isolation for credential-sensitive contracts — `patch.dict(os.environ, {}, clear=True)` + `pop` at factory level, `monkeypatch.delenv` + `env={...: ""}` at CLI level (Click's `CliRunner` `env=` OVERLAYS, it does not unset); (6) a reachability-derived expected-today ledger per test, surfaced as a table in `acceptance_test.md`.
- **Orchestrator pre-flight before the `test_adversary` round** (`skills/orchemist-run.md`) — collect-only + full run from the WORKTREE cwd (fixtures may be cwd-sensitive), per-anomaly failure-reason extraction, evidence embedded in the adversary dispatch (the adversary has no Bash). Caught the defect before the adversary on multiple campaign runs.
- **Contract-amendment protocol** (`skills/orchemist-adversary.md` + `skills/orchemist-run.md`) — when mechanical evidence disproves a sealed-contract claim, the adversary authors a verbatim `OLD → NEW` edit, the orchestrator applies it with a dated banner, and the tester re-derives the affected tests in a fresh round. No conditional approvals. (Invented under fire mid-campaign; worked first try.)
- **Behavioral self-containedness stress test** (`skills/orchemist-behavioral.md` output contract + `skills/orchemist-adversary.md` check 6) — before sealing, mentally write one test for the hardest contract from the contract text ALONE; any underivable step (guessed class name, input shape, expected value) means the contract is not self-contained and must be fixed. The downstream tester has no spec access.
- **Decisive-check pattern** (`skills/orchemist-run.md` + `skills/orchemist-adversary.md`) — every adversary dispatch names 1-2 make-or-break verification targets; the adversary rules on them explicitly before secondary nitpicks.
- **Issue-staleness discipline** (`skills/orchemist-spec.md`) — issue bodies are snapshots; the spec re-grounds against the present-tense code, and any acceptance-criterion reinterpretation is flagged in an `## AC reinterpretation` subsection for adversary ratification rather than silently absorbed.
- **Surgical revision rounds** (`skills/orchemist-run.md`) — revision prompts carry verbatim-prescribed fixes + an explicit "everything else byte-stable" mandate; the re-auditor receives the inter-round diff as its change surface (a diff-scoped re-audit ran ~1 min versus a full re-read).
- **Seal-integrity verification** (`skills/orchemist-run.md` + `skills/orchemist-acceptance-run.md`) — hash the sealed test file at seal time into `state.json`, then verify at `acceptance_run` and post-implement. The standard pipeline has no `verify_tests_integrity` phase (that gate exists only on skip-spec), so this is its tamper guard.
- **Explicit-model-override hardening** (`skills/orchemist-run.md`) — always pass an explicit model on every `Agent` dispatch; a `(default)`/ambient dispatch can die instantly on some main-loop models (0-token return, `400` with a `thinking.type.disabled`-style cause). A 0-token instant death is NOT a content verdict — re-dispatch the same phase with an explicit model rather than routing it as `failed`.
- **External run-dir guidance** (`skills/orchemist-run.md`) — keep `.orchemist/runs/` out of the consumer's tracked tree (in-repo run dirs have clobbered tracked files); verify `.gitignore` coverage or place the run directory outside the repo.
- **"Glob unreliable in worktrees" note** (`agents/orchemist-tester.md` + `skills/orchemist-existing-symbols-inventory.md` + `skills/orchemist-adversary.md`) — verify path/symbol existence with `Grep`/`Bash`; never treat an empty `Glob` as proof of absence.
- **Unconditional CLI network seal** (`agents/orchemist-tester.md` + `skills/orchemist-acceptance-test.md`) — acceptance tests that invoke the real run command must transport-seal the executors at class level even when the contract expects a pre-execution build failure: that "fails before execution" rationale only holds post-implementation, while at HEAD and against buggy code the run proceeds into REAL phase execution and live HTTP. The class-level transport patch is a hermeticity backstop; a post-impl-only rationale never licenses omitting the seal (run-969 lesson).

### Motivation — engine standard-pipeline campaign (2026-06-10/11)

A 24-hour campaign of six full standard-pipeline runs against ToscanAI/orchemist (runs 474/713/962/702/703/967/968/969; artifacts in the engine workspace `.runs/`) surfaced a cluster of process defects. Three of four standard-pipeline runs lost at least one sealed-tester round to harness diseases these rules now prevent (lazy-import collection deaths, positional-stub `TypeError` swallowing, hand-rolled spec construction dropping phantom kwargs, logger-contamination warning counts, env-fallback leakage, mislabeled red/green ledgers). One run hit a sealed contract that was mechanically FALSE (a case-insensitivity belief about an exact-key API) and required the contract-amendment maneuver, which had no documented protocol at the time — it was invented under fire and worked first try. The decisive-check, issue-staleness, surgical-revision, and seal-integrity disciplines each turned a specific run from a multi-round slog into a fast, evidence-grounded pass. Encoding them here moves the catch from "operator remembers" to "the skills enforce it."

### Notes

- **No `pipelines/*.yaml` changes** — verified against the engine's `scripts/check_template_sync.py --skills-dir <branch>/pipelines` (STRICT/ANCHORED cross-repo byte-comparison + `spec_adversary.model_tier == "opus"` lock all still green). The boilerplate lint (`_run_phase_skill_boilerplate`) confirms both fresh-subagent anchor substrings remain verbatim in all 7 pinned wrapper files.
- All additions are ADDITIVE prose in each file's existing voice; no existing section was renumbered and no anchor sentence was altered. Wording is repo-agnostic — the engine campaign is cited as precedent, not hardcoded as the only applicable repo.
- Structural-pipeline version line bumped `4.3.0` → `4.4.0` (minor — additive process guidance, no YAML/behaviour change for consumers). The `version` field in `pipelines/coding-pipeline-standard.yaml` (distribution layer) is unchanged at `"2.0.0"` per the two-axis version scheme; `package.json` distribution version bumped `0.1.0` → `0.2.0`.
- Skip-spec pipeline (`pipelines/coding-pipeline-skip-spec.yaml`) is NOT touched — by design it already carries its own `verify_tests_integrity` tamper gate and assumes the consumer pre-places SPEC + behavioral.

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
