"""orchemist-wave `standard` (sealed-acceptance) mode — structural/behavioral test.

SEALED test for issue #47 (ToscanAI/orchemist-skills): `workflows/orchemist-wave.js`
gains a fifth wave mode, `standard`, that runs the FULL sealed-acceptance flow per
lane: spec -> behavioral -> spec_adversary(fable) -> acceptance_test(orchemist-tester)
-> [pre-flight: run the sealed test, expect RED] -> test_adversary(fable) ->
SEAL(hash + commit the sealed test) -> implement(against the immutable seal) ->
acceptance_run(re-hash the seal) -> review(fable). Lane invariant = NEW behavior +
IMMUTABLE sealed tests (NOT behavior-preserving / NOT a surface-diff-facade bar).

Pure text-assertions over `workflows/orchemist-wave.js` (same approach as
`tests/test_wave_content_mode.py`, which this file mirrors verbatim for its shared
helpers: `_fn_body`, `_dispatch_segment`, `_label_segment`). No node runtime is
REQUIRED for any assertion in this file; the OPTIONAL `node --check` syntax gate
(`test_sm40_node_syntax_check_if_available`) skips gracefully when node is absent.

Written PRE-IMPLEMENTATION, against behavioral.md contracts SM-1..SM-46 only — no
implementation has been read. As of HEAD (no `standard` mode exists yet), nearly
every test below is expected to FAIL (red) — that is the point of a sealed
acceptance suite: it is the immutable, hashed contract the `standard`-mode
implementer must subsequently satisfy. The exceptions are the small number of
"shield" tests that assert something already true today and that must REMAIN true
once `standard` mode is added (see acceptance_test.md's expected-today ledger for
the full PASS-now/FAIL-now breakdown and the reachability reasoning behind each).
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

# ── REPO_ROOT resolution ───────────────────────────────────────────────────────
# Mirrors tests/test_wave_content_mode.py's `REPO_ROOT = Path(__file__).resolve().parent.parent`
# idiom so this file resolves correctly once it is copied to `tests/test_wave_standard_mode.py`
# (one level under the repo root). A second, explicit-constant candidate (NOT a /tmp path — the
# actual repo checkout) is tried first-match so the suite is ALSO directly runnable from its
# pre-seal staging location during the acceptance_test phase itself.
_HERE = Path(__file__).resolve()
_REPO_ROOT_CANDIDATES = [
    _HERE.parent.parent,  # <repo>/tests/<this file>.py  (the eventual sealed home)
    Path("/home/toscan/ToscanWorkspace/orchemist-skills"),  # known checkout root (pre-seal staging)
]
REPO_ROOT = next(
    (p for p in _REPO_ROOT_CANDIDATES if (p / "workflows" / "orchemist-wave.js").is_file()),
    _REPO_ROOT_CANDIDATES[0],
)
WAVE_JS = REPO_ROOT / "workflows" / "orchemist-wave.js"
JS = WAVE_JS.read_text()


def test_wave_js_exists():
    """Sanity shield: the file under test exists today (pre-implementation)."""
    assert WAVE_JS.is_file(), WAVE_JS


# ══════════════════════════════════════════════════════════════════════════════
# Group 1 — Mode registration / allow-list (SM-1 .. SM-10)
# ══════════════════════════════════════════════════════════════════════════════

def test_sm1_standard_is_first_class_mode_value():
    """SM-1: the mode-resolution ternary contains `A.mode === 'standard' ? 'standard'`."""
    assert "A.mode === 'standard' ? 'standard'" in JS


def test_sm2_standard_dispatcher_branch_correctly_positioned():
    """SM-2: `} else if (mode === 'standard') {` exists, strictly after the content
    branch and strictly before the file's LAST `} else {` (the refactor fallback)."""
    marker = "} else if (mode === 'standard') {"
    idx_standard = JS.find(marker)
    assert idx_standard != -1, "standard-mode dispatcher branch not found"
    idx_content = JS.find("} else if (mode === 'content') {")
    assert idx_content != -1, "content-mode dispatcher branch not found (precondition)"
    assert idx_content < idx_standard, "standard branch must come after the content branch"
    idx_last_else = JS.rfind("} else {")
    assert idx_last_else != -1, "refactor fallback `} else {` not found (precondition)"
    assert idx_standard < idx_last_else, "standard branch must come before the trailing else"


