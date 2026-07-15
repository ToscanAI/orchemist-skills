# Quarterly retrospective — <YYYY-Q<N>> (<YYYY-MM-DD> scan)

## Scope

- Consumers scanned: <repo-1>, <repo-2>, ...
- Time window: <YYYY-MM-DD> to <YYYY-MM-DD> (PRs merged in the trailing 90 days).
- PRs scanned: <N> (list at end).

## Findings

### Duplication groups surfaced (per consumer)

For each finding, one entry:

#### F<N> — <one-line description>

- **Consumer:** <repo>
- **Originating PR(s):** #<N>, #<M>, ... (commits: <sha>, <sha>)
- **Phase 0 / sub-check 7d era?** Yes/No (introduced before / after the relevant guard landed)
- **Pattern category:** intra-symbol (7e family) / inter-symbol consumer-side (7d family) / cross-package boilerplate / other
- **Verbatim duplicate** (quote one block per arm/site):
  ```ts
  // <file>:<line-range>
  ...
  ```
- **Why caught here, missed at gate:** <one paragraph>

### Gap patterns (cross-consumer)

For each pattern that recurs across consumers OR appears 3+ times in a single consumer:

- **GP<N> — <pattern name>:** <description>
- **Proposed canonical-template amendment:** <link to draft PR OR "none — consumer-side fix"; rationale>

## Decisions

| Pattern | Owner action | Resolution |
|---|---|---|
| GP1 | Open PR #<N> against `orchemist-skills` adding sub-check <X> | <DRAFT / MERGED / DEFERRED> |
| GP2 | No canonical change — consumer-side `lib_paths` widening | <consumer-PR-link> |

## Forward-pointers

- Next quarterly scan: <YYYY-Q<N+1>> on <YYYY-MM-DD>
- Open canonical PRs: <list>
