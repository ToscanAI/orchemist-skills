"""orchemist-wave Phase 0 recon — structural test (issue #58).

The single-issue pipelines open with `existing_symbols_inventory`; the wave did not,
folding grounding into one clause of the spec prompt ("Recon the area-of-change, then
plan"). That made it an instruction rather than a phase, with three costs:

  * no separately inspectable output;
  * no fresh-context separation between surveying and planning;
  * and the load-bearing one — the spec_adversary could only check the plan against its
    OWN reading of the code, never against the evidence the plan was actually built on.

These are pure text-assertions over `workflows/orchemist-wave.js`, the same approach as
`tests/test_wave_content_mode.py` / `test_wave_standard_mode.py` /
`test_wave_prompt_dispatch_invariants.py`, whose `_fn_body` / `_label_segment` helpers
this file reuses verbatim.

Deliberately NOT asserted: that the recon writes a file. The wave has no artifact
convention — only worktree-isolated implement agents write anything, and the harness
already persists every agent's structured return to the run's journal.jsonl. Requiring a
file would dirty the consumer's working tree for no gain in durability.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
JS = (REPO_ROOT / "workflows" / "orchemist-wave.js").read_text(encoding="utf-8")

# The three modes that PLAN before implementing. `refactor` goes straight to implement and
# `content` has its own research front-end, so neither takes a recon.
PLANNING_MODES = ("maintenance", "codemod", "standard")


def _fn_body(name: str) -> str:
    """Rough body of a top-level `function name(...) { ... }` (brace-balanced)."""
    m = re.search(rf"function {re.escape(name)}\(", JS)
    assert m, f"{name} not found"
    i = JS.index("{", m.end())
    depth, j = 0, i
    while j < len(JS):
        if JS[j] == "{":
            depth += 1
        elif JS[j] == "}":
            depth -= 1
            if depth == 0:
                return JS[i : j + 1]
        j += 1
    raise AssertionError(f"unbalanced braces in {name}")


def _recon_dispatches() -> list[str]:
    """Every `agent(reconPrompt(lane), {...})` dispatch, opts included."""
    out, idx = [], 0
    while True:
        k = JS.find("agent(reconPrompt(lane)", idx)
        if k == -1:
            break
        out.append(JS[k : k + 320])
        idx = k + 1
    return out


# ── the phase exists, and in exactly the right modes ──────────────────────
def test_recon_prompt_and_schema_exist():
    assert "function reconPrompt(" in JS
    assert "RECON_SCHEMA" in JS
    # reconBlock is what renders the findings into the downstream prompts.
    assert "function reconBlock(" in JS


def test_recon_dispatched_once_per_planning_mode():
    """One dispatch per planning mode — maintenance, codemod, standard."""
    assert len(_recon_dispatches()) == len(PLANNING_MODES), (
        f"expected {len(PLANNING_MODES)} reconPrompt dispatches "
        f"(one per planning mode), found {len(_recon_dispatches())}"
    )


def test_recon_uses_general_purpose_and_the_recon_schema():
    """`general-purpose` is required, not a read-only subagent type.

    The single-issue pack documents this (skills/orchemist-existing-symbols-inventory.md,
    ToscanAI/orchemist-skills#9): a read-only type such as Explore has no Write tool and
    silently breaks the phase's output contract.
    """
    dispatches = _recon_dispatches()
    # Non-vacuity: with zero dispatches the loop below would pass trivially, so this test
    # would go green on a wave that has no recon phase at all.
    assert dispatches, "no reconPrompt dispatches — nothing to check"
    for d in dispatches:
        assert "agentType: 'general-purpose'" in d, d
        assert "schema: RECON_SCHEMA" in d, d
        assert "phase: 'Recon'" in d, d


def test_recon_declares_no_worktree_isolation():
    """Recon is read-only; a worktree would be cost without purpose."""
    dispatches = _recon_dispatches()
    assert dispatches, "no reconPrompt dispatches — nothing to check"  # non-vacuity
    for d in dispatches:
        assert "isolation:" not in d, f"recon should not need a worktree: {d}"


# ── ordering: recon must precede the spec it feeds ────────────────────────
@pytest.mark.parametrize(
    "spec_fn", ["specPrompt", "standardSpecPrompt"]
)
def test_recon_precedes_the_spec_it_feeds(spec_fn):
    """A recon dispatched after its spec would be inert.

    Matches the DISPATCH (`agent(specPrompt(lane, recon)`), not the bare call text — the
    function *definition* also reads `specPrompt(lane, recon)` and necessarily precedes
    every dispatch, so a looser match would compare against the wrong occurrence.
    """
    call = f"agent({spec_fn}(lane, recon)"
    assert call in JS, f"{spec_fn} is not dispatched with a recon"
    idx = 0
    while True:
        k = JS.find(call, idx)
        if k == -1:
            break
        assert JS.rfind("agent(reconPrompt(lane)", 0, k) != -1, (
            f"{call} at offset {k} has no preceding recon dispatch"
        )
        idx = k + 1


# ── the payoff: BOTH the spec and the adversary see the evidence ──────────
@pytest.mark.parametrize(
    "fn",
    ["specPrompt", "standardSpecPrompt", "specRevisePrompt", "standardSpecRevisePrompt"],
)
def test_spec_family_renders_the_recon(fn):
    assert "reconBlock(recon)" in _fn_body(fn), f"{fn} does not render the recon"


@pytest.mark.parametrize(
    "fn", ["specAdversaryPrompt", "standardSpecAdversaryPrompt"]
)
def test_adversary_receives_the_recon(fn):
    """#58's highest-value change.

    Without the recon the adversary can only check the plan against its own reading. With
    it, the adversary is the one phase holding BOTH the plan and the evidence it was built
    on, and can catch "the plan asserts X, but the recon found Y".
    """
    body = _fn_body(fn)
    assert "reconBlock(recon)" in body, f"{fn} does not render the recon"
    assert re.search(r"PLAN vs EVIDENCE", body), (
        f"{fn} renders the recon but never asks the adversary to check the plan against it"
    )
    # and the signature must actually accept it
    assert re.search(rf"function {fn}\([^)]*\brecon\b", JS), f"{fn} does not take recon"


def test_recon_unavailable_is_stated_not_silently_empty():
    """A null recon must degrade loudly.

    `agent()` returns null when a dispatch dies; rendering an empty string there would let
    a lane plan blind while LOOKING grounded.
    """
    body = _fn_body("reconBlock")
    assert "unavailable" in body.lower(), body


# ── the superseded inline clause is gone ──────────────────────────────────
def test_inline_recon_clause_removed_from_spec_prompts():
    """The spec prompts must not still tell the agent to do its own recon."""
    for fn in ("specPrompt", "standardSpecPrompt"):
        assert "Recon the area-of-change" not in _fn_body(fn), (
            f"{fn} still carries the pre-#58 inline recon clause"
        )


# ── the wave must not misdescribe itself (the #55 invariant, extended) ────
def test_meta_phases_lists_recon():
    m = re.search(r"phases:\s*\[(.*?)\n\s*\],", JS, re.S)
    assert m, "meta.phases not found"
    assert "title: 'Recon'" in m.group(1)


def _banner_line() -> str:
    """The single `log(...)` statement that announces each mode's flow at run start.

    Selected by its own text rather than by pattern-matching ternaries: several unrelated
    ternaries branch on `mode === '<mode>'`, and at least one prompt string legitimately
    contains an arrow ("count N → residual"), so neither the first match nor an
    arrow-filter is a safe selector.
    """
    k = JS.find("log(`orchemist-wave [${mode}]")
    assert k != -1, "run-start banner log() not found"
    end = JS.index("\n", k)
    return JS[k:end]


@pytest.mark.parametrize("mode", PLANNING_MODES)
def test_runtime_banner_announces_recon(mode):
    """The per-run log line names each mode's flow; it must include the new phase."""
    banner = _banner_line()
    m = re.search(rf"mode === '{mode}' \? '([^']*)'", banner)
    assert m, f"no {mode} branch in the run-start banner: {banner!r}"
    assert m.group(1).startswith("recon"), (
        f"{mode} banner still describes a flow without recon: {m.group(1)!r}"
    )
