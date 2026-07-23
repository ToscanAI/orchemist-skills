export const meta = {
  name: 'orchemist-wave',
  description:
    'Parallel "wave" orchestrator for Orchemist: fan N independent, file-disjoint lanes through a per-lane pipeline — mode:"refactor" runs implement → independent fable review; mode:"maintenance" runs the maintenance pipeline per lane (spec → fable spec-adversary → implement+focused-test → independent fable review); mode:"codemod" runs a behavior-preserving lint/codemod cleanup WITH the same spec + fable spec-adversary planning gate (spec → fable spec-adversary → codemod-implement → independent fable review, no new test); mode:"content" runs the content pipeline per lane (research → draft(opus, real committed diff) → fact_check(fable gate) → red_team(fable gate), each gate with one bounded re-draft) for in-app content authored as a code diff. Per-lane lockstep, each lane sealed in its own git worktree. Produces reviewed, pushed branches + per-lane merge-readiness verdicts. Does NOT merge — the merge-coordination (branch-protection toggle + squash-merge + composition full-suite) stays a deliberate, outward-facing operator step.',
  whenToUse:
    'When several file-DISJOINT lanes are ready at once. mode:"refactor" (default) — behavior-preserving changes (a god-module decomposition, a mechanical codemod); each lane needs an immutable contract (a surface/contract test + the full suite). mode:"maintenance" — a batch of independent bug/infra/CI/data fixes; each lane runs the maintenance pipeline (spec → fable adversary → implement + a FOCUSED test → fable review), the right-sized flow that adds behavior + tests (NOT behavior-preserving). mode:"codemod" — the middle ground: a behavior-preserving lint/codemod cleanup (e.g. driving a per-package bulk-suppression baseline to zero) that still wants the spec + fable-adversary planning gate but adds NO behavior and NO new test. mode:"content" — a batch of independent in-app CONTENT modules (a gated route-page + a data-file entry + a curated link/video allowlist), each authored as a real committed diff and gated by a source-grounded fact_check + an IP/brand red_team (both fable, blocking); pre-place each lane\'s operator-refined source_material.md and pass its absolute path as lane.sourceFile. Rule of thumb: serialize lanes WITHIN one module (same files), parallelize ACROSS modules (disjoint dirs compose cleanly).',
  phases: [
    { title: 'Spec', detail: 'maintenance + codemod modes — spec + fable spec-adversary per lane (the pre-implement quality gate)', model: 'fable' },
    { title: 'Research', detail: 'content mode — one general-purpose (sonnet) per lane: web-verify links/videos + confirm the correctness anchors', model: 'sonnet' },
    { title: 'Implement', detail: 'refactor/maintenance/codemod modes — one orchemist-implementer (opus) per lane, sealed in its own git worktree', model: 'opus' },
    { title: 'Draft', detail: 'content mode — one orchemist-implementer (opus) per lane authors the content as a real committed diff (+ bounded gate re-drafts)', model: 'opus' },
    { title: 'Review', detail: 'refactor/maintenance/codemod modes — one independent fable reviewer per lane — verify, do not trust', model: 'fable' },
    { title: 'Fact-check', detail: 'content mode — a source-grounded fable gate: every claim traces to a source, every link/video web-verified', model: 'fable' },
    { title: 'Red-team', detail: 'content mode — an IP/brand/claim-support fable gate (orchemist-adversary, reads the captured diff)', model: 'fable' },
  ],
}

// ─────────────────────────────────────────────────────────────────────────────
// orchemist-wave — the parallel fan-out we run by hand, encoded deterministically.
//
// THREE modes, same skeleton (pipeline() = per-lane lockstep, no barrier between
// lanes; each lane sealed in its own git worktree so concurrent lanes never
// collide on the git index; the implementer pushes its branch, the reviewer
// fetches + diffs it):
//   • mode:"refactor"   — the proven EPIC #942 pattern: implement(opus) → fable
//     review. Bar = ZERO functional change; the reviewer's durable gate is the
//     public-surface diff (a dropped re-export passes both the contract test AND
//     the full suite; only an explicit surface-diff catches it).
//   • mode:"maintenance" — each lane runs the coding-pipeline-maintenance flow:
//     spec → spec_adversary(fable) → implement(+focused test) → review(fable). The
//     spec_adversary is the key quality gate for prod-affecting maintenance work;
//     it does ONE bounded revise round. Lanes ADD behavior + tests (not
//     behavior-preserving), so there is no surface-diff/facade invariant.
//   • mode:"codemod"    — the middle ground: maintenance's spec → spec_adversary(fable)
//     planning gate + refactor's behavior-preserving bar. Each lane runs
//     spec → spec_adversary(fable) → codemod-implement → review(fable) for a
//     behavior-preserving lint/codemod cleanup (e.g. driving a per-package
//     bulk-suppression baseline to zero). Behavior 100% UNCHANGED, NO new
//     behavior, NO new test; the reviewer's durable gate is that the target
//     suppression file SHRANK (fix-then-`eslint --prune-suppressions`), not a
//     focused test.
//
// WHY the merge is NOT here: toggling branch protection + squash-merging to a
// shared default branch + the post-merge composition suite are outward-facing and
// easy to get subtly wrong. Those stay a deliberate operator step; this workflow
// hands you reviewed, pushed branches + a go/no-go verdict.
//
// ── args contract ────────────────────────────────────────────────────────────
//   args = {
//     mode:          "maintenance",                // "refactor" (default) | "maintenance" | "codemod" | "content"
//     tiering_profile: "default",                  // "default" | "budget-first" | "quality-first" (profiles/tiering-profiles.yaml)
//     repo:          "ToscanAI/value-investing",
//     base:          "main",
//     suiteCmd:      "pnpm --filter @rule1/web typecheck",  // the per-lane suite/gate
//     expectedSuite: "tsc --noEmit clean",
//     facadeTest:    "",                            // refactor mode only: the contract/surface test
//     invariant:     "...",                         // override the per-mode default invariant
//     lanes: [
//       {
//         id: "651-marketcap", issue: 651, branch: "fix/651-marketcap",
//         files:       "the exact files this lane may edit",
//         implement:   "the lane-specific change (content mode: the content brief for the module)",
//         reviewFocus: "what the spec-adversary/reviewer (or content gates) must scrutinize",
//         suppressionFile: "packages/db/.eslint-suppressions.json", // codemod mode: EFFECTIVELY REQUIRED — the bulk-suppression baseline the lane must shrink (the reviewer's count-gate is disarmed without it)
//         residual:    "none",                      // codemod mode OPTIONAL: pre-declared protected suppression entries that MAY remain (+ a one-line load-bearing rationale each); "none"/empty ⇒ drive the file to zero (or delete it)
//         sourceFile:  "/tmp/e22-sources/greeks.md", // content mode: REQUIRED — absolute host path to the operator-refined source_material.md (readable from the worktree agents); research + draft + fact_check all read it
//         content_type: "page",                     // content mode OPTIONAL: "page" | "glossary-term" | "video-entry" (informational)
//       },
//       ...
//     ],
//   }
// ─────────────────────────────────────────────────────────────────────────────

