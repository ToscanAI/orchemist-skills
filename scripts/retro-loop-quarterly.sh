#!/usr/bin/env bash
# retro-loop-quarterly.sh — Orchemist Skills Pack quarterly retro-loop driver
#
# Run from the orchemist-skills repo root. Iterates over each consumer in
# docs/retro/CONSUMERS.txt, runs the added-line duplication scan over that
# consumer's trailing-90-day merged PRs, and emits findings to
# docs/retro/RETROSPECTIVE-<YYYY-Q<N>>.md from the template.
#
# Scaffolding phase (#7): emits the Scope section + a Findings skeleton only.
# The real 90-day PR scan and LLM candidate classification are a deliberate
# follow-up; a missing/unauthenticated gh degrades gracefully (SKIP note, not a
# hard error).
#
# Usage:
#   bash scripts/retro-loop-quarterly.sh <YYYY-Q<N>>   # e.g. 2026-Q2
#   bash scripts/retro-loop-quarterly.sh --help        # print usage, exit 0

set -euo pipefail

# ── Usage text ───────────────────────────────────────────────────────────────
usage() {
  cat <<'EOF'
usage: bash scripts/retro-loop-quarterly.sh <YYYY-Q<N>>

Run from the orchemist-skills repo root. Iterates over each consumer in
docs/retro/CONSUMERS.txt, runs the duplication scan over that consumer's
trailing-90-day merged PRs, and emits findings to
docs/retro/RETROSPECTIVE-<YYYY-Q<N>>.md.

Arguments:
  <YYYY-Q<N>>   Target quarter, e.g. 2026-Q2 (N is 1-4).
  -h, --help    Print this message and exit 0 (no network).
EOF
}

# ── Parse args BEFORE any path/network work (usage errors must not be masked) ─
QUARTER=""
case "${1:-}" in
  -h|--help)
    usage
    exit 0
    ;;
  "")
    echo "error: missing required <YYYY-Q<N>> argument (e.g. 2026-Q2)" >&2
    usage >&2
    exit 2
    ;;
  *)
    QUARTER="$1"
    ;;
esac

# ── Validate quarter format: YYYY-Q<N>, N in 1-4 ─────────────────────────────
if [[ ! "$QUARTER" =~ ^[0-9]{4}-Q[1-4]$ ]]; then
  echo "error: invalid quarter '$QUARTER' — expected form YYYY-Q<N> (N is 1-4), e.g. 2026-Q2" >&2
  exit 2
fi

# ── Locate repo root (this script lives in scripts/, root is its parent) ──────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RETRO_DIR="$REPO_ROOT/docs/retro"
CONSUMERS_FILE="$RETRO_DIR/CONSUMERS.txt"
TEMPLATE_FILE="$RETRO_DIR/RETROSPECTIVE-TEMPLATE.md"
OUTPUT_FILE="$RETRO_DIR/RETROSPECTIVE-$QUARTER.md"

# ── Pre-flight: required inputs must exist ───────────────────────────────────
if [ ! -f "$CONSUMERS_FILE" ]; then
  echo "error: $CONSUMERS_FILE not found — the consumer registry is required" >&2
  exit 1
fi
if [ ! -f "$TEMPLATE_FILE" ]; then
  echo "error: $TEMPLATE_FILE not found — the retrospective template is required" >&2
  exit 1
fi

# ── Refuse to clobber an existing retro (MVP: no --force) ─────────────────────
if [ -e "$OUTPUT_FILE" ]; then
  echo "error: $OUTPUT_FILE already exists — refusing to overwrite (remove it first to regenerate)" >&2
  exit 1
fi

