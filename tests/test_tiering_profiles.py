"""Tiering-profile validation test (#41).

Enforces, without any live LLM (prompt-rendering-only style, plain pytest + pyyaml):
  (a)  profile-registry shape (all four phase_classes, valid model/effort vocab)
  (a2) phase_class annotation is TOTAL across every in-scope pipeline phase
  (b)  backward-compat lock: `default` resolves every LLM phase to its own model_tier
  (c)  the Fable gate-invariant holds for every shipped profile
  (c0) gate-annotation lock: WHICH phases are annotated `gate` is byte-locked
  (d)  a gate->sonnet profile is rejected (GateInvariantError)
  (e)  budget-first haiku floor + gate effort xhigh (both opt-in ladders)
  (f)  the wave JS TIER_BY_PROFILE map is in sync with the YAML profiles (BOTH model + effort)
  (f2) the wave never dispatches an effort without a model (v4.4 hardening, #59)
  (g)  a partial profile (missing a phase_class) strict-FAILS (KeyError), never
       silently falls back to default
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import tiering_profiles as tp  # noqa: E402


PROFILES = tp.load_profiles()
SHIPPED_PROFILES = ("default", "budget-first", "quality-first")


# ── (a) schema / shape ─────────────────────────────────────────────────────
def test_expected_profiles_present():
    assert {"default", "budget-first", "quality-first"} <= set(PROFILES)


@pytest.mark.parametrize("profile_name", sorted(PROFILES))
def test_profile_shape(profile_name):
    profile = PROFILES[profile_name]
    for cls in tp.PHASE_CLASSES:
        assert cls in profile, f"{profile_name} missing phase_class {cls}"
        entry = profile[cls]
        assert entry["model"] in tp.MODEL_VALUES, f"{profile_name}.{cls}.model={entry['model']}"
        assert entry["effort"] in tp.EFFORT_VALUES, f"{profile_name}.{cls}.effort={entry['effort']}"


# ── (a2) annotation completeness — every phase has a valid class ───────────
@pytest.mark.parametrize("name", tp.IN_SCOPE_PIPELINES)
def test_every_phase_has_valid_class(name):
    doc = tp.load_pipeline(name)
    for p in doc["phases"]:
        assert p.get("phase_class") in tp.PHASE_CLASSES, f"{name}:{p['id']} bad phase_class"


# ── (b) backward-compat lock — default is passthrough ─────────────────────
@pytest.mark.parametrize("name", tp.IN_SCOPE_PIPELINES)
def test_default_is_passthrough(name):
    doc = tp.load_pipeline(name)
    default = PROFILES["default"]
    for phase in tp.llm_phases(doc):
        assert tp.resolve(phase, default)["model"] == phase["model_tier"], phase["id"]


# ── (c) gate invariant holds for every shipped profile ────────────────────
@pytest.mark.parametrize("name", tp.IN_SCOPE_PIPELINES)
@pytest.mark.parametrize("profile_name", SHIPPED_PROFILES)
def test_gate_floor_holds(name, profile_name):
    doc = tp.load_pipeline(name)
    tp.assert_gate_floor(doc["phases"], PROFILES[profile_name])  # must not raise


# ── (c0) gate-annotation lock — WHICH phases carry the gate class ─────────
@pytest.mark.parametrize("name", tp.IN_SCOPE_PIPELINES)
def test_gate_annotation_lock(name):
    doc = tp.load_pipeline(name)
    # (1) every fable-model phase MUST be annotated gate
    for p in doc["phases"]:
        if p.get("model_tier") == "fable":
            assert p.get("phase_class") == "gate", f"{name}:{p['id']} fable but not gate"
    # (2) the gate id-set is exactly the byte-locked expected set
    gate_ids = {p["id"] for p in doc["phases"] if p.get("phase_class") == "gate"}
    assert gate_ids == tp.EXPECTED_GATES[name], f"{name} gate ids {gate_ids}"


# ── (d) bad-profile rejection ─────────────────────────────────────────────
def test_bad_gate_profile_rejected():
    BAD = {
        "rote": {"model": "haiku", "effort": "low"},
        "interpretive": {"model": "sonnet", "effort": "medium"},
        "implement": {"model": "opus", "effort": "high"},
        "gate": {"model": "sonnet", "effort": "xhigh"},
    }
    with pytest.raises(tp.GateInvariantError):
        tp.assert_gate_floor(
            tp.load_pipeline("coding-pipeline-standard.yaml")["phases"], BAD
        )


# ── (e) budget floor + gate effort ────────────────────────────────────────
def test_budget_floor_and_gate_effort():
    assert PROFILES["budget-first"]["rote"]["model"] == "haiku"
    assert PROFILES["budget-first"]["gate"]["effort"] == "xhigh"
    assert PROFILES["quality-first"]["gate"]["effort"] == "xhigh"


# ── (f) wave tier-map JS <-> YAML sync — BOTH fields ──────────────────────
def test_wave_tier_map_in_sync():
    """The wave's inline ladder must mirror BOTH halves of each profile entry.

    #59: this test previously compared only `effort`, so the JS map could carry — and did
    carry — the effort half alone. A profile's `model` was silently dropped, leaving
    `budget-first` half-implemented AND emitting effort-without-model dispatches that die
    at 0 tokens. Comparing both fields is what makes that drift impossible.
    """
    js = (tp.REPO_ROOT / "workflows" / "orchemist-wave.js").read_text(encoding="utf-8")
    assert "TIER_BY_PROFILE" in js
    for profile_name, profile in PROFILES.items():
        if profile_name == "default":
            continue
        for cls in tp.PHASE_CLASSES:
            model = profile[cls]["model"]
            effort = profile[cls]["effort"]
            # The JS renders one entry per class as: `cls: { model: 'M', effort: 'E' }`
            # (whitespace-tolerant, since the map is column-aligned for readability).
            pattern = (
                rf"{cls}:\s*\{{\s*model:\s*'{model}',\s*effort:\s*'{effort}'\s*\}}"
            )
            assert re.search(pattern, js), (
                f"{profile_name}.{cls} = {{model: {model!r}, effort: {effort!r}}} "
                f"absent from the wave's TIER_BY_PROFILE"
            )


# ── (f2) the wave may NEVER dispatch an effort without a model ────────────
def test_wave_never_dispatches_effort_without_model():
    """v4.4 hardening, enforced structurally.

    A dispatch that pins `effort` while inheriting the ambient model dies instantly,
    returning 0 tokens (skills/orchemist-run.md, "Always pass an EXPLICIT model"). #59 hit
    exactly this: every lane of a `budget-first` wave failed before executing a single tool
    call, because 14 dispatches carry no literal `model:` and the profile supplied only an
    effort.

    Two invariants:
      (a) `tierFor` gates `effort` on a resolved `out.model`;
      (b) no dispatch hardcodes a bare `effort:` literal alongside no model.
    """
    js = (tp.REPO_ROOT / "workflows" / "orchemist-wave.js").read_text(encoding="utf-8")

    # (a) the guard itself — effort is only assigned when a model resolved.
    assert re.search(r"out\.model\)\s*out\.effort\s*=", js), (
        "tierFor must gate `out.effort` on a resolved `out.model`"
    )

    # (b) no agent() dispatch may pin an effort literal without a model literal.
    for lineno, line in enumerate(js.splitlines(), start=1):
        if "await agent(" in line and re.search(r"\beffort:\s*'", line):
            assert re.search(r"\bmodel:\s*'", line), (
                f"orchemist-wave.js:{lineno} pins an effort with no model — "
                f"that dispatch dies at 0 tokens"
            )


# ── (g) incomplete-profile strict-fail (no silent default fallback) ───────
def test_partial_profile_strict_fail():
    PARTIAL = {
        "rote": {"model": "haiku", "effort": "low"},
        "interpretive": {"model": "sonnet", "effort": "medium"},
        "implement": {"model": "opus", "effort": "high"},
        # no "gate" key on purpose
    }
    with pytest.raises(KeyError):
        tp.assert_gate_floor(
            tp.load_pipeline("coding-pipeline-standard.yaml")["phases"], PARTIAL
        )
