"""Regression test — issue #13: skip-spec dedup parity (Option A).

Verifies that `coding-pipeline-skip-spec.yaml` was brought to dedup parity with
`coding-pipeline-standard.yaml` by porting standard's 5 dedup sub-checks into
the correct skip-spec phases:

  IMPLEMENT: 7d (re-implementation of existing symbol),
             7e-implement (intra-symbol self-check before file output),
             7e-seal (§7.2 byte-identical added-block diff lint).
  REVIEW:    7h (diff-symmetric cross-file new-symbol grep),
             7d-producer (intra-symbol return-arm comparison),
             plus the Sticky-7d (v4) 3-arm enforcement.

It also locks in:
  - The B1 absent-file clause on BOTH ported inventory-reading blocks
    (skip-spec has no Phase-0 inventory, so `existing_symbols.md` is absent —
    without the clause the dedup check silently no-ops).
  - Non-regression of skip-spec's unique `## ANTI-TAMPERING — ENGINE-ENFORCED`
    section after the merge.
  - The 9->10 IMPLEMENT Task renumber (§7.2 diff lint inserted as step 8).
  - Every skip-spec prompt_template still `.format()`-renders (doubled braces
    intact; no new config-schema key introduced).

PROMPT-RENDERING-ONLY test (no live LLM call), consistent with the repo's
existing test style (see test_spec_adversary_7e_intra_symbol.py).
"""

from __future__ import annotations

import string
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKIP_SPEC_YAML = REPO_ROOT / "pipelines" / "coding-pipeline-skip-spec.yaml"
STANDARD_YAML = REPO_ROOT / "pipelines" / "coding-pipeline-standard.yaml"
EXAMPLE_ISSUE = REPO_ROOT / "examples" / "example-issue.md"


def _phase_prompt(yaml_path: Path, phase_id: str) -> str:
    doc = yaml.safe_load(yaml_path.read_text())
    for phase in doc["phases"]:
        if phase["id"] == phase_id:
            return phase["prompt_template"]
    raise KeyError(f"{phase_id} phase not found in {yaml_path.name}")


def _skip_implement() -> str:
    return _phase_prompt(SKIP_SPEC_YAML, "implement")


def _skip_review() -> str:
    return _phase_prompt(SKIP_SPEC_YAML, "review")


# ---------------------------------------------------------------------------
# IMPLEMENT-phase ported sub-checks
# ---------------------------------------------------------------------------

def test_implement_has_7d_heading() -> None:
    """IMPLEMENT contains the ported 7d (re-implementation of existing symbol) HARD RULE."""
    assert (
        "### HARD RULE — Re-implementation of existing symbol (sub-check 7d)"
        in _skip_implement()
    )


def test_implement_has_7e_implement_heading_and_sentinel() -> None:
    """IMPLEMENT contains the 7e-implement HARD RULE + its BLOCKED sentinel."""
    prompt = _skip_implement()
    assert (
        "### HARD RULE — Intra-symbol self-check before file output (sub-check 7e-implement)"
        in prompt
    )
    assert "BLOCKED: 7e-intra-symbol-duplication" in prompt


def test_implement_has_7e_seal_sentinel() -> None:
    """IMPLEMENT contains the §7.2 diff-lint (7e-seal) BLOCKED sentinel."""
    assert "BLOCKED: 7e-seal-diff-lint" in _skip_implement()


def test_implement_preserves_anti_tampering_section() -> None:
    """Non-regression: skip-spec's unique ANTI-TAMPERING section survives the merge."""
    assert "## ANTI-TAMPERING — ENGINE-ENFORCED" in _skip_implement()


def test_implement_preserves_immutable_constraint_section() -> None:
    """Non-regression: skip-spec's unique IMMUTABLE CONSTRAINT section survives the merge."""
    assert "## IMMUTABLE CONSTRAINT — READ THIS FIRST" in _skip_implement()