def test_sm3_suitecmd_has_standard_arm():
    """SM-3: the `suiteCmd` assignment contains a `mode === 'standard' ?` sub-expression."""
    idx = JS.find("const suiteCmd = A.suiteCmd ||")
    assert idx != -1, "suiteCmd assignment not found"
    line_end = JS.find("\n", idx)
    line = JS[idx: line_end if line_end != -1 else len(JS)]
    assert "mode === 'standard' ?" in line


def _invariant_text() -> str:
    """The `const invariant = ...` assignment's full text (through the ternary's close)."""
    idx = JS.find("const invariant =")
    assert idx != -1, "invariant assignment not found"
    end = JS.find("\n\n", idx)
    return JS[idx: end if end != -1 else len(JS)]


_STANDARD_INVARIANT_ARM_RE = re.compile(r"mode === 'standard'\s*\?\s*'((?:[^'\\]|\\.)*)'")


def test_sm4_invariant_standard_arm_names_new_and_immutable():
    """SM-4: the `invariant`'s `mode === 'standard' ?` arm's string names NEW behavior
    + immutability + the MUST-NOT-modify bar."""
    m = _STANDARD_INVARIANT_ARM_RE.search(_invariant_text())
    assert m, "no mode === 'standard' ? '...' invariant arm found"
    arm = m.group(1)
    for token in ("NEW", "immutable", "MUST NOT modify, delete, or work around"):
        assert token in arm, f"{token!r} missing from standard invariant arm"


def test_sm5_invariant_standard_arm_negates_behavior_preserving():
    """SM-5: the same arm explicitly negates the behavior-preserving/surface-diff bar."""
    m = _STANDARD_INVARIANT_ARM_RE.search(_invariant_text())
    assert m, "no mode === 'standard' ? '...' invariant arm found"
    arm = m.group(1)
    assert "NOT a behavior-preserving refactor" in arm
    assert "no surface-diff/facade" in arm


def _assert_tokens_in_order(text: str, tokens: list[str]) -> None:
    cursor = 0
    lower_text = text.lower()
    for tok in tokens:
        idx = lower_text.find(tok.lower(), cursor)
        assert idx != -1, f"token {tok!r} not found (in order) from cursor {cursor} in: {text!r}"
        cursor = idx + 1


def test_sm6_startup_log_line_lists_ten_steps_in_order():
    """SM-6: the startup log's `mode === 'standard' ?` arm names all 10 flow steps,
    case-insensitively, in strictly increasing source-order."""
    anchor = JS.find("log(`orchemist-wave [${mode}]:")
    assert anchor != -1, "startup log line not found"
    line_end = JS.find("\n", anchor)
    log_line = JS[anchor: line_end if line_end != -1 else len(JS)]
    m = _STANDARD_INVARIANT_ARM_RE.search(log_line)
    assert m, "no mode === 'standard' ? '...' arm in the startup log line"
    arm = m.group(1)
    tokens = [
        "spec", "behavioral", "spec_adversary", "acceptance_test", "pre-flight",
        "test_adversary", "SEAL", "implement", "acceptance_run", "review",
    ]
    _assert_tokens_in_order(arm, tokens)


def _meta_field_line(field_name: str) -> str:
    """The line immediately following a bare `<field_name>:` line inside `export const meta`."""
    lines = JS.splitlines()
    for i, line in enumerate(lines):
        if line.strip() == f"{field_name}:":
            assert i + 1 < len(lines), f"{field_name}: has no following value line"
            return lines[i + 1]
    raise AssertionError(f"{field_name}: field not found on its own line inside meta")


def test_sm7_meta_description_documents_standard_mode():
    """SM-7: `meta.description` contains the exact substring `mode:"standard"`."""
    assert 'mode:"standard"' in _meta_field_line("description")


