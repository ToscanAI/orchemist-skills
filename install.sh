#!/usr/bin/env bash
# install.sh — Orchemist Skills Pack installer
#
# Idempotent installer: copies skills/*.md to ~/.claude/skills/
# and agents/*.md to ~/.claude/agents/. Backs up any existing files
# to <name>.bak.<timestamp> before overwrite. Running twice is safe:
# the second run produces identical state.
#
# Usage:
#   ./install.sh            # install into ~/.claude/
#   CLAUDE_HOME=/tmp/c ./install.sh   # install into a custom location

set -euo pipefail

# ── Locate repo root (directory of this script) ──────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILLS_SRC="$SCRIPT_DIR/skills"
AGENTS_SRC="$SCRIPT_DIR/agents"
PIPELINES_SRC="$SCRIPT_DIR/pipelines"

# ── Resolve install target ───────────────────────────────────────────────────
CLAUDE_HOME="${CLAUDE_HOME:-$HOME/.claude}"
SKILLS_DST="$CLAUDE_HOME/skills"
AGENTS_DST="$CLAUDE_HOME/agents"
PIPELINES_DST="$CLAUDE_HOME/skills/orchemist/pipelines"

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

mkdir -p "$SKILLS_DST" "$AGENTS_DST" "$PIPELINES_DST"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

# ── install_file SRC DST ──────────────────────────────────────────────────────
# Copies SRC -> DST. If DST exists and is byte-identical to SRC, skip silently.
# If DST exists and differs, back up DST to DST.bak.<timestamp> then copy.
install_file() {
  local src="$1"
  local dst="$2"
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
  fname="$(basename "$src")"
  install_file "$src" "$SKILLS_DST/$fname"
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

# ── Summary ──────────────────────────────────────────────────────────────────
echo ""
echo "Orchemist Skills Pack installed:"
echo "  $SKILL_COUNT skill(s)       in $SKILLS_DST"
echo "  $AGENT_COUNT subagent(s)    in $AGENTS_DST"
echo "  $PIPELINE_COUNT pipeline YAML(s) in $PIPELINES_DST"
echo ""
echo "Next step: run 'claude' inside any git repo and try"
echo "  /orchemist:run examples/example-issue.md"
echo "(replace the path with your own issue file once you're ready)."
