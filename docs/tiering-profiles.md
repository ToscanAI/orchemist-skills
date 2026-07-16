# Tiering profiles — consumer-configurable per-phase model + effort (#41)

## What it is

A **tiering profile** is a named map from a phase's `phase_class`
(`rote | interpretive | implement | gate`) to a `{ model, effort }` pair. You select one
profile once per project via `config.tiering_profile`; it then governs the model and effort
of **every** phase in the coding pipelines (`coding-pipeline-standard`,
`coding-pipeline-maintenance`, `coding-pipeline-skip-spec`). Profiles live in
[`profiles/tiering-profiles.yaml`](../profiles/tiering-profiles.yaml). The default profile is a
**no-op**: it reproduces each pipeline's declared per-phase `model_tier` with session-inherited
effort, so a project that sets nothing sees zero behavior change.

## Select a shipped profile

Set `tiering_profile` in your run config / issue config:

```yaml
config:
  tiering_profile: budget-first
```

Three profiles ship out of the box:

| profile         | rote           | interpretive   | implement    | gate           |
|-----------------|----------------|----------------|--------------|----------------|
| `default`       | inherit        | inherit        | inherit      | inherit        |
| `budget-first`  | haiku / low    | sonnet / medium| opus / high  | fable / xhigh  |
| `quality-first` | sonnet / medium| opus / high    | opus / high  | fable / xhigh  |

`inherit` means "use the phase's own declared `model_tier`" (for model) and "use the session
default" (for effort). `default` is all-inherit — a byte-for-byte reproduction of today's
behavior. `budget-first` puts a **haiku** floor on rote phases; `quality-first` spends on
interpretation + implementation. Both opt-in ladders keep gates at `fable` / `xhigh`.

## Define or override a custom profile

Add a named entry to the registry mapping **all four** `phase_class`es to `{ model, effort }`,
then select it by name:

```yaml
profiles:
  my-profile:
    rote:         { model: haiku,  effort: low }
    interpretive: { model: sonnet, effort: medium }
    implement:    { model: opus,   effort: high }
    gate:         { model: fable,  effort: xhigh }   # gate MUST stay fable
```

- `model`  ∈ `haiku | sonnet | opus | fable | inherit` (`inherit` = the phase's own `model_tier`).
- `effort` ∈ `low | medium | high | xhigh | inherit` (`inherit` = the session default).
- A profile **MUST** define all four `phase_class`es. A partial profile is a configuration
  error: a missing class raises a `KeyError` at resolve time (there is no silent fallback to
  `default`) — see `tests/tiering_profiles.py` / `tests/test_tiering_profiles.py` case (g).

A "consumer copy" means editing the **installed** registry
`~/.claude/skills/orchemist/profiles/tiering-profiles.yaml`. After you edit it, `install.sh --check`
will report a `MISMATCH` for that file — that is expected and harmless for a consumer-local
profile. Re-running `install.sh` **backs the file up** (`.bak.<UTC-timestamp>`) rather than
destroying your edits.

## The Fable gate-invariant (non-negotiable)

The `gate` class can **never** resolve below `fable`. Judgment gates (`spec_adversary`,
`test_adversary`, `acceptance_test_adversary`, `review`) are where real defects are caught; no
budget setting may tier them down. A profile that maps `gate` to anything other than `fable`
**HARD-STOPS the run** with a configuration error — it does not silently downgrade. The canonical
check is the pure function `tests/tiering_profiles.py::assert_gate_floor`, which is the single
source of truth shared by the test suite and the `skills/orchemist-run.md` prose. A phase whose
`model_tier` is `fable` but whose `phase_class` is not `gate` is itself a configuration error and
HALTs under the same rule.

## Agent vs Workflow — the effort limitation

Per-phase **effort** is fully honored ONLY on the **Workflow `agent()` path**
(`workflows/orchemist-wave.js`), where each dispatch passes the resolved `effort`. The
**single-issue Agent (Task) path has NO per-dispatch effort parameter** (the Agent tool exposes
`model`, not `effort`). On that path the orchestrator treats the profile's effort as a recommended
**SESSION** effort: set it once via `/effort` to at least the profile's `gate` effort (`xhigh` for
`budget-first` / `quality-first`) so the judgment gates are not under-powered; rote phases cannot
be individually tiered DOWN in effort here. FULL per-phase effort tiering requires the Workflow
path. Do NOT assume the Agent path applies per-phase effort.

Note on the Workflow path: it applies the profile's **effort only** — the wave dispatch **models**
stay the mode's hardcoded ladder (e.g. `budget-first` does NOT re-model wave dispatches). This is
safe for the gate floor because the wave JS already pins `model: 'fable'` on every gate dispatch.

## Model sources of truth

The profile-resolved explicit dispatch model overrides the `agents/*.md` frontmatter `model:`
default (per the explicit-model rule in `skills/orchemist-run.md`). The frontmatter
(`claude-sonnet-4-6`) is only the fallback used when no explicit model is passed, so the profile
does not introduce an unreconciled fourth source of truth — it sits on top of the existing
`model_tier` (YAML) → explicit dispatch model chain.