def test_sm8_meta_whentouse_documents_standard_mode():
    """SM-8: `meta.whenToUse` contains the exact substring `mode:"standard"`."""
    assert 'mode:"standard"' in _meta_field_line("whenToUse")


def test_sm9_args_comment_mode_enum_lists_standard():
    """SM-9: the args-contract comment's mode-enum line also lists `| "standard"`."""
    needle = '"refactor" (default) | "maintenance" | "codemod" | "content"'
    matching = [line for line in JS.splitlines() if needle in line]
    assert matching, "mode-enum comment line not found"
    assert '| "standard"' in matching[0], matching[0]


def _phases_array_body() -> str:
    idx = JS.find("phases: [")
    assert idx != -1, "meta.phases array not found"
    start = JS.index("[", idx)
    depth, j = 0, start
    while j < len(JS):
        if JS[j] == "[":
            depth += 1
        elif JS[j] == "]":
            depth -= 1
            if depth == 0:
                return JS[start: j + 1]
        j += 1
    return JS[start:]


@pytest.mark.parametrize(
    "title",
    [
        "title: 'Behavioral'",
        "title: 'Acceptance Test'",
        "title: 'Test Adversary'",
        "title: 'Seal'",
        "title: 'Acceptance Run'",
    ],
    ids=["SM-10-Behavioral", "SM-10-AcceptanceTest", "SM-10-TestAdversary", "SM-10-Seal", "SM-10-AcceptanceRun"],
)
def test_sm10_meta_phases_gains_new_title_rows(title):
    """SM-10: `meta.phases` gains 5 new phase-title rows (parametrized, one per title)."""
    assert title in _phases_array_body()


# ══════════════════════════════════════════════════════════════════════════════
# Group 2 — New symbols defined and dispatched (SM-11)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize(
    "fn",
    [
        "standardSpecPrompt",
        "standardSpecRevisePrompt",
        "standardBehavioralPrompt",
        "standardSpecAdversaryPrompt",
        "standardAcceptanceTestPrompt",
        "standardAcceptanceTestRevisePrompt",
        "standardPreflightPrompt",
        "standardTestAdversaryPrompt",
        "standardSealPrompt",
        "standardImplementPrompt",
        "standardAcceptanceRunPrompt",
        "standardReviewPrompt",
    ],
)
def test_sm11_standard_prompt_helpers_defined_and_called(fn):
    """SM-11: each of the 12 standard-mode prompt-builder functions is BOTH defined
    (`function <fn>(`) AND referenced at least once beyond its own definition."""
    defined = f"function {fn}(" in JS or f"const {fn} =" in JS
    assert defined, f"{fn} not defined"
    assert JS.count(fn) >= 2, f"{fn} defined but never called"


# ══════════════════════════════════════════════════════════════════════════════
# Group 3 — Dispatch metadata: agentType / model / isolation (SM-12 .. SM-18)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.parametrize(
    "fn",
    ["standardSpecAdversaryPrompt", "standardTestAdversaryPrompt"],
    ids=["SM-12-spec_adversary", "SM-13-test_adversary"],
)
def test_sm12_sm13_both_adversary_gates_dispatch_adversary_plus_fable(fn):
    """SM-12/SM-13: BOTH adversary gates (spec_adversary, test_adversary) independently
    dispatch `orchemist-adversary` + `model: 'fable'` — checked per-gate so a partial
    implementation that pins fable on only one gate is caught."""
    seg = _dispatch_segment(fn)
    assert "agentType: 'orchemist-adversary'" in seg, seg
    assert "model: 'fable'" in seg, seg


def test_sm14_acceptance_test_dispatches_orchemist_tester():
    """SM-14: `acceptance_test` dispatches `agentType: 'orchemist-tester'`."""
    seg = _dispatch_segment("standardAcceptanceTestPrompt")
    assert "agentType: 'orchemist-tester'" in seg, seg


def test_sm15_implement_dispatches_implementer_opus_worktree():
    """SM-15: `implement` dispatches `orchemist-implementer` + `opus` + worktree isolation."""
    seg = _dispatch_segment("standardImplementPrompt")
    assert "agentType: 'orchemist-implementer'" in seg, seg
    assert "model: 'opus'" in seg, seg
    assert "isolation: 'worktree'" in seg, seg


