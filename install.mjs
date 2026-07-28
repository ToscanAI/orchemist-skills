#!/usr/bin/env node
// install.mjs — Orchemist Skills Pack installer (cross-platform, Node builtins only)
//
// Idempotent installer: copies skills/*.md to <CLAUDE_HOME>/skills/<name>/SKILL.md
// and agents/*.md to <CLAUDE_HOME>/agents/. Backs up any existing file
// to <name>.bak.<timestamp> before overwrite. Running twice is safe:
// the second run produces identical state.
//
// Replaces the previous bash install.sh (issue #52) so a Windows/PowerShell-only
// host has a supported install path: `node` is the only prerequisite, and every
// path is built with path.join() so it is native on every platform.
//
// Usage:
//   npm run install:pack               # install into <CLAUDE_HOME>
//   npm run install:pack -- --check    # dry-run: verify install is in sync, write nothing
//   node install.mjs                   # identical, bypassing npm
//   node install.mjs --check
//   CLAUDE_HOME=/tmp/c node install.mjs   # install into a custom location

import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';
import os from 'node:os';
import process from 'node:process';

const USAGE = 'usage: install.mjs [--check]\n';

// ── Predicates ───────────────────────────────────────────────────────────────
// statSync (not lstatSync) FOLLOWS symlinks, matching bash's `-f` / `-d` tests.
// install.sh had no symlink-specific handling; neither does this port.
function isFile(p) {
  try {
    return fs.statSync(p).isFile();
  } catch {
    return false;
  }
}

function isDir(p) {
  try {
    return fs.statSync(p).isDirectory();
  } catch {
    return false;
  }
}

// ── normalizeLf(srcPath) -> Buffer ───────────────────────────────────────────
// Return SRC's bytes with every CR (0x0D) byte removed. A Windows clone running
// Git for Windows' default core.autocrlf=true yields a CRLF working tree; copied
// verbatim, those CRs are control characters that make Claude Code's Workflow
// permission layer refuse to launch workflows/orchemist-wave.js (issue #50).
// .gitattributes fixes FRESH clones only, so the installer normalises defensively
// and does not assume a clean checkout.
//
// This is a BYTE-level strip, not a `\r\n` -> `\n` text replace: a lone CR not
// followed by LF is removed too (exactly what bash's `tr -d '\r'` did). Never
// decode to a JS string — a text round-trip risks mangling non-UTF-8-clean bytes
// and normalises more than CR.
//
// Every file this installer copies is text (skills/*.md, agents/*.md,
// pipelines/*.yaml, profiles/*.yaml, workflows/*.js) — the pack ships no binary
// artifact — so stripping CR unconditionally is safe. On an LF checkout this is a
// byte-level no-op. If a binary artifact is ever added, it must bypass this.
function normalizeLf(srcPath) {
  const raw = fs.readFileSync(srcPath);
  // Build a plain array and Buffer.from() it: TypedArray.prototype.filter on a
  // Buffer does not reliably yield a Buffer across engines/versions.
  const out = [];
  for (const byte of raw) {
    if (byte !== 0x0d) out.push(byte);
  }
  return Buffer.from(out);
}

// ── listSources(dir, ext) -> sorted filenames ────────────────────────────────
// Mirrors bash pathname expansion (`for src in "$DIR"/*.ext`): lexicographically
// SORTED, and dotfiles excluded. fs.readdirSync() returns raw OS directory-entry
// order (hash order on ext4 htree, etc.), so the explicit .sort() is load-bearing
// — without it per-file report-line order is non-deterministic.
function listSources(dir, ext) {
  return fs
    .readdirSync(dir)
    .filter((name) => !name.startsWith('.') && name.endsWith(ext))
    .sort();
}