// `args` may arrive as a JSON STRING (the Workflow harness stringifies args on
// the persisted/{name} path) or as a plain object — tolerate BOTH so the wave is
// callable with lanes either way. A string that fails to parse degrades to the
// empty-lanes no-op below rather than throwing.
let A = args || {}
if (typeof A === 'string') {
  try { A = JSON.parse(A) } catch (e) { log(`orchemist-wave: args arrived as a non-JSON string — ${e.message}`); A = {} }
}
const lanes = Array.isArray(A.lanes) ? A.lanes : []

if (lanes.length === 0) {
  log('orchemist-wave: args.lanes is empty — nothing to do. Pass lanes via the Workflow `args`.')
  return { ready: false, lanes: [], note: 'no lanes provided' }
}

const mode = A.mode === 'maintenance' ? 'maintenance' : A.mode === 'codemod' ? 'codemod' : A.mode === 'content' ? 'content' : 'refactor'
const repo = A.repo || '(repo unset)'
const base = A.base || 'main'
const suiteCmd = A.suiteCmd || (mode === 'maintenance' ? 'the repo typecheck/build/lint gate' : mode === 'codemod' ? 'the repo lint + typecheck + full-suite gate' : mode === 'content' ? 'the repo typecheck + lint + focused unit-test gate' : 'python3 -m pytest -q')

// content mode: absolute host path where the draft captures its diff for the Bash-less
// red-team gate to Read (the orchemist-adversary has no git). lane.id is unique per wave.
const contentDiffPath = (lane) => `/tmp/orchemist-wave-content/${lane.id}.diff`
const expectedSuite = A.expectedSuite || '(unspecified — match the pre-wave green baseline)'
const facadeTest = A.facadeTest || ''
const invariant =
  A.invariant ||
  (mode === 'maintenance'
    ? 'Maintenance/infra/data fix — you DO add behavior + a FOCUSED test (this is NOT a behavior-preserving refactor). Keep the change MINIMAL + additive; edit ONLY the planned files. Preserve every UNRELATED seal pin; an explicitly-anticipated seal-break is an AUDITED re-baseline — change only the named pins, byte-correct, never an accommodation. Validate with a focused unit/e2e test when locally testable, else PROD-VALIDATION. Do NOT hand-edit unrelated tests. middleware HARD-NO.'
    : mode === 'codemod'
    ? 'Behavior-preserving codemod/lint cleanup — behavior 100% UNCHANGED; NO new behavior, NO new test. Each fix is EITHER auto-fixable-style (`eslint --fix`) OR an inline `// eslint-disable-next-line <rule> -- <reason>` with a REAL one-line rationale for a genuinely load-bearing case (never a blanket re-suppress). **Behavior-preserving boundary:** type-only narrowing that leaves the runtime path unchanged (a non-null assertion `arr[i]!`, an `as`-narrowing, a type guard that does NOT alter emitted control flow) IS the behavior-preserving path and is PERMITTED; any fix that changes a runtime-observable path (introducing a `?.` short-circuit, a guard/throw/early-return, a changed value) must instead be a pre-declared `residual` with a rationale, OR be routed OUT of the codemod lane into a maintenance lane. The public surface + every caller import path stay byte-identical. Do NOT modify tests EXCEPT to drop a now-unnecessary suppression. Preserve every UNRELATED seal pin. Edit ONLY the planned files. middleware HARD-NO.'
    : mode === 'content'
    ? 'In-app CONTENT authored as a real committed diff. Author ORIGINAL explainers in OUR OWN VOICE — never reproduce source prose. DROP all proprietary "Rule #1"/"Rule One"/product-version branding. Every FACTUAL claim must trace to the pre-placed source_material.md OR an authoritative source verified during research; every curated link must RESOLVE; every video ID + its stated duration must be WEB-VERIFIED (no fabrication — a fabricated duration is a hard defect). Honor the correctness anchors named in the source material (e.g. option SELLER = obligation + collects premium). Options content MUST carry the asymmetric-risk + education-not-advice framing. Edit ONLY the planned disjoint files (do not touch a sibling lane\'s file or any shared/pre-wired file); existing content stays unchanged. middleware HARD-NO.'
    : 'Behavior 100% unchanged; the public surface and every caller import path stay byte-identical; do NOT modify any tests.')

// ── #41 tiering-profile effort (Workflow path — the one path that CAN pass per-phase effort) ──
// Inline effort ladders MIRROR profiles/tiering-profiles.yaml; tests/test_tiering_profiles.py
// (test_wave_effort_map_in_sync) locks the shipped values so JS + YAML cannot silently diverge.
// `inherit` ⇒ omit `effort` entirely, so the `default` profile passes NO effort and every dispatch
// stays byte-identical to the pre-#41 wave (backward-compat).
const tieringProfile = A.tiering_profile || 'default'
const EFFORT_BY_PROFILE = {
  'default':       { rote: 'inherit', interpretive: 'inherit', implement: 'inherit', gate: 'inherit' },
  'budget-first':  { rote: 'low',     interpretive: 'medium',  implement: 'high',    gate: 'xhigh' },
  'quality-first': { rote: 'medium',  interpretive: 'high',    implement: 'high',    gate: 'xhigh' },
}
const effortFor = (cls) => {
  const e = (EFFORT_BY_PROFILE[tieringProfile] || EFFORT_BY_PROFILE['default'])[cls]
  return e && e !== 'inherit' ? { effort: e } : {}
}

const IMPL_SCHEMA = {
  type: 'object',
  additionalProperties: true,
  required: ['status'],
  properties: {
    status: { type: 'string', enum: ['pushed', 'blocked'], description: "'pushed' ONLY if the suite/test is green and the branch is on origin; else 'blocked'." },
    pushed_sha: { type: 'string', description: 'full sha of the pushed branch head (empty if blocked)' },
    suite: { type: 'string', description: 'the suite/test result line' },
    facade_test: { type: 'string', description: 'refactor mode: PASS/FAIL of the contract/surface test' },
    files: { type: 'array', items: { type: 'string' }, description: 'files created/changed' },
    notes: { type: 'string', description: 'anything the reviewer should scrutinize: seal-breaks, deviations, BLOCKED reasons' },
  },
}

const VERDICT_SCHEMA = {
  type: 'object',
  additionalProperties: true,
  required: ['verdict'],
  properties: {
    verdict: { type: 'string', enum: ['APPROVE', 'REQUEST_CHANGES'] },
    blockers: { type: 'array', items: { type: 'string' } },
    majors: { type: 'array', items: { type: 'string' } },
    surface_diff_clean: { type: 'boolean' },
    notes: { type: 'string' },
  },
}

const SPEC_SCHEMA = {
  type: 'object',
  additionalProperties: true,
  required: ['plan'],
  properties: {
    plan: { type: 'string', description: 'the focused implementation plan: exact files to touch, the approach, the seal surface to AVOID, the VALIDATION plan (focused test or prod-validation)' },
    files: { type: 'array', items: { type: 'string' } },
    validation: { type: 'string', description: 'focused-test (and which) OR prod-validation steps' },
  },
}

