"""Focused regression tests for issue #50 part 1 — CRLF line endings.

Ground truth (issue #50): on a Windows clone with Git-for-Windows' default
``core.autocrlf=true`` every text artifact lands CRLF in the working tree,
``install.sh`` copies those bytes verbatim into ``~/.claude/``, and Claude
Code's ``Workflow`` permission layer then REFUSES to launch
``workflows/orchemist-wave.js`` because the CR (0x0D) bytes are "control
characters that would be hidden in the approval dialog".

The fix is belt-and-braces and these tests lock both halves in:

* ``.gitattributes`` (``* text=auto eol=lf``) fixes *fresh* clones — asserted
  with ``git check-attr`` and end-to-end with a simulated Windows clone.
* ``normalize_lf`` inside ``install.sh``'s ``install_file`` covers the
  population ``.gitattributes`` cannot reach: an existing consumer clone keeps
  its CRLF working tree until ``git add --renormalize`` is run.

THE TRAP these tests exist to guard (see tests 2 and 3): normalising only the
*write* while leaving the two ``cmp -s`` comparisons reading the raw source
makes every run see drift. That is not merely a noisy ``--check`` — it breaks
the installer's headline idempotency promise ("Running twice is safe: the
second run produces identical state") and litters unbounded ``.bak.<timestamp>``
files on every invocation. The source side of BOTH comparisons must be
normalised too, i.e. three substitutions, not one.

No Windows host is available, so the issue's criterion "``Workflow`` launches
from a stock Windows install" is discharged transitively: the permission layer
rejects the script *because of CR bytes*, and we assert zero CR bytes. Git's
attribute handling is platform-independent and ``core.autocrlf=true`` can be
set on any host, so the clone simulation is faithful.

All assertions are on **bytes**, never decoded text — a ``str`` comparison can
normalise newlines and silently pass.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = REPO_ROOT / "install.sh"

requires_bash = pytest.mark.skipif(
    shutil.which("bash") is None,
    reason="install.sh is bash-only; nothing to test on a host without bash",
)
requires_git_repo = pytest.mark.skipif(
    shutil.which("git") is None or not (REPO_ROOT / ".git").exists(),
    reason="needs git and a real checkout (suite must stay runnable from a tarball)",
)

# Source artifact -> installed destination, relative to CLAUDE_HOME. One entry
# per loop in install.sh so all five artifact classes are exercised.
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


def _build_pack(root: Path, *, crlf: bool) -> Path:
    """Create a throwaway artifact pack next to a copy of the real install.sh."""
    pack = root / "pack"
    pack.mkdir(parents=True, exist_ok=True)
    shutil.copy2(INSTALL_SH, pack / "install.sh")
    for rel, text in CONTENTS.items():
        src = pack / rel
        src.parent.mkdir(parents=True, exist_ok=True)
        data = text.encode("utf-8")
        if crlf:
            data = data.replace(b"\n", b"\r\n")
        src.write_bytes(data)
    return pack


def _lf_bytes(rel: str) -> bytes:
    return CONTENTS[rel].encode("utf-8")


def _run_install(pack: Path, claude_home: Path, *args: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["CLAUDE_HOME"] = str(claude_home)
    # Redirect HOME too, so a bug in CLAUDE_HOME resolution can never reach the
    # developer's real ~/.claude.
    env["HOME"] = str(claude_home.parent / "fake-home")
    Path(env["HOME"]).mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        ["bash", str(pack / "install.sh"), *args],
        capture_output=True,
        text=True,
        env=env,
        cwd=str(pack),
    )


def _event_lines(stdout: str, prefix: str) -> list[str]:
    """Per-file report lines only.

    Matched on the stripped line PREFIX, not as a bare substring: the closing
    summary banner "Orchemist Skills Pack installed:" contains the substring
    "installed:" and would otherwise make an idempotent run look like a re-copy.
    """
    return [line.strip() for line in stdout.splitlines() if line.strip().startswith(prefix)]


def _backups(claude_home: Path) -> list[Path]:
    return sorted(p for p in claude_home.rglob("*.bak.*") if p.is_file())


def _count_cr_bytes(root: Path) -> int:
    total = 0
    for path in root.rglob("*"):
        rel_parts = path.relative_to(root).parts
        if ".git" in rel_parts:
            continue
        if path.is_file() and not path.is_symlink():
            total += path.read_bytes().count(b"\r")
    return total


# ── 1. Part 1 core ───────────────────────────────────────────────────────────
@requires_bash
def test_install_strips_crlf_from_all_artifact_classes(tmp_path: Path) -> None:
    pack = _build_pack(tmp_path, crlf=True)
    claude_home = tmp_path / "claude"

    result = _run_install(pack, claude_home)
    assert result.returncode == 0, result.stderr

    for rel, dest_rel in ARTIFACTS.items():
        dst = claude_home / dest_rel
        assert dst.is_file(), f"{dest_rel} was not installed"
        installed = dst.read_bytes()
        assert b"\r" not in installed, f"CR byte survived into {dest_rel}"
        assert installed == _lf_bytes(rel), f"{dest_rel} content changed beyond CR removal"

    # The source pack really was CRLF — otherwise this test proves nothing.
    assert b"\r\n" in (pack / "workflows/w.js").read_bytes()


# ── 2. THE TRAP: idempotency on a CRLF source ────────────────────────────────
@requires_bash
def test_second_run_is_idempotent_on_crlf_source(tmp_path: Path) -> None:
    pack = _build_pack(tmp_path, crlf=True)
    claude_home = tmp_path / "claude"

    first = _run_install(pack, claude_home)
    assert first.returncode == 0, first.stderr

    second = _run_install(pack, claude_home)
    assert second.returncode == 0, second.stderr

    assert _event_lines(second.stdout, "installed:") == [], (
        "second run re-copied files — the cmp -s comparisons are still reading the "
        "raw CRLF source, which destroys idempotency\n" + second.stdout
    )
    assert _event_lines(second.stdout, "backed up:") == [], (
        "second run created backups — unbounded .bak litter regression\n" + second.stdout
    )
    assert len(_event_lines(second.stdout, "unchanged:")) == len(ARTIFACTS)
    assert _backups(claude_home) == [], "no .bak.* file may exist after a re-run"


# ── 3. THE TRAP: --check in sync after installing from CRLF ──────────────────
@requires_bash
def test_check_mode_reports_in_sync_after_install_from_crlf_source(tmp_path: Path) -> None:
    pack = _build_pack(tmp_path, crlf=True)
    claude_home = tmp_path / "claude"

    assert _run_install(pack, claude_home).returncode == 0

    check = _run_install(pack, claude_home, "--check")
    assert check.returncode == 0, (
        "--check reports permanent drift against a CRLF source\n" + check.stdout
    )
    assert "All targets in sync." in check.stdout
    assert "MISMATCH" not in check.stdout


# ── 4. Normalisation must not blind the drift check ──────────────────────────
@requires_bash
def test_check_still_detects_real_drift(tmp_path: Path) -> None:
    pack = _build_pack(tmp_path, crlf=True)
    claude_home = tmp_path / "claude"

    assert _run_install(pack, claude_home).returncode == 0

    drifted = claude_home / ARTIFACTS["workflows/w.js"]
    with drifted.open("ab") as handle:
        handle.write(b"// genuine drift\n")

    check = _run_install(pack, claude_home, "--check")
    assert check.returncode == 1, "genuine content drift must still fail --check"
    mismatches = [line for line in check.stdout.splitlines() if "MISMATCH" in line]
    assert len(mismatches) == 1, mismatches
    assert str(drifted) in mismatches[0]
    assert "1 target(s) out of sync" in check.stdout


# ── 5. Migration path: a pre-existing CRLF install ───────────────────────────
@requires_bash
def test_preexisting_crlf_install_is_migrated_once(tmp_path: Path) -> None:
    pack = _build_pack(tmp_path, crlf=True)
    claude_home = tmp_path / "claude"

    # Seed CLAUDE_HOME exactly as the OLD (verbatim-cp) installer would have.
    for rel, dest_rel in ARTIFACTS.items():
        dst = claude_home / dest_rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(_lf_bytes(rel).replace(b"\n", b"\r\n"))

    first = _run_install(pack, claude_home)
    assert first.returncode == 0, first.stderr
    assert len(_event_lines(first.stdout, "backed up:")) == len(ARTIFACTS)
    assert len(_event_lines(first.stdout, "installed:")) == len(ARTIFACTS)

    backups = _backups(claude_home)
    assert len(backups) == len(ARTIFACTS), "exactly one backup per file on migration"
    # The backup must be a FAITHFUL snapshot of the pre-overwrite destination,
    # CRs included — install.sh must not normalise `cp "$dst" "$backup"`.
    assert all(b"\r\n" in b.read_bytes() for b in backups)

    for rel, dest_rel in ARTIFACTS.items():
        assert (claude_home / dest_rel).read_bytes() == _lf_bytes(rel)

    second = _run_install(pack, claude_home)
    assert second.returncode == 0, second.stderr
    assert len(_event_lines(second.stdout, "unchanged:")) == len(ARTIFACTS)
    assert _event_lines(second.stdout, "backed up:") == []
    assert _backups(claude_home) == backups, "migration must converge, not loop"


# ── 6. Zero regression for existing Linux/macOS users ────────────────────────
@requires_bash
def test_lf_source_install_is_unchanged_by_normalisation(tmp_path: Path) -> None:
    pack = _build_pack(tmp_path, crlf=False)
    claude_home = tmp_path / "claude"

    assert _run_install(pack, claude_home).returncode == 0

    for rel, dest_rel in ARTIFACTS.items():
        assert (claude_home / dest_rel).read_bytes() == (pack / rel).read_bytes()

    check = _run_install(pack, claude_home, "--check")
    assert check.returncode == 0, check.stdout
    assert "All targets in sync." in check.stdout


# ── 7. .gitattributes forces LF ──────────────────────────────────────────────
@requires_git_repo
def test_gitattributes_forces_lf() -> None:
    assert (REPO_ROOT / ".gitattributes").is_file(), ".gitattributes is missing"

    paths = [
        "workflows/orchemist-wave.js",
        "install.sh",
        "skills/orchemist-run.md",
        "pipelines/coding-pipeline-standard.yaml",
    ]
    result = subprocess.run(
        ["git", "check-attr", "text", "eol", "--", *paths],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=True,
    )
    for path in paths:
        assert f"{path}: text: set" in result.stdout, result.stdout
        assert f"{path}: eol: lf" in result.stdout, result.stdout


# ── 8. Simulated Windows clone (closest Linux-executable proxy) ──────────────
@requires_git_repo
def test_simulated_windows_clone_has_no_cr(tmp_path: Path) -> None:
    clone = tmp_path / "winclone"
    subprocess.run(
        [
            "git",
            "-c",
            "core.autocrlf=true",
            "clone",
            "--no-hardlinks",
            "--quiet",
            str(REPO_ROOT),
            str(clone),
        ],
        capture_output=True,
        text=True,
        check=True,
    )

    cr_bytes = _count_cr_bytes(clone)
    assert cr_bytes == 0, (
        f"{cr_bytes} CR byte(s) in a core.autocrlf=true clone — "
        "orchemist-wave.js would be unlaunchable on Windows"
    )

    status = subprocess.run(
        ["git", "status", "--porcelain"],
        capture_output=True,
        text=True,
        cwd=str(clone),
        check=True,
    )
    assert status.stdout == "", f"clone is not clean:\n{status.stdout}"


# ── 9. Part 3 — POSIX tool prose names a portable alternative ────────────────
@pytest.mark.parametrize(
    "skill",
    ["skills/orchemist-run.md", "skills/orchemist-acceptance-run.md"],
)
def test_posix_tool_prose_names_a_portable_alternative(skill: str) -> None:
    lines = (REPO_ROOT / skill).read_text(encoding="utf-8").splitlines()

    for number, line in enumerate(lines, start=1):
        if "sha256sum" in line:
            assert "Get-FileHash" in line, (
                f"{skill}:{number} invokes sha256sum without naming a portable "
                "alternative for a PowerShell-only host"
            )
        if "diff -u" in line:
            assert "git diff --no-index" in line, (
                f"{skill}:{number} invokes `diff -u` without naming the portable "
                "`git diff --no-index` alternative"
            )