# ── Read consumers (skip blank lines and #-comments) ─────────────────────────
CONSUMERS=()
while IFS= read -r line || [ -n "$line" ]; do
  line="${line#"${line%%[![:space:]]*}"}"   # ltrim
  line="${line%"${line##*[![:space:]]}"}"   # rtrim
  [ -z "$line" ] && continue
  case "$line" in
    \#*) continue ;;
  esac
  CONSUMERS+=("$line")
done < "$CONSUMERS_FILE"

if [ "${#CONSUMERS[@]}" -eq 0 ]; then
  echo "error: no consumers found in $CONSUMERS_FILE" >&2
  exit 1
fi

# ── Compute the trailing-90-day window (GNU date on the Linux runner) ────────
WINDOW_END="$(date +%Y-%m-%d)"
WINDOW_START="$(date -d '90 days ago' +%Y-%m-%d)"

# ── dup_lint <base> <head> — canonical §7.2 added-block duplication lint ──────
# Emits each added line (50+ chars) that appears 2+ times across the base...head
# diff. Reused per consumer PR. Empty output (0 duplicates) is a NORMAL, passing
# result — the trailing `|| true` keeps set -e/pipefail from treating a no-match
# grep as a hard failure.
dup_lint() {
  local base="$1"
  local head="$2"
  git diff "$base...$head" -- '*.ts' '*.tsx' '*.js' '*.jsx' '*.py' '*.go' '*.rs' '*.java' '*.kt' '*.swift' \
    | grep '^+' | grep -v '^+++' \
    | sed 's/^+//' \
    | sort | uniq -c | awk '$1 >= 2 && length($0) > 50' \
    || true
}

# ── gh availability probe (network work degrades gracefully) ─────────────────
GH_OK=1
if ! command -v gh >/dev/null 2>&1; then
  GH_OK=0
  echo "SKIP: gh unavailable/unauthenticated — emitting skeleton only (gh not on PATH)." >&2
elif ! gh auth status >/dev/null 2>&1; then
  GH_OK=0
  echo "SKIP: gh unavailable/unauthenticated — emitting skeleton only (no token)." >&2
fi

# ── Per-consumer scan (deferred: real PR enumeration is a follow-up) ──────────
for consumer in "${CONSUMERS[@]}"; do
  echo "scanning consumer: $consumer (window $WINDOW_START .. $WINDOW_END)"
  if [ "$GH_OK" -eq 0 ]; then
    echo "  SKIP: gh unavailable/unauthenticated — no PRs enumerated for $consumer" >&2
    continue
  fi
  # Deferred real scan (NOT executed in the scaffolding phase). Wiring a
  # GH_TOKEN with consumer-repo read + populating Findings is a follow-up:
  #   prs="$(gh pr list -R "$consumer" --state merged \
  #            --search "merged:>=$WINDOW_START" \
  #            --json number,mergeCommit,baseRefName --limit 200 2>/dev/null || true)"
  #   # for each PR: dup_lint "<base-sha>" "<head-sha>"
  :
done

# ── Emit the retro from the template: fill Scope, leave Findings as skeleton ──
cp "$TEMPLATE_FILE" "$OUTPUT_FILE"
consumers_csv="$(IFS=,; echo "${CONSUMERS[*]}")"
sed -i \
  -e "s|# Quarterly retrospective — <YYYY-Q<N>> (<YYYY-MM-DD> scan)|# Quarterly retrospective — $QUARTER ($WINDOW_END scan)|" \
  -e "s|- Consumers scanned: <repo-1>, <repo-2>, ...|- Consumers scanned: $consumers_csv|" \
  -e "s|- Time window: <YYYY-MM-DD> to <YYYY-MM-DD> (PRs merged in the trailing 90 days).|- Time window: $WINDOW_START to $WINDOW_END (PRs merged in the trailing 90 days).|" \
  -e "s|- PRs scanned: <N> (list at end).|- PRs scanned: (not scanned — scaffolding phase) (list at end).|" \
  "$OUTPUT_FILE"

echo ""
echo "Wrote $OUTPUT_FILE"
echo "Scope filled (consumers + window). Findings left as a skeleton — the real"
echo "90-day PR scan is a deferred follow-up."
echo "Next step: wire a GH_TOKEN with consumer-repo read, run the duplication"
echo "scan per consumer PR, and populate the Findings section."
