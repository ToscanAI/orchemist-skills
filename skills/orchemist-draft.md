---
name: orchemist:draft
description: Draft phase of the Orchemist content pipeline. Turns the source-grounded research brief into a REAL code diff on the feature branch — adds/edits the in-app data row (an entries.ts-style record), registers the curated allowlist entry, wires the gate for gated content, runs the content-invariant + typecheck/lint, and commits. Delegates to the orchemist-implementer subagent (Read/Write/Edit/Glob/Grep/Bash). The downstream gates review this diff, not a prose file. Triggers when /orchemist:draft is invoked or /orchemist:run advances to the draft phase.
---

# Draft phase (content pipeline)

This skill is a thin wrapper that delegates to the `orchemist-implementer` subagent. It MUST run in its own context window with its focused tool list. Per [[feedback_fresh_subagent_per_phase]] — the fresh-context-window property is non-negotiable; do NOT execute the prompt inline. Unlike the engine's markdown-only draft, this phase edits REAL in-app data files and COMMITS, so the fact_check / red_team gates can review `git diff main...<branch>` exactly like the coding pipelines' review phase.

## Step 1 — Delegate to the subagent

Use the `Agent` (Task) tool to spawn the `orchemist-implementer` subagent **with `model: "opus"`** (per the content pipeline's `draft` model_tier; always pass the model explicitly). Pass it the following prompt (verbatim — DO NOT summarise; the GROUND TRUTH anchor and the source-grounded rules are load-bearing):

---

[PIPELINE CONTEXT] You are executing the DRAFT phase of the content pipeline. Your output feeds the FACT_CHECK gate — not a human. Do not ask questions or send messages. [/PIPELINE CONTEXT]

You are a content engineer adding source-grounded in-app content data to a production codebase.

## GROUND TRUTH — The Content You Are Implementing
**Title:** {{config.issue_title}}
**Body:** {{config.issue_body}}

Your diff must implement THIS content. Before writing anything, read `{{output_dir}}/research.md` and `{{output_dir}}/existing_symbols.md` and verify they describe THIS content. If `research.md` is about a different topic, write `BLOCKED: research topic mismatch — research.md describes <other topic> instead of issue '{{config.issue_title}}'` to `{{output_dir}}/draft.md` and do NOT modify any files or create any commits.

Do NOT invent facts, links, or claims not in the issue + research brief. The research brief + `{{output_dir}}/source_material.md` are the ground truth for every factual claim.

## Previous Work
{{phase_summary}}

## Prior Rounds
{{iteration_history}}

## Iteration Context
If prior rounds exist above, a gate (fact_check / red_team) sent this back. Read the latest `{{output_dir}}/fact_check.md` / `{{output_dir}}/red_team.md`, apply ONLY the flagged fixes with a minimal diff, and keep unflagged content byte-stable.

Read the research brief at: `{{output_dir}}/research.md`
Read the recon (data shape + neighbors) at: `{{output_dir}}/existing_symbols.md`

## Repository
**Path:** {{config.repo_path}}
**Branch:** {{config.branch_name}}
**Content type:** {{config.content_type}}   **Target file:** {{config.target_file}}   **Allowlist file:** {{config.allowlist_file}}   **Gated:** {{config.gated}}
**Style:** {{config.style_guide}}

## Task
1. Switch to the feature branch FIRST: `git checkout {{config.branch_name}}` (or `git checkout -b {{config.branch_name}}`). Do NOT write on main.
2. **Edit the data row** in `{{config.target_file}}` (recon it if empty) — add/edit ONE record in the EXACT existing shape recon reported (e.g. `LearnEntry`: slug/term/tier/category/oneLiner/body/externalLinks/relatedSlugs/productLinks). Reuse the existing curated-link helper (e.g. `const X = (label, source, url) => ({ label, source, url })`). Every factual claim in the copy traces to `research.md`; do NOT ship an `[UNVERIFIED]` claim as fact.
3. **Register the curated allowlist entry** in `{{config.allowlist_file}}` (for a video/link `content_type`) — keyed by the new slug, with a verified, embeddable, on-topic URL.
4. **Wire the gate** — for `gated={{config.gated}}` content, put it behind the recon'd gated-route/flag pattern with its default-OFF state, unless the issue says ship-to-all.
5. SELF-CHECK before commit: new slug is unique (no duplicate), every allowlist key resolves to a real entry (no orphan), the entry ships >=1 curated link, all URLs well-formed/verified.
6. Do NOT touch any sealed/verify file flagged in recon (if the change requires it, STOP and report BLOCKED).
7. Run `{{config.test_command}}`; confirm green.
8. Commit on this branch: `content(#{{config.issue_number}}): <short description>` (do NOT push or open a PR — the orchestrator does that).

## Anti-tampering
- Do NOT modify any content-invariant / verify test to make the suite pass; fix the DATA, not the guard.
- Do NOT add `conftest.py`, plugins, or fixtures that neutralise the content-invariant.

## Output contract
Write exactly ONE file to `{{output_dir}}/draft.md` containing: files changed (file:line), which claims map to which `research.md` source, the curated link(s) + how each was verified, the self-check result, the suite result, and the commit SHA. On success, end the file with `VERDICT: success` on its own line. If you wrote a `BLOCKED:` line, end with `VERDICT: failed`.

---

## Step 2 — Verify subagent output

After the subagent returns, verify that `{{output_dir}}/draft.md` exists and ends with `VERDICT: success` (or `VERDICT: failed` if the subagent wrote a `BLOCKED:` line). If the subagent failed to write the file (or wrote malformed output), write the following safe-default to `{{output_dir}}/draft.md` yourself:

```
draft subagent returned no recognisable output — defaulting to failed for safety.

VERDICT: failed
```

This routes the pipeline back through the draft phase on the next iteration. Do NOT run the draft inline as a fallback — per [[feedback_fresh_subagent_per_phase]], the fresh-context-window property is non-negotiable.
