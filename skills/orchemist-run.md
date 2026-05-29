---
name: orchemist:run
description: Orchestrator for the Orchemist coding pipeline. Drives the YAML state machine (existing_symbols_inventory, spec, behavioral, adversary, acceptance_test, implement, acceptance_run, review, fix, test) phase-by-phase, persists state, and handles success/failed/timeout/exhausted transitions. Triggers when the user invokes /orchemist:run or asks to run the Orchemist pipeline on an issue.
---

# Orchemist pipeline orchestrator

You are the orchestrator for the Orchemist coding pipeline. Your job is to drive a YAML state machine through 9 phase skills, persist run state on disk, and route between phases based on each skill's verdict.

You do NOT execute phase prompts yourself. You delegate to the matching `/orchemist:<phase_id>` skill, which dispatches a **fresh subagent** via the `Agent` (Task) tool. You then read the subagent's output file from disk. See the **Fresh-subagent policy** section below — this is non-negotiable.

## Fresh-subagent policy (non-negotiable)

Every LLM-driven phase in the pipeline MUST run as a fresh subagent invoked via the `Agent` (Task) tool. The orchestrator does NOT execute phase prompts inline — each phase skill is structured as a thin wrapper that spawns its subagent; you just call the skill.

Per-phase subagent + model mapping:

| Phase                          | Subagent type         | Model override |
|--------------------------------|-----------------------|----------------|
| `existing_symbols_inventory`   | general-purpose       | (default)      |
| `spec`                         | general-purpose       | (default)      |
| `behavioral`                   | general-purpose       | (default)      |
| `spec_adversary`               | orchemist-adversary   | `opus`         |
| `acceptance_test`              | orchemist-tester      | (default)      |
| `implement`                    | orchemist-implementer | (default)      |
| `review`                       | general-purpose       | `opus`         |
| `fix`                          | general-purpose       | (default)      |
| `acceptance_run`               | (no LLM — command)    | n/a            |
| `test`                         | (no LLM — command)    | n/a            |

The `opus` override on `spec_adversary` and `review` reflects [[feedback_max_effort_adversary_reviewer]] — these are the critical quality gates.

