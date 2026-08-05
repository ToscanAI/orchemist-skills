# The wave — parallel lane orchestration (`workflows/orchemist-wave.js`)

## What it is

Where a **pipeline** (`pipelines/*.yaml`, driven by `/orchemist:run`) takes **one issue** through
its phases, a **workflow** sits one layer up and coordinates **many lanes in parallel**. The wave
fans N independent, **file-disjoint** lanes through a per-lane phase sequence and hands back
reviewed, pushed branches plus a go/no-go verdict for each one.

It installs to `~/.claude/workflows/orchemist-wave.js` (`npm run install:pack`) and runs through
Claude Code's `Workflow` tool.

### When to use it

Several behavior-preserving or independently-scoped, **file-disjoint** lanes ready at once: a
god-module decomposition, a mechanical codemod across packages, a batch of independent maintenance
fixes, a set of new modules that each need the full sealed-acceptance bar.

> **Rule of thumb:** serialize lanes **within** one module — they edit the same files, so they
> conflict. Parallelize **across** modules — disjoint directories compose cleanly. Wall-clock is
> the slowest single lane, not the sum.

## The five modes

`args.mode` selects the per-lane phase sequence. Every adversary and review gate runs on **Fable 5**
regardless of mode; implement and draft dispatches run on **Opus**.

| mode | per-lane sequence | the bar |
|---|---|---|
| `refactor` (default) | `implement` → `review` | ZERO functional change. The reviewer's durable gate is an explicit **public-surface diff** — a dropped re-export passes both the contract test and the full suite, so only the diff catches it. Pass `facadeTest` to name the contract/surface test. |
| `maintenance` | `recon` → `spec` → `spec_adversary` → `implement` (+ a FOCUSED test) → `review` | Lanes **ADD** behavior and tests. Not behavior-preserving, so there is no surface-diff invariant. The spec-adversary is the key quality gate for prod-affecting work. |
| `codemod` | `recon` → `spec` → `spec_adversary` → `codemod-implement` → `review` | Behavior 100% unchanged, NO new behavior, NO new test. The reviewer's durable gate is that the target bulk-suppression file **shrank** via fix-then-`eslint --prune-suppressions` — never a bare deletion, never merely lint exit 0. |
| `content` | `research` → `draft` → `fact_check` gate → `red_team` gate | In-app content authored as a **real committed diff**. Both gates BLOCK. Every factual claim must trace to the pre-placed source material or a web-verified source. |
| `standard` | `recon` → `spec` → `behavioral` → `spec_adversary` → `acceptance_test` → pre-flight RED → `test_adversary` → **SEAL** → `implement` → `acceptance_run` → `review` | NEW, sealable behavior gated by an **immutable, sha256-hashed** acceptance test. The implementer must make the sealed test pass and must not modify it; an apparent test defect is a BLOCKED report, never a silent edit. |

### Phase 0 recon (`maintenance`, `codemod`, `standard`)

Every planning mode opens with a read-only **recon** dispatch per lane, mirroring the single-issue
pipelines' `existing_symbols_inventory`. It inventories what the area of change *already contains* —
real signatures with `file:line`, the seal surface, and the open questions the spec must resolve —
before any approach has been chosen.

Its findings are rendered into **both** the spec **and** the spec-adversary. That second consumer is
the point: the adversary is then the one phase holding the plan *and* the evidence it was built on,
so it can catch "the plan asserts X, but the recon found Y" — a class of defect it cannot see when
it only has the plan.

The single most valuable thing a recon reports is that something **already exists**: a guard, a
column, or an issue item a previous change already delivered. Rebuilding one of those is a real
defect, not a harmless duplicate.

`refactor` has no recon (it goes straight to implement) and `content` has its own `research`
front-end instead.

The recon returns structured output rather than writing a file. The wave has no artifact convention
— only worktree-isolated implement agents write anything — and the harness already persists every
agent's return value to the run's `journal.jsonl`, so the findings are durable and inspectable
without dirtying the consumer's working tree.

### Mode selection is an exact string match

`mode` is matched exactly against `"maintenance"`, `"codemod"`, `"content"`, `"standard"`. **Any
other value — an omitted `mode`, or a typo like `"maintenence"` — resolves to `refactor`.** There is
no error on an unrecognised mode, so check the startup log line, which names the resolved mode and
its flow, before letting a wave run.

### What each mode's revise rounds cost