def test_implement_7d_absent_file_clause() -> None:
    """B1 fix: IMPLEMENT 7d carries the explicit absent-inventory clause."""
    prompt = _skip_implement()
    assert "this pipeline has no Phase-0 inventory" in prompt
    assert "go straight to the ad-hoc grep fallback below" in prompt


def test_implement_hard_rules_before_anti_tampering() -> None:
    """Merge placement: HARD RULES block is inserted BEFORE the ANTI-TAMPERING section."""
    prompt = _skip_implement()
    hard_rules = prompt.index("## HARD RULES (return BLOCKED rather than violate any of these)")
    anti = prompt.index("## ANTI-TAMPERING — ENGINE-ENFORCED")
    ground = prompt.index("## GROUND TRUTH")
    assert ground < hard_rules < anti


def test_implement_task_renumber_9_to_10() -> None:
    """9->10 Task renumber: §7.2 diff lint is step 8; test-suite is 9; push is 10."""
    prompt = _skip_implement()
    assert "8. **§7.2 diff lint**" in prompt
    assert "9. Run the full test suite to verify:" in prompt
    assert "10. Push your branch to remote:" in prompt


# ---------------------------------------------------------------------------
# REVIEW-phase ported sub-checks
# ---------------------------------------------------------------------------

def test_review_has_7h_subcheck() -> None:
    """REVIEW contains the ported 7h diff-symmetric cross-file new-symbol grep."""
    assert (
        "Sub-check 7h — Diff-symmetric cross-file new-symbol grep" in _skip_review()
    )


def test_review_has_7d_producer_subcheck() -> None:
    """REVIEW contains the ported 7d-producer intra-symbol return-arm comparison."""
    assert (
        "Sub-check 7d-producer — Intra-symbol return-arm comparison" in _skip_review()
    )


def test_review_has_sticky_7d_enforcement() -> None:
    """REVIEW contains the Sticky-7d (v4) enforcement block."""
    assert (
        "Sticky enforcement (v4 — Phase-0 existing-symbols inventory)" in _skip_review()
    )


def test_review_sticky_7d_absent_file_clause() -> None:
    """B1 fix: REVIEW Sticky-7d carries the explicit absent-inventory clause."""
    prompt = _skip_review()
    assert "this pipeline has no Phase-0 inventory" in prompt
    assert "the always-on 7h grep below" in prompt


def test_review_has_post_review_commit_hard_rule() -> None:
    """REVIEW contains the ported post-review-commit-triggers-new-round HARD RULE."""
    assert "## HARD RULE — Post-review-commit triggers new round" in _skip_review()


def test_review_has_seal_break_audit_trail() -> None:
    """REVIEW contains the ported seal-break audit-trail verification (Task item 5)."""
    assert "Seal-break audit-trail verification (when applicable)" in _skip_review()


# ---------------------------------------------------------------------------
# Diff-symmetry / wording: ported blocks match standard's wording verbatim
# ---------------------------------------------------------------------------

def test_ported_blocks_match_standard_wording() -> None:
    """The verbatim-copied sub-checks appear byte-identically in standard.yaml."""
    std_impl = _phase_prompt(STANDARD_YAML, "implement")
    std_review = _phase_prompt(STANDARD_YAML, "review")
    skip_impl = _skip_implement()
    skip_review = _skip_review()

    # IMPLEMENT-side canonical substrings (NOT the absent-file clause, which is
    # the authorized skip-spec-only addition).
    for sub in (
        "### HARD RULE — Intra-symbol self-check before file output (sub-check 7e-implement)",
        "### HARD RULE — §7.2 byte-identical added-block diff lint (sub-check 7e-seal)",
        "BLOCKED: 7e-intra-symbol-duplication",
        "BLOCKED: 7e-seal-diff-lint",
    ):
        assert sub in std_impl, f"sanity: {sub!r} missing from standard implement"
        assert sub in skip_impl, f"parity: {sub!r} missing from skip-spec implement"

    # REVIEW-side canonical substrings.
    for sub in (
        "Sub-check 7h — Diff-symmetric cross-file new-symbol grep",
        "Sub-check 7d-producer — Intra-symbol return-arm comparison",
        "Sticky enforcement (v4 — Phase-0 existing-symbols inventory)",
        "## HARD RULE — Post-review-commit triggers new round",
    ):
        assert sub in std_review, f"sanity: {sub!r} missing from standard review"
        assert sub in skip_review, f"parity: {sub!r} missing from skip-spec review"


