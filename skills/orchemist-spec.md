---
name: orchemist:spec
description: Phase 1a of the Orchemist coding pipeline (spec loop). Interprets a GitHub issue into an implementation plan (Section B only) anchored to GROUND TRUTH. Does not write behavioral contracts. Delegates to a fresh general-purpose subagent so the spec writer's context does not leak into downstream behavioral / adversary phases. Triggers when /orchemist:spec is invoked or when /orchemist:run advances to the spec phase.
---

# Implementation Spec phase

This skill is a thin wrapper that delegates to a fresh `general-purpose` subagent. The spec writer MUST run in its own context window so that downstream phases (behavioral, adversary) review work that wasn't drafted in the orchestrator's main context. Per [[feedback_fresh_subagent_per_phase]] — the fresh-context-window property is non-negotiable; do NOT execute the prompt inline.

## Step 1 — Delegate to the subagent

Use the `Agent` (Task) tool to spawn a `general-purpose` subagent. Pass it the following prompt (verbatim — DO NOT summarise; the GROUND TRUTH anchor and revision rules are load-bearing):

---

[PIPELINE CONTEXT] You are executing the SPEC phase (1a/3) of the spec loop. Your output feeds the BEHAVIORAL phase — not the adversary directly. Write implementation guidance only. Do not write behavioral contracts. Do not ask questions or send messages. [/PIPELINE CONTEXT]

You are a senior developer interpreting a GitHub issue into an implementation plan.

## GROUND TRUTH — The Issue You Are Implementing
**Title:** {{config.issue_title}}
**Body:** {{config.issue_body}}

Your implementation spec MUST be about this issue. Do NOT write a spec for any other system or feature.

## Repository
**Path:** {{config.repo_path}}
**Branch:** {{config.branch_name}}
**Language:** {{config.language}}

## Codebase Context
{{config.files_context}}

## Previous Work
{{phase_summary}}

## Prior Rounds
{{iteration_history}}

## Iteration Context
If prior rounds exist above, this is a REVISION round. The adversary flagged issues with the behavioral contracts AND/OR the implementation plan. Read the adversary's findings and adjust your implementation guidance to support any tightened contracts.
If no prior rounds exist, this is round 1.

## Task
Produce an implementation spec containing ONLY Section B (implementation guidance). Do NOT write behavioral contracts — a separate agent handles that.

### Section B: Implementation Guidance
1. **Problem Statement** — What exactly needs to change and why
2. **Files to Modify** — List each file with what changes are needed
3. **Files to Create** — Any new files with their purpose
4. **Implementation Steps** — Ordered steps, specific enough to code from
5. **Risk Assessment** — What could break, backward compatibility concerns
6. **Observable Outcomes** — For each change, describe what a user/caller can observe (exit codes, stdout content, return values, error messages). The behavioral agent will use these to write tight contracts.

Be specific. Reference actual file paths and function names from the codebase context.

**CRITICAL INSTRUCTIONS FOR REVISION ROUNDS:**
1. Read the EXISTING file at `{{output_dir}}/spec.md`
2. Read the adversary's findings from the most recent round above
3. Fix ONLY the sections related to adversary findings — do not rewrite unflagged sections
4. Implementation steps the adversary did NOT flag MUST remain byte-identical
5. If findings relate to implementation details leaking into behavioral contracts, adjust your spec to clearly separate observable outcomes from internal implementation
6. If findings relate to missing edge cases, add implementation steps for those cases and describe their observable outcomes
7. If findings relate to divergence between spec and behavioral contracts, update your spec to match

Think of this as a code review fix: apply the minimum targeted edit. Do not refactor the whole file.
A full rewrite wastes tokens and loses adversary-approved content. Surgical edits only.

## Output contract
Write exactly ONE file to `.orchemist/runs/<run-id>/spec.md` (this is `{{output_dir}}/spec.md`). The file must contain only the implementation spec body — no orchestration metadata. On success, end the file with the verdict word `success` on its own line.

---

## Step 2 — Verify subagent output

After the subagent returns, verify that `{{output_dir}}/spec.md` exists and ends with the verdict word `success`. If the subagent failed to write the file (or wrote malformed output), write the following safe-default to `{{output_dir}}/spec.md` yourself:

```
spec subagent returned no recognisable output — defaulting to failed for safety.

failed
```

This routes the pipeline back through the spec phase on the next iteration. Do NOT run the spec inline as a fallback — per [[feedback_fresh_subagent_per_phase]], the fresh-context-window property is non-negotiable.
