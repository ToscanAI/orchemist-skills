# Trim leading/trailing whitespace in `parseConfig` input keys

Closes #142

## Background

We have a small utility module `src/utils/parseConfig.ts` that loads a `.env`-style configuration file and returns a `Record<string, string>`. Today it preserves whitespace around keys verbatim. That bites us when users hand-edit the file and accidentally leave a trailing space — `parseConfig` returns `{"API_KEY ": "abc"}` and downstream lookups for `config["API_KEY"]` silently fail.

## Acceptance criteria

1. When `parseConfig` reads a line like `  API_KEY  = abc  `, the returned record contains the key `"API_KEY"` with the value `"abc"`. Leading and trailing whitespace are stripped from BOTH the key AND the value.
2. Internal whitespace inside a key (e.g. `MY KEY = abc`) is preserved verbatim — only leading/trailing whitespace is trimmed.
3. Internal whitespace inside a value (e.g. `MY_KEY = a b c`) is preserved verbatim.
4. Quoted values keep their quotes intact: `MY_KEY = "abc"` returns the value `"\"abc\""` — quote-stripping is out of scope for this fix.
5. If two lines define the same key (after trimming), the LAST one wins.
6. Lines that are blank or start with `#` after trimming are ignored.
7. Existing public API surface (`parseConfig(filePath: string): Record<string, string>`) is unchanged.

## Files likely involved

- `src/utils/parseConfig.ts` — the implementation
- `src/utils/__tests__/parseConfig.test.ts` — Jest tests live here
- No new files expected

## Test command

```
test_command: npm test -- --testPathPattern=parseConfig
```

## Style

Follow the existing TypeScript style in this repo: strict mode, explicit return types on exported functions, no `any`, no `unknown` outside of input boundaries. Add a JSDoc comment on the public function describing the new trimming behaviour.

## Out of scope

- Quote stripping
- Multi-line values
- Interpolation (`$VAR` substitution)
- Type coercion (everything stays string-valued)