def test_sm16_review_dispatches_general_purpose_fable():
    """SM-16: `review` dispatches `general-purpose` + `fable`."""
    seg = _dispatch_segment("standardReviewPrompt")
    assert "agentType: 'general-purpose'" in seg, seg
    assert "model: 'fable'" in seg, seg


@pytest.mark.parametrize(
    "fn",
    ["standardPreflightPrompt", "standardSealPrompt", "standardAcceptanceRunPrompt"],
)
def test_sm17_preflight_seal_acceptance_run_use_worktree_isolation(fn):
    """SM-17: preflight/SEAL/acceptance_run each dispatch with `isolation: 'worktree'`."""
    seg = _dispatch_segment(fn)
    assert "isolation: 'worktree'" in seg, seg


@pytest.mark.parametrize(
    "fn",
    [
        "standardSpecPrompt",
        "standardSpecRevisePrompt",
        "standardBehavioralPrompt",
        "standardAcceptanceTestPrompt",
        "standardAcceptanceTestRevisePrompt",
    ],
)
def test_sm18_readonly_dispatches_omit_isolation(fn):
    """SM-18: spec/behavioral/acceptance_test dispatches do NOT request `isolation:`
    (only git-writing dispatches request a worktree)."""
    seg = _dispatch_segment(fn)
    assert "isolation:" not in seg, seg


# ══════════════════════════════════════════════════════════════════════════════
# Group 4 — Per-lane phase ordering (SM-19 .. SM-26)
# ══════════════════════════════════════════════════════════════════════════════

def _standard_block() -> str:
    """The standard-mode dispatcher block: from `} else if (mode === 'standard') {`
    through (but not including) the next top-level `} else {` / EOF."""
    start_marker = "} else if (mode === 'standard') {"
    start = JS.find(start_marker)
    assert start != -1, 'standard-mode dispatcher branch not found (mode:"standard" not implemented yet)'
    nxt = JS.find("} else {", start)
    return JS[start:] if nxt == -1 else JS[start:nxt]


def _first_call_index(prompt_fn: str, block: str) -> int:
    idx = block.find(f"agent({prompt_fn}(lane")
    assert idx != -1, f"no agent() dispatch of {prompt_fn} found in the standard-mode block"
    return idx


_STANDARD_CHAIN = [
    "standardSpecPrompt",
    "standardBehavioralPrompt",
    "standardSpecAdversaryPrompt",
    "standardAcceptanceTestPrompt",
    "standardPreflightPrompt",
    "standardTestAdversaryPrompt",
    "standardSealPrompt",
    "standardImplementPrompt",
    "standardAcceptanceRunPrompt",
    "standardReviewPrompt",
]
_CHAIN_PAIRS = list(zip(_STANDARD_CHAIN, _STANDARD_CHAIN[1:]))
_CHAIN_IDS = ["SM-19", "SM-20", "SM-21", "SM-22", "SM-23", "SM-24", "SM-25", "SM-26a", "SM-26b"]


@pytest.mark.parametrize("fn_a,fn_b", _CHAIN_PAIRS, ids=_CHAIN_IDS)
def test_sm19_sm26_phase_ordering_chain(fn_a, fn_b):
    """SM-19..SM-26: within the standard-mode dispatcher block, each phase's FIRST
    `agent()` dispatch source-text index precedes the next phase's first dispatch
    index, in the exact spec -> behavioral -> spec_adversary -> acceptance_test ->
    pre-flight -> test_adversary -> SEAL -> implement -> acceptance_run -> review
    order the issue mandates (source order is pipeline()'s execution-order proxy)."""
    block = _standard_block()
    idx_a = _first_call_index(fn_a, block)
    idx_b = _first_call_index(fn_b, block)
    assert idx_a < idx_b, f"{fn_a} (idx {idx_a}) does not precede {fn_b} (idx {idx_b})"


