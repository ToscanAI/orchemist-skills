"""Render-smoke test — all pipelines/*.yaml prompt_templates must format() cleanly.

Regression guard for issue #912: a bare `};` in coding-pipeline-standard.yaml's
implement phase prompt_template caused Python str.format() to raise
`ValueError: Single '}' encountered in format string`, silently breaking every
run through that phase.

Design:
  - Iterates every pipelines/*.yaml file.
  - Builds a config dict from config_schema defaults + a set of plausible
    placeholder values (mirrors the approach in test_skip_spec_dedup_parity.py).
  - Uses a SafeDict so that legitimate {config[key]} references that happen not
    to appear in the schema don't mask ValueError with KeyError.
  - .format_map()s every phase prompt_template.
  - Asserts NO ValueError (single-brace escape failure) and NO IndexError.
  - Tolerates KeyError from legitimate {config[unknown_key]} placeholders (the
    SafeDict converts them to harmless literal text).

This test MUST fail on the pre-fix coding-pipeline-standard.yaml (implement
phase had `};` — single un-escaped brace) and pass on the corrected version.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PIPELINES_DIR = REPO_ROOT / "pipelines"
EXAMPLE_ISSUE = REPO_ROOT / "examples" / "example-issue.md"


class SafeDict(dict):
    """dict that returns a placeholder string for missing keys instead of raising KeyError.

    This lets .format_map() succeed for legitimate {config[x]} references
    whose key isn't in config_schema, while still raising ValueError for
    un-escaped single braces.
    """

    def __missing__(self, key: str) -> str:
        return f"<{key}>"


def _build_config(schema: dict) -> dict:
    """Build a config dict from config_schema defaults + standard placeholders."""
    cfg: dict = {}
    # Populate defaults from schema
    for name, spec in schema.get("properties", {}).items():
        if "default" in spec:
            cfg[name] = spec["default"]
    # Standard placeholder values for required/common keys
    placeholders = {
        "issue_title": "Trim whitespace in parseConfig keys",
        "issue_body": EXAMPLE_ISSUE.read_text() if EXAMPLE_ISSUE.exists() else "(example issue)",
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


def _pipeline_phase_ids():
    """Collect (yaml_path, phase_id) pairs for all pipeline files."""
    params = []
    for yaml_path in sorted(PIPELINES_DIR.glob("*.yaml")):
        doc = yaml.safe_load(yaml_path.read_text())
        for phase in doc.get("phases", []):
            if phase.get("prompt_template") is not None:
                params.append((yaml_path, phase["id"]))
    return params


@pytest.mark.parametrize(
    "yaml_path,phase_id",
    _pipeline_phase_ids(),
    ids=lambda x: x.name if isinstance(x, Path) else x,
)
def test_prompt_template_renders_without_value_error(yaml_path: Path, phase_id: str) -> None:
    """Every prompt_template must .format_map() without ValueError or IndexError.

    ValueError means a single un-escaped '{' or '}' exists in the template
    (Python's str.format() raises this for lone braces that don't form a valid
    replacement field). This is the class of bug fixed in issue #912.

    KeyError is tolerated: it means a {config[key]} reference whose key is
    absent from our test config dict — a legitimate runtime placeholder, not
    a broken escape.
    """
    doc = yaml.safe_load(yaml_path.read_text())

    # Find the target phase
    tmpl = None
    for phase in doc["phases"]:
        if phase["id"] == phase_id:
            tmpl = phase["prompt_template"]
            break
    assert tmpl is not None, f"Phase '{phase_id}' not found in {yaml_path.name}"

    cfg = SafeDict(_build_config(doc.get("config_schema", {})))

    kwargs = SafeDict(
        config=cfg,
        output_dir="/tmp/run-out",
        phase_summary="(none)",
        iteration_history="(none)",
        phase_diff="(none)",
    )

    try:
        tmpl.format_map(kwargs)
    except (ValueError, IndexError) as exc:
        raise AssertionError(
            f"{yaml_path.name} phase='{phase_id}' failed to render — "
            f"{type(exc).__name__}: {exc}\n"
            "This indicates an un-escaped single '{{' or '}}' in the template "
            "(fix: double the brace so Python str.format() treats it as a literal)."
        ) from exc
    # KeyError is intentionally NOT caught — it would indicate a missing SafeDict entry
    # which shouldn't happen given our catch-all SafeDict.__missing__. If it does
    # surface, it's a test infrastructure bug worth surfacing loudly.
