---
name: orchemist:implement
description: Phase 3 of the Orchemist coding pipeline. Implements the feature, constrained by the acceptance tests written in phase 2 (which must NOT be modified). Switches to the feature branch, writes code, runs tests, commits, pushes. Triggers when /orchemist:implement is invoked or /orchemist:run advances to the implement phase.
---

# Implementation phase

This skill should be delegated to the `orchemist-implementer` subagent via the Task tool, so the implementer runs with its own focused tool list and context budget.

### If the Task tool is not available

Some Claude Code sessions are launched without the Task tool. If you cannot delegate, run the implement phase **inline** using the same prompt body below and the same output contract — the orchestrator's verdict contract is unchanged. You lose the fresh-context-window property of subagent delegation, but the phase still produces the correct artifact. Add a line `note: ran inline; Task tool unavailable` near the top of the resulting `implement.md` so the post-run summary records it.

When delegating, pass the following prompt verbatim:

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