# ══════════════════════════════════════════════════════════════════════════════
# Group 5 — Seal-hash lifecycle (SM-27 .. SM-36)
# ══════════════════════════════════════════════════════════════════════════════

def _const_body(name: str) -> str:
    """Brace-balanced body of a top-level `const NAME = { ... }` object literal."""
    m = re.search(rf"const {re.escape(name)}\s*=\s*\{{", JS)
    assert m, f"{name} not found"
    i = m.end() - 1  # index of the opening brace
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


def _enum_values_span(schema_body: str, prop_name: str) -> str:
    """The `enum: [...]` text span immediately following a named property."""
    idx = schema_body.find(f"{prop_name}:")
    assert idx != -1, f"property {prop_name!r} not found in schema body"
    enum_idx = schema_body.find("enum:", idx)
    assert enum_idx != -1, f"no enum: found for property {prop_name!r}"
    start = schema_body.find("[", enum_idx)
    end = schema_body.find("]", start)
    assert start != -1 and end != -1, f"malformed enum array for {prop_name!r}"
    return schema_body[start: end + 1]


def test_sm27_sm28_preflight_schema_seal_hash_and_red_status():
    """SM-27: `PREFLIGHT_SCHEMA` declares `seal_sha256:`.
    SM-28: its `status` property's `enum` array includes `'red'`."""
    body = _const_body("PREFLIGHT_SCHEMA")
    assert "seal_sha256:" in body  # SM-27
    assert "'red'" in _enum_values_span(body, "status")  # SM-28


def test_sm29_seal_schema_seal_hash_and_status_enum():
    """SM-29: `SEAL_SCHEMA` declares `seal_sha256:` and a `status` enum with both
    `'sealed'` and `'blocked'`."""
    body = _const_body("SEAL_SCHEMA")
    assert "seal_sha256:" in body
    span = _enum_values_span(body, "status")
    assert "'sealed'" in span
    assert "'blocked'" in span


def test_sm30_acceptance_run_schema_seal_intact_boolean():
    """SM-30: `ACCEPTANCE_RUN_SCHEMA` declares a boolean `seal_intact:` field."""
    body = _const_body("ACCEPTANCE_RUN_SCHEMA")
    idx = body.find("seal_intact:")
    assert idx != -1, "seal_intact: property not found"
    window = body[idx: idx + 200]
    assert "type: 'boolean'" in window, window


def test_sm31_preflight_hashes_and_explicitly_expects_red():
    """SM-31: pre-flight's prompt body computes a sha256 hash AND explicitly
    instructs a RED (failing) expectation — word-boundary matched so it does not
    false-positive on 'required'/'prepared'/'credential'."""
    body = _fn_body("standardPreflightPrompt")
    assert "sha256" in body
    assert re.search(r"(?i)\b(red|fail|error|expect)\w*\b", body), body


def test_sm32_preflight_evidence_threaded_to_test_adversary():
    """SM-32: pre-flight's RED evidence is threaded into `test_adversary`'s prompt
    body (the substring `evidence`, confirming the RED run's output is handed to
    the adversary as text, not merely assumed)."""
    body = _fn_body("standardTestAdversaryPrompt")
    assert "evidence" in body


_HASH_REVERIFICATION_CASES = [
    ("standardSealPrompt", ["sha256", "commit"], []),
    ("standardImplementPrompt", ["${invariant}", "sha256"], []),
    ("standardAcceptanceRunPrompt", ["sha256"], ["git commit"]),
    ("standardReviewPrompt", ["sha256", "SEAL"], []),
]
_HASH_REVERIFICATION_IDS = ["SM-33-seal", "SM-34-implement", "SM-35-acceptance_run", "SM-36-review"]


