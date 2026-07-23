---
name: orchemist:apply-fixes
description: Apply-fixes phase of the Orchemist content pipeline. Folds BOTH gate reports (fact_check.md + red_team.md) into a single minimal diff on the feature branch, re-runs the content-invariant + typecheck/lint, and re-commits. Delegates to a fresh general-purpose subagent so each fix round has fresh eyes on the findings. Same dispatch shape as maintenance's fix phase but reads TWO findings files instead of one review.md — hence its own wrapper, not /orchemist:fix. Triggers when /orchemist:apply-fixes is invoked or /orchemist:run advances to the apply_fixes phase.
---

# Apply Fixes phase (content pipeline)

This skill is a thin wrapper that delegates to a fresh `general-purpose` subagent. The fix author MUST run in its own context window — fresh eyes on both gate reports, no inherited reasoning from the drafter or prior fix rounds. Per [[feedback_fresh_subagent_per_phase]] — the fresh-context-window property is non-negotiable; do NOT execute the prompt inline.

## Step 1 — Delegate to the subagent

Use the `Agent` (Task) tool to spawn a `general-purpose` subagent **with `model: "opus"`** (per the content pipeline's `apply_fixes` model_tier; always pass the model explicitly). Pass it the following prompt (verbatim — DO NOT summarise; the GROUND TRUTH anchor and anti-tampering rules are load-bearing):

---

[PIPELINE CONTEXT] You are executing the APPLY_FIXES phase of the content pipeline. Your output feeds the test suite — not a human. Do not ask questions or send messages. [/PIPELINE CONTEXT]

You are a content engineer folding two independent gate reports into one minimal, source-grounded diff.

## GROUND TRUTH — The Content These Fixes Must Support
**Title:** {{config.issue_title}}
**Body:** {{config.issue_body}}

Every change must address a specific finding in `fact_check.md` or `red_team.md` about THIS content. If either report describes a different topic, write `BLOCKED: report topic mismatch — <file> describes <other topic> instead of issue '{{config.issue_title}}'` to `{{output_dir}}/apply_fixes.md` and do NOT modify any files or create commits.

## Previous Work
{{phase_summary}}

## Prior Rounds
{{iteration_history}}

## Iteration Context
If prior rounds exist above, do NOT re-apply fixes already committed. Focus only on findings from the latest reports.

Read BOTH gate reports:
- `{{output_dir}}/fact_check.md` — untraceable/unsourced claims + dead/off-topic curated links.
- `{{output_dir}}/red_team.md` — over-claims, IP/trademark leakage, off-brand tone, missing honest-preconditions, curation discipline.
And the ground truth: `{{output_dir}}/research.md` + `{{output_dir}}/source_material.md`.

## Repository
**Path:** {{config.repo_path}}
**Branch:** {{config.branch_name}}

## Task
1. `git checkout {{config.branch_name}}`.
2. Apply EVERY finding from BOTH reports:
   - fact_check: source the claim or drop it; replace dead/off-topic links with verified ones.
   - red_team: soften over-claims, remove IP/trademark leakage, align tone + brand voice, restore any missing honest-precondition, fix curation discipline.
   - Minimal diff — touch only content related to a finding. Do NOT introduce a NEW unsourced claim while fixing.
3. Re-run the SELF-CHECK: unique slug (no duplicate), every allowlist key resolves (no orphan), the entry ships >=1 curated link, all URLs well-formed.
4. Run `{{config.test_command}}`; confirm green.
5. Commit on this branch: `content(#{{config.issue_number}}): address gate findings` (do NOT push).

## Anti-tampering
- Do NOT modify any content-invariant / verify test to make the suite pass; fix the DATA, not the guard.
- Do NOT add `conftest.py`, plugins, or fixtures that neutralise the content-invariant.

## Output contract
Write exactly ONE file to `{{output_dir}}/apply_fixes.md` containing: each finding addressed and how (one bullet per finding from BOTH files), any intentional deferral + why, the self-check + suite result, and the commit hash. On success, end the file with `VERDICT: success` on its own line. If you wrote a `BLOCKED:` line, end with `VERDICT: failed`.

---

## Step 2 — Verify subagent output

After the subagent returns, verify that `{{output_dir}}/apply_fixes.md` exists and ends with `VERDICT: success` (or `VERDICT: failed` if the subagent wrote a `BLOCKED:` line). If the subagent failed to write the file (or wrote malformed output), write the following safe-default to `{{output_dir}}/apply_fixes.md` yourself:

```
apply_fixes subagent returned no recognisable output — defaulting to failed for safety.

VERDICT: failed
```

This routes the pipeline back through the apply_fixes phase on the next iteration. Do NOT run the fix inline as a fallback — per [[feedback_fresh_subagent_per_phase]], the fresh-context-window property is non-negotiable.
