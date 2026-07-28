"""orchemist-wave prompt/dispatch truthfulness invariants (issue #55).

Pure text-assertions over `workflows/orchemist-wave.js` — the same approach as
`tests/test_wave_content_mode.py` and `tests/test_wave_standard_mode.py`, whose
`_fn_body` helper this file reuses verbatim.

Two invariants, both of the genre "the wave must not describe its own behaviour
inaccurately":

  A. ISOLATION-CLAIM INVARIANT (general, not a hardcoded line check) — no prompt
     body may claim worktree isolation unless EVERY `agent()` dispatch of that
     prompt declares `isolation: 'worktree'`. Discovery is by regex over every
     `function *Prompt(` in the wave, so a FUTURE prompt/dispatch mismatch is
     caught without touching this file.

  B. REVISE-ROUND LOG INVARIANT — the bounded-revise log lines must not claim the
     adversary's findings reach the downstream dispatch; mechanically only the
     revised artifact is forwarded.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
WAVE_JS = REPO_ROOT / "workflows" / "orchemist-wave.js"
JS = WAVE_JS.read_text()

# every prompt-builder in the wave is a top-level `function <name>Prompt(...)`
_PROMPT_FN_RE = re.compile(r"^function (\w+Prompt)\(", re.M)
# a mention of "worktree" is a DENIAL, not a claim, when the clause that precedes
# it on the same line negates it ("no worktree", "not this worktree", "outside
# the worktree", "without a worktree").
_NEGATOR_RE = re.compile(r"\b(?:no|not|without|outside)\b", re.I)

PROMPT_FNS = sorted(set(_PROMPT_FN_RE.findall(JS)))


def _fn_body(name: str) -> str:
    """Rough body of a top-level `function name(...) { ... }` (brace-balanced).

    Verbatim from tests/test_wave_content_mode.py.
    """
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
                return JS[i: j + 1]
        j += 1
    return JS[i:]


def _worktree_claims(body: str) -> list[str]:
    """Every ASSERTION in `body` that the agent has a worktree of its own.

    Each mention of "worktree" counts as a claim unless the clause preceding it on
    the same line negates it. Deliberately strict: a prompt that merely mentions a
    worktree it does not have is itself the defect class this test exists to catch,
    and the escape hatch is a one-word negation.
    """
    claims = []
    for m in re.finditer(r"worktree", body, re.I):
        line_start = body.rfind("\n", 0, m.start()) + 1
        clause = re.split(r"[.;—(]", body[line_start:m.start()])[-1]
        if _NEGATOR_RE.search(clause):
            continue
        claims.append(body[line_start:m.end()].strip())
    return claims


def _dispatch_lines(prompt_fn: str) -> list[str]:
    """Every FULL source line that dispatches this prompt fn.

    Per-line (not a fixed-width window) so a multi-dispatch prompt is checked at
    EACH site and no neighbouring dispatch's options can bleed in — the
    `test_sm44_*` lesson from tests/test_wave_standard_mode.py.
    """
    needle = f"agent({prompt_fn}(lane"
    return [ln for ln in JS.splitlines() if needle in ln]


# ── A. isolation-claim invariant ──────────────────────────────────────────────

def test_prompt_helpers_discovered():
    """Anti-vacuity: the discovery regex actually finds the wave's prompt builders."""
    assert len(PROMPT_FNS) >= 20, PROMPT_FNS
    for known in ("refactorReviewPrompt", "maintImplementPrompt", "standardSealPrompt"):
        assert known in PROMPT_FNS, PROMPT_FNS


def test_every_prompt_helper_is_dispatched():
    """Anti-escape: a prompt with no discoverable dispatch would pass the invariant
    vacuously, so require every prompt builder to have at least one `agent()` site."""
    for fn in PROMPT_FNS:
        assert _dispatch_lines(fn), f"{fn} is never dispatched via agent({fn}(lane…)"


def test_claim_detector_is_not_vacuous():
    """Anti-vacuity: the detector must SEE a claim where one exists and must NOT
    fire on a prompt that denies or never mentions a worktree."""
    assert _worktree_claims(_fn_body("maintImplementPrompt")), "detector missed a real claim"
    assert not _worktree_claims(_fn_body("standardReviewPrompt"))
    assert not _worktree_claims(_fn_body("contentResearchPrompt")), "negated mention misread as a claim"
    assert not _worktree_claims(_fn_body("standardSpecPrompt")), "negated mention misread as a claim"


@pytest.mark.parametrize("fn", PROMPT_FNS)
def test_worktree_claim_requires_declared_isolation(fn):
    """THE INVARIANT: no prompt body may claim worktree isolation for a dispatch
    that does not declare `isolation: 'worktree'`."""
    claims = _worktree_claims(_fn_body(fn))
    if not claims:
        return
    for line in _dispatch_lines(fn):
        assert "isolation: 'worktree'" in line, (
            f"{fn} claims worktree isolation but this dispatch declares none.\n"
            f"  claim:    {claims[0]}\n"
            f"  dispatch: {line.strip()}"
        )


def test_refactor_review_inspects_the_pushed_branch_read_only():
    """#55 regression pin: the refactor reviewer is told it has NO worktree and
    inspects the pushed branch the way its four sibling gates do."""
    body = _fn_body("refactorReviewPrompt")
    assert "You are in your own worktree." not in body
    assert "git fetch origin" in body
    assert "git diff ${base}...origin/${lane.branch}" in body


@pytest.mark.parametrize(
    "fn",
    ["refactorReviewPrompt", "maintReviewPrompt", "codemodReviewPrompt",
     "standardReviewPrompt", "contentFactCheckPrompt"],
)
def test_post_push_gates_are_consistent(fn):
    """All five post-push gates inspect origin without a worktree — same shape."""
    body = _fn_body(fn)
    assert "git fetch origin" in body, fn
    assert "git diff ${base}...origin/${lane.branch}" in body, fn
    for line in _dispatch_lines(fn):
        assert "isolation:" not in line, f"{fn}: post-push gate should not need a worktree: {line.strip()}"


# ── B. revise-round log invariant ─────────────────────────────────────────────

def test_no_log_claims_the_findings_were_folded_in():
    """The bounded-revise log lines must not tell an operator the adversary's
    unresolved findings reached the downstream dispatch — they are dropped."""
    assert "folded in" not in JS


@pytest.mark.parametrize(
    "marker,count",
    [
        ("implement proceeds on the spec plan alone — the unresolved findings are NOT forwarded.", 2),
        ("acceptance_test proceeds on the behavioral contracts alone — the unresolved findings are NOT forwarded.", 1),
        ("SEAL proceeds on the sealed test as it stands — the unresolved findings are NOT forwarded.", 1),
    ],
)
def test_revise_log_lines_state_what_the_dispatch_receives(marker, count):
    """All FOUR bounded-revise log lines (maintenance, codemod, and standard's two)
    say what the next dispatch actually receives."""
    assert JS.count(marker) == count, f"{marker!r} appears {JS.count(marker)}x, expected {count}x"
