---
name: orchemist:existing-symbols-inventory
description: Phase 0 of the Orchemist coding pipeline. Greps the project for existing UI primitives, shared libraries, adjacent action/hook patterns, and workspace-barrel exports. Writes a sticky `existing_symbols.md` artifact read by every subsequent phase. Resolves the late-catch problem for sub-check 7d (re-implementation of existing symbol). Delegates to a fresh general-purpose subagent — general-purpose is MANDATORY because the agent must write to disk; read-only subagent types like Explore cannot satisfy the file-write contract. Triggers when /orchemist:existing-symbols-inventory is invoked or /orchemist:run advances to the existing_symbols_inventory phase.
---

# Existing-symbols inventory (Phase 0, sub-check 7d pre-flight)

This skill is a thin wrapper that delegates to a fresh `general-purpose` subagent.

**Why `general-purpose` is mandatory:** the Phase 0 prompt instructs the subagent to write `{{output_dir}}/existing_symbols.md` to disk. Read-only subagent types (notably Claude Code's `Explore`, which has no Write/Edit tool) cannot satisfy that contract and silently break the file-write invariant that every downstream phase (SPEC, BEHAVIORAL, SPEC_ADVERSARY, IMPLEMENT, REVIEW, FIX) depends on. See ToscanAI/orchemist-skills#9 (field report) and ToscanAI/orchemist#903 (upstream contract).

Per [[feedback_fresh_subagent_per_phase]] — the fresh-context-window property is non-negotiable; do NOT execute the prompt inline.

## Step 1 — Delegate to the subagent

Use the `Agent` (Task) tool to spawn a `general-purpose` subagent. Pass it the following prompt (verbatim — DO NOT summarise; the GROUND TRUTH anchor, the write-to-disk instruction, and the structured output schema are all load-bearing):

---

[PIPELINE CONTEXT] You are executing the EXISTING_SYMBOLS_INVENTORY phase (Phase 0). Your output feeds every subsequent phase. Do not ask questions or send messages. [/PIPELINE CONTEXT]

You are a codebase-survey specialist. Your job is to produce a STRUCTURED inventory of existing symbols (UI primitives, shared libraries, adjacent action/hook patterns, workspace barrels) so downstream phases can CONSUME rather than RE-AUTHOR them.

## GROUND TRUTH — The Issue This Inventory Serves
**Title:** {{config.issue_title}}
**Body:** {{config.issue_body}}

The inventory you produce must surface symbols RELEVANT to this issue (don't dump the entire codebase — focus on symbols a SPEC author would plausibly want to use when implementing this feature).

## Repository
**Path:** {{config.repo_path}}
**Language:** {{config.language}}

## Grep targets (from config; newline-separated globs)

### UI primitives
{{config.ui_primitive_paths}}

### Project shared libraries
{{config.lib_paths}}

### Adjacent action / hook / route patterns
{{config.action_dirs}}

### Workspace barrels
{{config.workspace_barrels}}

If a section's config input is EMPTY, write the section header + a single line `(empty — consumer did not provide inventory inputs for this category)` and move to the next section. Downstream phases will treat the empty section as "no constraint" but still benefit from the non-empty ones.

## Task

For each non-empty section, expand the globs (use `ls`, `find`, or shell glob expansion via Bash), then for each matching file extract the exported public symbols. Recommended pattern per language:

- **TypeScript / JavaScript**: grep `^export (const|function|class|interface|type|default)`; record symbol name + the file it's exported from.
- **Python**: grep `^def `/`^class ` at module top-level + scan `__all__` if present.
- **Go**: grep `^func [A-Z]`/`^type [A-Z]` (capitalized = public); scan package barrels.
- **For UI primitives**: extract component name + props-type name + the file path so SPEC can reference precisely (e.g. `Dialog` from `packages/ui/src/components/dialog.tsx` with `DialogProps` type).

Aim for a curated, high-signal inventory:
- ≤ 50 entries per section (if a section has >50 candidates, group them or filter to most-likely-relevant).
- Each entry: `<symbol-name>` ← `<file-path>:<line>` ← (optional) one-line description.
- For UI primitives: include the prop-type name AND any variants/options (so SPEC can reference `<Badge variant="..." />` shapes precisely).
- For adjacent action patterns: extract the canonical try/catch/auth/ownership boilerplate as a code-snippet anchor (file:line range), so SPEC + IMPLEMENT can `mirror byte-shape`.

## Output

Write your inventory to `{{output_dir}}/existing_symbols.md`. Use this exact section structure (so downstream phases have stable anchors):

````markdown
# Existing-symbols inventory for issue #{{config.issue_number}}

Inventory date: <ISO-8601 date>
Repository: {{config.repo_path}}
Issue: {{config.issue_title}}

## 1. UI primitives (consume — do NOT re-author)

<one entry per primitive, OR `(empty — consumer did not provide inventory inputs)` if the config input is empty>

## 2. Project shared libraries

<one entry per exported helper, OR empty stub>

## 3. Adjacent action / hook / route patterns (mirror byte-shape)

<one entry per pattern + the file:line range to mirror, OR empty stub>

## §3a. Pre-existing dual-path helpers (regex heuristic, may have false positives)

For every helper in §2 (project shared libraries) whose body contains a multi-branch return (regex heuristic: `grep -B 8 "return [^;]*;" <file> | grep "if (" | head -50`), record the `file:line` and a one-line description of WHY the branching exists (e.g. "SB#2 fixture carve-out + production fallback"). Acknowledged false-positive rate: legitimate guard-clause patterns will surface here too. SPEC reads this list and considers EXTEND-ing an existing dual-path helper (per the EXTEND verdict in §5) before authoring a new one — particularly when the new use site needs the same multi-branch shape (e.g. fixture-stub short-circuit + production fallback). The §3a sub-section is OPTIONAL: if §2 is empty OR the regex returns nothing, write `(empty — no multi-branch helpers in shared libraries OR §2 inventory is empty)` and downstream phases treat as "no constraint".

<one entry per dual-path helper + the file:line + branching rationale, OR empty stub>

## 4. Workspace barrels (consumable cross-package imports)

<one entry per exported package symbol, OR empty stub>

## 5. Consume-vs-author guidance (sub-check 7d enforcement)

Per sub-check 7d (HARD RULE in IMPLEMENT phase): before authoring ANY new symbol that overlaps with sections 1-4 above, downstream agents MUST pick exactly one of four verdicts per overlap:

1. **CONSUME** (preferred) — import the existing symbol byte-identical, no signature change. SPEC's Files-to-Modify lists the import-add at the call site; nothing else changes.
2. **EXTEND** (added v4.2, 2026-05-24; §3a wired in v4.3, 2026-05-26) — parameterize the existing symbol (add an options arg / safe-superset wrapper / accept a path or callback) so the existing call site AND the new call site both consume the same source. The existing symbol moves nowhere; its contract widens. SPEC's Files-to-Modify describes the parameterization in Implementation Steps; SPEC's Files-to-Create lists nothing new. Use when CONSUME is "almost" but the new use site needs one more arg / one slightly different code path. This was the dominant Wave 5/6 pattern in ToscanAI/value-investing: N5-1 took a private fixture loader and added a `fixturePath` parameter so 5 panel modules shared it instead of inlining 5 copies of the 16-field AnnualFacts builder. **Includes EXTEND-ing an existing dual-path helper surfaced in §3a** — when the new use site needs the same multi-branch shape an existing helper already implements (e.g. fixture short-circuit + production fallback), prefer EXTEND over authoring a new dual-path helper that would itself trigger the 7e intra-symbol duplication audit downstream.
3. **DIVERGENT** — a near-equivalent that has a contract-required difference (different sort order, different precision, different sealed string). NOT duplication — but the spec MUST include a `## Divergence justification` subsection naming the existing symbol and the contract-required difference. SPEC's Files-to-Create lists the new symbol with a clear divergence rationale.
4. **BLOCKED** — if consume / extend are both impossible (e.g. cross-package boundary not in scope, the existing copy is test-scope but you need prod-scope), return: `BLOCKED: 7d-duplication — <new-symbol> duplicates <existing path:line>; consolidating needs <shared module> not in the spec; recommend spec amendment.` Route back to the orchestrator for a scope decision.

Verdict labels (CONSUME / EXTEND / DIVERGENT / BLOCKED) appear in §6 below + are quoted verbatim by SPEC + SPEC_ADVERSARY + REVIEW for stable cross-phase tracking.

## 6. SPEC's proposed new symbols (filled in by Phase 1a SPEC; cross-checked at every subsequent phase)

Each entry uses this format so verdicts are scannable:

```
- **<symbol-name>** (verdict: CONSUME | EXTEND | DIVERGENT | NEW-OK)
  Existing: <path:line or "(none — genuinely new)">
  Rationale: <one line>
```

NEW-OK = genuinely new; no overlap with sections 1-4. Use only when grep returned zero plausibly-related symbols.

<initially empty; SPEC adds entries as it authors new files/symbols>
````

Be terse: this file is read by every downstream agent, so concision matters. Aim for ≤ 200 lines total.

## CRITICAL: do NOT make up symbols

Only record symbols you have empirically verified via grep / find / cat. Do NOT speculate. If a section is empty (config input absent OR globs match nothing), use the stub line — do NOT invent placeholder entries.

**Glob is unreliable in worktrees (v4.4).** Expand the grep targets and verify existence with `Grep` or `Bash` (`ls` / `find` / `grep -r`) — NOT the `Glob` tool. In worktree checkouts `Glob` has returned empty for files that demonstrably exist; an empty `Glob` is NOT proof a path is absent. A section wrongly stubbed as empty because `Glob` missed real files removes a real reuse constraint from every downstream phase. When a config-provided path appears to match nothing, re-confirm with `ls`/`find` before writing the empty stub.

After writing the file, respond with a brief 3-line summary:
1. Total symbols inventoried per section (e.g. "UI: 18, Lib: 4, Actions: 7, Barrels: 12")
2. Highest-signal entries the SPEC author should consider for this issue
3. Any grep target where the config input pointed at a non-existent path (orchestrator escalation candidate)

End your response with the verdict word `success` on its own line.

---

## Step 2 — Verify subagent output and write the verdict file

After the subagent returns:

1. **Verify the inventory artifact.** Check that `{{output_dir}}/existing_symbols.md` exists and is non-empty. (This is the file every downstream phase consumes — its presence on disk is the actual success criterion, not anything the subagent says in its response text.)

2. **Write the orchestrator-readable verdict file.** The orchestrator reads `{{output_dir}}/existing_symbols_inventory.md` (matching the `<phase.id>.md` convention) to extract the phase verdict — separate from the `existing_symbols.md` artifact. Write one of:

   - **Success case** — if `existing_symbols.md` exists AND is non-empty AND the subagent's response ends with `success`, write to `{{output_dir}}/existing_symbols_inventory.md`:

     ```
     Phase 0 (existing_symbols_inventory) complete — inventory written to {{output_dir}}/existing_symbols.md.

     <paste the subagent's 3-line summary here for the orchestrator's run log>

     VERDICT: success
     ```

   - **Failure case** — if `existing_symbols.md` is missing OR empty OR the subagent's response is malformed, write to `{{output_dir}}/existing_symbols_inventory.md`:

     ```
     Phase 0 (existing_symbols_inventory) failed — inventory not written or malformed.

     VERDICT: failed
     ```

     ALSO write a minimal stub to `{{output_dir}}/existing_symbols.md` so downstream phases (which read this file unconditionally) get the graceful-degradation empty-sections fallback:

     ````markdown
     # Existing-symbols inventory — phase exhausted

     Phase 0 failed to produce a valid inventory.

     ## 1. UI primitives (consume — do NOT re-author)
     (empty — phase exhausted)

     ## 2. Project shared libraries
     (empty — phase exhausted)

     ## 3. Adjacent action / hook / route patterns (mirror byte-shape)
     (empty — phase exhausted)

     ## §3a. Pre-existing dual-path helpers
     (empty — phase exhausted)

     ## 4. Workspace barrels (consumable cross-package imports)
     (empty — phase exhausted)

     ## 5. Consume-vs-author guidance (sub-check 7d enforcement)
     (see canonical pipeline YAML — agents fall back to ad-hoc grep per the empty-section short-circuit)

     ## 6. SPEC's proposed new symbols
     (initially empty)
     ````

The `failed` verdict routes the pipeline back through Phase 0 (per `transitions.failed: existing_symbols_inventory` in the pipeline YAML). After `max_iterations: 2` rounds the pipeline reaches `transitions.exhausted: spec` (graceful degradation — SPEC and downstream phases read the empty stub and revert to ad-hoc grep). To enable HARD GATE behaviour (HALT on Phase 0 exhaustion instead of falling through), set `admin.feature_flags.phase0_hard_gate=True` in `~/.orchestration-engine/admin.json` (mirrors the engine wiring from ToscanAI/orchemist#840).

Do NOT run the Phase 0 prompt inline as a fallback — per [[feedback_fresh_subagent_per_phase]], the fresh-context-window property is non-negotiable.