// content mode — research findings feeding the draft, and the draft's committed diff.
const RESEARCH_SCHEMA = {
  type: 'object',
  additionalProperties: true,
  required: ['notes'],
  properties: {
    notes: { type: 'string', description: 'research findings: which curated links resolve, and confirmation (against ≥2 authoritative sources, cited) of each correctness anchor the source material names' },
    verified_links: { type: 'array', items: { type: 'string' }, description: 'the source URLs confirmed to RESOLVE' },
    verified_videos: { type: 'array', items: { type: 'string' }, description: 'each entry: source · title · youtube-nocookie ID · REAL duration (oEmbed-verified) — draft uses ONLY these' },
    corrections: { type: 'string', description: 'any claim in source_material.md that web-verification CONTRADICTS, with the corrected fact (empty if none)' },
  },
}
// draft impl adds diff_path (the captured diff the Bash-less red-team reads).
const CONTENT_IMPL_SCHEMA = {
  type: 'object',
  additionalProperties: true,
  required: ['status'],
  properties: {
    status: { type: 'string', enum: ['pushed', 'blocked'], description: "'pushed' ONLY if the gate is green and the branch is on origin; else 'blocked'." },
    pushed_sha: { type: 'string', description: 'full sha of the pushed branch head (empty if blocked)' },
    suite: { type: 'string', description: 'the typecheck/lint/unit-test gate result line' },
    diff_path: { type: 'string', description: 'absolute path where the full `git diff base...HEAD` was captured for the red-team' },
    files: { type: 'array', items: { type: 'string' }, description: 'files created/changed' },
    notes: { type: 'string', description: 'anything the gates should scrutinize: deviations, BLOCKED reasons' },
  },
}

// ── refactor-mode prompts (the original EPIC #942 flow) ───────────────────────
function refactorImplementPrompt(lane) {
  return `You are running lane "${lane.id}" (issue #${lane.issue}) of a parallel WAVE of behavior-preserving changes. The bar is ZERO functional change.

## Sealed sandbox
You are in your OWN fresh git worktree (isolated for this lane). Work ONLY here; do not touch sibling lanes.
1. \`git fetch origin --quiet\` then \`git checkout -b ${lane.branch} origin/${base}\`.
2. Run EVERY python/pytest invocation the way the suite command shows below — an editable install otherwise resolves the ORIGINAL checkout, not this worktree (e.g. prefix \`PYTHONPATH=src\`).

## The change (lane-specific)
${lane.implement}

## Invariant — non-negotiable
${invariant}
- Move code VERBATIM. Preserve the public surface so NO caller import path changes (the facade re-exports the exact current surface).
- If a moved symbol uses a MODULE-GLOBAL that a test patches (e.g. \`patch("pkg.module.dep")\`), reference that dep at CALL time through the package facade so the patch still intercepts — do NOT capture it at import. Apply this ONLY to module-globals, not to function-local lazy imports.

## Validate — ALL must pass before you push
1. **Surface-diff FIRST:** capture the relevant public surface BEFORE editing (CLI \`--help\` tree / \`dir(Class)\` / FastAPI route table / module \`dir()\`), and diff after — it must be IDENTICAL. Re-export anything dropped. The full suite will NOT catch an internally-referenced-only drop (constant/regex/private) — only this explicit diff will.
2. Lint/format clean on the files you changed.
${facadeTest ? `3. The contract test must stay green: run it specifically (\`${facadeTest}\`). If it fails, fix the facade re-exports — NEVER the test.\n` : ''}4. **Full suite:** \`${suiteCmd}\` — expect ${expectedSuite}. A failure, or a drop in the collected count, means an import broke.
5. Do NOT modify anything under \`tests/\`.

## Commit & push (NO PR — the operator opens PRs at merge time)
Stage only your intended files, commit, then \`git push -u origin ${lane.branch}\`. Confirm local HEAD == the pushed remote head.

Return the StructuredOutput: status ('pushed' only if the full suite is green AND the branch is pushed; otherwise 'blocked'), pushed_sha, suite (the pass/fail/skip line), facade_test, files, and notes. If you cannot get the suite green, set status='blocked', do NOT push, and explain in notes.`
}

function refactorReviewPrompt(lane, impl) {
  return `You are an INDEPENDENT senior reviewer for wave lane "${lane.id}" (issue #${lane.issue}) on ${repo}. Verdict: APPROVE or REQUEST_CHANGES. Be adversarial — VERIFY, do not trust the implementer. A dropped re-export can pass both the contract test AND the full suite; only an explicit surface-diff catches it.

## Read-only mandate
You are in your own worktree. Inspect the branch \`${lane.branch}\` @ \`${impl.pushed_sha || '(see origin)'}\`, forked from \`${base}\`. Use \`git fetch origin\`, \`git diff ${base}...origin/${lane.branch}\`, \`git show\`, read files, and READ-ONLY checks. Do NOT write/edit/commit/stash/restore/push. If a fix is needed, describe it — do not apply it.

## Implementer claimed (verify, don't trust)
suite = ${impl.suite || '(none)'} · files = ${(impl.files || []).join(', ') || '(unspecified)'} · notes = ${impl.notes || '(none)'}

## Verify — the durable gates
1. **Public-surface diff:** reconstruct the parent surface from \`${base}\` and compare to the branch. Nothing dropped — especially internally-referenced-only constants/regexes/privates. ${lane.reviewFocus || ''}
2. **Verbatim fidelity:** AST/byte-compare the moved symbols against \`${base}\` — no logic drift beyond the intended, declared rewrites.
3. **Contract + suite:** confirm the contract test is green and the full-suite claim is consistent (re-run the targeted tests).
4. **No test tampering:** \`git diff --stat ${base}...origin/${lane.branch}\` shows ZERO files under \`tests/\`.

Return the StructuredOutput: verdict, blockers (numbered, file:line + why), majors, surface_diff_clean (bool), notes. REQUEST_CHANGES on any blocker or any real surface regression.`
}

// ── maintenance/codemod-mode prompts (shared spec trio + per-mode implement/review) ──
// laneKind is reached ONLY by codemod + maintenance (refactor never calls the trio);
// with mode==='maintenance' it is the literal 'bug/infra/data fix' the trio always used.
const laneKind = mode === 'codemod' ? 'behavior-preserving codemod/lint cleanup' : 'bug/infra/data fix'
function specPrompt(lane) {
  return `You are the SPEC agent for ${mode}-wave lane "${lane.id}" (issue #${lane.issue}) on ${repo}. Produce a FOCUSED implementation plan for this ${laneKind} (WHAT + HOW). READ-ONLY — no code edits.

## The change
${lane.implement}

## Files this lane may touch
${lane.files || '(infer from the change; keep it minimal + file-disjoint from sibling lanes)'}

Recon the area-of-change in the repo, then plan: the EXACT files to edit, the approach, the SEAL SURFACE to AVOID (verify-scripts/SHA-pins near the change — or, if a seal-break is genuinely required, name the exact pin to re-baseline and why it's anticipated), and the VALIDATION plan: ${mode === 'codemod' ? 'lint+typecheck+suite stay GREEN AND the target bulk-suppression file shrinks to ONLY the pre-declared protected residual (name the residual entries you keep + why each is load-bearing) — no new test.' : 'a FOCUSED unit/e2e test if locally testable, else the concrete PROD-VALIDATION steps.'} Do NOT propose a heavyweight sealed verify-script.

Return the StructuredOutput: { plan: <the full plan>, files: [...], validation: <focused-test (which) | prod-validation steps> }.`
}

