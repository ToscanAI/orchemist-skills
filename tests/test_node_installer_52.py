"""Sealed acceptance tests for issue #52 (ToscanAI/orchemist-skills) — a Node
installer, ``install.mjs`` + ``npm run install:pack``, replacing the bash
``install.sh`` so Windows/PowerShell-only hosts have a supported install path.

Ground truth: `gh issue view 52 --repo ToscanAI/orchemist-skills` (follow-up to
#50). Written from ``behavioral.md`` (contracts BC-1..BC-15) ALONE — no access
to any implementation of ``install.mjs``, which does not exist yet at
collection time. Every assertion below is on process exit code, stdout/stderr
text, or file bytes on disk, per the contract's own stated observability
boundary.

Idiom mirrors the sibling #50 suite for the bash installer,
``tests/test_install_crlf_normalization.py``: build a throwaway artifact pack
next to a copy of the real installer script, drive it via subprocess with
``CLAUDE_HOME`` redirected into ``tmp_path``, and match per-file report lines
by a stripped-line PREFIX (never a bare substring) — a bare ``"installed:"``
substring check false-positives on the closing banner line "Orchemist Skills
Pack installed:".

THE TRAP these tests exist to guard (per behavioral.md's two amendment
banners):

* BC-6 + BC-9 together close a 2x2 CRLF matrix (under/over-normalisation x
  install/check mode). BC-6 pins that a CRLF SOURCE must not permanently
  "drift" in either mode (normalising only install-mode's comparison leaves
  ``--check`` red forever on a CRLF consumer). BC-9 pins the mirror-image
  trap: a directly-seeded CRLF DESTINATION must be flagged MISMATCH/exit 1 by
  ``--check`` and backed-up+reinstalled by install mode — an implementation
  that also normalises the destination before comparing would wrongly report
  OK/exit 0 on real drift.
* BC-14 uses FOUR skills files, created in strictly reverse-lexicographic
  order, specifically because two files give a sort-omitting port a coin-flip
  chance of passing on a hash-ordered directory read (e.g. ext4 htree).
* BC-15 requires a ``node_modules/``/``.git/`` carve-out when scanning for a
  leftover ``install.sh``, AND pins an install-mode (no-argument) leg — a
  script that hard-wires ``--check`` must fail this contract even though its
  ``--check`` leg looks correct in isolation.

Because ``install.mjs`` does not exist anywhere in the repository at the time
this suite is sealed (verified directly, not assumed), essentially every test
below is expected to FAIL today (red) — see the ledger in
``acceptance_test.md``. No test imports ``install.mjs`` as a Python module;
all module-level names below are today-real (stdlib + pytest only).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
# No production Python module is imported by this suite (the SUT is a Node
# script driven over subprocess) — this insert is a harmless no-op kept for
# consistency with the harness's general import-resolution convention.
sys.path.insert(0, str(REPO_ROOT))

INSTALL_MJS = REPO_ROOT / "install.mjs"  # does NOT exist yet — probed in-body only

requires_node = pytest.mark.skipif(
    shutil.which("node") is None,
    reason="install.mjs is a Node script; nothing to test without a node binary",
)
requires_npm = pytest.mark.skipif(
    shutil.which("npm") is None,
    reason="BC-15's packaged entry point (`npm run install:pack`) needs npm",
)

# Source artifact -> installed destination, relative to CLAUDE_HOME. One file
# per artifact class (skills/agents/pipelines/profiles/workflows) — per
# behavioral.md's "Destination mapping" table and its "one file per class"
# fixture note, this also makes every "N target(s)" count in summary lines
# predictable (each count is 1).
ARTIFACTS: dict[str, str] = {
    "skills/demo.md": "skills/demo/SKILL.md",
    "agents/a.md": "agents/a.md",
    "pipelines/p.yaml": "skills/orchemist/pipelines/p.yaml",
    "profiles/pr.yaml": "skills/orchemist/profiles/pr.yaml",
    "workflows/w.js": "workflows/w.js",
}

CONTENTS: dict[str, str] = {
    "skills/demo.md": "# demo skill\n\nline one\nline two\n",
    "agents/a.md": "# demo agent\n\nalpha\nbeta\n",
    "pipelines/p.yaml": "name: demo\nphases:\n  - spec\n  - implement\n",
    "profiles/pr.yaml": "tiers:\n  spec: opus\n  implement: sonnet\n",
    "workflows/w.js": "#!/usr/bin/env node\nconst x = 1;\nconsole.log(x);\n",
}

# Dedicated fixture for ONE test only -- BC-7's lone-CR distinguishing test
# (test_bc7_lone_cr_byte_stripped_not_generic_newline_normalized). Every
# other CRLF fixture in this suite is built from CONTENTS via a blanket
# `replace(b"\n", b"\r\n")`, so no other fixture ever contains a LONE 0x0D
# byte (one not part of a \r\n pair) -- deliberately kept out of the shared
# CONTENTS/ARTIFACTS dicts above so it cannot perturb BC-9's "differs ONLY
# in line endings" seed arithmetic (every BC-9 fixture byte must be
# reachable via LF -> CRLF substitution alone).
LONE_CR_CONTENTS: dict[str, bytes] = {
    "skills/demo.md": b"# demo skill\n\nline one\nline two\n",
    "agents/a.md": b"# demo agent\n\nalpha\nbeta\n",
    "pipelines/p.yaml": b"name: demo\nphases:\n  - spec\n  - implement\n",
    "profiles/pr.yaml": b"tiers:\n  spec: opus\n  implement: sonnet\n",
    # A LONE 0x0D byte mid-line, NOT part of any \r\n pair -- BC-7 requires
    # "every 0x0D byte removed ... not a generic text/newline
    # normalisation". An implementation that decodes to text and replaces
    # `\r\n` -> `\n` (or splits on universal newlines) either leaves this
    # byte untouched (failing BC-7's "zero 0x0D bytes") or converts it to a
    # DIFFERENT byte, 0x0A, rather than removing it outright (failing the
    # "nothing else changed" byte-identity requirement) -- both
    # anti-patterns are caught by this one fixture.
    "workflows/w.js": b"#!/usr/bin/env node\nconst x = 1;\rconsole.log(x);\n",
}

# Fixed check order per BC-12: "skills, agents, pipelines, profiles,
# workflows, in that fixed order".
CLASS_ORDER = ["skills", "agents", "pipelines", "profiles", "workflows"]


# ── Fixture builders ──────────────────────────────────────────────────────


def _require_install_mjs() -> None:
    if not INSTALL_MJS.is_file():
        pytest.fail(
            f"{INSTALL_MJS} does not exist yet -- install.mjs has not been "
            "implemented. Expected FAIL-now (red) per issue #52's behavioral "
            "contracts (BC-1..BC-15); this suite is sealed pre-implementation."
        )


def _build_pack(root: Path, *, crlf: bool) -> Path:
    """Create a throwaway artifact pack next to a copy of the REAL install.mjs.

    Mirrors ``tests/test_install_crlf_normalization.py::_build_pack`` (the #50
    suite for install.sh), swapped to the Node installer under test here.
    """
    _require_install_mjs()
    pack = root / "pack"
    pack.mkdir(parents=True, exist_ok=True)
    shutil.copy2(INSTALL_MJS, pack / "install.mjs")
    for rel, text in CONTENTS.items():
        src = pack / rel
        src.parent.mkdir(parents=True, exist_ok=True)
        data = text.encode("utf-8")
        if crlf:
            data = data.replace(b"\n", b"\r\n")
        src.write_bytes(data)
    return pack


def _build_pack_partial(root: Path, *, missing: list[str], as_file: bool = False) -> Path:
    """Like ``_build_pack``, but omit (or replace with a plain file) the named
    source-directory classes — for BC-12's pre-flight hard-error contract.
    """
    _require_install_mjs()
    pack = root / "pack"
    pack.mkdir(parents=True, exist_ok=True)
    shutil.copy2(INSTALL_MJS, pack / "install.mjs")
    for rel, text in CONTENTS.items():
        cls = rel.split("/", 1)[0]
        if cls in missing:
            continue
        src = pack / rel
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text(text, encoding="utf-8")
    for cls in missing:
        if as_file:
            (pack / cls).write_text("not a directory\n", encoding="utf-8")
    return pack


def _build_bc14_pack(root: Path) -> Path:
    """BC-14 fixture: four ``skills/`` files created in STRICTLY
    reverse-lexicographic order (zzz, mmm, ggg, aaa) plus one file per other
    class. Four files, not two — behavioral.md explains a two-file fixture is
    a coin flip on a hash-ordered directory read (e.g. ext4 htree).
    """
    _require_install_mjs()
    pack = root / "pack"
    pack.mkdir(parents=True, exist_ok=True)
    shutil.copy2(INSTALL_MJS, pack / "install.mjs")

    skills_src = pack / "skills"
    skills_src.mkdir(parents=True, exist_ok=True)
    for name in ["zzz-fourth", "mmm-third", "ggg-second", "aaa-first"]:
        (skills_src / f"{name}.md").write_text(f"# {name}\n", encoding="utf-8")

    for rel, text in CONTENTS.items():
        if rel.startswith("skills/"):
            continue
        src = pack / rel
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_text(text, encoding="utf-8")
    return pack


def _build_pack_lone_cr(root: Path) -> Path:
    """BC-7 dedicated fixture only: a full five-class pack built from
    ``LONE_CR_CONTENTS`` rather than the shared ``CONTENTS``/``ARTIFACTS``
    dicts, so that one file (``workflows/w.js``) contains a LONE 0x0D byte
    mid-line -- not part of any ``\\r\\n`` pair -- the load-bearing
    distinction BC-7 draws between exact byte-level CR stripping and a
    generic text/newline normalisation.
    """
    _require_install_mjs()
    pack = root / "pack"
    pack.mkdir(parents=True, exist_ok=True)
    shutil.copy2(INSTALL_MJS, pack / "install.mjs")
    for rel, data in LONE_CR_CONTENTS.items():
        src = pack / rel
        src.parent.mkdir(parents=True, exist_ok=True)
        src.write_bytes(data)
    return pack


def _lf_bytes(rel: str) -> bytes:
    return CONTENTS[rel].encode("utf-8")


def _run_install(pack: Path, claude_home: Path, *args: str) -> subprocess.CompletedProcess:
    """Invoke ``node <pack>/install.mjs [args]`` with CLAUDE_HOME (and HOME, as
    a belt-and-braces backstop) redirected into a disposable sandbox — never
    the real invoking user's home directory.
    """
    env = dict(os.environ)
    env["CLAUDE_HOME"] = str(claude_home)
    fake_home = claude_home.parent / "fake-home"
    fake_home.mkdir(parents=True, exist_ok=True)
    env["HOME"] = str(fake_home)
    return subprocess.run(
        ["node", str(pack / "install.mjs"), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(pack),
    )


def _run_claude_home_only(pack: Path, claude_home: Path, *args: str) -> subprocess.CompletedProcess:
    """Like ``_run_install`` but named separately for BC-13, where we must
    assert nothing outside CLAUDE_HOME is ever touched. HOME is still
    redirected -- into ``claude_home.parent / "fake-home"``, a disposable
    directory that sits INSIDE the sandbox root used by BC-13's own
    before/after listing but OUTSIDE CLAUDE_HOME itself -- because a
    CLAUDE_HOME-resolution bug is exactly the first-attempt failure this
    suite must catch without ever touching the real invoking user's home
    directory; placing the fake home inside the sandboxed root means such a
    bug is caught twice over, both by this redirection AND by BC-13's own
    "nothing changes outside CLAUDE_HOME" assertion.
    """
    env = dict(os.environ)
    env["CLAUDE_HOME"] = str(claude_home)
    fake_home = claude_home.parent / "fake-home"
    fake_home.mkdir(parents=True, exist_ok=True)
    env["HOME"] = str(fake_home)
    return subprocess.run(
        ["node", str(pack / "install.mjs"), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(pack),
    )


def _event_lines(stdout: str, prefix: str) -> list[str]:
    """Per-file / per-run report lines only, matched on the stripped line
    PREFIX (e.g. ``"installed:"``, ``"OK:"``) — not a bare substring: the
    closing banner "Orchemist Skills Pack installed:" contains the substring
    "installed:" and would otherwise make an idempotent run look like a
    re-copy.
    """
    return [line.strip() for line in stdout.splitlines() if line.strip().startswith(prefix)]


def _report_lines(stdout: str) -> list[str]:
    """All per-file report lines (OK:/MISSING:/MISMATCH:), in original stdout
    order, prefix-stripped of surrounding whitespace — used for BC-15's
    differential comparison between the packaged npm entry point and a direct
    invocation.
    """
    prefixes = ("OK:", "MISSING:", "MISMATCH:")
    return [line.strip() for line in stdout.splitlines() if line.strip().startswith(prefixes)]


def _backups(claude_home: Path) -> list[Path]:
    return sorted(p for p in claude_home.rglob("*.bak.*") if p.is_file())


def _file_snapshot(root: Path) -> dict[str, bytes]:
    """Relative path -> bytes, for every file under root. Empty dict if root
    doesn't exist.
    """
    if not root.exists():
        return {}
    return {str(p.relative_to(root)): p.read_bytes() for p in root.rglob("*") if p.is_file()}


def _path_snapshot(root: Path) -> frozenset:
    """Every file AND directory path under root, relative to root. Empty
    frozenset if root doesn't exist. Combined with ``_file_snapshot``, this
    catches creation/removal of empty directories that a bytes-only diff
    would miss.
    """
    if not root.exists():
        return frozenset()
    return frozenset(str(p.relative_to(root)) for p in root.rglob("*"))


def _expected_install_stdout(claude_home: Path) -> str:
    """Full expected stdout for an install-mode run against the standard
    one-file-per-class ARTIFACTS/CONTENTS fixture (all "installed:"), built
    verbatim from behavioral.md's "Exact output text" section (section
    headers, per-file line format, and the install-mode closing banner,
    literal internal spacing included -- e.g. "skill(s)" is followed by 7
    spaces before "in", "pipeline YAML(s)" by exactly 1).
    """
    skills_dst = claude_home / "skills"
    agents_dst = claude_home / "agents"
    pipelines_dst = claude_home / "skills" / "orchemist" / "pipelines"
    profiles_dst = claude_home / "skills" / "orchemist" / "profiles"
    workflows_dst = claude_home / "workflows"
    return (
        f"Installing Orchemist skills to {skills_dst}\n"
        f"  installed: {skills_dst / 'demo' / 'SKILL.md'}\n"
        "\n"
        f"Installing Orchemist subagents to {agents_dst}\n"
        f"  installed: {agents_dst / 'a.md'}\n"
        "\n"
        f"Installing pipeline YAMLs to {pipelines_dst}\n"
        f"  installed: {pipelines_dst / 'p.yaml'}\n"
        "\n"
        f"Installing tiering profiles to {profiles_dst}\n"
        f"  installed: {profiles_dst / 'pr.yaml'}\n"
        "\n"
        f"Installing workflows to {workflows_dst}\n"
        f"  installed: {workflows_dst / 'w.js'}\n"
        "\n"
        "Orchemist Skills Pack installed:\n"
        f"  1 skill(s)       in {skills_dst}\n"
        f"  1 subagent(s)    in {agents_dst}\n"
        f"  1 pipeline YAML(s) in {pipelines_dst}\n"
        f"  1 tiering profile(s) in {profiles_dst}\n"
        f"  1 workflow(s)    in {workflows_dst}\n"
        "\n"
        "Next step: run 'claude' inside any git repo and try\n"
        "  /orchemist:run examples/example-issue.md\n"
        "(replace the path with your own issue file once you're ready).\n"
    )


def _expected_check_stdout(claude_home: Path, *, status: str) -> str:
    """Full expected stdout for a --check run where EVERY fixture file has the
    given status ('OK', 'MISSING', or 'MISMATCH'), against the standard
    one-file-per-class fixture.
    """
    skills_dst = claude_home / "skills"
    agents_dst = claude_home / "agents"
    pipelines_dst = claude_home / "skills" / "orchemist" / "pipelines"
    profiles_dst = claude_home / "skills" / "orchemist" / "profiles"
    workflows_dst = claude_home / "workflows"
    summary_tail = "All targets in sync." if status == "OK" else f"{len(ARTIFACTS)} target(s) out of sync"
    return (
        f"Installing Orchemist skills to {skills_dst}\n"
        f"  {status}: {skills_dst / 'demo' / 'SKILL.md'}\n"
        "\n"
        f"Installing Orchemist subagents to {agents_dst}\n"
        f"  {status}: {agents_dst / 'a.md'}\n"
        "\n"
        f"Installing pipeline YAMLs to {pipelines_dst}\n"
        f"  {status}: {pipelines_dst / 'p.yaml'}\n"
        "\n"
        f"Installing tiering profiles to {profiles_dst}\n"
        f"  {status}: {profiles_dst / 'pr.yaml'}\n"
        "\n"
        f"Installing workflows to {workflows_dst}\n"
        f"  {status}: {workflows_dst / 'w.js'}\n"
        "\n"
        "Checked: 1 skill(s), 1 subagent(s), 1 pipeline YAML(s), "
        "1 tiering profile(s), 1 workflow(s)\n"
        f"{summary_tail}\n"
    )


# ── BC-1 ─────────────────────────────────────────────────────────────────
@requires_node
def test_bc1_install_happy_path_lf_source(tmp_path: Path) -> None:
    """BC-1: "an empty Claude home directory and a source tree with LF line
    endings ... it exits 0; every destination file ... exists and is
    byte-identical to its source file; stdout contains, for every file, a
    line `  installed: <dst>` ... stdout ends with the exact closing banner".

    FAIL-now (red): install.mjs does not exist yet, so `_build_pack` fails
    outright before any node invocation happens.
    """
    pack = _build_pack(tmp_path, crlf=False)
    claude_home = tmp_path / "claude"

    result = _run_install(pack, claude_home)
    assert result.returncode == 0, result.stderr

    for rel, dest_rel in ARTIFACTS.items():
        dst = claude_home / dest_rel
        assert dst.is_file(), f"{dest_rel} was not installed"
        assert dst.read_bytes() == _lf_bytes(rel)

    assert result.stdout.rstrip("\n") == _expected_install_stdout(claude_home).rstrip("\n")
    assert _event_lines(result.stdout, "unchanged:") == []
    assert _event_lines(result.stdout, "backed up:") == []
    assert len(_event_lines(result.stdout, "installed:")) == len(ARTIFACTS)


# ── BC-2 ─────────────────────────────────────────────────────────────────
@requires_node
def test_bc2_check_reports_in_sync_after_install_no_side_effects(tmp_path: Path) -> None:
    """BC-2: "--check ... exits 0; stdout contains one `  OK: <dst>` line per
    file and zero MISSING/MISMATCH lines ... stdout ends with the `Checked:
    ...` line followed by `All targets in sync.`; no file or directory under
    Claude home is created, removed, or modified by this run".

    FAIL-now (red): install.mjs does not exist yet.
    """
    pack = _build_pack(tmp_path, crlf=False)
    claude_home = tmp_path / "claude"

    assert _run_install(pack, claude_home).returncode == 0

    paths_before = _path_snapshot(claude_home)
    bytes_before = _file_snapshot(claude_home)

    check = _run_install(pack, claude_home, "--check")

    assert check.returncode == 0, check.stdout + check.stderr
    assert check.stdout.rstrip("\n") == _expected_check_stdout(claude_home, status="OK").rstrip("\n")
    assert "MISSING" not in check.stdout
    assert "MISMATCH" not in check.stdout

    assert _path_snapshot(claude_home) == paths_before
    assert _file_snapshot(claude_home) == bytes_before


# ── BC-3 ─────────────────────────────────────────────────────────────────
@requires_node
def test_bc3_check_reports_missing_before_install(tmp_path: Path) -> None:
    """BC-3: "an empty Claude home directory (nothing installed yet) ...
    --check ... it exits 1; stdout contains one `  MISSING: <dst>` line per
    expected destination file ... `<N> target(s) out of sync` ... no file or
    directory is created anywhere under (or in place of) Claude home".

    FAIL-now (red): install.mjs does not exist yet.
    """
    pack = _build_pack(tmp_path, crlf=False)
    claude_home = tmp_path / "claude"  # deliberately never created

    result = _run_install(pack, claude_home, "--check")

    assert result.returncode == 1
    assert result.stdout.rstrip("\n") == _expected_check_stdout(claude_home, status="MISSING").rstrip("\n")
    assert not claude_home.exists(), "a dry run must not create Claude home"


# ── BC-4 ─────────────────────────────────────────────────────────────────
@requires_node
def test_bc4_check_reports_mismatch_for_drifted_destination(tmp_path: Path) -> None:
    """BC-4: "one destination file's content is subsequently altered ... it
    exits 1; stdout contains exactly one `  MISMATCH: <dst>` line ... and `
    OK: <dst>` lines for every other ... unaltered file's bytes on disk are
    completely unchanged by this run".

    FAIL-now (red): install.mjs does not exist yet.
    """
    pack = _build_pack(tmp_path, crlf=False)
    claude_home = tmp_path / "claude"
    assert _run_install(pack, claude_home).returncode == 0

    drifted = claude_home / ARTIFACTS["workflows/w.js"]
    original_bytes = drifted.read_bytes()
    with drifted.open("ab") as handle:
        handle.write(b"// genuine drift\n")
    drifted_bytes = drifted.read_bytes()
    assert drifted_bytes != original_bytes  # sanity: drift really happened

    check = _run_install(pack, claude_home, "--check")

    assert check.returncode == 1, check.stdout
    mismatches = _event_lines(check.stdout, "MISMATCH:")
    assert len(mismatches) == 1
    assert str(drifted) in mismatches[0]
    assert len(_event_lines(check.stdout, "OK:")) == len(ARTIFACTS) - 1
    assert "1 target(s) out of sync" in check.stdout
    assert drifted.read_bytes() == drifted_bytes  # check mode never writes


# ── BC-5 ─────────────────────────────────────────────────────────────────
@requires_node
def test_bc5_second_install_is_full_noop_on_unchanged_lf_source(tmp_path: Path) -> None:
    """BC-5: "a second install with an unchanged LF source is a full no-op ...
    stdout contains one `  unchanged: <dst>` line per file and zero
    `installed:` / zero `backed up:` lines ... zero backup files ... every
    destination file's bytes on disk are unchanged".

    FAIL-now (red): install.mjs does not exist yet.
    """
    pack = _build_pack(tmp_path, crlf=False)
    claude_home = tmp_path / "claude"
    assert _run_install(pack, claude_home).returncode == 0
    before = _file_snapshot(claude_home)

    second = _run_install(pack, claude_home)

    assert second.returncode == 0
    assert len(_event_lines(second.stdout, "unchanged:")) == len(ARTIFACTS)
    assert _event_lines(second.stdout, "installed:") == []
    assert _event_lines(second.stdout, "backed up:") == []
    assert _backups(claude_home) == []
    assert _file_snapshot(claude_home) == before


# ── BC-6 (install leg) ──────────────────────────────────────────────────
@requires_node
def test_bc6_idempotent_second_install_on_crlf_source(tmp_path: Path) -> None:
    """BC-6, install leg: "the program runs again, unmodified, against the
    same CRLF source ... it exits 0; stdout contains one `  unchanged: <dst>`
    line per file and zero `installed:` / zero `backed up:` lines ... zero
    backup files exist". Regression guard: normalising only the WRITE while
    comparing against the raw CRLF source would re-copy every file forever.

    FAIL-now (red): install.mjs does not exist yet.
    """
    pack = _build_pack(tmp_path, crlf=True)
    claude_home = tmp_path / "claude"

    first = _run_install(pack, claude_home)
    assert first.returncode == 0, first.stderr
    for dest_rel in ARTIFACTS.values():
        assert b"\r" not in (claude_home / dest_rel).read_bytes()

    second = _run_install(pack, claude_home)

    assert second.returncode == 0, second.stderr
    assert _event_lines(second.stdout, "installed:") == []
    assert _event_lines(second.stdout, "backed up:") == []
    assert len(_event_lines(second.stdout, "unchanged:")) == len(ARTIFACTS)
    assert _backups(claude_home) == []


# ── BC-6 (check leg) ────────────────────────────────────────────────────
@requires_node
def test_bc6_check_reports_in_sync_on_crlf_source(tmp_path: Path) -> None:
    """BC-6, check leg: "the same guarantee holds in check mode: given that
    same CRLF-sourced installed state, running the program with --check
    exits 0 ... ending with ... `All targets in sync.` -- check mode's
    comparison must tolerate a CRLF source exactly as install mode's does,
    and an implementation that normalises only the install-mode comparison
    must fail this contract."

    FAIL-now (red): install.mjs does not exist yet.
    """
    pack = _build_pack(tmp_path, crlf=True)
    claude_home = tmp_path / "claude"
    assert _run_install(pack, claude_home).returncode == 0

    check = _run_install(pack, claude_home, "--check")

    assert check.returncode == 0, check.stdout
    assert len(_event_lines(check.stdout, "OK:")) == len(ARTIFACTS)
    assert "MISSING" not in check.stdout
    assert "MISMATCH" not in check.stdout
    assert "All targets in sync." in check.stdout


# ── BC-7 ─────────────────────────────────────────────────────────────────
@requires_node
def test_bc7_crlf_source_installs_as_lf_byte_exact(tmp_path: Path) -> None:
    """BC-7: "every installed destination file contains zero 0x0D bytes;
    every installed destination file's bytes equal its source file's bytes
    with every 0x0D byte removed and nothing else changed ... The source
    tree's own files, on disk, are byte-for-byte unchanged by this run".

    FAIL-now (red): install.mjs does not exist yet.
    """
    pack = _build_pack(tmp_path, crlf=True)
    claude_home = tmp_path / "claude"
    source_before = {rel: (pack / rel).read_bytes() for rel in ARTIFACTS}
    assert b"\r\n" in source_before["workflows/w.js"]  # sanity: source really is CRLF

    result = _run_install(pack, claude_home)

    assert result.returncode == 0, result.stderr
    for rel, dest_rel in ARTIFACTS.items():
        installed = (claude_home / dest_rel).read_bytes()
        assert b"\x0d" not in installed
        assert installed == bytes(b for b in source_before[rel] if b != 0x0D)
    for rel in ARTIFACTS:
        assert (pack / rel).read_bytes() == source_before[rel]


# ── BC-7 (lone CR, not part of \r\n -- the anti-pattern BC-7 names) ────────
@requires_node
def test_bc7_lone_cr_byte_stripped_not_generic_newline_normalized(tmp_path: Path) -> None:
    """BC-7: "exact byte-level CR stripping — not a generic text/newline
    normalisation, and not merely 'no visible `\\r\\n` when decoded as
    text'". Every CRLF fixture used elsewhere in this suite is built via a
    blanket `replace(b"\\n", b"\\r\\n")`, so no other test contains a LONE
    0x0D byte (one not part of a `\\r\\n` pair) -- an implementation that
    decodes to text and does a `\\r\\n` -> `\\n` replace (or splits on
    universal newlines) would pass every other test in this suite while
    mishandling this one; this test exists specifically to close that gap.
    Uses the dedicated ``LONE_CR_CONTENTS`` fixture, not the shared
    ``CONTENTS``, so as not to perturb BC-9's "differs ONLY in line
    endings" seed arithmetic.

    FAIL-now (red): install.mjs does not exist yet.
    """
    pack = _build_pack_lone_cr(tmp_path)
    claude_home = tmp_path / "claude"
    source_before = LONE_CR_CONTENTS["workflows/w.js"]
    assert b"\r" in source_before and b"\r\n" not in source_before  # sanity: lone CR, no CRLF pair

    result = _run_install(pack, claude_home)

    assert result.returncode == 0, result.stderr
    installed = (claude_home / ARTIFACTS["workflows/w.js"]).read_bytes()
    assert b"\x0d" not in installed
    assert installed == bytes(b for b in source_before if b != 0x0D)


# ── BC-8 ─────────────────────────────────────────────────────────────────
@requires_node
def test_bc8_genuine_drift_backed_up_once_then_converges(tmp_path: Path) -> None:
    """BC-8: "exactly one `  backed up: <dst> -> <backup>` line ... and
    exactly one `  installed: <dst>` line ... its bytes on disk are
    identical to the altered file's bytes as they were immediately before
    this run ... Then, given the program runs a third time ... creates no
    additional backup file, and the single backup file from the prior run
    still exists unchanged".

    FAIL-now (red): install.mjs does not exist yet.
    """
    pack = _build_pack(tmp_path, crlf=False)
    claude_home = tmp_path / "claude"
    assert _run_install(pack, claude_home).returncode == 0

    drifted = claude_home / ARTIFACTS["workflows/w.js"]
    pre_run_bytes = drifted.read_bytes() + b"// hand-edited\n"
    drifted.write_bytes(pre_run_bytes)

    second = _run_install(pack, claude_home)
    assert second.returncode == 0, second.stderr

    backed_up = _event_lines(second.stdout, "backed up:")
    assert len(backed_up) == 1
    assert str(drifted) in backed_up[0]
    installed = _event_lines(second.stdout, "installed:")
    assert len(installed) == 1
    assert str(drifted) in installed[0]
    assert len(_event_lines(second.stdout, "unchanged:")) == len(ARTIFACTS) - 1

    backups = _backups(claude_home)
    assert len(backups) == 1
    assert backups[0].read_bytes() == pre_run_bytes
    assert drifted.read_bytes() == _lf_bytes("workflows/w.js")

    third = _run_install(pack, claude_home)
    assert third.returncode == 0, third.stderr
    assert len(_event_lines(third.stdout, "unchanged:")) == len(ARTIFACTS)
    assert _event_lines(third.stdout, "backed up:") == []
    assert _event_lines(third.stdout, "installed:") == []
    assert _backups(claude_home) == backups
    assert backups[0].read_bytes() == pre_run_bytes  # bytes re-checked, not just the path -- an in-place rewrite at the same path must not slip through


# ── BC-9 (install leg) ──────────────────────────────────────────────────
@requires_node
def test_bc9_install_mode_backs_up_and_migrates_preexisting_crlf_destination(tmp_path: Path) -> None:
    """BC-9, install leg: "seeded directly ... with content that ... differs
    ONLY in line endings ... for each such pre-seeded file, stdout contains
    one `  backed up: <dst> -> <backup>` line followed by one `  installed:
    <dst>` line; the resulting backup file's bytes still contain \\r\\n
    sequences ... the destination file's bytes after this run contain zero
    0x0D bytes ... A subsequent (second) run ... reports every file
    unchanged, creates no new backup".

    FAIL-now (red): install.mjs does not exist yet.
    """
    pack = _build_pack(tmp_path, crlf=False)
    claude_home = tmp_path / "claude"

    # Directly seed CLAUDE_HOME (no install run yet) with CRLF content that is
    # byte-for-byte the LF source with LF -> CRLF only.
    for rel, dest_rel in ARTIFACTS.items():
        dst = claude_home / dest_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(_lf_bytes(rel).replace(b"\n", b"\r\n"))

    first = _run_install(pack, claude_home)
    assert first.returncode == 0, first.stderr
    assert len(_event_lines(first.stdout, "backed up:")) == len(ARTIFACTS)
    assert len(_event_lines(first.stdout, "installed:")) == len(ARTIFACTS)

    # BC-9: "stdout contains one `  backed up: <dst> -> <backup>` line
    # followed by one `  installed: <dst>` line" -- assert the adjacency,
    # not just the aggregate counts above.
    paired = [
        line.strip()
        for line in first.stdout.splitlines()
        if line.strip().startswith(("backed up:", "installed:"))
    ]
    assert len(paired) == 2 * len(ARTIFACTS)
    for i in range(0, len(paired), 2):
        assert paired[i].startswith("backed up:"), paired
        assert paired[i + 1].startswith("installed:"), paired

    backups = _backups(claude_home)
    assert len(backups) == len(ARTIFACTS)
    assert all(b"\r\n" in b.read_bytes() for b in backups), "backups must stay CRLF (byte-faithful)"
    backup_bytes_after_first = {b: b.read_bytes() for b in backups}

    for rel, dest_rel in ARTIFACTS.items():
        installed = (claude_home / dest_rel).read_bytes()
        assert b"\x0d" not in installed
        assert installed == _lf_bytes(rel)

    second = _run_install(pack, claude_home)
    assert second.returncode == 0, second.stderr
    assert len(_event_lines(second.stdout, "unchanged:")) == len(ARTIFACTS)
    assert _event_lines(second.stdout, "backed up:") == []
    assert _backups(claude_home) == backups
    for b in backups:
        assert b.read_bytes() == backup_bytes_after_first[b]  # bytes re-checked, not just the path


# ── BC-9 (check leg) ────────────────────────────────────────────────────
@requires_node
def test_bc9_check_mode_reports_mismatch_for_preexisting_crlf_destination(tmp_path: Path) -> None:
    """BC-9, check leg: "Separately, given that same directly-seeded CRLF
    pre-condition ... when the program runs with --check ... it exits 1;
    stdout contains one `  MISMATCH: <dst>` line per pre-seeded file and
    zero `  OK:` / zero `  MISSING:` lines ... no file or directory under
    Claude home is created, removed, or modified ... Check mode must compare
    the destination's raw bytes against the LF-normalised source -- an
    implementation that also normalises the destination's line endings
    before comparing ... must fail this contract."

    FAIL-now (red): install.mjs does not exist yet.
    """
    pack = _build_pack(tmp_path, crlf=False)
    claude_home = tmp_path / "claude"

    for rel, dest_rel in ARTIFACTS.items():
        dst = claude_home / dest_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(_lf_bytes(rel).replace(b"\n", b"\r\n"))

    paths_before = _path_snapshot(claude_home)
    bytes_before = _file_snapshot(claude_home)

    check = _run_install(pack, claude_home, "--check")

    assert check.returncode == 1, check.stdout
    assert len(_event_lines(check.stdout, "MISMATCH:")) == len(ARTIFACTS)
    assert _event_lines(check.stdout, "OK:") == []
    assert _event_lines(check.stdout, "MISSING:") == []
    assert f"{len(ARTIFACTS)} target(s) out of sync" in check.stdout

    assert _path_snapshot(claude_home) == paths_before
    assert _file_snapshot(claude_home) == bytes_before
    assert all(b"\r\n" in b for b in bytes_before.values())  # sanity: still CRLF


# ── BC-10 (CLAUDE_HOME wins) ────────────────────────────────────────────
@requires_node
def test_bc10_claude_home_env_var_wins_over_default(tmp_path: Path) -> None:
    """BC-10, leg 1: "CLAUDE_HOME ... set to some directory path that is
    unrelated to ... the process's home directory ... it exits 0; every
    destination file is created under the CLAUDE_HOME path exactly as given
    ... nothing is created under <home-directory>/.claude".

    FAIL-now (red): install.mjs does not exist yet.
    """
    pack = _build_pack(tmp_path, crlf=False)
    unrelated_target = tmp_path / "explicit-claude-home"
    fake_home = tmp_path / "unrelated-home"
    fake_home.mkdir()

    env = dict(os.environ)
    env["CLAUDE_HOME"] = str(unrelated_target)
    env["HOME"] = str(fake_home)
    result = subprocess.run(
        ["node", str(pack / "install.mjs")],
        capture_output=True, text=True, env=env, cwd=str(pack),
    )

    assert result.returncode == 0, result.stderr
    for dest_rel in ARTIFACTS.values():
        assert (unrelated_target / dest_rel).is_file()
    assert not (fake_home / ".claude").exists()


# ── BC-10 (HOME fallback) ───────────────────────────────────────────────
@requires_node
def test_bc10_home_env_var_controls_default_fallback_location(tmp_path: Path) -> None:
    """BC-10, leg 2: "CLAUDE_HOME is left unset and the process's home
    directory is instead controlled (e.g. via the HOME environment variable
    on a POSIX host) ... it exits 0 and every destination file is created
    under <that home directory>/.claude/... -- confirming the no-override
    fallback resolves relative to the process's actual home directory".

    FAIL-now (red): install.mjs does not exist yet.
    """
    pack = _build_pack(tmp_path, crlf=False)
    controlled_home = tmp_path / "controlled-home"
    controlled_home.mkdir()

    env = dict(os.environ)
    env.pop("CLAUDE_HOME", None)
    env["HOME"] = str(controlled_home)
    result = subprocess.run(
        ["node", str(pack / "install.mjs")],
        capture_output=True, text=True, env=env, cwd=str(pack),
    )

    assert result.returncode == 0, result.stderr
    for dest_rel in ARTIFACTS.values():
        assert (controlled_home / ".claude" / dest_rel).is_file()


# ── BC-11 ────────────────────────────────────────────────────────────────
@requires_node
@pytest.mark.parametrize("bad_arg", ["--verbose", "install", "-c", "--Check", "checkk"])
def test_bc11_unrecognized_argument_is_usage_error(tmp_path: Path, bad_arg: str) -> None:
    """BC-11: "a single command-line argument that is not the literal string
    --check ... it exits with status 2; stderr is non-empty and consists of
    exactly the line `usage: install.mjs [--check]` ... stdout is
    completely empty; no file or directory is created anywhere under the
    resolved Claude home directory".

    FAIL-now (red): install.mjs does not exist yet.
    """
    pack = _build_pack(tmp_path, crlf=False)
    claude_home = tmp_path / "claude"

    result = _run_install(pack, claude_home, bad_arg)

    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr == "usage: install.mjs [--check]\n"
    assert not claude_home.exists()


# ── BC-12 (single missing dir, both modes) ─────────────────────────────
@requires_node
@pytest.mark.parametrize("mode_args", [(), ("--check",)], ids=["install", "check"])
@pytest.mark.parametrize("missing_class", CLASS_ORDER)
def test_bc12_single_missing_source_dir_is_hard_error_before_writes(
    tmp_path: Path, missing_class: str, mode_args: tuple[str, ...]
) -> None:
    """BC-12: "missing one of its five required source directories ... it
    exits with status 1; stderr contains exactly one line matching `error:
    <path> not found — run this script from the orchemist-skills repo
    root` ... stdout is completely empty ... no file or directory is
    created ... When exactly one of the five directories is missing ... the
    reported <path> corresponds specifically to the missing one."

    FAIL-now (red): install.mjs does not exist yet.
    """
    pack = _build_pack_partial(tmp_path, missing=[missing_class])
    claude_home = tmp_path / "claude"

    result = _run_install(pack, claude_home, *mode_args)

    assert result.returncode == 1
    assert result.stdout == ""
    expected_path = str(pack / missing_class)
    expected_line = f"error: {expected_path} not found — run this script from the orchemist-skills repo root"
    assert result.stderr == expected_line + "\n"
    assert not claude_home.exists()


# ── BC-12 (non-directory file) ─────────────────────────────────────────
@requires_node
def test_bc12_source_present_as_non_directory_file_is_also_a_hard_error(tmp_path: Path) -> None:
    """BC-12: "either absent entirely, or present as a non-directory such as
    a plain file" — a required source path existing as a plain file is
    treated identically to it being absent.

    FAIL-now (red): install.mjs does not exist yet.
    """
    pack = _build_pack_partial(tmp_path, missing=["skills"], as_file=True)
    claude_home = tmp_path / "claude"
    assert (pack / "skills").is_file()  # sanity: really a file, not a dir

    result = _run_install(pack, claude_home)

    assert result.returncode == 1
    assert result.stdout == ""
    expected_line = f"error: {pack / 'skills'} not found — run this script from the orchemist-skills repo root"
    assert result.stderr == expected_line + "\n"
    assert not claude_home.exists()


# ── BC-12 (multiple missing, fixed-order reporting) ────────────────────
@requires_node
def test_bc12_multiple_missing_reports_first_in_fixed_order(tmp_path: Path) -> None:
    """BC-12: "When more than one is missing simultaneously, the reported
    <path> corresponds to whichever one would be checked first among:
    skills, agents, pipelines, profiles, workflows, in that fixed order ...
    exactly one error line is printed, never more than one."

    FAIL-now (red): install.mjs does not exist yet.
    """
    claude_home = tmp_path / "claude"

    # skills AND workflows both missing -> must report skills.
    pack_a = _build_pack_partial(tmp_path / "a", missing=["skills", "workflows"])
    result_a = _run_install(pack_a, claude_home / "a")
    assert result_a.returncode == 1
    lines_a = [l for l in result_a.stderr.splitlines() if l.strip()]
    assert len(lines_a) == 1
    assert str(pack_a / "skills") in lines_a[0]
    assert str(pack_a / "workflows") not in lines_a[0]

    # agents AND workflows missing (skills present) -> must report agents.
    pack_b = _build_pack_partial(tmp_path / "b", missing=["agents", "workflows"])
    result_b = _run_install(pack_b, claude_home / "b")
    assert result_b.returncode == 1
    lines_b = [l for l in result_b.stderr.splitlines() if l.strip()]
    assert len(lines_b) == 1
    assert str(pack_b / "agents") in lines_b[0]
    assert str(pack_b / "workflows") not in lines_b[0]


# ── BC-13 ────────────────────────────────────────────────────────────────
@requires_node
def test_bc13_no_artifact_written_outside_claude_home(tmp_path: Path) -> None:
    """BC-13: "a full recursive listing of the common temporary root, taken
    before and after, shows every newly-created or newly-modified file
    located strictly inside the CLAUDE_HOME subtree — zero files are
    created, modified, or removed anywhere else under the temporary root
    (including the program's own source tree, which must remain
    byte-for-byte unchanged throughout)."

    FAIL-now (red): install.mjs does not exist yet.
    """
    root = tmp_path / "sandbox"
    root.mkdir()
    pack = _build_pack(root, crlf=False)
    claude_home = root / "claude-home"

    def _outside_snapshot() -> dict[str, bytes]:
        snap = {}
        for p in root.rglob("*"):
            if p.is_file() and claude_home not in p.parents and p != claude_home:
                snap[str(p.relative_to(root))] = p.read_bytes()
        return snap

    before = _outside_snapshot()

    assert _run_claude_home_only(pack, claude_home).returncode == 0
    assert _run_claude_home_only(pack, claude_home, "--check").returncode == 0
    drifted = claude_home / ARTIFACTS["workflows/w.js"]
    drifted.write_bytes(drifted.read_bytes() + b"x")
    assert _run_claude_home_only(pack, claude_home).returncode == 0

    after = _outside_snapshot()
    assert after == before


# ── BC-14 (install mode) ────────────────────────────────────────────────
@requires_node
def test_bc14_per_file_lines_lexicographic_order_install_mode(tmp_path: Path) -> None:
    """BC-14, install leg: "the four per-file lines for this class appear in
    exactly this order: aaa-first, then ggg-second, then mmm-third, then
    zzz-fourth ... lexicographic order of the source .md filename, never
    filesystem read order, creation order, or any other order."

    FAIL-now (red): install.mjs does not exist yet.
    """
    pack = _build_bc14_pack(tmp_path)
    claude_home = tmp_path / "claude"

    result = _run_install(pack, claude_home)
    assert result.returncode == 0, result.stderr

    skills_dst = claude_home / "skills"
    installed_lines = _event_lines(result.stdout, "installed:")
    skills_lines = [l for l in installed_lines if "SKILL.md" in l]
    expected_order = [
        f"installed: {skills_dst / name / 'SKILL.md'}"
        for name in ["aaa-first", "ggg-second", "mmm-third", "zzz-fourth"]
    ]
    assert skills_lines == expected_order


# ── BC-14 (check mode) ───────────────────────────────────────────────────
@requires_node
def test_bc14_per_file_lines_lexicographic_order_check_mode(tmp_path: Path) -> None:
    """BC-14, check leg: "Separately, given that same installed state, when
    the program runs again with --check, then it exits 0 and the four `  OK:
    ...` lines for this class appear in that identical lexicographic order."

    FAIL-now (red): install.mjs does not exist yet.
    """
    pack = _build_bc14_pack(tmp_path)
    claude_home = tmp_path / "claude"
    assert _run_install(pack, claude_home).returncode == 0

    check = _run_install(pack, claude_home, "--check")
    assert check.returncode == 0, check.stdout

    skills_dst = claude_home / "skills"
    ok_lines = _event_lines(check.stdout, "OK:")
    skills_lines = [l for l in ok_lines if "SKILL.md" in l]
    expected_order = [
        f"OK: {skills_dst / name / 'SKILL.md'}"
        for name in ["aaa-first", "ggg-second", "mmm-third", "zzz-fourth"]
    ]
    assert skills_lines == expected_order


# ── BC-15 (install.sh removed) ──────────────────────────────────────────
def test_bc15_install_sh_no_longer_exists_in_package_root() -> None:
    """BC-15: "no file named install.sh exists anywhere in that package root
    — excluding the contents of any node_modules/ or .git/ directories ...
    the prior bash installer has been removed, not merely superseded or left
    alongside the new one."

    FAIL-now (red): install.sh is verifiably still present at REPO_ROOT today
    (it is the very script the sibling #50 suite,
    tests/test_install_crlf_normalization.py, drives directly) -- this
    assertion must fail until the implement phase deletes it.
    """
    offenders = []
    for path in REPO_ROOT.rglob("install.sh"):
        rel_parts = path.relative_to(REPO_ROOT).parts
        if "node_modules" in rel_parts or ".git" in rel_parts:
            continue
        offenders.append(path)
    assert offenders == [], f"install.sh still present: {offenders}"


# ── BC-15 (npm run install:pack -- --check parity) ─────────────────────
@requires_node
@requires_npm
def test_bc15_npm_run_install_pack_check_matches_direct_invocation(tmp_path: Path) -> None:
    """BC-15: "when node install.mjs --check is invoked directly from that
    same package root with that same CLAUDE_HOME value ... both invocations
    exit with the identical status code; and, comparing only the lines in
    each invocation's stdout that match one of the per-file report-line
    formats ... the two invocations produce the identical sequence of
    per-file report lines, in the identical order ... If that script is
    missing, misnamed, or still points at the now-deleted install.sh, the
    npm run install:pack -- --check invocation will either fail outright
    ... or produce stdout with zero per-file report lines while the direct
    invocation produces one per fixture file — and this contract fails
    either way."

    Uses the REAL, shipped package root (REPO_ROOT) per BC-15's own wording,
    not a throwaway pack -- so this exercises the actual package.json
    script. Both invocations share ONE CLAUDE_HOME, per the contract's own
    "that same CLAUDE_HOME value" wording -- using two different homes
    would make the compared report lines' embedded absolute `<dst>` paths
    diverge permanently, even against a fully conformant implementation.
    Safe to run --check twice sequentially against the same home: --check
    is read-only per BC-3.

    FAIL-now (red): package.json has no "install:pack" script today, and
    install.mjs does not exist -- both invocations fail (differently), so
    the "npm_lines != []" guard below trips even in the coincidental case
    where both return codes happen to match.
    """
    claude_home = tmp_path / "shared-claude-home"
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir(parents=True, exist_ok=True)

    env_npm = dict(os.environ)
    env_npm["CLAUDE_HOME"] = str(claude_home)
    env_npm["HOME"] = str(fake_home)
    npm_result = subprocess.run(
        ["npm", "run", "install:pack", "--", "--check"],
        capture_output=True, text=True, env=env_npm, cwd=str(REPO_ROOT),
    )

    env_direct = dict(os.environ)
    env_direct["CLAUDE_HOME"] = str(claude_home)
    env_direct["HOME"] = str(fake_home)
    direct_result = subprocess.run(
        ["node", "install.mjs", "--check"],
        capture_output=True, text=True, env=env_direct, cwd=str(REPO_ROOT),
    )

    assert npm_result.returncode == direct_result.returncode

    npm_lines = _report_lines(npm_result.stdout)
    direct_lines = _report_lines(direct_result.stdout)
    assert npm_lines == direct_lines
    assert npm_lines != [], "expected at least one per-file report line from a real package root"


# ── BC-15 (npm run install:pack default = real install) ────────────────
@requires_node
@requires_npm
def test_bc15_npm_run_install_pack_default_invocation_performs_real_install(tmp_path: Path) -> None:
    """BC-15: "Finally, given a fresh, empty disposable CLAUDE_HOME, when npm
    run install:pack is invoked with no extra arguments ... it exits 0 and
    stdout contains at least one `  installed: <dst>` line; and when node
    install.mjs --check is then invoked directly ... it exits 0 with one `
    OK: <dst>` line per file — proving the packaged entry point's default,
    no-argument invocation performs a real install (a script that hard-wires
    --check, or otherwise never installs, must fail this contract)."

    FAIL-now (red): package.json has no "install:pack" script today, and
    install.mjs does not exist.
    """
    claude_home = tmp_path / "claude"
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["CLAUDE_HOME"] = str(claude_home)
    env["HOME"] = str(fake_home)
    result = subprocess.run(
        ["npm", "run", "install:pack"],
        capture_output=True, text=True, env=env, cwd=str(REPO_ROOT),
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert _event_lines(result.stdout, "installed:") != []

    check_env = dict(os.environ)
    check_env["CLAUDE_HOME"] = str(claude_home)
    check_env["HOME"] = str(fake_home)
    check_result = subprocess.run(
        ["node", "install.mjs", "--check"],
        capture_output=True, text=True, env=check_env, cwd=str(REPO_ROOT),
    )
    assert check_result.returncode == 0, check_result.stdout + check_result.stderr
    assert _event_lines(check_result.stdout, "OK:") != []


# ── System-under-test note: source dirs resolve to script dir, not cwd ──
@requires_node
def test_source_dirs_resolve_relative_to_script_not_cwd(tmp_path: Path) -> None:
    """System under test: "The program locates its five source directories
    ... next to its own script file, regardless of the process's current
    working directory — i.e. node /some/pack/install.mjs looks for
    /some/pack/skills/, not <cwd>/skills/. A fixture can rely on this:
    copying install.mjs alongside a throwaway source tree and invoking it
    from anywhere is expected to work."

    FAIL-now (red): install.mjs does not exist yet.
    """
    pack = _build_pack(tmp_path, crlf=False)
    claude_home = tmp_path / "claude"
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    fake_home = tmp_path / "fake-home"
    fake_home.mkdir(parents=True, exist_ok=True)

    env = dict(os.environ)
    env["CLAUDE_HOME"] = str(claude_home)
    env["HOME"] = str(fake_home)
    result = subprocess.run(
        ["node", str(pack / "install.mjs")],
        capture_output=True, text=True, env=env, cwd=str(elsewhere),
    )

    assert result.returncode == 0, result.stderr
    for dest_rel in ARTIFACTS.values():
        assert (claude_home / dest_rel).is_file()