`maintenance`, `codemod`, and `standard` give their spec-adversary **exactly one** bounded revise
round; `standard` gives its test-adversary one as well. If a gate is still `REQUEST_CHANGES` after
that round, the wave logs it and proceeds **on the once-revised plan** rather than looping —
findings still unresolved at that point are not carried into implement. `content`'s two gates each
get **one** bounded re-draft, and a gate still
un-approved after it **blocks** the lane — the branch is pushed but not merge-ready.

## Launching a wave

```
Workflow({ name: "orchemist-wave", args: { … } })
```

### Top-level `args`

| arg | default | what it does |
|---|---|---|
| `mode` | `"refactor"` | the per-lane phase sequence (see above) |
| `repo` | `"(repo unset)"` | the repo slug, interpolated into every prompt |
| `base` | `"main"` | the branch every lane forks from and diffs against |
| `suiteCmd` | per-mode | the per-lane suite/gate command every lane must get green before pushing |
| `expectedSuite` | `"(unspecified — match the pre-wave green baseline)"` | the expected suite result, so a lane can detect a drop in collected count |
| `facadeTest` | `""` | **`refactor` only** — the contract/surface test that must stay green |
| `invariant` | per-mode | overrides the mode's default non-negotiable invariant text |
| `tiering_profile` | `"default"` | `"default" \| "budget-first" \| "quality-first"` — see [`tiering-profiles.md`](tiering-profiles.md) |
| `lanes` | `[]` | the lane array; empty ⇒ the wave is a no-op and returns `{ ready: false, note: "no lanes provided" }` |

`args` may arrive as a plain object or as a JSON **string** — both are tolerated, and a string that
fails to parse degrades to the empty-lanes no-op rather than throwing.

### The lane object

| field | required | what it is |
|---|---|---|
| `id` | **yes** | unique within the wave. Used in every dispatch label, in the output records, and in the `/tmp/orchemist-wave-*/…` handoff paths — a collision corrupts them. |
| `issue` | **yes** | the issue number. Goes into every prompt and every output record. `maintenance`, `codemod`, and `content` additionally mandate it as a `Refs #N` commit trailer; `refactor` and `standard` leave the commit message to the implementer. |
| `branch` | **yes** | the branch this lane creates and pushes. |
| `implement` | **yes** | the lane-specific change. In `content` mode, the content brief for the module. |
| `files` | recommended | the exact files this lane may edit. Omit it and the prompt falls back to "infer from the change" — which weakens the file-disjointness guarantee the whole wave rests on. |
| `reviewFocus` | optional | what the spec-adversary, reviewer, or content gates must scrutinize. |
| `suppressionFile` | **`codemod`: effectively required** | the bulk-suppression baseline this lane must shrink. Without it the reviewer's count-gate is disarmed. |
| `residual` | `codemod`, optional | pre-declared protected suppression entries that may remain, each with a one-line load-bearing rationale. `"none"` or empty ⇒ drive the file to zero (or delete it). |
| `sourceFile` | **`content`: REQUIRED** | absolute host path to the operator-refined `source_material.md`. `research`, `draft`, and `fact_check` all read it. |
| `content_type` | `content`, optional | `"page" \| "glossary-term" \| "video-entry"` — informational. |

### Example

```json
{
  "mode": "maintenance",
  "repo": "ToscanAI/orchemist",
  "base": "main",
  "suiteCmd": "PYTHONPATH=src python3 -m pytest -q",
  "expectedSuite": "7946 passed / 0 failed",
  "lanes": [
    {
      "id": "1034",
      "issue": 1034,
      "branch": "fix/1034-daemon-decomp",
      "files": "src/orchestration_engine/daemon/**",
      "implement": "Decompose daemon.py into a package; keep the facade re-exports exact.",
      "reviewFocus": "dir() surface-diff drops nothing; facade late-binding for patched module-globals."
    }
  ]
}
```

## Lane isolation and concurrency

Lanes run in **per-lane lockstep with no barrier**: each lane advances through its own sequence and
reviews as soon as its own implement finishes. Lane B never waits on lane A's implementer.

Every dispatch that **writes to the working tree** runs with its own git worktree — the implement
and draft dispatches in all modes, `content`'s re-drafts, and `standard`'s pre-flight, SEAL, and
acceptance-run. Concurrent lanes therefore never collide on the git index, and each pushed branch
survives its worktree's cleanup.

