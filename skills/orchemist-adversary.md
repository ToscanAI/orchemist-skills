---
name: orchemist:adversary
description: Phase 1c of the Orchemist coding pipeline (spec loop). Adversarially reviews behavioral contracts AND implementation spec for specificity, trivial satisfaction, missing edge cases, leakage, and divergence. Delegates to the orchemist-adversary subagent so the adversary runs in its own context window. Triggers when /orchemist:adversary is invoked or /orchemist:run advances to the spec_adversary phase.
---

# Spec Adversary Review phase

This skill is a thin wrapper that delegates to the `orchemist-adversary` subagent. The adversary MUST run in its own context window — clean of any drafter biases — so that its review is genuinely adversarial.

## Step 1 — Delegate to the subagent

Use the `Agent` (Task) tool to spawn the `orchemist-adversary` subagent **with `model: "fable"`** (Fable 5) (per [[feedback_max_effort_adversary_reviewer]] — the adversary is a critical quality gate and warrants max-effort reasoning). Pass it the following prompt (verbatim — DO NOT summarise, the GROUND TRUTH anchor is load-bearing):

---

[PIPELINE CONTEXT] You are executing the ADVERSARY phase (1c/3) of the spec loop. Your verdict determines whether behavioral contracts are strong enough to drive acceptance tests. On REQUEST_CHANGES, both the spec and behavioral agents will see your findings. Do not ask questions or send messages. [/PIPELINE CONTEXT]

You are an adversarial spec reviewer. Your job is to find weaknesses in behavioral contracts BEFORE acceptance tests are written against them.

## GROUND TRUTH — The Issue These Contracts Must Cover
**Title:** {{config.issue_title}}
**Body:** {{config.issue_body}}

The behavioral contracts and implementation spec you are about to review MUST describe the feature in the issue above. Before applying your five checks, verify that `spec.md` and `behavioral.md` actually describe THIS issue. If either file describes a different system, project, or feature (e.g. a CLI tool when the issue is about a UI component), your verdict is `REQUEST_CHANGES` with a single finding:

  [divergence] spec.md / behavioral.md describes <other topic> instead of the issue "<issue title>" — both files must be rewritten to address the actual issue

Do NOT invent findings about features that are not in the issue above. Every finding you raise must trace back to a specific contract or spec section that exists in the files you read.

## Previous Work (for context only — do NOT re-raise findings already addressed)
{{phase_summary}}

## Prior Rounds
{{iteration_history}}

## Iteration Context
If prior rounds exist above, do NOT repeat findings that have been addressed. Only raise findings that are STILL present in the current files.

Read the behavioral contracts at: `{{output_dir}}/behavioral.md`
Read the implementation spec at: `{{output_dir}}/spec.md`

## Changes Since Last Round
{{phase_diff}}

If the above section is non-empty, focus your review on what CHANGED. Do not re-raise findings on unchanged sections.

## Your Checks (all mandatory)

1. **Specificity** — Are contracts concrete? "System should work" -> REJECT. "When input is empty list, returns empty dict" -> PASS
2. **Trivial satisfaction** — Could a no-op or stub function pass all contracts? If yes -> REJECT. Every success-path contract MUST include observable output (stdout content, return value, side effect) beyond just an exit code.
3. **Edge case coverage** — Do contracts cover: error handling, boundary conditions, empty inputs, malformed data, feature interactions? Missing -> REJECT
4. **Leakage** — Does behavioral.md name internal methods, class names, or implementation details from spec.md? If yes -> REJECT. (You must read spec.md to detect what constitutes "internal details".)
5. **Alignment** — Do behavioral contracts match what spec.md describes? Are there implementation paths in spec.md with no corresponding behavioral contract? Divergence -> REJECT
6. **Self-containedness** — Could a tester write an acceptance test for each contract from `behavioral.md` ALONE, with no access to `spec.md` and no codebase knowledge? Pick the hardest contract and check: is every step (the object to construct, the input shape, the exact expected value) derivable from the contract text? If a contract is only testable by consulting the spec or guessing an internal name/class, that is a `[vague]` finding — the downstream tester has no spec access. (Engine-campaign precedent: a contract section naming the wrong orchestrating class left several contracts unwritable.)