@pytest.mark.parametrize("fn,must_contain,must_not_contain", _HASH_REVERIFICATION_CASES, ids=_HASH_REVERIFICATION_IDS)
def test_sm33_sm34_sm35_sm36_downstream_phases_reverify_the_hash(fn, must_contain, must_not_contain):
    """SM-33: SEAL re-verifies the hash (`sha256`) before `commit`.
    SM-34: implement embeds the shared `${invariant}` AND independently re-hashes.
    SM-35: acceptance_run re-verifies the hash and never itself `git commit`s.
    SM-36: review re-verifies the hash and audits the `SEAL` commit trail."""
    body = _fn_body(fn)
    for token in must_contain:
        assert token in body, f"{fn} body missing {token!r}"
    for token in must_not_contain:
        assert token not in body, f"{fn} body must NOT contain {token!r}"


# ══════════════════════════════════════════════════════════════════════════════
# Group 6 — Schema shape: EXTEND not replace (SM-37 .. SM-38)
# ══════════════════════════════════════════════════════════════════════════════

def test_sm37_spec_schema_extended_not_replaced():
    """SM-37: `SPEC_SCHEMA` keeps its pre-existing `plan:` property AND gains a new
    `observable_outcomes:` property (existing maintenance/codemod call sites, which
    never populate `observable_outcomes`, must remain unaffected)."""
    body = _const_body("SPEC_SCHEMA")
    assert "plan:" in body
    assert "observable_outcomes:" in body


def test_sm38_impl_schema_extended_not_replaced():
    """SM-38: `IMPL_SCHEMA` keeps its pre-existing `status` enum
    (`['pushed', 'blocked']`) AND gains a new `seal_verified:` property."""
    body = _const_body("IMPL_SCHEMA")
    assert "status: { type: 'string', enum: ['pushed', 'blocked']" in body
    assert "seal_verified:" in body


# ══════════════════════════════════════════════════════════════════════════════
# Group 7 — Backward compatibility + syntax (SM-39 .. SM-40)
# ══════════════════════════════════════════════════════════════════════════════

def test_sm39_refactor_fallback_invariant_untouched_and_final_arm():
    """SM-39 — SHIELD: this exact fallback string already exists today and must
    remain the invariant ternary's LAST arm — no arm (including the new `standard`
    arm) may be inserted after it."""
    fallback = (
        "'Behavior 100% unchanged; the public surface and every caller import path "
        "stay byte-identical; do NOT modify any tests.'"
    )
    idx_fallback = JS.find(fallback)
    assert idx_fallback != -1, "refactor fallback invariant string missing"
    idx_standard_arm = JS.find("mode === 'standard' ?")
    if idx_standard_arm != -1:
        assert idx_standard_arm < idx_fallback, (
            "the new mode === 'standard' ? arm must be inserted BEFORE the final "
            "refactor fallback, not after it"
        )