The read-only dispatches — spec, behavioral, acceptance-test, every adversary, every review and
content gate — run **without** a worktree. What they read differs by where they sit in the lane:

- **The planning dispatches** (spec, behavioral, spec-adversary) run *before* the lane's branch
  exists — it is first created by the implement dispatch, or by SEAL in `standard` mode — so they
  are plain read-only recon of the base tree plus the text handed forward to them.
- **The pure-text gates** (acceptance-test, test-adversary, and `content`'s red-team) have no Bash
  and no git at all. They reason from files on disk and the artifacts passed into the prompt.
- **The post-push gates** (every mode's review, and `content`'s fact-check) inspect the *pushed
  branch*, via `git fetch origin` and `git diff <base>...origin/<branch>`. This is deliberate:
  **verify, don't trust.** The reviewer independently reconstructs the parent surface and diffs it
  rather than believing the implementer's self-report.

Two modes stage a file outside the worktree so a Bash-less agent can read it: `content`'s draft
captures its diff to `/tmp/orchemist-wave-content/<lane.id>.diff` for the `red_team` gate, and
`standard`'s acceptance test is authored under `/tmp/orchemist-wave-standard/<lane.id>` before any
branch exists.

## What the wave returns

```json
{
  "ready": true,
  "mode": "maintenance",
  "approved_branches": [
    { "lane": "1034", "issue": 1034, "branch": "fix/1034-daemon-decomp", "sha": "…" }
  ],
  "lanes": [
    {
      "lane": "1034", "issue": 1034, "branch": "fix/1034-daemon-decomp",
      "pushed": true, "pushed_sha": "…", "suite": "…",
      "verdict": "APPROVE", "blockers": [], "majors": [],
      "surface_diff_clean": true, "review_notes": "…"
    }
  ],
  "next_step": "…the operator merge-wave recipe, or the blockers to fix…"
}
```

`ready` is true **only** when every lane returned `APPROVE`. Three verdicts reach the caller:

| verdict | meaning |
|---|---|
| `APPROVE` | reviewed, pushed, merge-ready |
| `REQUEST_CHANGES` | the reviewer or a content gate found blockers. The branch may be pushed, but the lane is not merge-ready. |
| `BLOCKED_IMPLEMENT` | the lane was **blocked before review** — implement blocked, SEAL blocked, or `acceptance_run` reported a seal break or failures. The record always reports `pushed: false`, but that means "not accepted as pushed", not "nothing reached origin": in `standard` mode SEAL performs the branch's first push before implement even runs, so a stale branch may already sit on origin. Check the record's `pushed_sha` — it is populated whenever the implementer got that far — and clean up before re-running the lane. |

## It deliberately does NOT merge

Toggling branch protection, squash-merging to a shared default branch, and running the post-merge
composition suite are outward-facing and easy to get subtly wrong. They stay a deliberate operator
step. The wave emits the recipe in `next_step`:

1. **Open a PR per approved branch** with `Closes #<issue>` — with the **umbrella guard**: when 2+
   lanes share one issue number (an umbrella split into sub-lanes), only the FINAL merged lane may
   carry the closing keyword. Non-final PRs use a `fix(#N):` subject and keep their bodies free of
   any closing keyword. If the umbrella is still open once all sub-lanes are merged, close it.
2. **ONE combined CI poll** across all PR head SHAs.
3. **Squash-merge all PRs.** File-disjoint lanes do not conflict. If branch protection blocks
   auto-merge, toggle the ruleset with a **full-body PUT** — a partial `-f enforcement=disabled`
   returns HTTP 422 — and restore it via a trap.
4. **Run ONE composition suite on the merged tree.** Each PR's CI validated its **own** base, not
   the merged union, so this is the only check that covers the merged result.

If any lane is blocked, `next_step` lists the blockers instead: address them and re-run the affected
lanes. Do **not** merge a partial wave that leaves the tree red.

## Effort tiering

`tiering_profile` selects a per-phase effort ladder. The Workflow path is the **only** path that can
pass per-dispatch effort — the single-issue `Agent` path has no effort parameter — so this is where
tiering profiles have their full effect. The `default` profile passes no effort at all, leaving
every dispatch identical to an untiered wave. Dispatch **models** always stay the mode's ladder,
which already pins every gate to Fable 5. See [`tiering-profiles.md`](tiering-profiles.md).
