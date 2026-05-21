# Orchemist Skills Pack for Claude Code

## What this is

A repackaging of the [Orchemist](https://github.com/ToscanAI/orchestration-engine) coding pipeline as a set of [Claude Code](https://claude.com/claude-code) skills (`.claude/skills/`) and subagents (`.claude/agents/`). Drop it into Claude Code and you get a one-command, ground-truth-anchored, adversarially-reviewed implementation pipeline for any GitHub issue: spec -> behavioral contracts -> adversary -> acceptance tests -> implement -> verify -> review -> fix -> test. Each phase writes exactly one file under `.orchemist/runs/<run-id>/`, so the whole run is auditable on disk.

## Why

The Orchemist coding pipeline lives in a Python/FastAPI engine ([the main repo](https://github.com/ToscanAI/orchestration-engine)) that requires a server, a queue, and an OpenRouter / Anthropic API key. This skills pack is a stripped-down distribution: pure markdown, no Python runtime, no server. It runs entirely inside Claude Code using whatever model and auth you've already configured there (Anthropic subscription or API key — your choice). The adversary phase runs as a Claude Code subagent in its own context window, which is the first concrete step toward the engine's planned cross-model adversarial review (issue #677).

## Install

```bash
git clone https://github.com/ToscanAI/orchemist-skills.git
cd orchemist-skills
./install.sh
```

This copies the skills to `~/.claude/skills/`, subagents to `~/.claude/agents/`, and pipeline YAMLs to `~/.claude/skills/orchemist/pipelines/`. Running `./install.sh` twice is safe — it backs up any existing files to `<name>.bak.<UTC-timestamp>` and then reports an unchanged state on the second run.

## First run

```
cd <your-git-repo>
claude
> /orchemist:run examples/example-issue.md
```

The orchestrator parses the issue file, creates a run directory at `<repo>/.orchemist/runs/<UTC-date>-<hex>/`, and walks the pipeline phase-by-phase. Watch the run directory fill with `spec.md`, `behavioral.md`, `spec_adversary.md`, `acceptance_tests.py`, `acceptance_results.json`, `implement.md`, `review.md`, `fix.md`, `test.md`, and a per-run `state.json` you can resume from with `/orchemist:run --resume <run-id>`.

## Status

**Alpha.** This is a fresh repackage. The underlying pipeline prompts have one successful end-to-end run via the Python engine (recorded 2026-04-17 on a fix branch for the engine repo), but this skills pack is new and has not been used in production. Expect rough edges:

- The orchestrator state machine is described in the `/orchemist:run` skill body but is executed by Claude reading and writing files — it is not a compiled state machine. Multi-phase runs depend on the model following the orchestrator skill's instructions accurately.
- Verdict extraction follows the engine's `verdict_parser.extract_verdict` contract, but the implementation is in a skill's prose, not a parser library — corner cases may differ.
- The acceptance-run and test phases shell out to `python3 -m pytest`. Non-Python projects will need to override `test_command` in the issue file.
- No telemetry, no auto-update, no e2e tests for the skills themselves yet.

If you want the full engine experience (web UI, queue, multi-provider model selection, daemon mode, history dashboards), see the main repo: <https://github.com/ToscanAI/orchestration-engine>.

License: MIT. See `LICENSE`.
