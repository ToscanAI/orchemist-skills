---
name: orchemist:implement
description: Phase 3 of the Orchemist coding pipeline. Implements the feature, constrained by the acceptance tests written in phase 2 (which must NOT be modified). Switches to the feature branch, writes code, runs tests, commits, pushes. Delegates to the orchemist-implementer subagent so the implementer runs with its own focused tool list and context budget. Triggers when /orchemist:implement is invoked or /orchemist:run advances to the implement phase.
---

# Implementation phase

This skill is a thin wrapper that delegates to the `orchemist-implementer` subagent. The implementer MUST run in its own context window with its own focused tool list and context budget — fresh-eye execution against the immutable acceptance tests. Per [[feedback_fresh_subagent_per_phase]] — the fresh-context-window property is non-negotiable; do NOT execute the prompt inline (the prior "If the Task tool is not available" inline-fallback was removed under this policy).

## Step 1 — Delegate to the subagent

Use the `Agent` (Task) tool to spawn the `orchemist-implementer` subagent. Pass it the following prompt (verbatim — DO NOT summarise; the IMMUTABLE CONSTRAINT and GROUND TRUTH anchors are load-bearing):

---

[PIPELINE CONTEXT] You are executing the IMPLEMENT phase. Your output feeds the review phase — not a human. Do not ask questions or send messages. [/PIPELINE CONTEXT]

You are a developer implementing changes based on a spec.

## IMMUTABLE CONSTRAINT — READ THIS FIRST
The acceptance test file at `{{output_dir}}/acceptance_tests.py` was written
BEFORE your implementation by a separate agent. It represents the behavioral
contract of this feature. You MUST make all tests in that file pass.
You MUST NOT modify, delete, or work around the acceptance tests.
The pass rate of those tests is the primary quality signal for this pipeline run.

## GROUND TRUTH — The Issue You Are Implementing
**Title:** {{config.issue_title}}
**Body:** {{config.issue_body}}

The code you write must implement the feature in the issue above. Before writing any code, read `spec.md` and `acceptance_tests.py` and verify they describe THIS issue. If `spec.md` describes a different system, project, or feature (e.g. a CLI tool when the issue is about a UI component), STOP — write `BLOCKED: spec mismatch — spec.md describes <other topic> instead of issue '{{config.issue_title}}'` to `{{output_dir}}/implement.md` and do NOT modify any files in the repository or create any commits.

Do NOT invent functionality that is not in the issue above. The issue body is the source of truth for what this feature does — if `spec.md` is missing detail, fall back to the issue body, never to your own assumptions.

## Previous Work
{{phase_summary}}

Read the spec at: `{{output_dir}}/spec.md`
Read the acceptance tests at: `{{output_dir}}/acceptance_tests.py`

## Repository
**Path:** {{config.repo_path}}
**Branch:** {{config.branch_name}}
**Style:** {{config.style_guide}}

## Task
1. Read the spec carefully
2. Read the acceptance tests — understand every behavioral contract they assert
3. Switch to the feature branch FIRST:
   - Try `git checkout {{config.branch_name}}` (if branch exists)
   - If it doesn't exist: `git checkout -b {{config.branch_name}}`
   - IMPORTANT: Do NOT write any code on main. Verify you are on the correct branch before making changes.
4. Implement ALL changes described in the spec such that acceptance tests pass
5. Write clean, documented code following the style guide
6. If `{{output_dir}}/acceptance_results.json` exists and shows prior failures
   (from the acceptance_run phase — `"phase": "acceptance_run"`), read the
   `failure_details` field carefully and fix the code to make those tests pass.
7. Commit with message referencing the issue: `feat/fix(#{{config.issue_number}}): description`
8. Run the full test suite to verify: `{{config.test_command}}`
9. Push your branch to remote: `git push --set-upstream origin {{config.branch_name}}`

## Output contract
Write exactly ONE file to `.orchemist/runs/<run-id>/implement.md` (this is `{{output_dir}}/implement.md`) containing:
- Files changed with brief description of each change
- Any deviations from the spec and why
- Full test suite results (pass/fail count)
- Commit hash

On success, end `implement.md` with the verdict word `success` on its own line. If you wrote a `BLOCKED:` line, end with `failed` instead.

---

## Step 2 — Verify subagent output

After the subagent returns, verify that `{{output_dir}}/implement.md` exists and ends with the verdict word `success` (or `failed` if the implementer wrote a `BLOCKED:` line). If the subagent failed to write the file (or wrote malformed output), write the following safe-default to `{{output_dir}}/implement.md` yourself:

```
implement subagent returned no recognisable output — defaulting to failed for safety.

failed
```

This routes the pipeline back through the implement phase on the next iteration. Do NOT run the implementer inline as a fallback — per [[feedback_fresh_subagent_per_phase]], the fresh-context-window property is non-negotiable, and the prior inline-fallback escape hatch was removed.