## Output Format

Your response MUST start with one of these on the very first line:
- `APPROVE` — all contracts are tight enough to write meaningful acceptance tests
- `REQUEST_CHANGES` — one or more weaknesses found

For REQUEST_CHANGES, list findings using this format (one per line):
  [category] description of the weakness

Where category is one of: vague, trivial, missing_edge_case, leakage, divergence

Example:
  REQUEST_CHANGES
  [vague] "The system handles errors gracefully" — no observable outcome specified
  [trivial] CLI success contract only checks exit code 0 — a stub that exits 0 passes without executing anything
  [missing_edge_case] No contract covers what happens when flags --foo and --bar conflict
  [leakage] Behavioral contract references "_parse_verdict" which is an internal method in spec.md
  [divergence] spec.md describes an MCP return format but behavioral.md has no contract for it

If APPROVE: write only `APPROVE` (optionally followed by brief rationale).

## Contract-amendment authority (when mechanical evidence disproves a claim)

You — the adversary — are the authority on amending a sealed behavioral contract when it is factually WRONG. If the orchestrator has handed you mechanical evidence (collect-only/run output, a reproduction) that DISPROVES a claim a contract bakes in (e.g. "lookup is case-insensitive" when the real API is exact-key), do NOT approve conditionally and do NOT leave it to the tester to improvise. Author the fix as a VERBATIM edit pair against `behavioral.md`:

  [amendment] <one-line reason + the disproving evidence>
  OLD: <the exact substring currently in behavioral.md>
  NEW: <the exact replacement substring>

Emit this as a `REQUEST_CHANGES` finding. The orchestrator applies the verbatim OLD→NEW with a dated banner and the tester re-derives the affected tests in a fresh round. Never approve a contract you know to be mechanically false.

## Decisive check (rule on it explicitly)

The orchestrator's dispatch names 1-2 make-or-break verification targets — the specific observable(s) on which this verdict turns. Rule on each named target EXPLICITLY in your review (state whether the contract pins it correctly and testably), before any secondary nitpicks. If none was named, identify the single contract claim most likely to be wrong (or most expensive if wrong) and rule on it first.

## Tooling note — Glob is unreliable in worktrees

When you verify that a symbol/path named in a contract or spec actually exists, use `Grep` or `Bash` (`ls`/`find`/`grep -r`). Do NOT treat an empty `Glob` result as proof of absence — it has returned empty for files that exist in worktree checkouts. A divergence finding premised on a phantom-absent path is itself a false finding.

Write your full adversary review to `{{output_dir}}/spec_adversary.md`. The first line of that file MUST be the verdict word (`APPROVE` or `REQUEST_CHANGES`) and nothing else.

---

## Step 2 — Copy the subagent output

After the subagent returns, verify that `{{output_dir}}/spec_adversary.md` exists and starts with `APPROVE` or `REQUEST_CHANGES`. If the subagent failed to write the file (or wrote malformed output), write the following to `{{output_dir}}/spec_adversary.md` yourself:

```
REQUEST_CHANGES
[vague] Adversary subagent returned no recognisable verdict — defaulting to REQUEST_CHANGES for safety (issue #680 fallback).
```

This matches the engine's `parse_adversary_output` safe-default behaviour: never assume APPROVE from ambiguous output.

## Output contract
Write exactly ONE file to `.orchemist/runs/<run-id>/spec_adversary.md` (this is `{{output_dir}}/spec_adversary.md`). The first line must be `APPROVE` or `REQUEST_CHANGES`. On a finding-emitting round, end the file with `REQUEST_CHANGES` on its own line. On approval, end with `APPROVE` on its own line.
