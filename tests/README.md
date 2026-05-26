# orchemist-skills test suite

This directory contains **regression tests for the pipeline YAML's prompt
templates**. The tests are PROMPT-RENDERING-ONLY: they parse the canonical
pipeline YAML and assert that load-bearing substrings (sub-check headings,
finding formats, BLOCKED categories) are present. No live LLM calls.

## Running

```bash
pip install pyyaml pytest    # or `pip install -e .[test]` if pyproject.toml extras are wired
pytest tests/ -v
```

Expected: all tests pass against a `main` that has merged issue
[#6](https://github.com/ToscanAI/orchemist-skills/issues/6)'s producer-side 7d
patches. Against unpatched `main`, `test_spec_adversary_*` tests FAIL (by
design — they assert the new 7e block exists).

## Test inventory

### `test_spec_adversary_7e_intra_symbol.py`

Verifies the new SPEC_ADVERSARY 7e (intra-symbol duplication audit) block
landed correctly. Asserts:

- `### 7e — Intra-symbol duplication audit` heading is present.
- `producer-side variant` qualifier appears (distinguishes 7e from 7d).
- `[divergence] F.X — intra-symbol duplication` canonical finding format is
  present in the rubric.
- The fixture SPEC `fixtures/spec-with-intra-duplication.md` reproduces the
  value-investing#449 dual-path SQL pattern (two byte-identical SELECT blocks
  separated by a fixture short-circuit) WITHOUT a divergence justification —
  so the 7e check would correctly fire if rendered against a live Opus.

## Manual reproduction protocol (integration-level — NOT in CI)

To verify end-to-end that the SPEC_ADVERSARY 7e check actually fires (i.e.
that Opus reads the new 7e rubric and emits a `[divergence] F.X —
intra-symbol duplication` finding when fed the fixture SPEC):

1. Stand up a local Orchemist pipeline run targeting a dummy issue.
2. Place `tests/fixtures/spec-with-intra-duplication.md` at
   `<run-dir>/spec.md`.
3. Write a minimal `<run-dir>/behavioral.md` describing the
   `findCompanyByTicker` loader's contracts (any plausible reconstruction).
4. Invoke the orchemist-adversary skill (Phase 1c) against this run-dir.
5. Inspect `<run-dir>/spec_adversary.md`. The verdict line should be
   `REQUEST_CHANGES`, and at least one finding line should match the regex
   `^\[divergence\].*intra-symbol duplication`.

This is the integration-test path the issue's acceptance criterion #6
describes ("re-running the Phase 4 SPEC_ADVERSARY against value-investing
#449's draft SPEC ... flags the dual-path SQL block"). It is intentionally
NOT automated in CI because each invocation costs an Opus call. Consumers
shipping a new orchemist-skills release should run this manually as part
of their pre-tag QA.

## Fixture provenance

`fixtures/spec-with-intra-duplication.md` is a reconstruction (not a
verbatim copy) of the SPEC that would have been drafted for value-investing
PR #449 had it gone through the v4.3 pipeline. The original PR did not go
through Orchemist; the fixture is a synthetic reconstruction calibrated to
surface the same 7e finding the real-world PR would have triggered. The
fixture's Implementation Steps §B.4 deliberately produce two byte-identical
SQL blocks within the same `findCompanyByTicker` function body.
