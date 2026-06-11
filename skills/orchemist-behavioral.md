---
name: orchemist:behavioral
description: Phase 1b of the Orchemist coding pipeline (spec loop). Translates the implementation spec into precise, testable behavioral contracts (Section A) describing WHAT the system does — never HOW. Delegates to a fresh general-purpose subagent so the contract author's context does not leak into the downstream adversary review. Triggers when /orchemist:behavioral is invoked or when /orchemist:run advances to the behavioral phase.
---

# Behavioral Contracts phase

This skill is a thin wrapper that delegates to a fresh `general-purpose` subagent. The contract author MUST run in its own context window so that the adversary reviews contracts that weren't drafted in the orchestrator's main context. Per [[feedback_fresh_subagent_per_phase]] — the fresh-context-window property is non-negotiable; do NOT execute the prompt inline.

## Step 1 — Delegate to the subagent

Use the `Agent` (Task) tool to spawn a `general-purpose` subagent. Pass it the following prompt (verbatim — DO NOT summarise; the GROUND TRUTH anchor and revision rules are load-bearing):

---

[PIPELINE CONTEXT] You are executing the BEHAVIORAL phase (1b/3) of the spec loop. Your output feeds the adversary. Write behavioral contracts only — describe WHAT the system does, not HOW. Do not ask questions or send messages. [/PIPELINE CONTEXT]

You are a behavioral contract specialist. Your job is to translate an implementation spec into precise, testable behavioral contracts.

## GROUND TRUTH — The Feature You Are Writing Contracts For
**Title:** {{config.issue_title}}
**Body:** {{config.issue_body}}

Your behavioral contracts MUST describe the feature above. Do NOT write contracts for any other system, project, or feature. If the implementation spec describes a different feature than the issue above, write contracts based on the ISSUE — not the spec.

## Implementation Spec
Read the implementation spec at: `{{output_dir}}/spec.md`
This describes HOW the feature will be built. Use it to understand the system,
but DO NOT copy implementation details into your behavioral contracts.

## Previous Work
{{phase_summary}}

## Prior Rounds
{{iteration_history}}

## Iteration Context
If prior rounds exist above, this is a REVISION round. The adversary flagged specific weaknesses in the behavioral contracts. Fix ONLY the flagged issues. Do NOT rewrite contracts the adversary did not flag.
If no prior rounds exist, this is round 1.

## Task
Write behavioral contracts describing WHAT the system should do. Use this format:
- "When [action/input], the system [expected behavior]"
- "Given [precondition], calling [operation] produces [outcome]"
- "If [edge case], the system [graceful behavior]"

### Rules
- DO NOT name internal functions, private methods, or class names
- DO NOT specify data structures, variable names, or implementation patterns
- DO reference exact observable values: exit codes, stdout content, stderr messages, return formats
- Wrong: "The system calls `PipelineRunner.dry_run()`"
- Right: "When `--mode dry-run` is specified, no API calls are made and phase names are printed to stdout"
- Wrong: "Add `_extract_code_quality()` method"
- Right: "When code quality results are available, the composite score includes them"

### Coverage checklist (mandatory)
For EACH feature path described in the implementation spec, ensure you have contracts covering:
1. **Happy path** — what happens when everything works (include observable output: stdout, return value, exit code)
2. **Error paths** — what happens on each failure mode (include exact error messages or required substrings)
3. **Edge cases** — boundary conditions, empty inputs, invalid values
4. **Interactions** — what happens when features combine (e.g., flags + modes)

A contract that only specifies an exit code without observable output is TRIVIALLY satisfiable. Always include what the user can SEE or RECEIVE.

### CRITICAL INSTRUCTIONS FOR REVISION ROUNDS
1. Read the EXISTING file at `{{output_dir}}/behavioral.md`
2. Read the adversary's findings from the most recent round above
3. Fix ONLY the flagged contracts — do not rewrite unflagged ones
4. Contracts the adversary previously approved MUST remain byte-identical
5. If the adversary flagged a "missing edge case", add a new contract for it
6. If the adversary flagged "leakage", remove the internal reference and describe the observable outcome instead
7. If the adversary flagged "vague", make the contract concrete with specific observable values (exit codes, exact strings, regex patterns)
8. If the adversary flagged "divergence", align the contract with what the implementation spec describes

Think of this as a code review fix: apply the minimum targeted edit. Do not refactor the whole file.
A full rewrite wastes tokens and loses adversary-approved content. Surgical edits only.

### Self-containedness stress test (mandatory before sealing)

Before you end the file, take the HARDEST contract and mentally write one acceptance test for it using §0 / the contract section ALONE — no spec, no codebase memory. If any step is underivable from the contracts as written (you would have to guess a class/sequencer name, an input shape, an expected value), the contracts are NOT self-contained: fix the contract (add the missing observable, name the exact value) so the test becomes writable from the contract text only. A downstream tester has no access to the spec; a contract that needs the spec to be testable is a defect. (Engine-campaign precedent: a contract section that named the wrong orchestrating class left several contracts unwritable until the section was corrected.)

## Output contract
Write exactly ONE file to `.orchemist/runs/<run-id>/behavioral.md` (this is `{{output_dir}}/behavioral.md`). The file must contain only the behavioral contracts — no orchestration metadata, no implementation pseudocode. Apply the self-containedness stress test above before ending. On success, end the file with the verdict word `success` on its own line.

---

## Step 2 — Verify subagent output

After the subagent returns, verify that `{{output_dir}}/behavioral.md` exists and ends with the verdict word `success`. If the subagent failed to write the file (or wrote malformed output), write the following safe-default to `{{output_dir}}/behavioral.md` yourself:

```
behavioral subagent returned no recognisable output — defaulting to failed for safety.

failed
```

This routes the pipeline back through the behavioral phase on the next iteration. Do NOT run the behavioral phase inline as a fallback — per [[feedback_fresh_subagent_per_phase]], the fresh-context-window property is non-negotiable.
