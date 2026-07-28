# Orchemist Workflows

Deterministic multi-agent orchestrators (for the Claude Code `Workflow` tool), installed to `~/.claude/workflows/`. Where a **pipeline** (`pipelines/*.yaml`, driven by `/orchemist:run`) takes **one issue** through its phases, a **workflow** sits one layer up and coordinates **many lanes in parallel**.

## `orchemist-wave.js` — parallel wave orchestrator

> **Full reference: [`../docs/orchemist-wave.md`](../docs/orchemist-wave.md)** — all five modes,
> the complete lane object, every argument, the output schema, and the operator merge recipe. This
> page is the short version.

Fans **N independent, file-disjoint lanes** through a per-lane phase sequence, in **per-lane lockstep** (each lane reviews as soon as its own implement finishes — no barrier). Five modes select the sequence: `refactor` (default — `implement → review`), `maintenance` and `codemod` (`spec → spec-adversary → implement → review`), `content` (`research → draft → fact-check gate → red-team gate`), and `standard` (the full sealed-acceptance flow). Implement and draft dispatches run on **opus**; every adversary and review gate runs on **Fable 5**. It hands back reviewed, pushed branches plus a go/no-go verdict per lane.

It deliberately **does not merge**. The merge-coordination — toggling branch protection, squash-merging to the shared default branch, and the post-merge composition full-suite — is outward-facing and easy to get subtly wrong, so it stays a deliberate operator step (described in the workflow's `next_step` output).

### When to use
Several behavior-preserving, machine-checkable, **file-disjoint** lanes ready at once — a god-module decomposition wave, a mechanical codemod across modules, a batch of independent maintenance fixes. Each lane needs an immutable, reviewer-checkable contract (a surface/contract test + the full suite).

> **Rule of thumb:** serialize lanes **within** one module (they edit the same files → conflicts); parallelize **across** modules (disjoint dirs compose cleanly). The wall-clock is the slowest single lane, not the sum.

### Run it
```
Workflow({ name: "orchemist-wave", args: { …see below… } })
```

`args` shape:
```json
{
  "repo": "ToscanAI/orchemist",
  "base": "main",
  "suiteCmd": "PYTHONPATH=src python3 -m pytest -q",
  "expectedSuite": "7928 passed / 0 failed / 8 skipped",
  "facadeTest": "tests/test_facade_surface_942.py",
  "invariant": "facade re-exports preserve the exact public surface; behavior 100% unchanged; do NOT modify tests/",
  "lanes": [
    {
      "id": "950e",
      "issue": 1005,
      "branch": "fix/950e-cli-serve-eval",
      "implement": "Extract serve/ui/api-server/mcp → cli/serve_cmds.py (keep create_api_app lazy) and rubric/scenario/reviews → cli/eval_cmds.py; thin __init__.py to a facade.",
      "reviewFocus": "cli --help tree byte-identical; _cli. late-binding for any patched module-globals; dir() surface-diff drops nothing."
    },
    {
      "id": "951e",
      "issue": 1014,
      "branch": "fix/951e-db-reviews-cal-trust-audit",
      "implement": "Extract reviews/calibration/trust/audit (+ orchestra/diagnosis/routing/failure-pattern) into mixins so `class Database(...): pass`.",
      "reviewFocus": "dir(Database) byte-identical; monkeypatch targets MRO-safe; Database body empty."
    }
  ]
}
```

### Output
```json
{
  "ready": true,
  "mode": "refactor",
  "approved_branches": [{ "lane": "950e", "issue": 1005, "branch": "...", "sha": "..." }],
  "lanes": [{ "lane": "...", "verdict": "APPROVE|REQUEST_CHANGES", "blockers": [], "suite": "..." }],
  "next_step": "…the operator merge-wave recipe, or the blockers to fix…"
}
```

### Design notes
- **`pipeline()` not `parallel()`** — per-lane lockstep, no barrier; lane B never waits on lane A's implementer.
- **`isolation: 'worktree'`** on every dispatch that writes to the tree (implement/draft, plus `standard`'s pre-flight, SEAL, and acceptance-run) — concurrent lanes never collide on the git index, and the pushed branch survives worktree cleanup. Read-only planning and gate dispatches run without a worktree and inspect the pushed branch via `git fetch` + `git diff`.
- **Verify, don't trust** — the reviewer independently reconstructs the parent surface and diffs it. (A dropped re-export can pass *both* the contract test and the full suite; only an explicit surface-diff catches it.)
- **Composition gate is mandatory** — each PR's CI validated its *own* base, not the merged union, so the operator runs one full-suite on the merged tree after all merges.
