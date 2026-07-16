#!/usr/bin/env bash
# install.sh — Orchemist Skills Pack installer
#
# Idempotent installer: copies skills/*.md to ~/.claude/skills/<name>/SKILL.md
# and agents/*.md to ~/.claude/agents/. Backs up any existing files
# to <name>.bak.<timestamp> before overwrite. Running twice is safe:
# the second run produces identical state.
#
# Usage:
#   ./install.sh            # install into ~/.claude/
#   ./install.sh --check    # dry-run: verify install is in sync, write nothing
#   CLAUDE_HOME=/tmp/c ./install.sh   # install into a custom location

set -euo pipefail

# ── Parse args (BEFORE pre-flight so an unknown flag deterministically exits 2,
#    regardless of cwd or whether source dirs exist — a usage error must not be
#    masked by a pre-flight exit 1). Use ${1:-} for set -u safety. ─────────────
CHECK_ONLY=0
case "${1:-}" in
  --check) CHECK_ONLY=1 ;;
  "")      CHECK_ONLY=0 ;;
  *)       echo "usage: $0 [--check]" >&2; exit 2 ;;
esac

# ── Locate repo root (directory of this script) ──────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_SRC="$SCRIPT_DIR/skills"
AGENTS_SRC="$SCRIPT_DIR/agents"
PIPELINES_SRC="$SCRIPT_DIR/pipelines"
PROFILES_SRC="$SCRIPT_DIR/profiles"
WORKFLOWS_SRC="$SCRIPT_DIR/workflows"

# ── Resolve install target ───────────────────────────────────────────────────
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
SKILLS_DST="$CLAUDE_HOME/skills"
AGENTS_DST="$CLAUDE_HOME/agents"
PIPELINES_DST="$CLAUDE_HOME/skills/orchemist/pipelines"
PROFILES_DST="$CLAUDE_HOME/skills/orchemist/profiles"
WORKFLOWS_DST="$CLAUDE_HOME/workflows"

# ── Pre-flight ────────────────────────────────────────────────────────────────
if [ ! -d "$SKILLS_SRC" ]; then
  echo "error: $SKILLS_SRC not found — run this script from the orchemist-skills repo root" >&2
  exit 1
fi
if [ ! -d "$AGENTS_SRC" ]; then
  echo "error: $AGENTS_SRC not found — run this script from the orchemist-skills repo root" >&2
  exit 1
fi
if [ ! -d "$PIPELINES_SRC" ]; then
  echo "error: $PIPELINES_SRC not found — run this script from the orchemist-skills repo root" >&2
  exit 1
fi
if [ ! -d "$PROFILES_SRC" ]; then
  echo "error: $PROFILES_SRC not found — run this script from the orchemist-skills repo root" >&2
  exit 1
fi
if [ ! -d "$WORKFLOWS_SRC" ]; then
  echo "error: $WORKFLOWS_SRC not found — run this script from the orchemist-skills repo root" >&2
  exit 1
fi

if [ "$CHECK_ONLY" -eq 0 ]; then
  mkdir -p "$SKILLS_DST" "$AGENTS_DST" "$PIPELINES_DST" "$PROFILES_DST" "$WORKFLOWS_DST"
fi

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

# ── Drift accumulator (used in --check mode only) ─────────────────────────────
MISMATCH_COUNT=0

# ── install_file SRC DST ──────────────────────────────────────────────────────
# Copies SRC -> DST. If DST exists and is byte-identical to SRC, skip silently.
# If DST exists and differs, back up DST to DST.bak.<timestamp> then copy.
install_file() {
  local src="$1"
  local dst="$2"

  # ── --check (dry-run): read-only compare, NEVER write, ALWAYS return 0. ──────
  # Discrepancies are recorded by incrementing MISMATCH_COUNT (data, not a
  # return code) so a single run reports ALL drift without set -e aborting on
  # the first one. cmp -s legitimately returns non-zero on a content diff; it is
  # captured inside the if and must not propagate. The increment uses
  # $((x+1)) (not ((x++)), which returns non-zero when x is 0 and would trip
  # set -e).
  if [ "$CHECK_ONLY" -eq 1 ]; then
    if [ ! -f "$dst" ]; then
      echo "  MISSING: $dst"
      MISMATCH_COUNT=$((MISMATCH_COUNT + 1))
    elif cmp -s "$src" "$dst"; then
      echo "  OK: $dst"
    else
      echo "  MISMATCH: $dst"
      MISMATCH_COUNT=$((MISMATCH_COUNT + 1))
    fi
    return 0
  fi

  # ── install mode: copy SRC -> DST, backing up a differing DST first. ─────────
  if [ -f "$dst" ]; then
    if cmp -s "$src" "$dst"; then
      echo "  unchanged: $dst"
      return 0
    fi
    local backup="${dst}.bak.${TIMESTAMP}"
    cp "$dst" "$backup"
    echo "  backed up: $dst -> $backup"
  fi
  cp "$src" "$dst"
  echo "  installed: $dst"
}

