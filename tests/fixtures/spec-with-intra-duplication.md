# Implementation Spec — Reconstructed value-investing#449 (Section B)

> **Fixture provenance.** This file reconstructs the SPEC that would have been
> drafted for [value-investing#449](https://github.com/ToscanAI/value-investing/pull/449)
> based on the lift commit [`11db4eb`](https://github.com/ToscanAI/value-investing/commit/11db4eb).
> It is INTENTIONALLY structured to surface the F1 intra-symbol duplication
> finding when SPEC_ADVERSARY 7e is applied. Do NOT use as a real-pipeline SPEC.
>
> The §B.4 Implementation Steps deliberately produce two byte-identical
> `SELECT id::text AS id, name FROM companies WHERE ticker = ${t} LIMIT 1`
> SQL blocks within the same `findCompanyByTicker` function — once on the
> SB#2 fixture-carve-out path, once on the production fallback path —
> WITHOUT a §B.5.x divergence justification.

## B.1 Problem Statement

The web app's `findCompanyByTicker` loader needs to support a Sandbox #2 (SB#2)
E2E-fixture carve-out: when `E2E_FIXTURES_ENABLED=1` AND the inbound ticker
matches the env-var `E2E_REAL_COMPANY_TICKER`, query the real DB; otherwise
when `E2E_FIXTURES_ENABLED=1`, return a fixture stub; in production, query
the real DB normally.

## B.2 Files to Modify

(none — new file only)

## B.3 Files to Create

- `apps/web/lib/queries/companies.ts` — new module exporting `findCompanyByTicker(t: string)`.

## B.4 Implementation Steps

1. **Create `apps/web/lib/queries/companies.ts`** with a single exported async
   function `findCompanyByTicker(t: string): Promise<{ id: string; name: string } | null>`.

2. **Add the SB#2 carve-out branch** (per the issue's §16 Inngest signal):

   ```ts
   const realTicker = process.env['E2E_REAL_COMPANY_TICKER'];
   if (process.env['E2E_FIXTURES_ENABLED'] === '1' && realTicker && t === realTicker) {
     const rows = await db<{ id: string; name: string }[]>`
       SELECT id::text AS id, name FROM companies WHERE ticker = ${t} LIMIT 1
     `;
     return rows[0] ?? null;
   }
   ```

   The SB#2 path queries the real DB to confirm the real ticker resolves.

3. **Add the fixture-stub short-circuit** for the general E2E case:

   ```ts
   if (process.env['E2E_FIXTURES_ENABLED'] === '1') {
     return { id: 'fixture', name: `${t} (fixture)` };
   }
   ```

4. **Add the production fallback** that runs when neither E2E flag matches:

   ```ts
   const rows = await db<{ id: string; name: string }[]>`
     SELECT id::text AS id, name FROM companies WHERE ticker = ${t} LIMIT 1
   `;
   return rows[0] ?? null;
   ```

5. Export the function as a named export. No barrel index update needed at this stage.

## B.5 New Symbols

- **`findCompanyByTicker`** (verdict: NEW-OK)
  Existing: (none — no overlap with inventory)
  Rationale: new query loader; no existing ticker-lookup helper found.

## B.6 Observable Outcomes

- `findCompanyByTicker('AAPL')` in production: returns `{ id: '<uuid>', name: 'Apple Inc.' }` (or `null` if ticker absent).
- `findCompanyByTicker('FIX')` with `E2E_FIXTURES_ENABLED=1`: returns `{ id: 'fixture', name: 'FIX (fixture)' }`.
- `findCompanyByTicker('AAPL')` with `E2E_FIXTURES_ENABLED=1` and `E2E_REAL_COMPANY_TICKER=AAPL`: returns the real DB row (SB#2 carve-out).
