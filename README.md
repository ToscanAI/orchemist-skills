# Orchemist Skills Pack for Claude Code

## What this is

A repackaging of the [Orchemist](https://github.com/ToscanAI/orchemist) coding pipeline as a set of [Claude Code](https://claude.com/claude-code) skills (`.claude/skills/`) and subagents (`.claude/agents/`). Drop it into Claude Code and you get a one-command, ground-truth-anchored, adversarially-reviewed implementation pipeline for any GitHub issue: spec -> behavioral contracts -> adversary -> acceptance tests -> implement -> verify -> review -> fix -> test. Each phase writes exactly one file under `.orchemist/runs/<run-id>/`, so the whole run is auditable on disk.

## Why

The Orchemist coding pipeline lives in a Python/FastAPI engine ([the main repo](https://github.com/ToscanAI/orchemist)) that requires a server, a queue, and an OpenRouter / Anthropic API key. This skills pack is a stripped-down distribution: pure markdown, no Python runtime, no server. It runs entirely inside Claude Code using whatever model and auth you've already configured there (Anthropic subscription or API key — your choice). The adversary phase runs as a Claude Code subagent in its own context window, which is the first concrete step toward the engine's planned cross-model adversarial review (issue #677).

## Install

```bash
git clone https://github.com/ToscanAI/orchemist-skills.git
cd orchemist-skills
./install.sh
```

This copies the skills to `~/.claude/skills/`, subagents to `~/.claude/agents/`, pipeline YAMLs to `~/.claude/skills/orchemist/pipelines/`, and tiering profiles to `~/.claude/skills/orchemist/profiles/`. Running `./install.sh` twice is safe — it backs up any existing files to `<name>.bak.<UTC-timestamp>` and then reports an unchanged state on the second run.

### Tiering profiles (optional)

The coding pipelines resolve each phase's `{model, effort}` through a named **tiering profile** (`config.tiering_profile`, default `"default"`). The default is a zero-change no-op — every phase runs on its own declared model. Opt into `budget-first` or `quality-first`, or define your own, and the `gate` class can never resolve below Fable 5. See [`docs/tiering-profiles.md`](docs/tiering-profiles.md).

## First run

```
cd <your-git-repo>
claude
> /orchemist:run examples/example-issue.md
```

The orchestrator parses the issue file, creates a run directory at `<repo>/.orchemist/runs/<UTC-date>-<hex>/`, and walks the pipeline phase-by-phase. Watch the run directory fill with `spec.md`, `behavioral.md`, `spec_adversary.md`, `acceptance_tests.py`, `acceptance_results.json`, `implement.md`, `review.md`, `fix.md`, `test.md`, and a per-run `state.json` you can resume from with `/orchemist:run --resume <run-id>`.

## Status

**Alpha.** This is a fresh repackage. The underlying pipeline prompts have one successful end-to-end run via the Python engine (recorded 2026-04-17 on a fix branch for the engine repo), plus one E2E test of this skills pack itself (2026-05-21, parseDuration bug fix on a TypeScript test repo — reached `acceptance_run` with 12/12 acceptance tests passing post-fix). Expect rough edges:

- The orchestrator state machine is described in the `/orchemist:run` skill body but is executed by Claude reading and writing files — it is not a compiled state machine. Multi-phase runs depend on the model following the orchestrator skill's instructions accurately.
- Verdict extraction follows the engine's `verdict_parser.extract_verdict` contract, but the implementation is in a skill's prose, not a parser library — corner cases may differ.
- **Multi-language support landed 2026-05-21** (after the first E2E test). `acceptance_test` and `acceptance_run` now switch on `config.language` between Python/pytest, TypeScript+JavaScript/jest, and Go/`go test`. Unknown languages fall back to Python.
- **Task tool fallback:** the `adversary` and `implement` skills delegate to subagents when the Task tool is available. If your Claude Code session lacks it, both skills have an explicit inline-mode fallback — you lose the fresh-context-window property, but the pipeline still produces the correct artifacts.
- No telemetry, no auto-update, no automated CI for the skills themselves yet.

If you want the full engine experience (web UI, queue, multi-provider model selection, daemon mode, history dashboards), see the main repo: <https://github.com/ToscanAI/orchemist>.

## What's next

The skills pack is **Track A** of the 2026-05-21 pivot — it ships the coding pipeline to anyone already using Claude Code. **Track B** is the engine-side dialogue phase ([PR #808](https://github.com/ToscanAI/orchemist/pull/808)), which adds a cross-model reviewer (Claude drafter ↔ Gemini reviewer) for the full trust-engine wedge.

The web surface that operates both tracks at scale is the **Orchemist Harness Redesign**, tracked as epic [ToscanAI/orchemist#810](https://github.com/ToscanAI/orchemist/issues/810). The investigation pack with vision, mockups, and the duplicate-function audit lives at [`docs/harness-redesign-2026-05-24/`](https://github.com/ToscanAI/orchemist/tree/main/docs/harness-redesign-2026-05-24) in the engine repo.

## Versioning

The pipeline YAML's structural revisions are tracked in [`CHANGELOG.md`](CHANGELOG.md). Current pipeline structure: **v4.4** (process upgrades from the engine standard-pipeline campaign — sealed-test harness rules, test-adversary pre-flight, contract-amendment protocol, decisive checks, surgical revision rounds, seal-integrity verification; process-only, no pipeline-YAML changes, 2026-06-11). The skills-pack distribution version (`package.json`) tracks separately.

License: MIT. See `LICENSE`.
