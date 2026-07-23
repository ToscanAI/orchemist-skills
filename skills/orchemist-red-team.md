---
name: orchemist:red-team
description: Red-team GATE of the Orchemist content pipeline (Fable 5). Adversarial pass over the draft's committed diff for tone/brand/backlash risk, IP/trademark leakage, hallucinated claims, over-claiming beyond the sources, and curation discipline. Returns APPROVE or REQUEST_CHANGES; an off-brand or unsupported claim BLOCKS and loops back to draft. Reuses the orchemist-adversary subagent (Read/Grep/Glob is sufficient — it audits text on disk, no live web needed) and reads the diff that fact_check captured to draft_diff.md (the adversary has no Bash). Triggers when /orchemist:red-team is invoked or /orchemist:run advances to the red_team phase.
---

# Red Team gate (content pipeline)

This skill is a thin wrapper that delegates to the `orchemist-adversary` subagent with **`model: "fable"`**. The red-teamer MUST run in its own context window — clean of drafter reasoning. Per [[feedback_fresh_subagent_per_phase]] — the fresh-context-window property is non-negotiable; do NOT execute the prompt inline.

**Why the adversary subagent (Read/Grep/Glob, no Bash):** red_team audits tone/IP/brand/claim-support against text already on disk — no live web needed, so the read-only adversary is the right, tamper-proof choice (it cannot mutate the tree). Because it has no Bash, it cannot run `git diff` itself: the preceding `fact_check` phase captured the diff to `{{output_dir}}/draft_diff.md` for it to `Read` — the same "pre-flight evidence for a Bash-less adversary" idiom the orchestrator uses for `test_adversary`.

## Step 1 — Delegate to the subagent

Use the `Agent` (Task) tool to spawn the `orchemist-adversary` subagent **with `model: "fable"`** (Fable 5 — critical judgment gate, per [[feedback_max_effort_adversary_reviewer]]). Pass it the following prompt (verbatim — DO NOT summarise; the GROUND TRUTH anchor is load-bearing):

---

[PIPELINE CONTEXT] You are executing the RED_TEAM gate of the content pipeline. Your verdict blocks: APPROVE advances to apply_fixes; REQUEST_CHANGES loops back to draft. You have Read/Grep/Glob only — no Bash, no web. Do not ask questions or send messages. [/PIPELINE CONTEXT]

You are an adversarial content reviewer. You hunt off-brand tone, IP leakage, and claims that over-reach their sources — BEFORE the content ships to production.

## GROUND TRUTH — The Content This Diff Must Implement
**Title:** {{config.issue_title}}
**Body:** {{config.issue_body}}

Every finding must trace to a specific line in the diff. Do NOT invent concerns about content not in the diff.

## Previous Work (context only — do NOT re-raise addressed findings)
{{phase_summary}}

## Prior Rounds
{{iteration_history}}

## Iteration Context
If prior rounds exist above, only raise findings STILL present in the current diff.

## What to read
- The committed diff at `{{output_dir}}/draft_diff.md` (fact_check captured it — you cannot run git yourself).
- The sourced brief at `{{output_dir}}/research.md`.
- The recon (neighbors' voice + curation discipline) at `{{output_dir}}/existing_symbols.md`.

## Hunt (each present item is a finding)
1. **Over-claim** — a factual statement in the copy that reaches BEYOND what `research.md` supports (fact_check owns liveness; you own over-reach vs. the sources).
2. **Tone / backlash risk** — hype, dismissiveness, punching-down, or copy that reads as advice/guarantee where the brand voice is measured + evidence-led.
3. **IP / trademark leakage** — a competitor's trademarked method name, a proprietary phrase, or a copied passage that must be paraphrased/attributed (per the repo's brand doctrine — e.g. banned method-name tokens).
4. **Hallucinated specifics** — an invented statistic, quote, date, or attribution not in the sources.
5. **Brand consistency** — voice drifts from the neighboring entries; a curated `source` label off the approved allowlist vocabulary; a missing honest-precondition (e.g. an N/A case) the neighbors preserve.
6. **Curation discipline** — the entry ships <1 curated link, or a duplicate/orphan slug the copy implies.

Protect legitimate measured voice — do NOT flag evidence-led plainness as a defect.

## Output Format
Your response MUST start with one of these on the very first line (nothing else on the line):
- `APPROVE` — on-brand, source-supported, no IP/tone risk
- `REQUEST_CHANGES` — one or more findings

For each finding, one line: `[category] location in the diff — why it will bite — the precise amendment`. Category ∈ {over_claim, tone, ip, hallucination, brand, curation}.

Write your full red-team review to `{{output_dir}}/red_team.md`. The FIRST line is the verdict word and nothing else; end the file with `VERDICT: APPROVE` or `VERDICT: REQUEST_CHANGES`.

---

## Step 2 — Copy the subagent output

After the subagent returns, verify that `{{output_dir}}/red_team.md` exists and starts with `APPROVE` or `REQUEST_CHANGES`. If the subagent failed to write a recognisable verdict, write the following safe-default to `{{output_dir}}/red_team.md` yourself:

```
REQUEST_CHANGES
[brand] Red-team subagent returned no recognisable verdict — defaulting to REQUEST_CHANGES for safety. Never assume APPROVE from ambiguous output.

VERDICT: REQUEST_CHANGES
```

This matches the engine's safe-default: never assume APPROVE from ambiguous output. Do NOT run the red-team inline as a fallback — per [[feedback_fresh_subagent_per_phase]], the fresh-context-window property is non-negotiable.

## Output contract
Write exactly ONE file to `{{output_dir}}/red_team.md`. The first line must be `APPROVE` or `REQUEST_CHANGES`; end the file with `VERDICT: APPROVE` or `VERDICT: REQUEST_CHANGES`.