def test_sm40_node_syntax_check_if_available():
    """SM-40 — SHIELD/skip: `node --check` passes today (verbatim reuse of
    tests/test_wave_content_mode.py:127-132); skips gracefully if node is absent."""
    node = shutil.which("node")
    if not node:
        pytest.skip("node not on PATH — syntax gate skipped (text-assertions still cover shape)")
    r = subprocess.run([node, "--check", str(WAVE_JS)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


# ══════════════════════════════════════════════════════════════════════════════
# Group 8 — Round-2: seal-gate enforcement, revise-loop, path/branch pinning (SM-41 .. SM-46)
# ══════════════════════════════════════════════════════════════════════════════

def test_sm41_implement_gated_behind_seal_status_check():
    """SM-41: within the standard-mode block, `seal.status !== 'sealed'` appears at
    an index strictly LESS than the first `agent(standardImplementPrompt(lane`
    occurrence (an unsealed/mismatched seal must short-circuit before implement)."""
    block = _standard_block()
    idx_guard = block.find("seal.status !== 'sealed'")
    assert idx_guard != -1, "seal.status !== 'sealed' guard not found in standard block"
    idx_impl = _first_call_index("standardImplementPrompt", block)
    assert idx_guard < idx_impl


def test_sm42_review_gated_behind_seal_intact_blocked_record():
    """SM-42: `!run.seal_intact` appears; the FIRST `return blockedRecord(` at-or-after
    that index is strictly LESS than the first `agent(standardReviewPrompt(lane`
    index (a broken seal at acceptance_run must route to blockedRecord, not review)."""
    block = _standard_block()
    idx_guard = block.find("!run.seal_intact")
    assert idx_guard != -1, "!run.seal_intact guard not found in standard block"
    idx_blocked = block.find("return blockedRecord(", idx_guard)
    assert idx_blocked != -1, "no return blockedRecord( at-or-after the seal_intact guard"
    idx_review = _first_call_index("standardReviewPrompt", block)
    assert idx_blocked < idx_review


def test_sm43_revise_loop_reruns_preflight_before_looping_back():
    """SM-43: the test_adversary revise loop always re-runs pre-flight (>=2 dispatches
    of `standardPreflightPrompt`, a `preflight2:` label) and the SINGLE
    `standardAcceptanceTestRevisePrompt` call precedes the SECOND pre-flight
    dispatch — never reusing a stale hash after the test content changed."""
    block = _standard_block()
    count_preflight = block.count("agent(standardPreflightPrompt(lane")
    assert count_preflight >= 2, f"expected >=2 pre-flight dispatches in block, found {count_preflight}"
    assert "preflight2:" in block, "preflight2: label not found in standard block"
    idx_revise = block.find("agent(standardAcceptanceTestRevisePrompt(lane")
    assert idx_revise != -1, "no agent() dispatch of standardAcceptanceTestRevisePrompt in block"
    first_pf = block.find("agent(standardPreflightPrompt(lane")
    second_pf = block.find("agent(standardPreflightPrompt(lane", first_pf + 1)
    assert second_pf != -1, "second pre-flight dispatch not found"
    assert idx_revise < second_pf


def test_sm44_both_preflight_labels_independently_worktree_isolated():
    """SM-44: BOTH the first (`preflight:`) and second (`preflight2:`) pre-flight
    dispatches are INDEPENDENTLY worktree-isolated (closes the gap where SM-17's
    joined-window check could pass even if only the first pre-flight were sealed)."""
    seg1 = _label_segment("preflight:")
    seg2 = _label_segment("preflight2:")
    assert "isolation: 'worktree'" in seg1, seg1
    assert "isolation: 'worktree'" in seg2, seg2


def test_sm45_standard_test_path_defined():
    """SM-45 (part 1): `standardTestPath` is defined as a stable scratch-dir helper
    rooted at `/tmp/orchemist-wave-standard`."""
    assert "const standardTestPath = (lane) =>" in JS
    assert "/tmp/orchemist-wave-standard" in JS


@pytest.mark.parametrize(
    "fn",
    ["standardAcceptanceTestPrompt", "standardPreflightPrompt", "standardSealPrompt"],
)
def test_sm45_standard_test_path_referenced_in_prompt_bodies(fn):
    """SM-45 (part 2): `standardTestPath` is threaded into the acceptance-test,
    pre-flight, and SEAL prompt bodies (not merely declared once and left
    unreferenced) — three independent per-function checks."""
    body = _fn_body(fn)
    assert "standardTestPath" in body


def test_sm46_seal_pushes_branch_first_and_implement_checks_out_pushed_branch():
    """SM-46: SEAL performs the lane's first branch push
    (`git push -u origin ${lane.branch}`), and implement checks out that
    already-pushed branch (`origin/${lane.branch}`) rather than branching fresh off
    base — confirming the SEAL commit is not orphaned/clobbered."""
    seal_body = _fn_body("standardSealPrompt")
    assert "git push -u origin ${lane.branch}" in seal_body
    impl_body = _fn_body("standardImplementPrompt")
    assert "origin/${lane.branch}" in impl_body


# ── shared helpers (verbatim from tests/test_wave_content_mode.py) ─────────────
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
                return JS[i: j + 1]
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
        hits.append(JS[k: k + 320])
        idx = k + 1
    assert hits, f"no agent() dispatch of {prompt_fn}"
    return "\n".join(hits)


def _label_segment(label: str) -> str:
    k = JS.find(f"label: `{label}")
    assert k != -1, f"label {label} not found"
    # widen to the enclosing agent() opts object
    start = JS.rfind("agent(", max(0, k - 400), k)
    return JS[start: k + 300]
