# Maintainers

The Orchemist Skills Pack has a single **Skills-pack maintainer** who owns pack releases and downstream consumer health.

- **Maintainer:** [@ToscanAI](https://github.com/ToscanAI) — the org account that owns `orchemist-skills` releases and consumer health.
- **Human backup:** [@Conny-Lazo](https://github.com/Conny-Lazo) — if the maintainer rotates, responsibility transfers via an update to this file.

## Responsibilities

1. Run the quarterly scan command (`scripts/retro-loop-quarterly.sh`) against each consumer's `main`.
2. File the per-quarter retrospective markdown (`docs/retro/RETROSPECTIVE-<YYYY-Q<N>>.md`).
3. Review surfaced gap patterns; either (a) open canonical-template amendment PRs OR (b) record a "no canonical change — consumer-side fix" rationale.
4. Close the quarterly retro issue with a status block linking the PRs / no-change decisions.

The consumer registry scanned by the quarterly process lives in [`docs/retro/CONSUMERS.txt`](docs/retro/CONSUMERS.txt).
