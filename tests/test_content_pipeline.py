"""Content-pipeline structural test (pack #44 — coding-adapted content pipeline).

Pure YAML + pyyaml, no live LLM and no engine `TemplateEngine`/`validate_template_extended`
(this pack is markdown-only). Mirrors the plain-pytest style of tests/test_tiering_profiles.py.

Locks the coding-adapted content-pipeline's shape:
  - identity (id / category / version) + phase id-list and ORDER
  - per-phase phase_class + model_tier
  - the transitions state machine (the two upgrades over the engine's advisory DAG:
    fact_check + red_team are BLOCKING gates that loop back to draft)
  - the LOAD-BEARING gate annotation — fact_check + red_team both resolve
    model_tier `fable` + phase_class `gate`, and NO other phase is `fable`
  - config_schema required/optional split (incl. the content-specific `source_material`)
  - phase-id reuse of the terminal `test` command phase (free /orchemist:test dispatch)
  - the Bash-less-adversary diff handoff: fact_check captures draft_diff.md, red_team reads it

The render-smoke suite (tests/test_all_pipelines_render_smoke.py) already auto-covers this
file's prompt_templates via its pipelines/*.yaml glob; this test covers the STRUCTURE.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_PATH = REPO_ROOT / "pipelines" / "content-pipeline.yaml"
SKILLS_DIR = REPO_ROOT / "skills"

DOC = yaml.safe_load(PIPELINE_PATH.read_text())
PHASES = DOC["phases"]
PHASE_BY_ID = {p["id"]: p for p in PHASES}

EXPECTED_ORDER = [
    "existing_symbols_inventory",
    "research",
    "draft",
    "fact_check",
    "red_team",
    "apply_fixes",
    "test",
]

EXPECTED_CLASS = {
    "existing_symbols_inventory": "rote",
    "research": "interpretive",
    "draft": "implement",
    "fact_check": "gate",
    "red_team": "gate",
    "apply_fixes": "implement",
    "test": "rote",
}

# `test` is a command phase with no model_tier (dispatches through the existing
# /orchemist:test wrapper by phase-id) — intentionally absent from this map.
EXPECTED_MODEL_TIER = {
    "existing_symbols_inventory": "sonnet",
    "research": "sonnet",
    "draft": "opus",
    "fact_check": "fable",
    "red_team": "fable",
    "apply_fixes": "opus",
}

EXPECTED_TRANSITIONS = {
    "existing_symbols_inventory": {
        "success": "research", "failed": "existing_symbols_inventory",
        "timeout": "existing_symbols_inventory", "exhausted": "research",
    },
    "research": {
        "success": "draft", "failed": "research",
        "timeout": "research", "exhausted": "draft",
    },
    "draft": {
        "success": "fact_check", "failed": "draft",
        "timeout": "draft", "exhausted": "draft",
    },
    "fact_check": {
        "approve": "red_team", "request_changes": "draft",
        "failed": "fact_check", "success": "red_team", "exhausted": "draft",
    },
    "red_team": {
        "approve": "apply_fixes", "request_changes": "draft",
        "failed": "red_team", "success": "apply_fixes", "exhausted": "draft",
    },
    "apply_fixes": {
        "success": "test", "failed": "apply_fixes",
        "timeout": "apply_fixes", "exhausted": "test",
    },
    "test": {
        "failed": "apply_fixes", "timeout": "test",
    },
}

# The five content-specific phases each get a dedicated wrapper (brief §3/§4 risk 3 —
# do NOT repeat comic-strip's undocumented looser treatment). test + existing_symbols_
# inventory REUSE existing wrappers by phase-id, so they are NOT in this set.
EXPECTED_NEW_WRAPPERS = {
    "research": "orchemist-research.md",
    "draft": "orchemist-draft.md",
    "fact_check": "orchemist-fact-check.md",
    "red_team": "orchemist-red-team.md",
    "apply_fixes": "orchemist-apply-fixes.md",
}


# ── identity ───────────────────────────────────────────────────────────────
def test_identity():
    assert DOC["id"] == "content-pipeline"
    assert DOC["category"] == "content"
    assert str(DOC["version"]) == "0.1.0"


# ── phase id-list + order ──────────────────────────────────────────────────
def test_phase_order():
    assert [p["id"] for p in PHASES] == EXPECTED_ORDER


# ── phase_class (total, and matches the expected map) ──────────────────────
@pytest.mark.parametrize("pid", EXPECTED_ORDER)
def test_phase_class(pid):
    assert PHASE_BY_ID[pid].get("phase_class") == EXPECTED_CLASS[pid]


# ── model_tier per LLM phase (test has none — command phase) ───────────────
@pytest.mark.parametrize("pid", sorted(EXPECTED_MODEL_TIER))
def test_model_tier(pid):
    assert PHASE_BY_ID[pid].get("model_tier") == EXPECTED_MODEL_TIER[pid]


def test_test_phase_has_no_model_tier():
    # The terminal `test` phase is an inert command — no LLM, so no model_tier.
    assert "model_tier" not in PHASE_BY_ID["test"]


# ── transitions state machine ──────────────────────────────────────────────
@pytest.mark.parametrize("pid", EXPECTED_ORDER)
def test_transitions(pid):
    assert PHASE_BY_ID[pid].get("transitions") == EXPECTED_TRANSITIONS[pid]


# ── LOAD-BEARING — the two gates are fable + gate, and nothing else is fable ─
def test_gates_are_fable_and_gate():
    for pid in ("fact_check", "red_team"):
        phase = PHASE_BY_ID[pid]
        assert phase["model_tier"] == "fable", f"{pid} must be fable"
        assert phase["phase_class"] == "gate", f"{pid} must be gate"


def test_only_the_two_gates_are_fable():
    fable_ids = {p["id"] for p in PHASES if p.get("model_tier") == "fable"}
    assert fable_ids == {"fact_check", "red_team"}


def test_gates_loop_back_to_draft():
    # The deliberate upgrade over the engine's advisory reports: a gate REQUEST_CHANGES
    # blocks and routes back to draft (not straight into apply_fixes).
    assert PHASE_BY_ID["fact_check"]["transitions"]["request_changes"] == "draft"
    assert PHASE_BY_ID["red_team"]["transitions"]["request_changes"] == "draft"


# ── config_schema required / optional split ────────────────────────────────
def test_required_config():
    required = set(DOC["config_schema"]["required"])
    assert required == {
        "issue_title", "issue_body", "repo_path", "branch_name",
        "issue_number", "repo_url", "source_material",
    }
    # source_material is the one content-specific required field (pre-placed-file handoff).
    assert "source_material" in required


@pytest.mark.parametrize(
    "opt", ["content_type", "target_file", "allowlist_file", "gated", "test_command", "tiering_profile"]
)
def test_optional_config_present(opt):
    props = DOC["config_schema"]["properties"]
    assert opt in props, f"{opt} missing from config_schema.properties"
    assert opt not in DOC["config_schema"]["required"], f"{opt} must be optional, not required"


# ── terminal `test` reuses the existing command wrapper by phase-id ────────
def test_test_phase_is_command():
    phase = PHASE_BY_ID["test"]
    assert phase.get("task_type") == "command"
    assert "{config[test_command]}" in phase["command"]
    # Free reuse: the existing /orchemist:test wrapper resolves off phase.id.
    assert (SKILLS_DIR / "orchemist-test.md").exists()


# ── each content-specific phase has its dedicated wrapper (no looser treatment) ─
@pytest.mark.parametrize("pid,wrapper", sorted(EXPECTED_NEW_WRAPPERS.items()))
def test_new_wrapper_exists(pid, wrapper):
    path = SKILLS_DIR / wrapper
    assert path.exists(), f"missing wrapper {wrapper} for phase {pid}"
    # slug convention: phase.id underscores -> hyphens in the skill name
    text = path.read_text()
    slug = pid.replace("_", "-")
    assert f"name: orchemist:{slug}" in text, f"{wrapper} frontmatter name mismatch"


# ── Bash-less-adversary diff handoff (brief §4 risk 3/5) ───────────────────
def test_fact_check_captures_diff_for_red_team():
    # fact_check (has Bash) must capture the diff so the Bash-less red_team can Read it.
    fc = PHASE_BY_ID["fact_check"]["prompt_template"]
    assert "draft_diff.md" in fc, "fact_check must capture draft_diff.md"
    rt = PHASE_BY_ID["red_team"]["prompt_template"]
    assert "draft_diff.md" in rt, "red_team must read draft_diff.md"
    # and the fact_check wrapper (general-purpose, has web+Bash) documents the same.
    assert "draft_diff.md" in (SKILLS_DIR / "orchemist-fact-check.md").read_text()


# ── every phase carries a valid phase_class (annotation completeness) ──────
def test_every_phase_has_valid_class():
    valid = {"rote", "interpretive", "implement", "gate"}
    for p in PHASES:
        assert p.get("phase_class") in valid, f"{p['id']} bad phase_class"
