export const meta = {
  name: 'orchemist-wave',
  description:
    'Parallel "wave" orchestrator for Orchemist: fan N independent, file-disjoint lanes through implement (opus, sealed worktree) → independent opus review, in per-lane lockstep. Produces reviewed, pushed branches + per-lane merge-readiness verdicts. Does NOT merge — the merge-coordination (branch-protection toggle + squash-merge + composition full-suite) stays a deliberate, outward-facing operator step.',
  whenToUse:
    'When several behavior-preserving, machine-checkable, file-DISJOINT lanes are ready at once (a god-module decomposition wave, a mechanical codemod across modules, a batch of independent maintenance fixes). Each lane needs an immutable, reviewer-checkable contract (a surface/contract test + the full suite). Rule of thumb: serialize lanes WITHIN one module (they edit the same files), parallelize ACROSS modules (disjoint dirs compose cleanly).',
  phases: [
    { title: 'Implement', detail: 'one orchemist-implementer (opus) per lane, sealed in its own git worktree', model: 'opus' },
    { title: 'Review', detail: 'one independent opus reviewer per lane — verify, do not trust', model: 'opus' },
  ],
}

// ─────────────────────────────────────────────────────────────────────────────
// orchemist-wave — the parallel fan-out we run by hand, encoded deterministically.
//
// This mirrors the proven EPIC #942 pattern: 4-wide / 3-wide / 2-wide waves of
// behavior-preserving package extractions, each lane sealed in its own worktree,
// implemented by an opus orchemist-implementer, then independently re-verified by
// an opus reviewer (NOT trusting the implementer's claims — a dropped re-export
// can pass both the contract test AND the full suite; only an explicit
// surface-diff catches it).
//
// WHY pipeline() and not parallel(): each lane should review as soon as ITS
// implement finishes — lane B shouldn't wait for lane A's implementer. pipeline()
// gives per-lane lockstep with no barrier; wall-clock = slowest single lane.
//
// WHY the merge is NOT here: toggling branch protection + squash-merging to a
// shared default branch + the post-merge composition suite are outward-facing and
// easy to get subtly wrong (the ruleset toggle needs a FULL-BODY PUT — a partial
// `-f enforcement=disabled` returns HTTP 422; and each PR's CI validated its OWN
// base, not the merged union, so a composition full-suite after merging ALL lanes
// is mandatory). Those stay a deliberate operator step; this workflow hands you
// reviewed, pushed branches + a go/no-go verdict.
//
// ── args contract ────────────────────────────────────────────────────────────
//   args = {
//     repo:          "ToscanAI/orchemist",        // owner/name (for the reviewer's context)
//     base:          "main",                      // branch (or sha) every lane forks from
//     suiteCmd:      "PYTHONPATH=src python3 -m pytest -q",   // how to run the full suite
//     expectedSuite: "7928 passed / 0 failed / 8 skipped",   // the green baseline to match
//     facadeTest:    "tests/test_facade_surface_942.py",     // the contract/surface test (optional)
//     invariant:     "facade re-exports preserve the exact public surface; behavior 100% unchanged; do NOT modify tests/",
//     lanes: [
//       {
//         id:          "950e",                       // short lane label
//         issue:       1005,                          // GitHub issue number (for the PR the operator opens)
//         branch:      "fix/950e-cli-serve-eval",     // branch the implementer creates + pushes
//         implement:   "Extract serve/ui/api-server/mcp → cli/serve_cmds.py ...",  // the lane-specific change
//         reviewFocus: "cli --help tree byte-identical; _cli. late-binding for patched globals; dir() surface-diff",
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

const repo = A.repo || '(repo unset)'
const base = A.base || 'main'
const suiteCmd = A.suiteCmd || 'python3 -m pytest -q'
const expectedSuite = A.expectedSuite || '(unspecified — match the pre-wave green baseline)'
const facadeTest = A.facadeTest || ''
const invariant =
  A.invariant ||
  'Behavior 100% unchanged; the public surface and every caller import path stay byte-identical; do NOT modify any tests.'

