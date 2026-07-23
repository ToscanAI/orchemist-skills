"""orchemist-wave content-mode structural test (pack — content wave).

Pure text-assertions over workflows/orchemist-wave.js (same approach as
tests/test_tiering_profiles.py::test_wave_effort_map_in_sync, which reads the wave JS as
text). No node runtime required for the assertions; an OPTIONAL `node --check` syntax gate
runs when node is on PATH, else it skips.

Locks the content mode's shape — the fourth wave mode that runs the content pipeline per
lane (research → draft(real diff) → fact_check(fable gate) → red_team(fable gate), each gate
with one bounded re-draft), so a wrong fact / off-brand claim blocks the lane instead of
shipping. The two load-bearing invariants versus the coding modes:
  - fact_check dispatches general-purpose + fable (it needs web + git);
  - red_team dispatches orchemist-adversary + fable and reads a PRE-CAPTURED diff
    (the read-only adversary has no Bash/git).
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
WAVE_JS = REPO_ROOT / "workflows" / "orchemist-wave.js"
JS = WAVE_JS.read_text()


def test_wave_js_exists():
    assert WAVE_JS.is_file(), WAVE_JS


def test_content_is_a_recognized_mode():
    # mode parse must recognize 'content' (else it silently degrades to refactor)
    assert "A.mode === 'content' ? 'content'" in JS


def test_content_pipeline_branch_present():
    assert "} else if (mode === 'content') {" in JS


@pytest.mark.parametrize(
    "fn",
    [
        "contentResearchPrompt",
        "contentDraftPrompt",
        "contentFactCheckPrompt",
        "contentRedTeamPrompt",
        "contentRedraftPrompt",
        "contentBlocked",
    ],
)
def test_content_helpers_defined_and_called(fn):
    # each helper is both DEFINED (`function fn(` or `const fn =`) and referenced elsewhere
    defined = f"function {fn}(" in JS or f"const {fn} =" in JS
    assert defined, f"{fn} not defined"
    assert JS.count(fn) >= 2, f"{fn} defined but never called"


def test_fact_check_is_a_general_purpose_fable_gate():
    # fact_check needs web + git → general-purpose + fable
    seg = _dispatch_segment("contentFactCheckPrompt")
    assert "agentType: 'general-purpose'" in seg, seg
    assert "model: 'fable'" in seg, seg
    assert "phase: 'Fact-check'" in seg, seg


def test_red_team_is_a_bashless_adversary_fable_gate():
    # red_team is a pure textual audit → orchemist-adversary (Read/Grep/Glob) + fable
    seg = _dispatch_segment("contentRedTeamPrompt")
    assert "agentType: 'orchemist-adversary'" in seg, seg
    assert "model: 'fable'" in seg, seg
    assert "phase: 'Red-team'" in seg, seg


def test_red_team_reads_a_precaptured_diff():
    # the Bash-less adversary cannot `git diff` — it must be handed a captured diff file
    assert "contentDiffPath" in JS
    body = _fn_body("contentRedTeamPrompt")
    assert "diff_path" in body or "contentDiffPath" in body, body


def test_draft_captures_the_diff_and_pushes():
    body = _fn_body("contentDraftPrompt")
    assert "git diff origin/${base}...HEAD > ${contentDiffPath(lane)}" in body
    assert "git push -u origin ${lane.branch}" in body


def test_draft_and_redraft_use_worktree_isolation():
    # both the draft and every re-draft must be sealed in their own worktree
    for label in ("draft:", "redraft-fc:", "redraft-rt:"):
        seg = _label_segment(label)
        assert "isolation: 'worktree'" in seg, f"{label} not worktree-isolated: {seg}"
        assert "model: 'opus'" in seg, f"{label} not opus: {seg}"


def test_each_gate_has_one_bounded_redraft():
    # exactly one re-draft per gate (fact-check + red-team), then block — not an unbounded loop
    assert "redraft-fc:" in JS
    assert "redraft-rt:" in JS
    # the gate re-runs after a successful re-draft
    assert "fact-check2:" in JS
    assert "red-team2:" in JS


def test_blocked_gate_yields_request_changes_not_merge_ready():
    body = _fn_body("contentBlocked")
    assert "verdict: 'REQUEST_CHANGES'" in body, body


def test_content_invariant_and_suitecmd_defaults():
    # content gets its own invariant (source-grounded, anti-brand, no-fabrication) + suite default
    assert "mode === 'content'" in JS
    assert "education-not-advice" in JS  # the options risk-framing clause in the invariant
    assert "no fabrication" in JS  # the anti-fabricated-video clause
    assert "typecheck + lint + focused unit-test gate" in JS  # content suiteCmd default


def test_source_material_handoff_documented_and_used():
    assert "lane.sourceFile" in JS  # the pre-placed source_material.md handoff
    # research + draft + both gates all reference the source file
    for fn in ("contentResearchPrompt", "contentDraftPrompt", "contentFactCheckPrompt"):
        assert "sourceFile" in _fn_body(fn), fn


def test_node_syntax_check_if_available():
    node = shutil.which("node")
    if not node:
        pytest.skip("node not on PATH — syntax gate skipped (text-assertions still cover shape)")
    r = subprocess.run([node, "--check", str(WAVE_JS)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ── helpers ───────────────────────────────────────────────────────────────────
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
    return JS[i:]


def _dispatch_segment(prompt_fn: str) -> str:
    """The agent() dispatch line(s) that pass this prompt fn (opts follow the prompt arg)."""
    idx = 0
    hits = []
    while True:
        k = JS.find(f"agent({prompt_fn}(lane", idx)
        if k == -1:
            break
        hits.append(JS[k : k + 320])
        idx = k + 1
    assert hits, f"no agent() dispatch of {prompt_fn}"
    return "\n".join(hits)


def _label_segment(label: str) -> str:
    k = JS.find(f"label: `{label}")
    assert k != -1, f"label {label} not found"
    # widen to the enclosing agent() opts object
    start = JS.rfind("agent(", max(0, k - 400), k)
    return JS[start : k + 300]