function specRevisePrompt(lane, prevPlan, verdict) {
  return `You are the SPEC agent REVISING the plan for ${mode}-wave lane "${lane.id}" (issue #${lane.issue}). An independent fable adversary found problems. Apply the VERBATIM fixes; keep everything else stable. READ-ONLY.

## The change
${lane.implement}

## Previous plan
${prevPlan}

## Adversary findings (address every blocker)
${(verdict.blockers || []).map((b, i) => `${i + 1}. ${b}`).join('\n') || verdict.notes || '(see notes)'}

Return the StructuredOutput: { plan, files, validation } — the corrected plan.`
}

function specAdversaryPrompt(lane, spec) {
  return `You are the SPEC ADVERSARY (Fable 5) for ${mode}-wave lane "${lane.id}" (issue #${lane.issue}) on ${repo}. Independently pressure-test the fix APPROACH for correctness, safety, timing, seal-impact, and missed edge cases — the key quality gate for ${mode === 'codemod' ? 'behavior-preserving cleanup work' : 'prod-affecting maintenance work'}. READ-ONLY; verify against the REAL code.

## The change
${lane.implement}

## Proposed plan (vet it)
${spec.plan}

## Decisive checks
- ${mode === 'codemod' ? 'Does the plan PRESERVE behavior AND drive the target bulk-suppression file to the declared residual? Is each fix auto-fixable-style (`eslint --fix`) OR an inline `// eslint-disable-next-line <rule> -- <reason>` with a real load-bearing rationale (not a blanket re-suppress)?' : 'Does the approach actually fix the issue, end-to-end? Any path it misses?'}
- SEAL IMPACT: does it touch a byte-locked / SHA-pinned / HARD-NO surface unexpectedly? Is any seal-break genuinely anticipated + named (vs a surprise)?
- NIGHTLY SEAL FOOTPRINT: if the lane adds a shared-type field, a cross-package importer, or a new test / \`__tests__\` file, does the plan enumerate the NIGHTLY/AGGREGATE-only pins that footprint touches — a count·keyof / field-count / set-equality pin AND any recursive importer/dir allowlist (typically globs \`__tests__/\`) — BEYOND the lane's OWN verify script, and NAME each such pin to re-baseline? A lane green on its own suite can still land RED on the post-merge full-suite; catch it pre-merge.
- ${mode === 'codemod' ? 'Is the VALIDATION right — lint/typecheck/suite GREEN AND the suppression file shrank to the declared residual (count N → residual), not merely lint exit 0? No new test?' : 'Is the VALIDATION right — a focused test where locally testable, or honest prod-validation where deploy/cloud-side?'}
- Scope: does it edit ONLY its files (file-disjoint from sibling lanes)? ${lane.reviewFocus || ''}

Name BLOCKER / MAJOR / MINOR with file:line + a fix. Return the StructuredOutput: { verdict: APPROVE|REQUEST_CHANGES, blockers: [...], majors: [...], notes }.`
}

function maintImplementPrompt(lane, spec) {
  return `You are the IMPLEMENTER for maintenance-wave lane "${lane.id}" (issue #${lane.issue}) on ${repo}. This is a maintenance/infra/data fix — you DO add behavior + a FOCUSED test (NOT a behavior-preserving refactor).

## Sealed worktree
You are in your OWN fresh git worktree. Work ONLY here.
1. \`git fetch origin --quiet\` then \`git checkout -b ${lane.branch} origin/${base}\`.
2. If a JS/TS repo: \`pnpm install --prefer-offline\` (a worktree has no node_modules; warm store → fast). Run every test the way the suite command shows so it resolves THIS worktree.

## The change
${lane.implement}

## The approved plan (follow it)
${spec.plan}

## Files you may edit (ONLY these)
${lane.files || '(per the plan — minimal + file-disjoint from sibling lanes)'}

## Invariant — non-negotiable
${invariant}

## Validate — ALL green before you push
1. The suite/gate: \`${suiteCmd}\` (expect: ${expectedSuite}).
2. The FOCUSED test from the plan — GREEN (or, if prod-validatable only, state that clearly).
3. The regression seals for files you touched still pass their structural legs (a pre-existing environmental red that also fails on ${base} is acceptable; a NEW structural red is not). Any anticipated seal-break = audited re-baseline (only the named pins, byte-correct).

## Commit & push (NO PR — operator merges)
Stage ONLY your intended files, commit ("Refs #${lane.issue}"), \`git push -u origin ${lane.branch}\`. Confirm local HEAD == pushed.

Return the StructuredOutput: status ('pushed' only if green + pushed; else 'blocked'), pushed_sha, suite (the result line), files, notes (seal-breaks, deviations, BLOCKED reasons). If you cannot get green, status='blocked', do NOT push, explain in notes.`
}

function maintReviewPrompt(lane, impl) {
  return `You are an INDEPENDENT fable reviewer for maintenance-wave lane "${lane.id}" (issue #${lane.issue}) on ${repo}. Verdict: APPROVE or REQUEST_CHANGES. Be adversarial — VERIFY, do not trust the implementer.

## Read-only mandate
Inspect branch \`${lane.branch}\` @ \`${impl.pushed_sha || '(see origin)'}\`, forked from \`${base}\`. Use \`git fetch origin\`, \`git diff ${base}...origin/${lane.branch}\`, \`git show\`, read files, read-only checks. Do NOT write/edit/commit/stash/restore/push.

## Implementer claimed (verify, don't trust)
suite = ${impl.suite || '(none)'} · files = ${(impl.files || []).join(', ') || '(unspecified)'} · notes = ${impl.notes || '(none)'}

## Verify — the durable gates
1. **The fix is correct + complete** per the issue. ${lane.reviewFocus || ''}
2. **Scope:** \`git diff --stat ${base}...origin/${lane.branch}\` touches ONLY this lane's intended files — no sibling-lane file, no middleware, no unrelated change.
3. **Seals:** unrelated pins intact; any seal-break is the ANTICIPATED/audited one (anti-mask — only the named pins changed, byte-correct, the old pin was the thing being corrected, not an accommodation). NIGHTLY FOOTPRINT: if the diff adds a shared-type field / cross-package importer / new test file, INDEPENDENTLY check whether a nightly/aggregate count·keyof pin or a recursive importer/dir allowlist should have been re-baselined and was — flag a MAJOR if an un-re-baselined nightly-only pin is left that the post-merge full-suite would fail on (a lane green on its own suite can still be RED on the aggregate gate).
4. **The focused test genuinely proves the fix** (not tautological); re-run the touched-area checks read-only. Distinguish a PRE-EXISTING red (also red on ${base}) from a NEW regression.

Return the StructuredOutput: verdict, blockers (file:line + why), majors, notes. REQUEST_CHANGES on any real fix-gap, scope breach, or seal regression.`
}

