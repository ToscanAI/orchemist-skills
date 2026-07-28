# Orchemist Skills Pack for Claude Code

## What this is

A repackaging of the [Orchemist](https://github.com/ToscanAI/orchemist) coding pipeline as a set of [Claude Code](https://claude.com/claude-code) skills (`.claude/skills/`) and subagents (`.claude/agents/`). Drop it into Claude Code and you get a one-command, ground-truth-anchored, adversarially-reviewed implementation pipeline for any GitHub issue: spec -> behavioral contracts -> adversary -> acceptance tests -> implement -> verify -> review -> fix -> test. Each phase writes exactly one file under `.orchemist/runs/<run-id>/`, so the whole run is auditable on disk.

## Why

The Orchemist coding pipeline lives in a Python/FastAPI engine ([the main repo](https://github.com/ToscanAI/orchemist)) that requires a server, a queue, and an OpenRouter / Anthropic API key. This skills pack is a stripped-down distribution: pure markdown, no Python runtime, no server. It runs entirely inside Claude Code using whatever model and auth you've already configured there (Anthropic subscription or API key — your choice). The adversary phase runs as a Claude Code subagent in its own context window, which is the first concrete step toward the engine's planned cross-model adversarial review (issue #677).

## Install

```bash
git clone https://github.com/ToscanAI/orchemist-skills.git
cd orchemist-skills
npm run install:pack
```

The installer is a dependency-free Node script (`install.mjs`), so it runs the same on Linux, macOS, and Windows/PowerShell — Node 18+ is the only prerequisite.

This copies the skills to `~/.claude/skills/`, subagents to `~/.claude/agents/`, pipeline YAMLs to `~/.claude/skills/orchemist/pipelines/`, tiering profiles to `~/.claude/skills/orchemist/profiles/`, and workflows to `~/.claude/workflows/`. Running `npm run install:pack` twice is safe — it backs up any existing files to `<name>.bak.<UTC-timestamp>` and then reports an unchanged state on the second run. Use `npm run install:pack -- --check` for a read-only dry run that reports whether the installed copy is in sync (exit 0) or has drifted (exit 1).

### Tiering profiles (optional)

The coding pipelines resolve each phase's `{model, effort}` through a named **tiering profile** (`config.tiering_profile`, default `"default"`). The default is a zero-change no-op — every phase runs on its own declared model. Opt into `budget-first` or `quality-first`, or define your own, and the `gate` class can never resolve below Fable 5. See [`docs/tiering-profiles.md`](docs/tiering-profiles.md).

## First run

```
cd <your-git-repo>
claude
> /orchemist:run examples/example-issue.md
```

The orchestrator parses the issue file, creates a run directory at `<repo>/.orchemist/runs/<UTC-date>-<hex>/`, and walks the pipeline phase-by-phase. Watch the run directory fill with `spec.md`, `behavioral.md`, `spec_adversary.md`, `acceptance_tests.py`, `acceptance_results.json`, `implement.md`, `review.md`, `fix.md`, `test.md`, and a per-run `state.json` you can resume from with `/orchemist:run --resume <run-id>`.

## Parallel waves

When several **file-disjoint** lanes are ready at once — a god-module decomposition, a mechanical
codemod across packages, a batch of independent fixes — `workflows/orchemist-wave.js` fans them out
instead of running the single-issue pipeline N times. It installs to `~/.claude/workflows/` and is
launched through Claude Code's `Workflow` tool:

```
Workflow({ name: "orchemist-wave", args: { mode: "maintenance", repo: "...", base: "main", lanes: [ ... ] } })
```

Five modes, each a different per-lane phase sequence:

| mode | per-lane sequence | use it for |
|---|---|---|
| `refactor` (default) | implement → review | behavior-preserving change; the bar is ZERO functional change and the reviewer's gate is an explicit public-surface diff |
| `maintenance` | spec → spec-adversary → implement + focused test → review | independent bug / infra / CI / data fixes; lanes ADD behavior and tests |
| `codemod` | spec → spec-adversary → codemod-implement → review | behavior-preserving lint/codemod cleanup — a planning gate, but no new behavior and no new test |
| `content` | research → draft → fact-check gate → red-team gate | in-app content authored as a real committed diff, with blocking source-grounded gates |
| `standard` | spec → behavioral → spec-adversary → acceptance test → pre-flight RED → test-adversary → SEAL → implement → acceptance run → review | NEW, sealable behavior held to the full sealed-acceptance bar |

Lanes run in **per-lane lockstep with no barrier** — each lane reviews as soon as its own implement
finishes, so wall-clock is the slowest single lane, not the sum. Every dispatch that writes to the
tree runs in its **own git worktree**, so concurrent lanes never collide on the git index. Every
adversary and review gate runs on Fable 5, independently of the Opus implementer.

The wave hands back **reviewed, pushed branches plus a per-lane verdict**. It deliberately does
**not merge**: toggling branch protection, squash-merging to the shared default branch, and running
the post-merge composition suite are outward-facing and easy to get subtly wrong, so they stay a
deliberate operator step — emitted as a recipe in the workflow's `next_step` output.

Full reference — mode selection, the lane object, every argument, the output schema, and the
operator merge recipe: [`docs/orchemist-wave.md`](docs/orchemist-wave.md).

## Status

**Alpha — proven on real work, with known rough edges.** The pipeline prompts started from one end-to-end run via the Python engine (2026-04-17) plus one E2E test of this pack itself (2026-05-21, a parseDuration fix on a TypeScript repo — 12/12 acceptance tests passing post-fix). That is no longer the evidence base. Since then the pack has driven: the engine's [#942](https://github.com/ToscanAI/orchemist/issues/942) mega-module decomposition through the wave's `refactor` mode (closed 2026-06-18); a six-run standard-pipeline campaign against the engine over 24h on 2026-06-10/11, whose lessons became v4.4; the pipeline-efficiency batch ([#23](https://github.com/ToscanAI/orchemist-skills/pull/23), 2026-06-14); multiple waves in a separate consumer repo; and **19 closed issues across 32 merged PRs in this repo**, shipped through the pack's own pipelines — most recently the `standard` wave mode (#47), the Windows/CRLF fixes (#50), and the Node installer (#52). It is still a young pack: two months old, 269 tests, no CI. Expect rough edges:

- The orchestrator state machine is described in the `/orchemist:run` skill body but is executed by Claude reading and writing files — it is not a compiled state machine. Multi-phase runs depend on the model following the orchestrator skill's instructions accurately.
- Verdict extraction follows the engine's `verdict_parser.extract_verdict` contract, but the implementation is in a skill's prose, not a parser library — corner cases may differ.
- **Multi-language support landed 2026-05-21** (after the first E2E test). `acceptance_test` and `acceptance_run` now switch on `config.language` between Python/pytest, TypeScript+JavaScript/jest, Go/`go test`, and C#/`dotnet test`. Genuinely unknown languages fall back to Python.
- **The `Agent` (Task) tool is a hard requirement — there is no inline fallback.** Every LLM-driven phase dispatches to a fresh subagent; the inline-mode escape hatch the `implement` and `adversary` skills once had was deliberately removed. If your Claude Code session lacks the `Agent` tool, the run **fails** rather than degrading. The fresh-context-window property is load-bearing: drafter context must not leak into a downstream evaluator or a fresh-eye implementer. (What the orchestrator still runs inline are the non-LLM phases — `acceptance_run`, the final `test` run, and skip-spec's `verify_tests_integrity` — which shell out to a test runner or a `git diff` check and need no LLM judgement at all.)
- No telemetry, no auto-update, no automated CI for the skills themselves yet.

If you want the full engine experience (web UI, queue, multi-provider model selection, daemon mode, history dashboards), see the main repo: <https://github.com/ToscanAI/orchemist>.

## What's next

The skills pack is **Track A** of the 2026-05-21 pivot — it ships the coding pipeline to anyone already using Claude Code. **Track B** is the engine-side dialogue phase, which **shipped** in [PR #808](https://github.com/ToscanAI/orchemist/pull/808) (merged 2026-05-25): a round-based drafter ↔ reviewer loop that alternates across different executors and models, with a `gemini` CLI executor alongside the Anthropic ones. The epic that owns it ([#677](https://github.com/ToscanAI/orchemist/issues/677)) and its empirical calibration ([#886](https://github.com/ToscanAI/orchemist/issues/886)) are still open.

The web surface that operates both tracks at scale is the **Orchemist Harness Redesign**, which shipped under epic [ToscanAI/orchemist#810](https://github.com/ToscanAI/orchemist/issues/810) (closed 2026-05-25). The investigation pack with vision, mockups, and the duplicate-function audit lives at [`docs/harness-redesign-2026-05-24/`](https://github.com/ToscanAI/orchemist/tree/main/docs/harness-redesign-2026-05-24) in the engine repo.

## Versioning

[`CHANGELOG.md`](CHANGELOG.md) tracks three independent version axes. The **structural-pipeline line** is still at **v4.4** (2026-06-11 — sealed-test harness rules, test-adversary pre-flight, contract-amendment protocol, decisive checks, surgical revision rounds, seal-integrity verification; that release was process-only, with zero `pipelines/*.yaml` changes). Entries since v4.4 are named rather than numbered, and several of them **did** change the pipeline YAMLs — Fable adversary/review gates, `phase_class` annotations, and a new content pipeline — so each YAML now carries its own `version`: standard `2.2.0`, maintenance `1.3.0`, skip-spec `1.3.0`, content `0.1.0`, comic-strip `0.1.1`. The skills-pack distribution version (`package.json`, currently `0.4.0`) tracks separately again.

License: MIT. See `LICENSE`.