const IMPL_SCHEMA = {
  type: 'object',
  additionalProperties: true,
  required: ['status', 'suite'],
  properties: {
    status: { type: 'string', enum: ['pushed', 'blocked'], description: "'pushed' ONLY if the full suite is green and the branch is on origin; else 'blocked'." },
    pushed_sha: { type: 'string', description: 'full sha of the pushed branch head (empty if blocked)' },
    suite: { type: 'string', description: 'the suite result line, e.g. "7928 passed / 0 failed / 8 skipped"' },
    facade_test: { type: 'string', description: 'PASS/FAIL of the contract/surface test' },
    files: { type: 'array', items: { type: 'string' }, description: 'files created/changed' },
    notes: { type: 'string', description: 'anything the reviewer should scrutinize: surface-diff catches, late-binding rewrites, deviations' },
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

function implementPrompt(lane) {
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

Return the StructuredOutput: status ('pushed' only if the full suite is green AND the branch is pushed; otherwise 'blocked'), pushed_sha, suite (the pass/fail/skip line), facade_test, files, and notes (surface-diff catches, any late-binding rewrites, anything a reviewer should scrutinize). If you cannot get the suite green, set status='blocked', do NOT push, and explain in notes.`
}

function reviewPrompt(lane, impl) {
  return `You are an INDEPENDENT senior reviewer for wave lane "${lane.id}" (issue #${lane.issue}) on ${repo}. Verdict: APPROVE or REQUEST_CHANGES. Be adversarial — VERIFY, do not trust the implementer. A dropped re-export can pass both the contract test AND the full suite; only an explicit surface-diff catches it.

## Read-only mandate
You are in your own worktree. Inspect the branch \`${lane.branch}\` @ \`${impl.pushed_sha || '(see origin)'}\`, forked from \`${base}\`. Use \`git fetch origin\`, \`git diff ${base}...origin/${lane.branch}\`, \`git show\`, read files, and READ-ONLY checks (same test prefix as the suite). Do NOT write/edit/commit/stash/restore/push or modify ANY file. If a fix is needed, describe it — do not apply it.

## Implementer claimed (verify, don't trust)
suite = ${impl.suite || '(none)'} · files = ${(impl.files || []).join(', ') || '(unspecified)'} · notes = ${impl.notes || '(none)'}

## Verify — the durable gates
1. **Public-surface diff:** reconstruct the parent surface from \`${base}\` (e.g. \`git show ${base}:<file>\`) and compare to the branch. Nothing dropped — especially internally-referenced-only constants/regexes/privates. ${lane.reviewFocus || ''}
2. **Verbatim fidelity:** AST/byte-compare the moved symbols against \`${base}\` — no logic drift beyond the intended, declared rewrites.
3. **Contract + suite:** confirm the contract test is green and the implementer's full-suite claim is consistent (re-run the targeted tests for the touched area — not necessarily the whole suite).
4. **No test tampering:** \`git diff --stat ${base}...origin/${lane.branch}\` shows ZERO files under \`tests/\`.

Return the StructuredOutput: verdict, blockers (numbered, with file:line and why), majors, surface_diff_clean (bool), notes. REQUEST_CHANGES on any blocker or any real surface regression.`
}

log(`orchemist-wave: ${lanes.length} lane(s) off ${repo}@${base} — implement (opus, sealed worktree) → independent opus review, per-lane lockstep. Merge stays an operator step.`)

// pipeline = per-lane implement → review with NO barrier between lanes.
// isolation:'worktree' gives each agent its own checkout so concurrent lanes
// never collide on the git index. The implementer pushes its branch (persists on
// origin regardless of worktree cleanup); the reviewer fetches + diffs it.
const results = await pipeline(
  lanes,
  (lane) =>
    agent(implementPrompt(lane), {
      label: `impl:${lane.id}`,
      phase: 'Implement',
      agentType: 'orchemist-implementer',
      model: 'opus',
      isolation: 'worktree',
      schema: IMPL_SCHEMA,
    }).then((impl) => ({ lane, impl })),
  ({ lane, impl }) => {
    if (!impl || impl.status !== 'pushed') {
      // Implement never reached a green pushed state — skip review, mark blocked.
      log(`lane ${lane.id}: implement BLOCKED — ${impl ? impl.notes || 'did not reach pushed state' : 'implementer returned null'}`)
      return {
        lane: lane.id, issue: lane.issue, branch: lane.branch,
        pushed: false, pushed_sha: impl ? impl.pushed_sha || '' : '',
        suite: impl ? impl.suite : '', verdict: 'BLOCKED_IMPLEMENT',
        blockers: [impl ? impl.notes || 'implement did not reach pushed state' : 'implementer returned null'],
      }
    }
    return agent(reviewPrompt(lane, impl), {
      label: `review:${lane.id}`,
      phase: 'Review',
      agentType: 'general-purpose',
      model: 'opus',
      schema: VERDICT_SCHEMA,
    }).then((v) => ({
      lane: lane.id, issue: lane.issue, branch: lane.branch,
      pushed: true, pushed_sha: impl.pushed_sha, suite: impl.suite,
      verdict: v.verdict, blockers: v.blockers || [], majors: v.majors || [],
      surface_diff_clean: v.surface_diff_clean, review_notes: v.notes,
    }))
  }
)

const lanesOut = results.filter(Boolean)
const approved = lanesOut.filter((r) => r.verdict === 'APPROVE')
const blocked = lanesOut.filter((r) => r.verdict !== 'APPROVE')
const ready = blocked.length === 0 && approved.length === lanes.length

log(`orchemist-wave done: ${approved.length}/${lanes.length} APPROVE${blocked.length ? `, ${blocked.length} blocked (${blocked.map((b) => b.lane).join(', ')})` : ''}.`)

return {
  ready,
  approved_branches: approved.map((r) => ({ lane: r.lane, issue: r.issue, branch: r.branch, sha: r.pushed_sha })),
  lanes: lanesOut,
  next_step: ready
    ? `All ${approved.length} lane(s) APPROVED & pushed. OPERATOR MERGE-WAVE (kept out of this workflow — outward-facing): (1) for each approved branch open a PR with "Closes #<issue>"; (2) ONE combined CI poll across all PR head SHAs; (3) disable the branch-protection ruleset with a FULL-BODY PUT (a partial \`-f enforcement=disabled\` returns HTTP 422 — GET the ruleset, flip enforcement, PUT {name,target,enforcement,conditions,bypass_actors,rules}), squash-merge all PRs, restore enforcement via a trap; (4) pull ${base} and run ONE composition \`${suiteCmd}\` on the merged tree — each PR's CI validated its OWN base, not the union, so this is the only check that covers the merged result.`
    : `NOT READY — ${blocked.map((b) => `${b.lane}:${b.verdict}`).join(', ')}. Address the blockers and re-run the affected lane(s). Do NOT merge a partial wave that leaves the tree red.`,
}
