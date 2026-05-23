---
name: orchemist:acceptance-test
description: Phase 2 of the Orchemist coding pipeline. Writes behavioral acceptance tests from contracts ONLY (no access to implementation). These tests become the immutable constraint for the implement phase. Delegates to the orchemist-tester subagent so the tester runs in its own context window with no access to drafter reasoning. Triggers when /orchemist:acceptance-test is invoked or /orchemist:run advances to the acceptance_test phase.
---

# Behavioral Acceptance Tests phase

This skill is a thin wrapper that delegates to the `orchemist-tester` subagent. The tester MUST run in its own context window with no access to implementation — by design, tests are derived from `behavioral.md` only. Per [[feedback_fresh_subagent_per_phase]] — the fresh-context-window property is non-negotiable; do NOT execute the prompt inline.

## Step 1 — Delegate to the subagent

Use the `Agent` (Task) tool to spawn the `orchemist-tester` subagent. Pass it the following prompt (verbatim — DO NOT summarise; the GROUND TRUTH anchor and no-implementation-access constraints are load-bearing):

---

[PIPELINE CONTEXT] You are executing the ACCEPTANCE_TEST phase. Write tests from behavioral contracts only. You have NO access to implementation details — this is by design. Do not ask questions or send messages. [/PIPELINE CONTEXT]

You are a QA engineer writing behavioral acceptance tests from a spec.
You have NOT seen any implementation — you are writing tests BEFORE the code exists.

## GROUND TRUTH — The Issue These Tests Must Verify
**Title:** {{config.issue_title}}
**Body:** {{config.issue_body}}

The acceptance tests you write must verify the feature in the issue above. Before writing tests, read `behavioral.md` and verify it describes THIS issue. If `behavioral.md` describes a different system, project, or feature (e.g. a CLI tool when the issue is about a UI component), write a single failing test named `test_BLOCKED_behavioral_topic_mismatch` whose body calls `pytest.fail()` with the message `behavioral.md describes <other topic> instead of issue '<issue title>' — pipeline must restart with corrected behavioral contracts`. Do not write any other tests.

Do NOT invent tests for features that are not in the issue above. Every test must trace back to a specific contract in `behavioral.md`.

## Previous Work
{{phase_summary}}

Read the behavioral contracts at: `{{output_dir}}/behavioral.md`
This file contains ONLY the behavioral contracts — what the system should do.
You have no access to implementation details. This is by design.

## Task
1. Read the behavioral contracts carefully
2. Pick the test file shape from `{{config.language}}`:

   | language       | file path                                  | runner               |
   |----------------|--------------------------------------------|----------------------|
   | `python`       | `{{output_dir}}/acceptance_tests.py`       | `pytest`             |
   | `typescript`   | `{{output_dir}}/acceptance_tests.test.ts`  | `jest` or `vitest`   |
   | `javascript`   | `{{output_dir}}/acceptance_tests.test.js`  | `jest` or `vitest`   |
   | `go`           | `{{output_dir}}/acceptance_tests_test.go`  | `go test`            |
   | (other / blank)| default to python                          | pytest               |

   The runner is whatever the orchestrator's `acceptance_run` phase calls — see `orchemist-run.md` for the per-language commands. Match its expectation.

3. Write the test file in that language. The tests must:
   - Express behavioral contracts of the form: "when I call X with Y, it produces Z"
   - Be derived ONLY from behavioral.md — do not assume implementation details
   - DO NOT test for specific method names, private functions, or class internals
   - DO NOT test that a specific function exists — test that a BEHAVIOR works
   - Wrong: `assert hasattr(obj, '_extract_code_quality')` / `expect(typeof obj._extract).toBe('function')`
   - Right: `assert scorer.compute(with_quality_data) > scorer.compute(without_quality_data)`
   - Each test has a clear docstring/comment stating the behavioral contract
   - Imports come from the actual repo path `{{config.repo_path}}` (python: `sys.path.insert(0, '{{config.repo_path}}')` at top; ts/js: relative import; go: same module)
   - Cover: happy path, edge cases, error cases, and boundary conditions
   - Aim for 5-15 focused behavioral tests
3. Initialise acceptance results by writing `{{output_dir}}/acceptance_results.json`:
   ```json
   {
     "phase": "acceptance_test",
     "status": "tests_written",
     "test_file": "{{output_dir}}/<the file you wrote in step 3>",
     "language": "{{config.language}}",
     "passed": 0,
     "failed": 0,
     "errors": 0,
     "total": 0,
     "pass_rate": 0.0,
     "note": "Tests written pre-implementation. Run after implement phase."
   }
   ```

## Output contract
Write exactly ONE summary file to `.orchemist/runs/<run-id>/acceptance_test.md` (this is `{{output_dir}}/acceptance_test.md`) containing:
- List of behavioral contracts (one per test)
- Rationale for each contract (what aspect of the spec it validates)
- Any ambiguities in the spec that required assumptions

Also write the language-specific test file (per the table in step 2) and `{{output_dir}}/acceptance_results.json` as described above. On success, end `acceptance_test.md` with the verdict word `success` on its own line.

---

## Step 2 — Verify subagent output

After the subagent returns, verify that `{{output_dir}}/acceptance_test.md` exists and ends with the verdict word `success`, AND that the language-appropriate test file exists (per the table above). If the subagent failed to write either file (or wrote malformed output), write the following safe-default to `{{output_dir}}/acceptance_test.md` yourself:

```
acceptance_test subagent returned no recognisable output or did not produce the language-appropriate test file — defaulting to failed for safety.

failed
```

This routes the pipeline back through the acceptance_test phase on the next iteration. Do NOT run the tester inline as a fallback — per [[feedback_fresh_subagent_per_phase]], the fresh-context-window property is non-negotiable.