function main() {
  // ── Parse args (BEFORE pre-flight so an unknown flag deterministically exits 2,
  //    regardless of cwd or whether source dirs exist — a usage error must not be
  //    masked by a pre-flight exit 1). Only argv[2] is inspected, mirroring
  //    install.sh's `"${1:-}"`-only case statement. ────────────────────────────
  const arg = process.argv[2];
  let checkOnly = false;
  if (arg === undefined || arg === '') {
    checkOnly = false;
  } else if (arg === '--check') {
    checkOnly = true;
  } else {
    // A fixed literal, not $0/argv[1]: the message must be identical whether the
    // script was run as `node install.mjs`, `npm run install:pack`, an absolute
    // path, or a bin symlink.
    process.stderr.write(USAGE);
    return 2;
  }

  // ── Locate repo root (directory of THIS script, never process.cwd()) ────────
  const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
  const SKILLS_SRC = path.join(SCRIPT_DIR, 'skills');
  const AGENTS_SRC = path.join(SCRIPT_DIR, 'agents');
  const PIPELINES_SRC = path.join(SCRIPT_DIR, 'pipelines');
  const PROFILES_SRC = path.join(SCRIPT_DIR, 'profiles');
  const WORKFLOWS_SRC = path.join(SCRIPT_DIR, 'workflows');

  // ── Resolve install target ─────────────────────────────────────────────────
  // CLAUDE_HOME wins outright on every platform. Otherwise os.homedir() — Node's
  // own cross-platform primitive ($HOME/passwd on POSIX, %USERPROFILE% on
  // Windows) — joined with path.join, never string concatenation.
  const CLAUDE_HOME = process.env.CLAUDE_HOME || path.join(os.homedir(), '.claude');
  const SKILLS_DST = path.join(CLAUDE_HOME, 'skills');
  const AGENTS_DST = path.join(CLAUDE_HOME, 'agents');
  const PIPELINES_DST = path.join(CLAUDE_HOME, 'skills', 'orchemist', 'pipelines');
  const PROFILES_DST = path.join(CLAUDE_HOME, 'skills', 'orchemist', 'profiles');
  const WORKFLOWS_DST = path.join(CLAUDE_HOME, 'workflows');

  // ── Pre-flight: fixed order, first missing one wins, short-circuit before any
  //    directory is created or any byte is written. ────────────────────────────
  for (const src of [SKILLS_SRC, AGENTS_SRC, PIPELINES_SRC, PROFILES_SRC, WORKFLOWS_SRC]) {
    if (!isDir(src)) {
      process.stderr.write(
        `error: ${src} not found — run this script from the orchemist-skills repo root\n`,
      );
      return 1;
    }
  }

  if (!checkOnly) {
    for (const dst of [SKILLS_DST, AGENTS_DST, PIPELINES_DST, PROFILES_DST, WORKFLOWS_DST]) {
      fs.mkdirSync(dst, { recursive: true });
    }
  }

  // date -u +%Y%m%dT%H%M%SZ — computed ONCE, so every backup from one run shares
  // a single suffix.
  const TIMESTAMP = new Date()
    .toISOString()
    .replace(/[-:]/g, '')
    .replace(/\.\d{3}Z$/, 'Z');

  // ── Drift accumulator (used in --check mode only) ──────────────────────────
  let mismatchCount = 0;

  // ── installFile(src, dst) ─────────────────────────────────────────────────
  // Copies SRC -> DST with CR stripped. If DST already equals the normalised
  // SRC, skip silently. If DST exists and differs, back DST up RAW to
  // DST.bak.<timestamp>, then write the normalised SRC.
  //
  // Normalisation happens at exactly three sites and deliberately NOT at a
  // fourth:
  //   1. check-mode comparison:   normalised(src) vs RAW(dst)   — yes
  //   2. install-mode comparison: normalised(src) vs RAW(dst)   — yes
  //   3. install-mode write:      normalised(src) -> dst        — yes
  //   4. backup:                  RAW(dst) -> dst.bak.<ts>      — NO
  // Sites 1/2 must normalise only the SOURCE side: normalising the destination
  // too would blind the drift check (a genuinely CRLF-drifted destination would
  // wrongly report OK). Site 4 must stay raw: a backup is a faithful
  // pre-overwrite snapshot, so a CRLF destination must back up as CRLF.
  function installFile(src, dst) {
    if (checkOnly) {
      // --check (dry-run): read-only compare, NEVER write. Discrepancies are
      // recorded as data (mismatchCount), so a single run reports ALL drift.
      if (!isFile(dst)) {
        console.log(`  MISSING: ${dst}`);
        mismatchCount += 1;
      } else if (normalizeLf(src).equals(fs.readFileSync(dst))) {
        console.log(`  OK: ${dst}`);
      } else {
        console.log(`  MISMATCH: ${dst}`);
        mismatchCount += 1;
      }
      return;
    }

    if (isFile(dst)) {
      if (normalizeLf(src).equals(fs.readFileSync(dst))) {
        console.log(`  unchanged: ${dst}`);
        return;
      }
      const backup = `${dst}.bak.${TIMESTAMP}`;
      fs.copyFileSync(dst, backup); // RAW — no normalizeLf here, by design
      console.log(`  backed up: ${dst} -> ${backup}`);
    }
    fs.writeFileSync(dst, normalizeLf(src));
    console.log(`  installed: ${dst}`);
  }

  // ── Install skills ────────────────────────────────────────────────────────
  console.log(`Installing Orchemist skills to ${SKILLS_DST}`);
  let skillCount = 0;
  for (const name of listSources(SKILLS_SRC, '.md')) {
    const src = path.join(SKILLS_SRC, name);
    if (!isFile(src)) continue;
    const slug = path.basename(name, '.md'); // strip .md -> slug, e.g. orchemist-run
    if (!checkOnly) {
      // ensure <CLAUDE_HOME>/skills/<slug>/ exists (install mode only)
      fs.mkdirSync(path.join(SKILLS_DST, slug), { recursive: true });
    }
    installFile(src, path.join(SKILLS_DST, slug, 'SKILL.md'));
    skillCount += 1;
  }

  // ── Install agents ────────────────────────────────────────────────────────
  console.log('');
  console.log(`Installing Orchemist subagents to ${AGENTS_DST}`);
  let agentCount = 0;
  for (const name of listSources(AGENTS_SRC, '.md')) {
    const src = path.join(AGENTS_SRC, name);
    if (!isFile(src)) continue;
    installFile(src, path.join(AGENTS_DST, name));
    agentCount += 1;
  }

  // ── Install pipeline YAMLs (skills reference these via /orchemist:run) ─────
  console.log('');
  console.log(`Installing pipeline YAMLs to ${PIPELINES_DST}`);
  let pipelineCount = 0;
  for (const name of listSources(PIPELINES_SRC, '.yaml')) {
    const src = path.join(PIPELINES_SRC, name);
    if (!isFile(src)) continue;
    installFile(src, path.join(PIPELINES_DST, name));
    pipelineCount += 1;
  }

  // ── Install tiering profiles (consumer model+effort registry, #41) ─────────
  console.log('');
  console.log(`Installing tiering profiles to ${PROFILES_DST}`);
  let profileFileCount = 0;
  for (const name of listSources(PROFILES_SRC, '.yaml')) {
    const src = path.join(PROFILES_SRC, name);
    if (!isFile(src)) continue;
    installFile(src, path.join(PROFILES_DST, name));
    profileFileCount += 1;
  }

  // ── Install workflows (JS orchestrators for the Workflow tool) ─────────────
  console.log('');
  console.log(`Installing workflows to ${WORKFLOWS_DST}`);
  let workflowCount = 0;
  for (const name of listSources(WORKFLOWS_SRC, '.js')) {
    const src = path.join(WORKFLOWS_SRC, name);
    if (!isFile(src)) continue;
    installFile(src, path.join(WORKFLOWS_DST, name));
    workflowCount += 1;
  }

  // ── Summary ───────────────────────────────────────────────────────────────
  if (checkOnly) {
    console.log('');
    console.log(
      `Checked: ${skillCount} skill(s), ${agentCount} subagent(s), ` +
        `${pipelineCount} pipeline YAML(s), ${profileFileCount} tiering profile(s), ` +
        `${workflowCount} workflow(s)`,
    );
    if (mismatchCount > 0) {
      console.log(`${mismatchCount} target(s) out of sync`);
      return 1;
    }
    console.log('All targets in sync.');
    return 0;
  }

  // NOTE: the padding below is hand-written fixed-width whitespace carried over
  // verbatim from install.sh — it is not computed alignment. Do not "fix" it.
  console.log('');
  console.log('Orchemist Skills Pack installed:');
  console.log(`  ${skillCount} skill(s)       in ${SKILLS_DST}`);
  console.log(`  ${agentCount} subagent(s)    in ${AGENTS_DST}`);
  console.log(`  ${pipelineCount} pipeline YAML(s) in ${PIPELINES_DST}`);
  console.log(`  ${profileFileCount} tiering profile(s) in ${PROFILES_DST}`);
  console.log(`  ${workflowCount} workflow(s)    in ${WORKFLOWS_DST}`);
  console.log('');
  console.log("Next step: run 'claude' inside any git repo and try");
  console.log('  /orchemist:run examples/example-issue.md');
  console.log("(replace the path with your own issue file once you're ready).");
  return 0;
}

// Set process.exitCode rather than calling process.exit(): stdout/stderr are
// ASYNCHRONOUS when piped, and process.exit() can truncate pending writes.
process.exitCode = main();
