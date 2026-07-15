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
   | `csharp`       | `.cs` file inside a dedicated test project (see the C# note below — NOT a single `{{output_dir}}` path) | `dotnet test` (xUnit) |
   | (other / blank)| default to python                          | pytest               |

   The runner is whatever the orchestrator's `acceptance_run` phase calls — see `orchemist-run.md` for the per-language commands. Match its expectation.

   **C# / .NET (`language == csharp`):** write xUnit tests (`[Fact]` / `[Theory]`) into a dedicated test project in the repo — convention `{{config.repo_path}}/src/<SUT-name>.Tests/` — reusing an existing `*.Tests` project if present, else creating one via `dotnet new xunit` + `dotnet add reference` to the SUT project + `dotnet sln add`. Select the SUT and test projects DETERMINISTICALLY (SUT = the project named in the issue/spec context, else the single non-test `*.csproj`; test project = the single existing `*.Tests`, else create `<SUT-name>.Tests`); if EITHER is ambiguous — multiple candidates on either side, none named — HALT with a clear BLOCKED reason rather than guess (a wrong `dotnet add reference` compiles the sealed test against the wrong or absent API). If ZERO non-test `*.csproj` candidates exist and none is named, HALT with a BLOCKED reason (`no SUT project found — csharp detected but no non-test *.csproj in repo`). Record the chosen SUT and test-project absolute paths in `state.json` (`state.csharp_sut_project`, `state.csharp_test_project`) — see the ".NET / C#" subsection in `orchemist-run.md` for the exact rule. The sealed test is that `.cs` file (its absolute path is recorded as `state.acceptance_test_file`, and its fully-qualified name — namespace + class — as `state.acceptance_test_fqn` so `acceptance_run` can `--filter` to it; absent an FQN, `acceptance_run` runs the whole test project with no `--filter`), NOT a `{{output_dir}}` loose file. Assert against the real API surface the contract names; pre-implement these tests will FAIL TO COMPILE (the SUT types do not exist yet) — that is the intended RED. The tests remain the immutable sealed contract.

3. Write the test file in that language. The tests must:
   - Express behavioral contracts of the form: "when I call X with Y, it produces Z"
   - Be derived ONLY from behavioral.md — do not assume implementation details
   - DO NOT test for specific method names, private functions, or class internals
   - DO NOT test that a specific function exists — test that a BEHAVIOR works
   - Wrong: `assert hasattr(obj, '_extract_code_quality')` / `expect(typeof obj._extract).toBe('function')`
   - Right: `assert scorer.compute(with_quality_data) > scorer.compute(without_quality_data)`
   - Each test has a clear docstring/comment stating the behavioral contract
   - Imports come from the actual repo path `{{config.repo_path}}` (python: `sys.path.insert(0, '{{config.repo_path}}')` at top; ts/js: relative import; go: same module; csharp: the test project references the SUT via `dotnet add reference`)
   - Cover: happy path, edge cases, error cases, and boundary conditions
   - Aim for 5-15 focused behavioral tests

### Harness rules (v4.4) — apply ALL when writing the suite

Each rule below was earned in a multi-run engine campaign where a violation cost a sealed-test round; they are repo-agnostic. A violation makes a test pass or fail for the WRONG reason, which corrupts the red/green gate the implementer relies on. (The `orchemist-tester` subagent definition carries the full rationale — these are the imperative summary.)

- **Module-level imports = today-real names only.** Collection must succeed against the code as it exists now. Import/assert any `[NEW]` (not-yet-built) symbol lazily inside the test body; probe `[DELETED]` modules in-body via `importlib`. A `[NEW]` symbol imported at module scope kills collection and silently skips the whole file.
- **Every runner-stub / fake callable ends its signature with `**kwargs`.** Sequencers call workers with keyword args; a bare positional stub raises a (often swallowed) `TypeError` → phases report empty/failed and tests fail for the wrong reason.
- **Copy the contract-named real helper; never hand-roll its construction.** Build real spec/request/config objects with production's own idiom — hand-rolled versions silently drop phantom kwargs (permissive `extra="ignore"` models) or wrap an enum/plain value incorrectly.
- **Count logs/warnings with a keyword filter scoped to the contract's family — never raw `== []` over a logger.** Pre-existing unrelated warnings contaminate logger-level captures and flake a zero-warning assertion.
- **Isolate the environment for credential-sensitive contracts.** Factory/object level: `patch.dict(os.environ, {}, clear=True)` + explicit `pop`. CLI level: `monkeypatch.delenv(...)` AND `env={"THE_KEY": ""}` — Click's `CliRunner` `env=` OVERLAYS the parent env, it does NOT unset, so blank the key explicitly.
- **Derive each test's expected-today status from reachability, with stated reasoning.** For every test decide, against today's code, whether it should PASS now (a shield guarding existing behaviour) or FAIL now (a red awaiting `[NEW]` work), and record the reasoning. A mislabeled ledger corrupts the gate.
- **CLI tests that drive the real run command must transport-seal the executors UNCONDITIONALLY.** Even if the contract says the build fails before execution, that holds only post-implementation — at HEAD and against buggy code the run reaches REAL phase execution and live HTTP. Patch the executor transport methods class-level as a hermeticity backstop (when the eager guard fires first the patch is harmlessly unused). A post-impl-only rationale is never a license to omit the network seal.
- **Glob is unreliable in worktrees.** Verify a path/symbol exists with `Grep`/`Bash`; never treat an empty `Glob` as proof of absence.

### Render-determinism preflight (2026-06-14) — MANDATORY for computed-style / a11y specs

ANY e2e spec this phase authors that reads COMPUTED STYLE (`getComputedStyle` / Playwright `.evaluate(el => getComputedStyle(el)...)`) OR runs an a11y/axe check MUST satisfy BOTH of the following, or it produces a verdict for the WRONG reason:

- **Kill transitions+animations BEFORE any theme toggle.** Before flipping the `.dark` / theme class (or any class that animates colour), inject a kill-switch: `await page.addStyleTag({content:'*,*::before,*::after{transition:none!important;animation:none!important}'})`. Colour reads taken mid-`transition-colors` return an in-between value — the read is not SETTLED. Inject the kill-switch immediately after navigation and again after any DOM swap that could re-arm a transition.
- **The colour parser MUST accept 8-digit hex AND `rgb()`/`rgba()`, not 6-digit hex only.** Accept `#RRGGBB`, `#RRGGBBAA`, `rgb(r,g,b)`, and `rgba(r,g,b,a)`. Production CSS minifiers (e.g. Lightning CSS under `next start`) emit dark design tokens carrying alpha — e.g. `rgba(…,.15)` — as 8-digit hex (`#RRGGBBAA`). A 6-digit-only parser silently MISSES the dark value and reports a phantom "no colour applied" failure. Normalise both forms to comparable channels before asserting.

GROUNDING: an EPIC-20 production run burned **3 seal-break rounds** chasing a phantom "frozen-utility" bug that was in fact a mid-`transition-colors` colour read (compounded by a 6-digit-only parser missing the 8-digit dark token). This preflight prevents the entire defect class — apply it unconditionally to any colour/contrast/a11y spec, even when the contract does not name animation.

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
- **Expected-today ledger** — a table mapping each test → its expected-today verdict (`PASS-now` shield / `FAIL-now` red) → the one-line reachability reasoning (per the v4.4 harness rules above). The orchestrator's pre-flight and the adversary check this ledger against the actual collect-only + run output; a mislabeled entry is treated as a defect.

Also write the language-specific test file (per the table in step 2) and `{{output_dir}}/acceptance_results.json` as described above. On success, end `acceptance_test.md` with the verdict word `success` on its own line.

---

## Step 2 — Verify subagent output

After the subagent returns, verify that `{{output_dir}}/acceptance_test.md` exists and ends with the verdict word `success`, AND that the language-appropriate test file exists (per the table above). If the subagent failed to write either file (or wrote malformed output), write the following safe-default to `{{output_dir}}/acceptance_test.md` yourself:

```
acceptance_test subagent returned no recognisable output or did not produce the language-appropriate test file — defaulting to failed for safety.

failed
```

This routes the pipeline back through the acceptance_test phase on the next iteration. Do NOT run the tester inline as a fallback — per [[feedback_fresh_subagent_per_phase]], the fresh-context-window property is non-negotiable.