// ── codemod-mode prompts (behavior-preserving lint/codemod cleanup, no new test) ──
function codemodImplementPrompt(lane, spec) {
  return `You are the IMPLEMENTER for codemod-wave lane "${lane.id}" (issue #${lane.issue}) on ${repo}. This is a BEHAVIOR-PRESERVING codemod/lint cleanup — behavior 100% unchanged, NO new behavior, NO new test.

## Sealed worktree
You are in your OWN fresh git worktree. Work ONLY here.
1. \`git fetch origin --quiet\` then \`git checkout -b ${lane.branch} origin/${base}\`.
2. If a JS/TS repo: \`pnpm install --prefer-offline\` (a worktree has no node_modules; warm store → fast). Run every check the way the suite command shows so it resolves THIS worktree.

## The change
${lane.implement}

## The approved plan (follow it)
${spec.plan}

## Files you may edit (ONLY these)
${lane.files || '(per the plan — minimal + file-disjoint from sibling lanes)'}

## Invariant — non-negotiable
${invariant}

## Validate — ALL green before you push
1. The gate: \`${suiteCmd}\` (lint + typecheck + full suite) GREEN (expect: ${expectedSuite}).
2. The target bulk-suppression file \`${lane.suppressionFile || '(the baseline named in the plan)'}\` reduced to ONLY the declared residual \`${lane.residual || '(none — drive it to zero / delete if empty)'}\`. **Shrink MECHANISM:** fix the violation, THEN run \`eslint --prune-suppressions\` — its safety property (a pruned entry that still lints GREEN ⇒ the violation is genuinely gone) is the whole point. FORBID bare-deletion-of-entries-without-fix. NOT merely lint exit 0 — lint/typecheck MUST stay GREEN AFTER the prune. A deleted suppression file counts as zero residual. Report the before→after count.
3. Public surface + caller import paths byte-identical; tests untouched EXCEPT dropping a now-unnecessary suppression; unrelated seal pins intact.

## Commit & push (NO PR — operator merges)
Stage ONLY your intended files, commit ("Refs #${lane.issue}"), \`git push -u origin ${lane.branch}\`. Confirm local HEAD == pushed.

Return the StructuredOutput: status ('pushed' only if green + pushed; else 'blocked'), pushed_sha, suite (the result line), files, notes (put the "N → residual" suppression count line in notes; you may add suppression_before/suppression_after; plus seal-breaks, deviations, BLOCKED reasons). If you cannot get green, status='blocked', do NOT push, explain in notes.`
}

function codemodReviewPrompt(lane, impl) {
  return `You are an INDEPENDENT fable reviewer for codemod-wave lane "${lane.id}" (issue #${lane.issue}) on ${repo}. This was a BEHAVIOR-PRESERVING codemod/lint cleanup (no new behavior, no new test). Verdict: APPROVE or REQUEST_CHANGES. Be adversarial — VERIFY, do not trust the implementer.

## Read-only mandate
Inspect branch \`${lane.branch}\` @ \`${impl.pushed_sha || '(see origin)'}\`, forked from \`${base}\`. Use \`git fetch origin\`, \`git diff ${base}...origin/${lane.branch}\`, \`git show\`, read files, read-only checks. Do NOT write/edit/commit/stash/restore/push.

## Implementer claimed (verify, don't trust)
suite = ${impl.suite || '(none)'} · files = ${(impl.files || []).join(', ') || '(unspecified)'} · notes = ${impl.notes || '(none)'}

## Verify — the durable gates
1. **The gate is GREEN:** verify the implementer's \`${suiteCmd}\` claim (expect ${expectedSuite}); re-run the touched-area checks read-only. Distinguish a PRE-EXISTING red (also red on ${base}) from a NEW regression. The suppression file may only shrink BECAUSE violations were genuinely fixed — proven by lint/typecheck still GREEN after prune — never by bare deletion.
2. **Behavior-preserving:** AST/byte-check no logic change; each disable is auto-fix-style OR carries a real load-bearing \`-- <reason>\` (spot-check the rationales; reject a blanket re-suppress).
3. **Suppression shrank** — INDEPENDENTLY identify + count the target file \`${lane.suppressionFile || '(the baseline named in the plan)'}\` on \`origin/${lane.branch}\` vs \`${base}\`: it dropped from N to the declared residual \`${lane.residual || '(none — drive it to zero / delete if empty)'}\` — via fix-then-\`eslint --prune-suppressions\`, NOT by bare deletion, NOT merely lint exit 0; a deleted suppression file counts as zero residual. REQUEST_CHANGES if you cannot identify + count the file independently on base vs branch (do NOT fall back to trusting the implementer).
4. **Scope:** \`git diff --stat ${base}...origin/${lane.branch}\` touches ONLY this lane's planned files; tests touched ONLY to drop a now-unnecessary suppression; no middleware/sibling-lane/unrelated change.
5. **Seals:** unrelated pins intact; any anticipated seal-break is the audited/named one.

Return the StructuredOutput: verdict, blockers (file:line + why), majors, notes. REQUEST_CHANGES on any behavior change, an un-shrunk file, a bare-deletion, a RED gate, or a bogus rationale.`
}

// ── content-mode prompts (research → draft → fact_check gate → red_team gate, per-lane) ──
// Content = in-app data (a route-page + a data file + a curated allowlist) authored as a REAL
// committed diff, so the two fable gates review `git diff` exactly like a code reviewer. The
// pre-condition is an operator-refined source_material.md at lane.sourceFile (absolute host path).
function contentResearchPrompt(lane) {
  return `You are the RESEARCH agent (sonnet) for content-wave lane "${lane.id}" (issue #${lane.issue}) on ${repo}. READ-ONLY — no code edits, no branch, no worktree. You have WebSearch/WebFetch.

## Source material (operator-refined — the authoritative brief)
Read the pre-placed source material in full: \`${lane.sourceFile || '(lane.sourceFile UNSET — this is a content-mode requirement; report blocked)'}\`.

## Your job — ground the draft before it writes a word
1. **Verify every curated source URL RESOLVES** (WebFetch each) — flag any dead / redirected / wrong-topic link, and suggest the correct URL where you can.
2. **Verify every video** — confirm each youtube-nocookie ID exists and capture its REAL duration (oEmbed/watch page). The content pipeline has shipped FABRICATED durations before — catch them HERE so the draft only uses real IDs + real durations.
3. **Confirm each "correctness anchor"** the source names (the facts the fact_check gate must enforce) against **≥2 authoritative sources you cite** — flag any anchor the sources CONTRADICT (with the corrected fact).
4. Note the exact disjoint file surface this lane fills: ${lane.files || '(per the source material)'}.

Return the StructuredOutput { notes, verified_links, verified_videos, corrections }. Put the cited-source confirmations of the anchors in \`notes\`; corrected facts (if any) in \`corrections\`.`
}

