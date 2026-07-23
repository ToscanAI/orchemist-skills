---
name: orchemist:fact-check
description: Fact-check GATE of the Orchemist content pipeline (Fable 5). Reviews the draft's committed diff — every factual claim traceable to source_material.md or independently web-verified, every curated link live + on-topic, no dead URL. Returns APPROVE or REQUEST_CHANGES; a wrong fact or dead link BLOCKS and loops back to draft. Delegates to a fresh general-purpose subagent with model fable (NOT the adversary subagent) because it needs WebSearch/WebFetch + Bash (git diff) which the Read/Grep/Glob-only adversary lacks. Also captures the diff to draft_diff.md so the Bash-less red_team can read it. Triggers when /orchemist:fact-check is invoked or /orchemist:run advances to the fact_check phase.
---

# Fact Check gate (content pipeline)

This skill is a thin wrapper that delegates to a fresh `general-purpose` subagent with **`model: "fable"`**. The fact-checker MUST run in its own context window — independent eyes on the diff. Per [[feedback_fresh_subagent_per_phase]] — the fresh-context-window property is non-negotiable; do NOT execute the prompt inline.

**Why `general-purpose`, not `orchemist-adversary`:** this gate needs WebSearch / WebFetch (live URL + claim verification) and Bash (`git diff`), which the `orchemist-adversary` subagent's `Read, Grep, Glob`-only tool list lacks. This exactly mirrors how the `review` phase dispatches `general-purpose`/fable rather than the dedicated adversary subagent. Per [[feedback_content_needs_source_grounded_factcheck]] — a fact-check must be grounded in the operator's ACTUAL sources with links verified, so a web-capable subagent is mandatory here.

## Step 1 — Delegate to the subagent

Use the `Agent` (Task) tool to spawn a `general-purpose` subagent **with `model: "fable"`** (Fable 5 — this is a critical judgment gate, per [[feedback_max_effort_adversary_reviewer]]). Pass it the following prompt (verbatim — DO NOT summarise; the GROUND TRUTH anchor, the diff-capture step, and the source-grounded rules are load-bearing):

---

[PIPELINE CONTEXT] You are executing the FACT_CHECK gate of the content pipeline. Your verdict blocks: APPROVE advances to red_team; REQUEST_CHANGES loops back to draft. Do not ask questions or send messages. [/PIPELINE CONTEXT]

You are a professional fact-checker (Fable 5) with live web access. You rule ONLY on factual accuracy + link liveness — not on tone/brand (that is red_team's job).

## GROUND TRUTH — The Content This Diff Must Implement
**Title:** {{config.issue_title}}
**Body:** {{config.issue_body}}

Every finding must trace to a specific changed line in the diff. Do NOT invent concerns about content not in the diff.

## Previous Work
{{phase_summary}}

## Prior Rounds
{{iteration_history}}

## Iteration Context
If prior rounds exist above, focus on (1) verifying prior fixes were applied, (2) finding NEW factual/link issues. Do NOT re-raise resolved findings.

## Repository
**Path:** {{config.repo_path}}
**Branch:** {{config.branch_name}}

## Evidence to gather FIRST
1. `git checkout {{config.branch_name}}`
2. `git diff main...{{config.branch_name}}` — the content the draft committed.
3. **Capture that diff for the next phase (REQUIRED):** `git diff main...{{config.branch_name}} > {{output_dir}}/draft_diff.md`. The red_team adversary that runs next has NO Bash and cannot produce this itself — if you skip this, red_team reviews nothing.
4. Read `{{output_dir}}/source_material.md` (operator ground truth) + `{{output_dir}}/research.md` (the sourced brief).

## Check (source-grounded content doctrine — STRICTER than an advisory report)
1. Every factual claim / definition / statistic in the new copy is EITHER traceable to `{{output_dir}}/source_material.md` OR independently confirmed by live web search. A claim that is neither → `REQUEST_CHANGES`.
2. Every curated link (each `externalLink` URL and any allowlist video URL) is LIVE (use WebFetch/WebSearch), on-topic, and authoritative. Any dead / off-topic / non-embeddable link → `REQUEST_CHANGES`.
3. No `[UNVERIFIED]` claim from `research.md` shipped as fact.
4. Numbers/definitions internally consistent; attribution accurate.
5. **Use web search** — a fact-check that only compares two documents without checking external reality is not a real fact-check.

## Output Format
Your response MUST start with one of these on the very first line (nothing else on the line):
- `APPROVE` — every factual claim is sourced and every curated link is live + on-topic
- `REQUEST_CHANGES` — one or more untraceable claims or dead/off-topic links

For each finding, one line: `[SEVERITY][category] location — claim — what's wrong — the source that should back it (or "untraceable") — the fix`. SEVERITY ∈ {BLOCKER, MAJOR, MINOR}; category ∈ {sourcing, link, consistency, attribution}.

Write your full fact-check to `{{output_dir}}/fact_check.md`. The FIRST line is the verdict word and nothing else; end the file with `VERDICT: APPROVE` or `VERDICT: REQUEST_CHANGES`.

---

## Step 2 — Verify subagent output

After the subagent returns, verify that `{{output_dir}}/fact_check.md` exists and starts with `APPROVE` or `REQUEST_CHANGES`, and that `{{output_dir}}/draft_diff.md` was written (red_team depends on it — if it is missing, produce it yourself with `git diff main...{{config.branch_name}} > {{output_dir}}/draft_diff.md`). If the subagent failed to write a recognisable verdict, write the following safe-default to `{{output_dir}}/fact_check.md` yourself:

```
REQUEST_CHANGES
[BLOCKER][sourcing] Fact-check subagent returned no recognisable verdict — defaulting to REQUEST_CHANGES for safety. Never assume APPROVE from ambiguous output.

VERDICT: REQUEST_CHANGES
```

This mirrors the engine's safe-default: never assume APPROVE from ambiguous output. Do NOT run the fact-check inline as a fallback — per [[feedback_fresh_subagent_per_phase]], the fresh-context-window property is non-negotiable.

## Output contract
Write exactly ONE verdict file to `{{output_dir}}/fact_check.md` (first line `APPROVE` / `REQUEST_CHANGES`; ends with `VERDICT: APPROVE` or `VERDICT: REQUEST_CHANGES`) and ensure `{{output_dir}}/draft_diff.md` exists for red_team.
