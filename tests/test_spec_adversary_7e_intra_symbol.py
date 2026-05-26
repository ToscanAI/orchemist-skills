"""Regression test — issue #6 acceptance criterion #6.

Verifies that the SPEC_ADVERSARY phase's prompt_template (after the 7e
edit lands) contains the canonical 7e intra-symbol duplication audit
language, AND that the fixture SPEC reproduces the value-investing#449
dual-path SQL pattern that 7e is designed to surface.

This is a PROMPT-RENDERING-ONLY test (no live Opus call): per the issue's
explicit cost-tolerance note, the integration-level test (render prompt
against Opus + assert verdict surfaces `[divergence] F.X — intra-symbol
duplication`) is too expensive for CI. Consumers wanting the live verification
can follow the manual-reproduction protocol in `tests/README.md`.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINE_YAML = REPO_ROOT / "pipelines" / "coding-pipeline-standard.yaml"
FIXTURE_SPEC = REPO_ROOT / "tests" / "fixtures" / "spec-with-intra-duplication.md"


def _load_spec_adversary_prompt() -> str:
    """Parse the pipeline YAML and return the spec_adversary phase's prompt_template."""
    with PIPELINE_YAML.open() as f:
        doc = yaml.safe_load(f)
    for phase in doc["phases"]:
        if phase["id"] == "spec_adversary":
            return phase["prompt_template"]
    raise KeyError("spec_adversary phase not found in pipeline YAML")


def test_spec_adversary_includes_7e_heading() -> None:
    """7e block exists in SPEC_ADVERSARY prompt with the canonical heading."""
    prompt = _load_spec_adversary_prompt()
    assert "### 7e — Intra-symbol duplication audit" in prompt, (
        "SPEC_ADVERSARY prompt missing 7e sub-check heading"
    )


def test_spec_adversary_7e_names_producer_variant() -> None:
    """7e block explicitly identifies itself as the producer-side variant of 7d."""
    prompt = _load_spec_adversary_prompt()
    assert "producer-side variant" in prompt, (
        "SPEC_ADVERSARY 7e block must explicitly name producer-side variant"
    )


def test_spec_adversary_7e_specifies_finding_format() -> None:
    """Adversary findings must use the [divergence] F.X — intra-symbol duplication format."""
    prompt = _load_spec_adversary_prompt()
    assert "[divergence] F.X — intra-symbol duplication" in prompt, (
        "SPEC_ADVERSARY 7e block must specify the canonical finding format"
    )


def test_fixture_spec_exists_with_dual_path_sql() -> None:
    """Fixture SPEC reproduces value-investing#449's intra-file SQL duplication."""
    assert FIXTURE_SPEC.exists(), f"Fixture SPEC missing at {FIXTURE_SPEC}"
    body = FIXTURE_SPEC.read_text()
    # The fixture's Implementation Steps must contain two steps with byte-identical
    # SQL blocks (the await db<…> dual-path pattern from value-investing#449).
    sql_count = body.count("SELECT id::text AS id, name FROM companies WHERE ticker")
    assert sql_count >= 2, (
        f"Fixture SPEC must reproduce the dual-path SQL pattern "
        f"(≥2 occurrences; found {sql_count})"
    )
    # The fixture must NOT contain a §B.5.x divergence justification — otherwise
    # the 7e check would correctly short-circuit and the regression target disappears.
    assert "Divergence justification" not in body, (
        "Fixture SPEC must NOT contain a divergence justification "
        "(otherwise the 7e check would short-circuit)"
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