function contentDraftPrompt(lane, research) {
  return `You are the DRAFT implementer (opus) for content-wave lane "${lane.id}" (issue #${lane.issue}) on ${repo}. You author IN-APP CONTENT as a real committed diff.

## Sealed worktree
You are in your OWN fresh git worktree. Work ONLY here.
1. \`git fetch origin --quiet\` then \`git checkout -b ${lane.branch} origin/${base}\`.
2. \`pnpm install --prefer-offline\` (a worktree has no node_modules; warm store → fast). Run every check the way the suite command shows so it resolves THIS worktree.

## Source material (author FROM this — it is the authoritative brief)
Read \`${lane.sourceFile}\` in FULL. Fold in the research findings:
${research.notes || '(no research notes)'}
- Verified videos — use ONLY these IDs + durations, do NOT invent any: ${(research.verified_videos || []).join('  |  ') || '(none verified — ship without a video rather than inventing one)'}
${research.corrections ? `- CORRECTIONS from research (the source material had errors — use the CORRECTED facts): ${research.corrections}` : ''}

## The content to build (lane-specific)
${lane.implement}

## Files you may edit (ONLY these — disjoint from sibling lanes; do NOT touch a shared/pre-wired file)
${lane.files || '(per the source material — minimal + file-disjoint)'}

## Invariant — non-negotiable
${invariant}

## Validate — ALL green before you push
1. The gate: \`${suiteCmd}\` (expect: ${expectedSuite}).
2. The FOCUSED invariant test you add (curated-link present per item, video IDs on the allowlist, anti-brand, the correctness anchor holds) — GREEN.

## Capture the diff (for the Bash-less red-team) + push
After committing, capture the full diff to an absolute path that survives outside the worktree:
\`mkdir -p /tmp/orchemist-wave-content && git diff origin/${base}...HEAD > ${contentDiffPath(lane)}\`
Then \`git push -u origin ${lane.branch}\`; confirm local HEAD == pushed remote head.
Commit "Refs #${lane.issue}".

Return the StructuredOutput: status ('pushed' only if the gate is green AND the branch is pushed AND ${contentDiffPath(lane)} was written; else 'blocked'), pushed_sha, suite (the result line), diff_path='${contentDiffPath(lane)}', files, notes. If you cannot get the gate green, status='blocked', do NOT push, explain in notes.`
}

function contentFactCheckPrompt(lane, impl) {
  return `You are the FACT-CHECK gate (Fable 5) for content-wave lane "${lane.id}" (issue #${lane.issue}) on ${repo}. You have web + git. Verdict: APPROVE or REQUEST_CHANGES. This is a BLOCKING gate — a wrong fact or dead link ships to production.

## Read-only mandate
Inspect the pushed branch: \`git fetch origin\` then \`git diff ${base}...origin/${lane.branch}\` and \`git show\`. Read the authoritative brief \`${lane.sourceFile}\`. Do NOT write/edit/commit/push.

## Draft claimed (verify, don't trust)
suite = ${impl.suite || '(none)'} · files = ${(impl.files || []).join(', ') || '(unspecified)'} · notes = ${impl.notes || '(none)'}

## Verify — SOURCE-GROUNDED (the durable gates)
1. **Every factual claim** in the new content traces to \`${lane.sourceFile}\` OR an authoritative source you WEB-VERIFY NOW (cite it). An unverifiable claim is a BLOCKER.
2. **Every curated link RESOLVES** (WebFetch each). **Every video ID exists + its stated duration is REAL** (oEmbed) — a fabricated/misstated duration or a dead link is a BLOCKER.
3. **The correctness anchors named in \`${lane.sourceFile}\` HOLD** in the content (e.g. the SELLER holds the obligation + collects the premium; no inverted mechanics; an approximation is not overstated as an identity). An inversion is a BLOCKER.
4. **Zero proprietary branding.** ${lane.reviewFocus || ''}

Name BLOCKER / MAJOR / MINOR with the file:line + the CORRECT fact + its source. Return the StructuredOutput: { verdict: APPROVE|REQUEST_CHANGES, blockers: [...], majors: [...], notes }. REQUEST_CHANGES on any unverifiable claim, dead link, fabricated video field, or anchor inversion.`
}

function contentRedTeamPrompt(lane, impl) {
  return `You are the RED-TEAM gate (Fable 5) for content-wave lane "${lane.id}" (issue #${lane.issue}) on ${repo}. READ-ONLY — you have Read/Grep/Glob only (NO Bash/git). Verdict: APPROVE or REQUEST_CHANGES. This is a BLOCKING gate.

## Evidence (you cannot run git — read the pre-captured diff)
The draft's full diff is pre-captured at \`${impl.diff_path || contentDiffPath(lane)}\` — READ it. Also read the new/edited files on disk under ${repo} and the authoritative brief \`${lane.sourceFile}\`.

## Audit — tone / IP / brand / claim-support / risk-framing
1. **Original voice** — no reproduced source prose; reading level + tone appropriate for a learner.
2. **NO proprietary branding** — zero "Rule #1"/"Rule One"/product-version strings anywhere in the diff.
3. **Every strong claim is SUPPORTED, not overstated**, and the required RISK FRAMING is present (this is options content — the asymmetric-loss-risk + education-not-advice posture must appear; per-strategy max-loss/trade-off where the source demands it).
4. **Scope** — only this lane's disjoint files are touched (no sibling-lane file, no shared/pre-wired file).${lane.reviewFocus ? `\n5. ${lane.reviewFocus}` : ''}

Name BLOCKER / MAJOR / MINOR. Return the StructuredOutput: { verdict: APPROVE|REQUEST_CHANGES, blockers: [...], majors: [...], notes }. REQUEST_CHANGES on any branding leak, unsupported/overstated claim, missing risk framing, or scope breach.`
}

function contentRedraftPrompt(lane, impl, verdict, whichGate) {
  const fixes = (verdict.blockers || []).concat(verdict.majors || [])
  return `You are the DRAFT implementer REVISING content-wave lane "${lane.id}" (issue #${lane.issue}) after the ${whichGate} gate returned REQUEST_CHANGES. Apply ONLY the prescribed fixes; keep everything else BYTE-STABLE. Fresh worktree.

## Sealed worktree — re-check out the pushed branch
1. \`git fetch origin --quiet\` then \`git checkout -B ${lane.branch} origin/${lane.branch}\` (reset local to the already-pushed branch). \`pnpm install --prefer-offline\`.

## Apply these verbatim fixes (nothing else)
${fixes.map((b, i) => `${i + 1}. ${b}`).join('\n') || verdict.notes || '(see notes)'}

## Invariant — still non-negotiable
${invariant}

## Validate + re-capture + push
1. \`${suiteCmd}\` GREEN + the focused test GREEN.
2. Re-capture the diff: \`mkdir -p /tmp/orchemist-wave-content && git diff origin/${base}...HEAD > ${contentDiffPath(lane)}\`.
3. \`git push origin ${lane.branch}\` (update the branch); confirm local HEAD == pushed.

Return the StructuredOutput: status ('pushed' only if green + pushed; else 'blocked'), pushed_sha, suite, diff_path='${contentDiffPath(lane)}', files, notes. If you cannot get green, status='blocked', do NOT push, explain in notes.`
}

