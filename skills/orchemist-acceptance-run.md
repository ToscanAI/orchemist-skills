---
name: orchemist:acceptance-run
description: Phase 3b of the Orchemist coding pipeline. Engine-verified pytest runner — no agent reasoning. Runs the acceptance_tests.py file against the current implementation, parses pass/fail counts, and persists engine-verified results. Triggers when /orchemist:acceptance-run is invoked or /orchemist:run advances to the acceptance_run phase.
---

# Acceptance Test Runner phase

This phase has NO LLM reasoning. It exists to provide an engine-verified gate between `implement` and `review`: the orchestrator runs pytest directly on the acceptance test file and persists the results to disk.

This skill is invoked when the user calls `/orchemist:acceptance-run` directly. The `/orchemist:run` orchestrator normally handles this phase inline (since it requires no LLM judgement), but the skill exists as a manual fallback.

## GROUND TRUTH — Issue context
**Title:** {{config.issue_title}}
**Body:** {{config.issue_body}}

(Reproduced here for traceability even though no LLM judgement is required this phase.)

## Task

1. Verify `{{output_dir}}/acceptance_tests.py` exists. If not, write `failed` to `{{output_dir}}/acceptance_run.md` with the reason `acceptance_tests.py not found — implement phase did not produce it` and stop.
1b. **Seal-integrity check (v4.4).** The sealed test file must be byte-identical to what `acceptance_test` produced — the implementer may NOT mutate the acceptance tests. If `state.json` recorded a seal hash (`acceptance_test_sha256`, written by the orchestrator at seal time), re-hash the file (`sha256sum {{output_dir}}/acceptance_tests.py`) and compare. On a MISMATCH, write `failed` to `{{output_dir}}/acceptance_run.md` with the reason `sealed acceptance tests were modified after seal — integrity check failed (sealed=<hash> now=<hash>)` and stop. Do NOT count a run against tampered tests. (The standard pipeline has no `verify_tests_integrity` phase — that gate exists only on skip-spec — so this in-phase check is the standard pipeline's tamper guard. If no seal hash was recorded, log that the integrity check was skipped and proceed.)
2. Run the tests:
   ```
   cd {{config.repo_path}}
   python3 -m pytest {{output_dir}}/acceptance_tests.py -v --tb=short
   ```
3. Capture stdout/stderr and exit code.
4. Parse pytest output to extract:
   - `passed` — count of `PASSED` lines
   - `failed` — count of `FAILED` lines
   - `errors` — count of `ERROR` lines
   - `total` = passed + failed + errors
   - `pass_rate` = passed / total (float, 0.0 if total == 0)
   - `failure_details` — the full `-v` output for failing tests (so the implement phase can read it on retry)
5. Write `{{output_dir}}/acceptance_results.json`:
   ```json
   {
     "phase": "acceptance_run",
     "passed": <int>,
     "failed": <int>,
     "errors": <int>,
     "total": <int>,
     "pass_rate": <float>,
     "failure_details": "<pytest output for failing tests>",
     "exit_code": <int>
   }
   ```
6. Write `{{output_dir}}/acceptance_run.md` containing the summary and full pytest output.

## Verdict

- `success` if `pass_rate == 1.0` AND `total > 0`
- `failed` otherwise

Do NOT modify the acceptance tests under any circumstance. If the tests are wrong, the spec loop or acceptance-test phase must be re-entered — not this phase.

## Output contract
Write exactly ONE summary file to `.orchemist/runs/<run-id>/acceptance_run.md` (this is `{{output_dir}}/acceptance_run.md`). Also write/update `{{output_dir}}/acceptance_results.json`. On success, end `acceptance_run.md` with `success` on its own line; on any test failure or error, end with `failed`.