# ── Install skills ────────────────────────────────────────────────────────────
echo "Installing Orchemist skills to $SKILLS_DST"
SKILL_COUNT=0
for src in "$SKILLS_SRC"/*.md; do
  [ -f "$src" ] || continue
  name="$(basename "$src" .md)"          # strip .md → slug, e.g. orchemist-run
  if [ "$CHECK_ONLY" -eq 0 ]; then
    mkdir -p "$SKILLS_DST/$name"         # ensure ~/.claude/skills/<slug>/ exists (install mode only)
  fi
  install_file "$src" "$SKILLS_DST/$name/SKILL.md"
  SKILL_COUNT=$((SKILL_COUNT + 1))
done

# ── Install agents ────────────────────────────────────────────────────────────
echo ""
echo "Installing Orchemist subagents to $AGENTS_DST"
AGENT_COUNT=0
for src in "$AGENTS_SRC"/*.md; do
  [ -f "$src" ] || continue
  fname="$(basename "$src")"
  install_file "$src" "$AGENTS_DST/$fname"
  AGENT_COUNT=$((AGENT_COUNT + 1))
done

# ── Install pipeline YAMLs (skills reference these via /orchemist:run) ────────
echo ""
echo "Installing pipeline YAMLs to $PIPELINES_DST"
PIPELINE_COUNT=0
for src in "$PIPELINES_SRC"/*.yaml; do
  [ -f "$src" ] || continue
  fname="$(basename "$src")"
  install_file "$src" "$PIPELINES_DST/$fname"
  PIPELINE_COUNT=$((PIPELINE_COUNT + 1))
done

# ── Install tiering profiles (consumer model+effort registry, #41) ────────────
echo ""
echo "Installing tiering profiles to $PROFILES_DST"
PROFILE_FILE_COUNT=0
for src in "$PROFILES_SRC"/*.yaml; do
  [ -f "$src" ] || continue
  fname="$(basename "$src")"
  install_file "$src" "$PROFILES_DST/$fname"
  PROFILE_FILE_COUNT=$((PROFILE_FILE_COUNT + 1))
done

# ── Install workflows (JS orchestrators for the Workflow tool) ────────────────
echo ""
echo "Installing workflows to $WORKFLOWS_DST"
WORKFLOW_COUNT=0
for src in "$WORKFLOWS_SRC"/*.js; do
  [ -f "$src" ] || continue
  fname="$(basename "$src")"
  install_file "$src" "$WORKFLOWS_DST/$fname"
  WORKFLOW_COUNT=$((WORKFLOW_COUNT + 1))
done

# ── Summary ──────────────────────────────────────────────────────────────────
if [ "$CHECK_ONLY" -eq 1 ]; then
  echo ""
  echo "Checked: $SKILL_COUNT skill(s), $AGENT_COUNT subagent(s), $PIPELINE_COUNT pipeline YAML(s), $PROFILE_FILE_COUNT tiering profile(s), $WORKFLOW_COUNT workflow(s)"
  if [ "$MISMATCH_COUNT" -gt 0 ]; then
    echo "$MISMATCH_COUNT target(s) out of sync"
    exit 1
  fi
  echo "All targets in sync."
  exit 0
fi

echo ""
echo "Orchemist Skills Pack installed:"
echo "  $SKILL_COUNT skill(s)       in $SKILLS_DST"
echo "  $AGENT_COUNT subagent(s)    in $AGENTS_DST"
echo "  $PIPELINE_COUNT pipeline YAML(s) in $PIPELINES_DST"
echo "  $PROFILE_FILE_COUNT tiering profile(s) in $PROFILES_DST"
echo "  $WORKFLOW_COUNT workflow(s)    in $WORKFLOWS_DST"
echo ""
echo "Next step: run 'claude' inside any git repo and try"
echo "  /orchemist:run examples/example-issue.md"
echo "(replace the path with your own issue file once you're ready)."