log(`orchemist-wave [${mode}]: ${lanes.length} lane(s) off ${repo}@${base} — ${mode === 'maintenance' ? 'spec → fable adversary → implement → fable review' : mode === 'codemod' ? 'spec → fable adversary → codemod-implement → fable review' : mode === 'content' ? 'research → draft (opus, worktree) → fact_check (fable gate) → red_team (fable gate)' : 'implement (opus, worktree) → fable review'}, per-lane lockstep. Merge stays an operator step.`)

// Shared: turn a (lane, impl) into a reviewed result, or a blocked record.
function blockedRecord(lane, impl, reason) {
  log(`lane ${lane.id}: BLOCKED — ${reason}`)
  return {
    lane: lane.id, issue: lane.issue, branch: lane.branch,
    pushed: false, pushed_sha: impl ? impl.pushed_sha || '' : '',
    suite: impl ? impl.suite : '', verdict: 'BLOCKED_IMPLEMENT',
    blockers: [reason],
  }
}
function reviewedRecord(lane, impl, v) {
  return {
    lane: lane.id, issue: lane.issue, branch: lane.branch,
    pushed: true, pushed_sha: impl.pushed_sha, suite: impl.suite,
    verdict: v.verdict, blockers: v.blockers || [], majors: v.majors || [],
    surface_diff_clean: v.surface_diff_clean, review_notes: v.notes,
  }
}
// content mode: a gate (fact_check/red_team) blocked the lane. The branch IS pushed, but the
// lane is NOT merge-ready — verdict REQUEST_CHANGES so it lands in `blocked`, never merged.
function contentBlocked(lane, impl, gate, v) {
  const reason = `${gate} gate ${v ? v.verdict : 'returned null'}${v && v.blockers && v.blockers.length ? ': ' + v.blockers.join('; ') : ''}`
  log(`lane ${lane.id}: BLOCKED — ${reason}`)
  return {
    lane: lane.id, issue: lane.issue, branch: lane.branch,
    pushed: true, pushed_sha: impl.pushed_sha, suite: impl.suite,
    verdict: 'REQUEST_CHANGES', blockers: (v && v.blockers && v.blockers.length ? v.blockers : [reason]),
    majors: (v && v.majors) || [], review_notes: v && v.notes,
  }
}

