export const meta = {
  name: 'orchemist-wave',
  description:
    'Parallel "wave" orchestrator for Orchemist: fan N independent, file-disjoint lanes through a per-lane pipeline — mode:"refactor" runs implement → independent opus review; mode:"maintenance" runs the maintenance pipeline per lane (spec → opus spec-adversary → implement+focused-test → independent opus review). Per-lane lockstep, each lane sealed in its own git worktree. Produces reviewed, pushed branches + per-lane merge-readiness verdicts. Does NOT merge — the merge-coordination (branch-protection toggle + squash-merge + composition full-suite) stays a deliberate, outward-facing operator step.',
  whenToUse:
    'When several file-DISJOINT lanes are ready at once. mode:"refactor" (default) — behavior-preserving changes (a god-module decomposition, a mechanical codemod); each lane needs an immutable contract (a surface/contract test + the full suite). mode:"maintenance" — a batch of independent bug/infra/CI/data fixes; each lane runs the maintenance pipeline (spec → opus adversary → implement + a FOCUSED test → opus review), the right-sized flow that adds behavior + tests (NOT behavior-preserving). Rule of thumb: serialize lanes WITHIN one module (same files), parallelize ACROSS modules (disjoint dirs compose cleanly).',
  phases: [
    { title: 'Spec', detail: 'maintenance mode only — spec + opus spec-adversary per lane (the pre-implement quality gate)', model: 'opus' },
    { title: 'Implement', detail: 'one orchemist-implementer (opus) per lane, sealed in its own git worktree', model: 'opus' },
    { title: 'Review', detail: 'one independent opus reviewer per lane — verify, do not trust', model: 'opus' },
  ],
}

// ─────────────────────────────────────────────────────────────────────────────
// orchemist-wave — the parallel fan-out we run by hand, encoded deterministically.
//
// TWO modes, same skeleton (pipeline() = per-lane lockstep, no barrier between
// lanes; each lane sealed in its own git worktree so concurrent lanes never
// collide on the git index; the implementer pushes its branch, the reviewer
// fetches + diffs it):
//   • mode:"refactor"   — the proven EPIC #942 pattern: implement(opus) → opus
//     review. Bar = ZERO functional change; the reviewer's durable gate is the
//     public-surface diff (a dropped re-export passes both the contract test AND
//     the full suite; only an explicit surface-diff catches it).
//   • mode:"maintenance" — each lane runs the coding-pipeline-maintenance flow:
//     spec → spec_adversary(opus) → implement(+focused test) → review(opus). The
//     spec_adversary is the key quality gate for prod-affecting maintenance work;
//     it does ONE bounded revise round. Lanes ADD behavior + tests (not
//     behavior-preserving), so there is no surface-diff/facade invariant.
//
// WHY the merge is NOT here: toggling branch protection + squash-merging to a
// shared default branch + the post-merge composition suite are outward-facing and
// easy to get subtly wrong. Those stay a deliberate operator step; this workflow
// hands you reviewed, pushed branches + a go/no-go verdict.
//
// ── args contract ────────────────────────────────────────────────────────────
//   args = {
//     mode:          "maintenance",                // "refactor" (default) | "maintenance"
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
//         implement:   "the lane-specific change",
//         reviewFocus: "what the spec-adversary + reviewer must scrutinize",
//       },
//       ...
//     ],
//   }
// ─────────────────────────────────────────────────────────────────────────────

const A = args || {}
const lanes = Array.isArray(A.lanes) ? A.lanes : []

if (lanes.length === 0) {
  log('orchemist-wave: args.lanes is empty — nothing to do. Pass lanes via the Workflow `args`.')
  return { ready: false, lanes: [], note: 'no lanes provided' }
}

