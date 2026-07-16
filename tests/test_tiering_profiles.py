"""Tiering-profile validation test (#41).

Enforces, without any live LLM (prompt-rendering-only style, plain pytest + pyyaml):
  (a)  profile-registry shape (all four phase_classes, valid model/effort vocab)
  (a2) phase_class annotation is TOTAL across every in-scope pipeline phase
  (b)  backward-compat lock: `default` resolves every LLM phase to its own model_tier
  (c)  the Fable gate-invariant holds for every shipped profile
  (c0) gate-annotation lock: WHICH phases are annotated `gate` is byte-locked
  (d)  a gate->sonnet profile is rejected (GateInvariantError)
  (e)  budget-first haiku floor + gate effort xhigh (both opt-in ladders)
  (f)  the wave JS EFFORT_BY_PROFILE map is in sync with the YAML profiles
  (g)  a partial profile (missing a phase_class) strict-FAILS (KeyError), never
       silently falls back to default
"""
from __future__ import annotations

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


# ── (f) wave effort-map JS <-> YAML sync ──────────────────────────────────
def test_wave_effort_map_in_sync():
    js = (tp.REPO_ROOT / "workflows" / "orchemist-wave.js").read_text()
    assert "EFFORT_BY_PROFILE" in js
    for profile_name, profile in PROFILES.items():
        if profile_name == "default":
            continue
        for cls in tp.PHASE_CLASSES:
            effort = profile[cls]["effort"]
            if effort == "inherit":
                continue
            assert f"{cls}: '{effort}'" in js, f"{profile_name} {cls}: '{effort}' absent from wave JS"


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
