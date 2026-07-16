"""Canonical tiering-profile resolution + gate-invariant validator (#41).

Single source of truth for:
  - tests/test_tiering_profiles.py (executes these)
  - skills/orchemist-run.md § "Tiering profiles" (restates this algorithm in prose)
  - profiles/tiering-profiles.yaml (the data these operate on)
Pure functions, no live LLM, no side effects.
"""
from __future__ import annotations
from pathlib import Path
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
PROFILES_PATH = REPO_ROOT / "profiles" / "tiering-profiles.yaml"
PIPELINES_DIR = REPO_ROOT / "pipelines"

# comic-strip is OUT of #41 (spec fork 1).
IN_SCOPE_PIPELINES = (
    "coding-pipeline-standard.yaml",
    "coding-pipeline-maintenance.yaml",
    "coding-pipeline-skip-spec.yaml",
)
PHASE_CLASSES = ("rote", "interpretive", "implement", "gate")
MODEL_VALUES = ("haiku", "sonnet", "opus", "fable", "inherit")
EFFORT_VALUES = ("low", "medium", "high", "xhigh", "inherit")
# Nothing in the tier vocabulary outranks fable; the gate floor allowlist is exactly {fable}.
GATE_ALLOWLIST = frozenset({"fable"})
# The gate-annotated phase-id set per in-scope pipeline, locked against the real bytes so no one can
# silently re-annotate a fable gate as non-gate and slip it below the floor (test (c0)). Verified
# against pipelines/*.yaml this session: every `model_tier: fable` phase, and only those.
EXPECTED_GATES = {
    "coding-pipeline-standard.yaml":    {"spec_adversary", "test_adversary", "review"},
    "coding-pipeline-maintenance.yaml": {"spec_adversary", "review"},
    "coding-pipeline-skip-spec.yaml":   {"acceptance_test_adversary", "review"},
}


class GateInvariantError(ValueError):
    """Raised when a profile would tier a `gate`-class phase below fable."""


def load_profiles(path: Path = PROFILES_PATH) -> dict:
    return yaml.safe_load(path.read_text())["profiles"]


def load_pipeline(name: str) -> dict:
    return yaml.safe_load((PIPELINES_DIR / name).read_text())


def resolve(phase: dict, profile: dict) -> dict:
    """Resolve {model, effort} for a phase under a profile.

    model 'inherit'  -> the phase's declared model_tier (explicit fallback).
    effort 'inherit' -> None (session-inherited; the Agent path has no per-dispatch knob).
    Raises KeyError if the profile omits the phase's phase_class.
    """
    entry = profile[phase["phase_class"]]      # KeyError => incomplete profile (a failure)
    model = entry["model"]
    if model == "inherit":
        model = phase.get("model_tier")
    effort = entry["effort"]
    if effort == "inherit":
        effort = None
    return {"model": model, "effort": effort}


def assert_gate_floor(phases: list[dict], profile: dict) -> None:
    """Raise GateInvariantError if any gate-class phase resolves below fable."""
    for phase in phases:
        if phase.get("phase_class") == "gate":
            model = resolve(phase, profile)["model"]
            if model not in GATE_ALLOWLIST:
                raise GateInvariantError(
                    f"profile tiers gate phase {phase['id']!r} to {model!r}, below the fable floor"
                )


def llm_phases(pipeline_doc: dict) -> list[dict]:
    """Phases carrying a model_tier (skips inert task_type engine/command phases)."""
    return [p for p in pipeline_doc.get("phases", []) if "model_tier" in p]