const mode = A.mode === 'maintenance' ? 'maintenance' : 'refactor'
const repo = A.repo || '(repo unset)'
const base = A.base || 'main'
const suiteCmd = A.suiteCmd || (mode === 'maintenance' ? 'the repo typecheck/build/lint gate' : 'python3 -m pytest -q')
const expectedSuite = A.expectedSuite || '(unspecified — match the pre-wave green baseline)'
const facadeTest = A.facadeTest || ''
const invariant =
  A.invariant ||
  (mode === 'maintenance'
    ? 'Maintenance/infra/data fix — you DO add behavior + a FOCUSED test (this is NOT a behavior-preserving refactor). Keep the change MINIMAL + additive; edit ONLY the planned files. Preserve every UNRELATED seal pin; an explicitly-anticipated seal-break is an AUDITED re-baseline — change only the named pins, byte-correct, never an accommodation. Validate with a focused unit/e2e test when locally testable, else PROD-VALIDATION. Do NOT hand-edit unrelated tests. middleware HARD-NO.'
    : 'Behavior 100% unchanged; the public surface and every caller import path stay byte-identical; do NOT modify any tests.')

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

// ── maintenance-mode prompts (the coding-pipeline-maintenance flow per lane) ──
function specPrompt(lane) {
  return `You are the SPEC agent for maintenance-wave lane "${lane.id}" (issue #${lane.issue}) on ${repo}. Produce a FOCUSED implementation plan for this bug/infra/data fix (WHAT + HOW). READ-ONLY — no code edits.

## The change
${lane.implement}

## Files this lane may touch
${lane.files || '(infer from the change; keep it minimal + file-disjoint from sibling lanes)'}

Recon the area-of-change in the repo, then plan: the EXACT files to edit, the approach, the SEAL SURFACE to AVOID (verify-scripts/SHA-pins near the change — or, if a seal-break is genuinely required, name the exact pin to re-baseline and why it's anticipated), and the VALIDATION plan: a FOCUSED unit/e2e test if locally testable, else the concrete PROD-VALIDATION steps. Do NOT propose a heavyweight sealed verify-script.

Return the StructuredOutput: { plan: <the full plan>, files: [...], validation: <focused-test (which) | prod-validation steps> }.`
}

function specRevisePrompt(lane, prevPlan, verdict) {
  return `You are the SPEC agent REVISING the plan for maintenance-wave lane "${lane.id}" (issue #${lane.issue}). An independent opus adversary found problems. Apply the VERBATIM fixes; keep everything else stable. READ-ONLY.

## The change
${lane.implement}

## Previous plan
${prevPlan}

## Adversary findings (address every blocker)
${(verdict.blockers || []).map((b, i) => `${i + 1}. ${b}`).join('\n') || verdict.notes || '(see notes)'}

Return the StructuredOutput: { plan, files, validation } — the corrected plan.`
}