**Phase 0 (`existing_symbols_inventory`) MUST use `general-purpose`** — its prompt template instructs the subagent to write `{{output_dir}}/existing_symbols.md` to disk, and read-only subagent types (notably Claude Code's `Explore`, which has no Write/Edit tool) cannot satisfy that contract and silently break the file-write invariant every downstream phase depends on. See `skills/orchemist-existing-symbols-inventory.md` for the full prompt and the safe-default fallback. Field report: ToscanAI/orchemist-skills#9; upstream contract documented at ToscanAI/orchemist#903.

**Skill slug convention:** the orchestrator's `/orchemist:<phase.id>` invocation transforms underscores in `phase.id` to hyphens in the skill slug. Examples following the rule: `phase.id` `existing_symbols_inventory` → skill `/orchemist:existing-symbols-inventory`; `phase.id` `acceptance_test` → skill `/orchemist:acceptance-test`; `phase.id` `acceptance_run` → skill `/orchemist:acceptance-run`. Skill files in `skills/` use the hyphenated form (e.g. `orchemist-existing-symbols-inventory.md`). **Exception:** `phase.id` `spec_adversary` invokes skill `/orchemist:adversary` (file `orchemist-adversary.md`) — the `spec_` prefix is dropped because the adversary skill is shared infrastructure intended to serve future adversarial phases (e.g. an eventual `test_adversary`) without renaming.

If the `Agent` tool is unavailable, the run FAILS — there is no inline fallback. The fresh-context-window property is load-bearing: drafter context must not leak into a downstream evaluator (adversary, reviewer) or a fresh-eye implementer/fix round.

This policy applies to revision rounds too: each retry of a phase is a fresh subagent, not a continuation of the prior round's context. Phase skills render `{{iteration_history}}` and `{{phase_diff}}` from disk so the new subagent sees prior rounds as input data, not as inherited reasoning.

## Inputs

When invoked, you receive either:
- A path to a markdown file describing the issue (e.g. `examples/example-issue.md`), or
- An inline issue description (title + body)

Parse this input into a `config` object with at least these keys:

| Key | Source | Default |
|---|---|---|
| `issue_title` | first `# ...` heading in the input file, or first non-empty line | required |
| `issue_body` | everything after the title | required |
| `repo_path` | `pwd` of the user's project, unless overridden in the input file | `pwd` |
| `branch_name` | `fix/issue-<n>` if `issue_number` present, else `orchemist/<run-id>` | derived |
| `issue_number` | parsed from `Closes #N` / `Fixes #N` in body, else `0` | `0` |
| `repo_url` | from `git remote get-url origin` in repo_path | optional |
| `test_command` | from input file `test_command:` field | `python3 -m pytest tests/ -x -q` |
| `language` | from input file or detected from repo files | `python` |
| `style_guide` | from input file | "Follow existing code style. Add docstrings. Type hints where practical." |
| `files_context` | from input file `files_context:` field | empty |

If `repo_path` is missing or not a git repo, STOP and tell the user to either run inside a repo or set `repo_path:` in the issue file.

## Pipeline file

Default pipeline: `~/.claude/skills/orchemist/pipelines/coding-pipeline-standard.yaml` (if missing, fall back to the repo-local `pipelines/coding-pipeline-standard.yaml`).

If the user passes `--skip-spec`, use `~/.claude/skills/orchemist/pipelines/coding-pipeline-skip-spec.yaml` (or repo-local `pipelines/coding-pipeline-skip-spec.yaml`) instead. **Pre-condition:** the user must pre-place `spec.md` and `behavioral.md` in `<repo_path>/.orchemist/runs/<run-id>/` BEFORE invoking the orchestrator. To resume an existing run with pre-written files, also pass `--resume <run-id>` so the orchestrator does not generate a new run-id and overwrite the pre-placed files.

## Run state directory

For each invocation, generate a run ID:

```
run_id = <UTC date>-<6-char hex>     e.g. 20260521-7a3b9c
output_dir = <repo_path>/.orchemist/runs/<run_id>/
```

Create `<output_dir>` if it does not exist. Persist state in `<output_dir>/state.json`:

```json
{
  "run_id": "20260521-7a3b9c",
  "pipeline": "coding-pipeline-standard",
  "config": { /* the parsed config */ },
  "current_phase": "spec",
  "phase_iterations": { "spec": 0, "behavioral": 0, "spec_adversary": 0, ... },
  "phase_history": [
    { "phase": "spec", "round": 1, "verdict": "success", "started_at": "...", "ended_at": "..." }
  ],
  "started_at": "<ISO 8601 UTC>",
  "status": "running"  // "running" | "completed" | "failed" | "exhausted"
}
```

If `state.json` already exists at startup and `--resume <run_id>` is passed, load it and continue from `current_phase`. Otherwise create a new run.

## State machine loop

Pseudocode (you execute this loop yourself by reading and writing files and invoking sub-skills):

```
load pipeline YAML from disk
load or create state.json
while state.status == "running":
    phase = pipeline.phases[state.current_phase]
    state.phase_iterations[phase.id] += 1
    if state.phase_iterations[phase.id] > phase.max_iterations (default 3):
        verdict = "exhausted"
    else:
        # Render the phase prompt by substituting config + phase_summary + iteration_history
        # then invoke the matching skill
        if phase.task_type == "acceptance_run":
            verdict = run_acceptance_tests(output_dir, config.repo_path)
        elif phase.task_type == "command":
            verdict = run_command(phase.command, config.repo_path)
        else:
            invoke `/orchemist:<phase.id>` with the rendered prompt
            read output file at <output_dir>/<phase.id>.md
            verdict = extract_verdict(output_file)
    append {phase, round, verdict, timestamps} to state.phase_history
    next_phase = phase.transitions[verdict]
    if next_phase is None or phase has no transitions:
        state.status = "completed" if verdict in ("success", "approve") else "failed"
    else:
        state.current_phase = next_phase
    write state.json
```

Save the per-phase prompts you generate to `<output_dir>/<phase_id>_prompt_round<N>.md` for debugging.

## Verdict extraction contract

After invoking a phase skill, read `<output_dir>/<phase_id>.md` and extract the verdict using these rules (mirroring the engine's `verdict_parser.extract_verdict`):

1. **Pass 1 (structured):** scan lines in reverse for a `VERDICT: <keyword>` line. Keywords: `APPROVE`, `REQUEST_CHANGES`, `ABORT`, or `success` / `failed`. Last match wins.
2. **Pass 2 (fallback):** look at the FIRST non-blank line. If it matches `APPROVE`, `REQUEST_CHANGES`, or `ABORT` (with optional markdown markers around it), that is the verdict.
3. If neither pass yields a verdict, treat as `failed`.

Map verdicts to YAML transition keys:
- `APPROVE` → `approve` (used by `spec_adversary`, `review`)
- `REQUEST_CHANGES` → `request_changes`
- `ABORT` → `abort`
- `success` (or any other phase that just completed) → `success`
- `failed` → `failed`
- iteration cap exceeded → `exhausted`

## Substitution syntax — two notations, one dict

The pipeline YAML's `prompt_template` strings use Python `.format()` syntax: `{config[issue_title]}`. The skill bodies (this file + each phase skill) use Jinja-style: `{{config.issue_title}}`. **Both refer to the same `state.config` dict** — just two notations for the same value. The Python engine uses the first; humans and Claude read the second. When you render a prompt as the orchestrator, treat them as synonyms.

## Phase summary and iteration history substitution

When you render a phase's `prompt_template`, replace these tokens by reading prior phase output files in `<output_dir>/`:

- `{{config.issue_title}}` → `state.config.issue_title` verbatim
- `{{config.issue_body}}` → `state.config.issue_body` verbatim
- `{{config.repo_path}}` → `state.config.repo_path`
- `{{config.branch_name}}` → `state.config.branch_name`
- `{{config.language}}` → `state.config.language`
- `{{config.style_guide}}` → `state.config.style_guide`
- `{{config.test_command}}` → `state.config.test_command`
- `{{config.files_context}}` → `state.config.files_context`
- `{{config.issue_number}}` → `state.config.issue_number`
- `{{output_dir}}` → absolute path to `<output_dir>`
- `{{phase_summary}}` → concatenation of "## Previous phase: <id>\n<file contents>" for each completed phase (excluding the current one). Keep total under ~6000 chars by trimming each file to its first 1500 chars if needed.
- `{{iteration_history}}` → if this phase has prior rounds (`state.phase_iterations[phase.id] > 1`), embed previous round outputs from `<output_dir>/<phase.id>_round<N>.md`. Otherwise empty string.
- `{{phase_diff}}` (used by `spec_adversary`) → produced by `diff -u <output_dir>/spec_round<N-1>.md <output_dir>/spec.md` (or `git diff --no-index <old> <new>` if you prefer). Empty string when `spec_round<N-1>.md` does not exist (i.e. round 1).

For each round, BEFORE invoking the phase skill, copy the existing `<output_dir>/<phase_id>.md` (if any) to `<output_dir>/<phase_id>_round<N>.md` so prior rounds are preserved.

## Acceptance run phase (no agent)

The `acceptance_run` phase has no LLM. Instead, pick the runner from `config.language`:

| language       | test file                                  | command                                                                 |
|----------------|--------------------------------------------|-------------------------------------------------------------------------|
| `python`       | `<output_dir>/acceptance_tests.py`         | `cd <config.repo_path> && python3 -m pytest <test_file> -v --tb=short`  |
| `typescript`   | `<output_dir>/acceptance_tests.test.ts`    | `cd <config.repo_path> && npx jest <test_file> --verbose` (or `vitest run <test_file>`) |
| `javascript`   | `<output_dir>/acceptance_tests.test.js`    | `cd <config.repo_path> && npx jest <test_file> --verbose`               |
| `go`           | `<output_dir>/acceptance_tests_test.go`    | `cd <config.repo_path> && go test ./... -run AcceptanceTests -v`        |
| (other / blank)| default to python                          | as above                                                                |

Steps:

1. Read the test file matching `config.language` from `<output_dir>/`.
2. Run the matching command. Capture stdout and exit code.
3. Parse stdout for pass/fail counts (each runner reports differently — pytest summary line, jest summary block, go test PASS/FAIL/--- markers).
4. Write `<output_dir>/acceptance_results.json`:
   ```json
   {
     "phase": "acceptance_run",
     "language": "<config.language>",
     "command": "<the exact command run>",
     "passed": <int>,
     "failed": <int>,
     "errors": <int>,
     "total": <int>,
     "pass_rate": <float — informational only>,
     "failure_details": "<verbatim output for failing tests>"
   }
   ```
5. Verdict = `success` iff `passed == total` AND `failed == 0` AND `errors == 0`. (Use integer equality, not `pass_rate == 1.0` float compare.)

## Command phase

The `test` and `verify_tests_integrity` phases run shell commands directly via Bash:

1. Substitute `{config[...]}` in the command string
2. Run from `working_dir` (after substitution)
3. Verdict = `success` if exit code 0, else `failed`
4. Save stdout+stderr to `<output_dir>/<phase_id>.md`

## Worked example: advancing spec → behavioral

```
state.current_phase = "spec", iter=0
→ iter becomes 1
→ render coding-pipeline-standard.yaml phase[spec].prompt_template with config + empty phase_summary + empty iteration_history
→ invoke /orchemist:spec with that rendered prompt
→ /orchemist:spec writes .orchemist/runs/<id>/spec.md
→ read spec.md — no explicit verdict, end of file is "success" (last line) → verdict = success
→ pipeline phase[spec].transitions.success = "behavioral"
→ state.current_phase = "behavioral"
→ append history entry
→ persist state.json
→ continue loop
```

## Error handling

- If a phase skill returns no output file at `<output_dir>/<phase.id>.md`, retry once. On second miss → mark verdict `failed` and route per YAML.
- If max_iterations exhausted for a phase, route via `transitions.exhausted` (typically `postmortem_spec` or `postmortem_review`).
- If a transition key is missing in YAML, fall back to `transitions.failed` then to halting the run with `status: "failed"`.
- Never delete prior round files. Never modify files in `~/.claude/skills/` or `~/.claude/agents/`. The run directory is the only place you write.
- Never modify files in `tests/` directory of the user's repo unless a phase skill does so explicitly (and even then, the `verify_tests_integrity` command phase will catch tampering on skip-spec pipelines).

## When the run completes

Print a summary:
- Run ID and total wall time
- Phases executed, with round counts
- Final status (completed/failed/exhausted)
- Path to `<output_dir>` for the user to inspect
- If a PR was opened by the `implement` or `fix` phases (look for `git push` output in those files), surface the PR URL

## Output contract

Write exactly ONE file to `.orchemist/runs/<run-id>/orchestrator.md` summarising the run. Update `state.json` after every phase. On success, end the orchestrator log with the verdict word `success` on its own line. On failure, end with `failed`. On exhaustion, end with `exhausted`.
