---
name: orchemist:research
description: Research phase of the Orchemist content pipeline. Synthesizes the operator's pre-placed source material ({output_dir}/source_material.md) plus live web search into a structured, source-grounded research brief — every claim gets an exact source + URL, unverifiable claims are marked [UNVERIFIED], and candidate curated links are proposed and verified. Delegates to a fresh general-purpose subagent so the research context does not leak into the draft phase. Triggers when /orchemist:research is invoked or /orchemist:run advances to the research phase.
---

# Research & Synthesis phase (content pipeline)

This skill is a thin wrapper that delegates to a fresh `general-purpose` subagent. The researcher MUST run in its own context window so the draft phase reviews a brief it did not itself write. Per [[feedback_fresh_subagent_per_phase]] — the fresh-context-window property is non-negotiable; do NOT execute the prompt inline. The subagent needs WebSearch / WebFetch — `general-purpose` (`Tools: *`) has them; a read-only subagent type cannot verify sources and MUST NOT be used here.

## Step 1 — Delegate to the subagent

Use the `Agent` (Task) tool to spawn a `general-purpose` subagent **with `model: "sonnet"`** (per the content pipeline's `research` model_tier; always pass the model explicitly per [[feedback_max_effort_adversary_reviewer]]'s explicit-model rule). Pass it the following prompt (verbatim — DO NOT summarise; the GROUND TRUTH anchor and the source-grounded rules are load-bearing):

---

[PIPELINE CONTEXT] You are executing the RESEARCH phase of the content pipeline. Your output feeds the DRAFT phase — not a human. Do not ask questions or send messages. [/PIPELINE CONTEXT]

You are a research analyst preparing a source-grounded brief for a content author who will edit in-app data (a glossary entry, a curated link) in a production codebase.

## GROUND TRUTH — The Content This Brief Must Support
**Title:** {{config.issue_title}}
**Body:** {{config.issue_body}}

Your brief MUST be about this content. Do NOT research an unrelated topic.

## Source Material (operator ground truth)
Read the full operator-provided sources from `{{output_dir}}/source_material.md`. If that file does not exist, proceed on the title/body + web research and NOTE the absence prominently — the draft will have thinner ground truth and every claim must then be web-verified.

## Previous Work
{{phase_summary}}

## Prior Rounds
{{iteration_history}}

## Iteration Context
If prior rounds exist above, this is a REVISION round — tighten only what a downstream phase flagged; keep verified sourcing intact.

## Task
1. Extract every fact, definition, statistic, and quote the content will rely on from `source_material.md`.
2. **Use web search** to independently verify each one and find authoritative corroboration — prefer the operator's canonical sources (e.g. Investopedia / OIC / SEC) over opinion blogs. Do NOT rely solely on the provided material.
3. For each fact, record the EXACT source (publication, date, URL). Every claim MUST carry a verifiable URL.
4. Mark any claim you cannot independently verify as `[UNVERIFIED]` with the reason. The draft must NOT ship an `[UNVERIFIED]` claim as fact — it either gets verified or dropped.
5. For a video/link entry, propose 1-3 CANDIDATE curated links: each authoritative, on-topic, and (for an embeddable video) verified reachable + embeddable — record the exact URL and why it fits.
6. Note brand/voice constraints from the existing entries (anti-hype, evidence-led) the copy must honor.
7. End with a complete SOURCES LIST — full attribution + URL for every source referenced.

**You have web-search tools. USE THEM.** A source-grounded brief without web-verified URLs is incomplete.

Read the recon at: `{{output_dir}}/existing_symbols.md` (the data shape + neighboring entries' voice the draft will match).

## Output contract
Write exactly ONE file to `{{output_dir}}/research.md` — a structured brief organized by theme, with inline source attribution for every claim and a complete sources list at the end. On success, end the file with the verdict word `success` on its own line.

---

## Step 2 — Verify subagent output

After the subagent returns, verify that `{{output_dir}}/research.md` exists and ends with the verdict word `success`. If the subagent failed to write the file (or wrote malformed output), write the following safe-default to `{{output_dir}}/research.md` yourself:

```
research subagent returned no recognisable output — defaulting to failed for safety.

failed
```

This routes the pipeline back through the research phase on the next iteration. Do NOT run the research inline as a fallback — per [[feedback_fresh_subagent_per_phase]], the fresh-context-window property is non-negotiable.
