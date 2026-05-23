---
name: orchemist:fix
description: Phase 4b of the Orchemist coding pipeline. Applies the code review feedback from review.md by addressing each blocker and major issue with the minimum-diff change. Re-runs tests, commits, pushes. Delegates to a fresh general-purpose subagent so each fix round has fresh eyes on the review findings — no inherited reasoning from the implementer or prior fix rounds. Triggers when /orchemist:fix is invoked or /orchemist:run advances to the fix phase after a REQUEST_CHANGES verdict.
---

# Apply Review Fixes phase

This skill is a thin wrapper that delegates to a fresh `general-purpose` subagent. The fix author MUST run in its own context window — fresh eyes on the review findings, no inherited reasoning from the implementer or prior fix rounds. Per [[feedback_fresh_subagent_per_phase]] — the fresh-context-window property is non-negotiable; do NOT execute the prompt inline.

## Step 1 — Delegate to the subagent

Use the `Agent` (Task) tool to spawn a `general-purpose` subagent. Pass it the following prompt (verbatim — DO NOT summarise; the GROUND TRUTH anchor and anti-tampering rules are load-bearing):

---

[PIPELINE CONTEXT] You are executing the FIX phase of an automated coding pipeline. Your output feeds a re-review — not a human. Do not ask questions, request clarification, or send messages to external channels. Deliver your complete output as structured text following the format below. [/PIPELINE CONTEXT]

You are a developer addressing code review feedback.

## GROUND TRUTH — The Issue This Fix Must Support
**Title:** {{config.issue_title}}
**Body:** {{config.issue_body}}

The fixes you apply must support the feature in the issue above. Before applying any fix from `review.md`, verify the review finding is about THIS issue's feature. If `review.md` requests changes for a different system, project, or feature than the issue above, write `BLOCKED: review topic mismatch — review.md describes <other topic> instead of issue '{{config.issue_title}}'` to `{{output_dir}}/fix.md` and do NOT modify any files in the repository or create any commits.

Do NOT apply speculative fixes for features not in the issue above. Every code change must address a specific finding in `review.md` that relates to this issue.

## Previous Work
{{phase_summary}}

## Prior Rounds
{{iteration_history}}

## Iteration Context
If prior rounds exist above, do NOT re-apply fixes already committed. Focus only on NEW issues from the latest review.

Read the code review at: `{{output_dir}}/review.md`
Read the original spec at: `{{output_dir}}/spec.md`

## Repository
**Path:** {{config.repo_path}}
**Branch:** {{config.branch_name}}

## Task
1. Checkout the feature branch: `git checkout {{config.branch_name}}`
2. Read the code review carefully
3. If the review says APPROVE with no blockers — write "No fixes needed" to `{{output_dir}}/fix.md` and stop
4. If REQUEST_CHANGES — apply ALL fixes mentioned:
   - Address every blocker and major issue
   - Address minor issues where practical
   - IMPORTANT: Only modify code directly related to the reviewer's feedback. Minimal diff.
5. Run tests: `{{config.test_command}}`
6. Commit fixes on this branch: `fix: address code review feedback`
7. Push your branch to remote: `git push origin {{config.branch_name}}`

## Anti-tampering
- Do NOT modify the acceptance test file at `{{output_dir}}/acceptance_tests.py`
- Do NOT modify anything in the user's `tests/` directory unless the reviewer specifically asked for a test change
- Do NOT add `conftest.py`, pytest plugins, or fixture overrides that neutralise test assertions

## Output contract
Write exactly ONE file to `.orchemist/runs/<run-id>/fix.md` (this is `{{output_dir}}/fix.md`) containing:
- Each issue addressed and how (one bullet per finding from `review.md`)
- Any issues intentionally deferred and why
- Updated test results (pass/fail count from `{{config.test_command}}`)
- Commit hash

On success, end the file with the verdict word `success` on its own line. If you wrote a `BLOCKED:` line at the top, end with `failed` instead.

---

## Step 2 — Verify subagent output

After the subagent returns, verify that `{{output_dir}}/fix.md` exists and ends with the verdict word `success` (or `failed` if the subagent wrote a `BLOCKED:` line). If the subagent failed to write the file (or wrote malformed output), write the following safe-default to `{{output_dir}}/fix.md` yourself:

```
fix subagent returned no recognisable output — defaulting to failed for safety.

failed
```

This routes the pipeline back through the fix phase on the next iteration (within the review→fix iteration cap). Do NOT run the fix inline as a fallback — per [[feedback_fresh_subagent_per_phase]], the fresh-context-window property is non-negotiable.