function specAdversaryPrompt(lane, spec) {
  return `You are the SPEC ADVERSARY (opus) for maintenance-wave lane "${lane.id}" (issue #${lane.issue}) on ${repo}. Independently pressure-test the fix APPROACH for correctness, safety, timing, seal-impact, and missed edge cases — the key quality gate for prod-affecting maintenance work. READ-ONLY; verify against the REAL code.

## The change
${lane.implement}

## Proposed plan (vet it)
${spec.plan}

## Decisive checks
- Does the approach actually fix the issue, end-to-end? Any path it misses?
- SEAL IMPACT: does it touch a byte-locked / SHA-pinned / HARD-NO surface unexpectedly? Is any seal-break genuinely anticipated + named (vs a surprise)?
- Is the VALIDATION right — a focused test where locally testable, or honest prod-validation where deploy/cloud-side?
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
  return `You are an INDEPENDENT opus reviewer for maintenance-wave lane "${lane.id}" (issue #${lane.issue}) on ${repo}. Verdict: APPROVE or REQUEST_CHANGES. Be adversarial — VERIFY, do not trust the implementer.

## Read-only mandate
Inspect branch \`${lane.branch}\` @ \`${impl.pushed_sha || '(see origin)'}\`, forked from \`${base}\`. Use \`git fetch origin\`, \`git diff ${base}...origin/${lane.branch}\`, \`git show\`, read files, read-only checks. Do NOT write/edit/commit/stash/restore/push.

## Implementer claimed (verify, don't trust)
suite = ${impl.suite || '(none)'} · files = ${(impl.files || []).join(', ') || '(unspecified)'} · notes = ${impl.notes || '(none)'}

## Verify — the durable gates
1. **The fix is correct + complete** per the issue. ${lane.reviewFocus || ''}
2. **Scope:** \`git diff --stat ${base}...origin/${lane.branch}\` touches ONLY this lane's intended files — no sibling-lane file, no middleware, no unrelated change.
3. **Seals:** unrelated pins intact; any seal-break is the ANTICIPATED/audited one (anti-mask — only the named pins changed, byte-correct, the old pin was the thing being corrected, not an accommodation).
4. **The focused test genuinely proves the fix** (not tautological); re-run the touched-area checks read-only. Distinguish a PRE-EXISTING red (also red on ${base}) from a NEW regression.

Return the StructuredOutput: verdict, blockers (file:line + why), majors, notes. REQUEST_CHANGES on any real fix-gap, scope breach, or seal regression.`
}

log(`orchemist-wave [${mode}]: ${lanes.length} lane(s) off ${repo}@${base} — ${mode === 'maintenance' ? 'spec → opus adversary → implement → opus review' : 'implement (opus, worktree) → opus review'}, per-lane lockstep. Merge stays an operator step.`)

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

let results
if (mode === 'maintenance') {
  // Per lane: spec + opus spec-adversary (one bounded revise) → implement → opus review.
  results = await pipeline(
    lanes,
    async (lane) => {
      let spec = await agent(specPrompt(lane), { label: `spec:${lane.id}`, phase: 'Spec', agentType: 'general-purpose', schema: SPEC_SCHEMA })
      if (!spec) return { lane, spec: null }
      for (let round = 0; round < 2; round++) {
        const v = await agent(specAdversaryPrompt(lane, spec), { label: `spec-adv:${lane.id}`, phase: 'Spec', agentType: 'orchemist-adversary', model: 'opus', schema: VERDICT_SCHEMA })
        if (!v || v.verdict === 'APPROVE') break
        if (round === 1) { log(`lane ${lane.id}: spec-adversary still REQUEST_CHANGES after 1 revise — implement proceeds with the adversary notes folded in.`); break }
        const revised = await agent(specRevisePrompt(lane, spec.plan, v), { label: `spec-rev:${lane.id}`, phase: 'Spec', agentType: 'general-purpose', schema: SPEC_SCHEMA })
        if (revised) spec = revised
      }
      return { lane, spec }
    },
    async ({ lane, spec }) => {
      if (!spec) return { lane, impl: null }
      const impl = await agent(maintImplementPrompt(lane, spec), { label: `impl:${lane.id}`, phase: 'Implement', agentType: 'orchemist-implementer', model: 'opus', isolation: 'worktree', schema: IMPL_SCHEMA })
      return { lane, impl }
    },
    async ({ lane, impl }) => {
      if (!impl || impl.status !== 'pushed') return blockedRecord(lane, impl, impl ? impl.notes || 'implement did not reach pushed state' : 'spec or implement returned null')
      const v = await agent(maintReviewPrompt(lane, impl), { label: `review:${lane.id}`, phase: 'Review', agentType: 'general-purpose', model: 'opus', schema: VERDICT_SCHEMA })
      return reviewedRecord(lane, impl, v)
    },
  )
} else {
  // Refactor mode (the original EPIC #942 flow): implement → review, no barrier.
  results = await pipeline(
    lanes,
    (lane) => agent(refactorImplementPrompt(lane), { label: `impl:${lane.id}`, phase: 'Implement', agentType: 'orchemist-implementer', model: 'opus', isolation: 'worktree', schema: IMPL_SCHEMA }).then((impl) => ({ lane, impl })),
    ({ lane, impl }) => {
      if (!impl || impl.status !== 'pushed') return blockedRecord(lane, impl, impl ? impl.notes || 'implement did not reach pushed state' : 'implementer returned null')
      return agent(refactorReviewPrompt(lane, impl), { label: `review:${lane.id}`, phase: 'Review', agentType: 'general-purpose', model: 'opus', schema: VERDICT_SCHEMA }).then((v) => reviewedRecord(lane, impl, v))
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
