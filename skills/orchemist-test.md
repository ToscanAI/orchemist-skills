---
name: orchemist:test
description: Phase 5 of the Orchemist coding pipeline. Runs the full project test suite as a command — no LLM reasoning — to verify the changes did not introduce regressions outside the acceptance test set. Triggers when /orchemist:test is invoked or /orchemist:run advances to the test phase.
---

# Full Test Suite Verification phase

This is a command-only phase. The orchestrator (or this skill, when invoked directly) runs the user-configured test command and surfaces the result. No agent judgement is involved.

## GROUND TRUTH — Issue context
**Title:** {{config.issue_title}}
**Body:** {{config.issue_body}}

(Reproduced here for traceability even though no LLM judgement is required this phase.)

## Task

1. Confirm you are on the feature branch:
   ```
   cd {{config.repo_path}}
   git status   # ensure clean working tree
   git rev-parse --abbrev-ref HEAD   # should print {{config.branch_name}}
   ```
   If not on the feature branch, `git checkout {{config.branch_name}}` first.

2. Run the full project test suite:
   ```
   cd {{config.repo_path}}
   {{config.test_command}}
   ```

3. Capture stdout, stderr, and exit code.

4. Write `{{output_dir}}/test.md` containing:
   - The exact command run
   - Exit code
   - Full stdout/stderr (trim to the last ~6000 chars if longer)
   - A one-line summary: `passed=<n>, failed=<n>, errors=<n>` parsed from pytest output (or `exit_code=<n>` if the suite is not pytest)

## Verdict

- `success` if exit code is 0
- `failed` otherwise

If the test suite fails, the pipeline ends in a `failed` state — there is no automatic fix loop for general regressions (the fix loop only addresses review findings on the feature branch).

## Output contract
Write exactly ONE file to `.orchemist/runs/<run-id>/test.md` (this is `{{output_dir}}/test.md`). On success, end the file with the verdict word `success` on its own line. On any non-zero exit code, end with `failed`.
