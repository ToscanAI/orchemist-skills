# Should We Have a Child? — Part 2: The Session

A character-consistent couples-therapist comic strip — the follow-up to "Post 14," which ended on *"to be continued…"*. Worked example input for `pipelines/comic-strip-pipeline.yaml`.

## Source (ground truth)

The strip realizes the **Long-Video table of storyboard `CL_SB_P&C 6`** — a 10-beat couples-therapist session for Alex & Taylor. Dialogue is **verbatim** from the storyboard; the strip must add nothing the storyboard does not contain (no improvised narration).

## Cast (canonical — lock to these)

- **Alex** — man, ~30s; dark tousled hair, round glasses, light-grey tee. Reference: `drive-assets/instagram/Post14/InstagramPost14_Panel1.png`.
- **Taylor** — woman, ~30s; long dark **loose** hair (no ponytail), white tee. Same reference.
- **Therapist** — **NEW, design-from-description**: woman ~50s, shoulder-length **silver-grey** hair, glasses, sage-green cardigan, holding a notepad. (Flagged by `asset_inventory` — no finished-art reference.)

## Anchor

`anchor_panel_id: p01` — wide establishing shot (couple on the couch left, therapist in the armchair right, warm office). Rendered and approved first; panels **p02–p10 re-frame a caption-cropped copy of it**, locking identity, room, and lighting.

## Panels (beats + verbatim dialogue)

1. **p01** — wide, all three. Therapist: "So — you've been discussing whether or not to have a child. What thoughts or feelings come to mind?"
2. **p02** — medium, couple. Alex: "There's so much I still want to do — places to see, experiences to have." · Taylor: "For me, it's my career. I've worked so hard to get where I am."
3. **p03** — close-up, therapist. "Those are valid concerns. What does having a child represent for each of you?"
4. **p04** — medium, couple (no held prop). Alex: "I guess it's about legacy… but I'm afraid of losing the freedom we have now." · Taylor: "It's about nurturing — but I'm scared of losing myself in it."
5. **p05** — close-up, therapist. "Let's take a step back. What values do you want your life together to reflect — whether or not you have children?"
6. **p06** — wide (anchor reframe). Alex: "Adventure and connection." · Taylor: "Growth, compassion, and partnership."
7. **p07** — close-up, therapist writing. "Those are powerful values. How might they guide your decision about having children?"
8. **p08** — close-up, Alex. "We could plan a few big trips first… and see how we feel afterward."
9. **p09** — close-up, Taylor. "And maybe talk to other parents — I could ask some colleagues how they balance career and family."
10. **p10** — wide (anchor reframe), couple holding hands. Therapist: "There's no reason to rush. You're already on your way." + bottom caption box: "Readiness isn't a finish line — it's the commitment to keep asking, together."

## Format
- dims `1080x1350`, aspect `4:5`
- image_model: `gemini-3-pro-image-preview`

## Commands (run in the comic repo)
```
render_command: python scripts/generate-comic-panels.py --brief {output_dir}/strip_brief.py --force
judge_command:  python scripts/judge_panels.py --criteria {output_dir}/acceptance_criteria.json --panels {output_dir}/panels --votes 3 --out {output_dir}/acceptance_results.json
```

## Style
Cozy slice-of-life, warm golden light, soft painterly, colored line art (no pure black), cream caption boxes + rounded speech bubbles.

## Out of scope
- AI-improvised narration captions — dialogue bubbles only; the one closing caption is authored, not generated text.
- Held props mid-conversation — the travel guide is a **p01 opening prop only**; absent from the rest.
- New plot beats — render the storyboard's 10 beats and only those.