# ---------------------------------------------------------------------------
# Render-smoke: every skip-spec prompt_template .format()-renders
# ---------------------------------------------------------------------------

def _build_config(schema: dict) -> dict:
    cfg: dict = {}
    for name, spec in schema.get("properties", {}).items():
        if "default" in spec:
            cfg[name] = spec["default"]
    placeholders = {
        "issue_title": "Trim whitespace in parseConfig keys",
        "issue_body": EXAMPLE_ISSUE.read_text(),
        "repo_path": "/path/to/repo",
        "branch_name": "fix/issue-123",
        "issue_number": 123,
        "repo_url": "https://github.com/ToscanAI/orchestration-engine",
    }
    for name in schema.get("required", []):
        cfg.setdefault(name, placeholders.get(name, f"<{name}>"))
    for name in schema.get("properties", {}):
        cfg.setdefault(name, placeholders.get(name, f"<{name}>"))
    return cfg


def test_skip_spec_all_prompts_render() -> None:
    """HARD assertion: every skip-spec prompt_template .format()s without KeyError/ValueError."""
    doc = yaml.safe_load(SKIP_SPEC_YAML.read_text())
    cfg = _build_config(doc["config_schema"])
    kwargs = dict(
        config=cfg,
        output_dir="/tmp/run-out",
        phase_summary="(none)",
        iteration_history="(none)",
        phase_diff="(none)",
    )
    rendered = 0
    for phase in doc["phases"]:
        tmpl = phase.get("prompt_template")
        if tmpl is None:
            continue
        rendered += 1
        try:
            tmpl.format(**kwargs)
        except (KeyError, ValueError, IndexError) as exc:  # pragma: no cover
            raise AssertionError(
                f"skip-spec phase '{phase['id']}' failed to render: "
                f"{type(exc).__name__}: {exc}"
            ) from exc
    assert rendered >= 6, f"expected >=6 prompt_templates, rendered {rendered}"


def test_skip_spec_no_new_config_key() -> None:
    """The merge introduces no new config-schema key skip-spec cannot supply.

    Every {config[...]} reference in skip-spec's prompts must resolve to a key in
    skip-spec's own config_schema (the ported blocks must use only branch_name +
    output_dir, never standard-only Phase-0 placeholders like ui_primitive_paths).
    """
    import re

    doc = yaml.safe_load(SKIP_SPEC_YAML.read_text())
    schema_keys = set(doc["config_schema"].get("properties", {}).keys())
    forbidden = {
        "ui_primitive_paths",
        "lib_paths",
        "action_dirs",
        "workspace_barrels",
        "phase0_hard_gate",
    }
    for phase in doc["phases"]:
        tmpl = phase.get("prompt_template")
        if tmpl is None:
            continue
        for key in re.findall(r"\{config\[([a-zA-Z_][a-zA-Z0-9_]*)\]\}", tmpl):
            assert key in schema_keys, (
                f"phase '{phase['id']}' references config[{key}] "
                f"absent from skip-spec config_schema"
            )
            assert key not in forbidden, (
                f"phase '{phase['id']}' references standard-only Phase-0 key "
                f"config[{key}] — must not appear in skip-spec"
            )


if __name__ == "__main__":  # pragma: no cover
    import sys

    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print(f"PASS  {name}")
            except AssertionError as e:
                failed += 1
                print(f"FAIL  {name}\n      {e}")
    sys.exit(1 if failed else 0)