let results
if (mode === 'maintenance') {
  // Per lane: spec + fable spec-adversary (one bounded revise) → implement → fable review.
  results = await pipeline(
    lanes,
    async (lane) => {
      let spec = await agent(specPrompt(lane), { label: `spec:${lane.id}`, phase: 'Spec', agentType: 'general-purpose', schema: SPEC_SCHEMA, ...effortFor('interpretive') })
      if (!spec) return { lane, spec: null }
      for (let round = 0; round < 2; round++) {
        const v = await agent(specAdversaryPrompt(lane, spec), { label: `spec-adv:${lane.id}`, phase: 'Spec', agentType: 'orchemist-adversary', model: 'fable', schema: VERDICT_SCHEMA, ...effortFor('gate') })
        if (!v || v.verdict === 'APPROVE') break
        if (round === 1) { log(`lane ${lane.id}: spec-adversary still REQUEST_CHANGES after 1 revise — implement proceeds with the adversary notes folded in.`); break }
        const revised = await agent(specRevisePrompt(lane, spec.plan, v), { label: `spec-rev:${lane.id}`, phase: 'Spec', agentType: 'general-purpose', schema: SPEC_SCHEMA, ...effortFor('interpretive') })
        if (revised) spec = revised
      }
      return { lane, spec }
    },
    async ({ lane, spec }) => {
      if (!spec) return { lane, impl: null }
      const impl = await agent(maintImplementPrompt(lane, spec), { label: `impl:${lane.id}`, phase: 'Implement', agentType: 'orchemist-implementer', model: 'opus', isolation: 'worktree', schema: IMPL_SCHEMA, ...effortFor('implement') })
      return { lane, impl }
    },
    async ({ lane, impl }) => {
      if (!impl || impl.status !== 'pushed') return blockedRecord(lane, impl, impl ? impl.notes || 'implement did not reach pushed state' : 'spec or implement returned null')
      const v = await agent(maintReviewPrompt(lane, impl), { label: `review:${lane.id}`, phase: 'Review', agentType: 'general-purpose', model: 'fable', schema: VERDICT_SCHEMA, ...effortFor('gate') })
      return reviewedRecord(lane, impl, v)
    },
  )
} else if (mode === 'codemod') {
  // Per lane: spec + fable spec-adversary (one bounded revise) → codemod-implement → fable review.
  results = await pipeline(
    lanes,
    async (lane) => {
      let spec = await agent(specPrompt(lane), { label: `spec:${lane.id}`, phase: 'Spec', agentType: 'general-purpose', schema: SPEC_SCHEMA, ...effortFor('interpretive') })
      if (!spec) return { lane, spec: null }
      for (let round = 0; round < 2; round++) {
        const v = await agent(specAdversaryPrompt(lane, spec), { label: `spec-adv:${lane.id}`, phase: 'Spec', agentType: 'orchemist-adversary', model: 'fable', schema: VERDICT_SCHEMA, ...effortFor('gate') })
        if (!v || v.verdict === 'APPROVE') break
        if (round === 1) { log(`lane ${lane.id}: spec-adversary still REQUEST_CHANGES after 1 revise — implement proceeds with the adversary notes folded in.`); break }
        const revised = await agent(specRevisePrompt(lane, spec.plan, v), { label: `spec-rev:${lane.id}`, phase: 'Spec', agentType: 'general-purpose', schema: SPEC_SCHEMA, ...effortFor('interpretive') })
        if (revised) spec = revised
      }
      return { lane, spec }
    },
    async ({ lane, spec }) => {
      if (!spec) return { lane, impl: null }
      const impl = await agent(codemodImplementPrompt(lane, spec), { label: `impl:${lane.id}`, phase: 'Implement', agentType: 'orchemist-implementer', model: 'opus', isolation: 'worktree', schema: IMPL_SCHEMA, ...effortFor('implement') })
      return { lane, impl }
    },
    async ({ lane, impl }) => {
      if (!impl || impl.status !== 'pushed') return blockedRecord(lane, impl, impl ? impl.notes || 'implement did not reach pushed state' : 'spec or implement returned null')
      const v = await agent(codemodReviewPrompt(lane, impl), { label: `review:${lane.id}`, phase: 'Review', agentType: 'general-purpose', model: 'fable', schema: VERDICT_SCHEMA, ...effortFor('gate') })
      return reviewedRecord(lane, impl, v)
    },
  )
} else if (mode === 'content') {
  // Per lane: research(sonnet) → draft(opus, worktree, real diff) → fact_check(fable gate)
  // → red_team(fable gate). Each gate does ONE bounded re-draft on REQUEST_CHANGES; a gate
  // still un-approved after the revise BLOCKS the lane (pushed but not merge-ready).
  results = await pipeline(
    lanes,
    async (lane) => {
      const research = await agent(contentResearchPrompt(lane), { label: `research:${lane.id}`, phase: 'Research', agentType: 'general-purpose', model: 'sonnet', schema: RESEARCH_SCHEMA, ...effortFor('interpretive') })
      return { lane, research: research || { notes: '(research returned null — draft proceeds from source_material alone)', verified_videos: [], corrections: '' } }
    },
    async ({ lane, research }) => {
      const impl = await agent(contentDraftPrompt(lane, research), { label: `draft:${lane.id}`, phase: 'Draft', agentType: 'orchemist-implementer', model: 'opus', isolation: 'worktree', schema: CONTENT_IMPL_SCHEMA, ...effortFor('implement') })
      return { lane, impl }
    },
    async ({ lane, impl }) => {
      if (!impl || impl.status !== 'pushed') return blockedRecord(lane, impl, impl ? impl.notes || 'draft did not reach pushed state' : 'research or draft returned null')
      let cur = impl
      // ── fact_check gate (one bounded re-draft) ──
      let fc = await agent(contentFactCheckPrompt(lane, cur), { label: `fact-check:${lane.id}`, phase: 'Fact-check', agentType: 'general-purpose', model: 'fable', schema: VERDICT_SCHEMA, ...effortFor('gate') })
      if (fc && fc.verdict === 'REQUEST_CHANGES') {
        const rd = await agent(contentRedraftPrompt(lane, cur, fc, 'fact-check'), { label: `redraft-fc:${lane.id}`, phase: 'Draft', agentType: 'orchemist-implementer', model: 'opus', isolation: 'worktree', schema: CONTENT_IMPL_SCHEMA, ...effortFor('implement') })
        if (rd && rd.status === 'pushed') {
          cur = rd
          fc = await agent(contentFactCheckPrompt(lane, cur), { label: `fact-check2:${lane.id}`, phase: 'Fact-check', agentType: 'general-purpose', model: 'fable', schema: VERDICT_SCHEMA, ...effortFor('gate') })
        }
      }
      if (!fc || fc.verdict !== 'APPROVE') return contentBlocked(lane, cur, 'fact_check', fc)
      // ── red_team gate (one bounded re-draft) ──
      let rt = await agent(contentRedTeamPrompt(lane, cur), { label: `red-team:${lane.id}`, phase: 'Red-team', agentType: 'orchemist-adversary', model: 'fable', schema: VERDICT_SCHEMA, ...effortFor('gate') })
      if (rt && rt.verdict === 'REQUEST_CHANGES') {
        const rd = await agent(contentRedraftPrompt(lane, cur, rt, 'red-team'), { label: `redraft-rt:${lane.id}`, phase: 'Draft', agentType: 'orchemist-implementer', model: 'opus', isolation: 'worktree', schema: CONTENT_IMPL_SCHEMA, ...effortFor('implement') })
        if (rd && rd.status === 'pushed') {
          cur = rd
          rt = await agent(contentRedTeamPrompt(lane, cur), { label: `red-team2:${lane.id}`, phase: 'Red-team', agentType: 'orchemist-adversary', model: 'fable', schema: VERDICT_SCHEMA, ...effortFor('gate') })
        }
      }
      if (!rt || rt.verdict !== 'APPROVE') return contentBlocked(lane, cur, 'red_team', rt)
      // both gates APPROVE → merge-ready
      return reviewedRecord(lane, cur, { verdict: 'APPROVE', blockers: [], majors: [], notes: `fact_check + red_team both APPROVE.${fc.notes ? ' fc: ' + fc.notes : ''}${rt.notes ? ' rt: ' + rt.notes : ''}` })
    },
  )
} else {
  // Refactor mode (the original EPIC #942 flow): implement → review, no barrier.
  results = await pipeline(
    lanes,
    (lane) => agent(refactorImplementPrompt(lane), { label: `impl:${lane.id}`, phase: 'Implement', agentType: 'orchemist-implementer', model: 'opus', isolation: 'worktree', schema: IMPL_SCHEMA, ...effortFor('implement') }).then((impl) => ({ lane, impl })),
    ({ lane, impl }) => {
      if (!impl || impl.status !== 'pushed') return blockedRecord(lane, impl, impl ? impl.notes || 'implement did not reach pushed state' : 'implementer returned null')
      return agent(refactorReviewPrompt(lane, impl), { label: `review:${lane.id}`, phase: 'Review', agentType: 'general-purpose', model: 'fable', schema: VERDICT_SCHEMA, ...effortFor('gate') }).then((v) => reviewedRecord(lane, impl, v))
    },
  )
}

const lanesOut = results.filter(Boolean)
const approved = lanesOut.filter((r) => r.verdict === 'APPROVE')
const blocked = lanesOut.filter((r) => r.verdict !== 'APPROVE')
const ready = blocked.length === 0 && approved.length === lanes.length

log(`orchemist-wave [${mode}] done: ${approved.length}/${lanes.length} APPROVE${blocked.length ? `, ${blocked.length} blocked (${blocked.map((b) => b.lane).join(', ')})` : ''}.`)

return {
  ready,
  mode,
  approved_branches: approved.map((r) => ({ lane: r.lane, issue: r.issue, branch: r.branch, sha: r.pushed_sha })),
  lanes: lanesOut,
  next_step: ready
    ? `All ${approved.length} lane(s) APPROVED & pushed. OPERATOR MERGE-WAVE (kept out of this workflow): (1) for each approved branch open a PR with "Closes #<issue>" — UMBRELLA GUARD: if 2+ lanes share the same issue number (one umbrella split into sub-lanes), do NOT put "Closes #<umbrella>" on the non-final lanes; use a parenthesis-safe "fix(#<umbrella>):" subject and keep each non-final PR/squash body EMPTY of any (clos|fix|resolv)\\w*\\s*:?\\s*#<umbrella>, so only the FINAL merged lane carries "Closes #<umbrella>"; after the wave, if the umbrella is still OPEN with all its sub-lanes merged, close it; (2) ONE combined CI poll across all PR head SHAs; (3) squash-merge all PRs (file-disjoint → no conflicts; if branch protection blocks auto-merge, toggle the ruleset with a FULL-BODY PUT — a partial \`-f enforcement=disabled\` returns HTTP 422 — then restore via a trap); (4) pull ${base} and run ONE composition \`${suiteCmd}\` on the merged tree — each PR's CI validated its OWN base, not the union, so this is the only check that covers the merged result.`
    : `NOT READY — ${blocked.map((b) => `${b.lane}:${b.verdict}`).join(', ')}. Address the blockers and re-run the affected lane(s). Do NOT merge a partial wave that leaves the tree red.`,
}
