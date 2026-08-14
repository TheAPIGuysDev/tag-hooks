"""Tests for the canonical commit-message gate .

The golden corpus lives in ``commit_message_cases.json`` so adopting repos can
run the same cases against the rev they have pinned — it is the drift detector
the ADR relies on, replacing "diff against canonical before editing".

The git-integration tests below cover what direct calls cannot: merge-state
skipping (v1 blocked ordinary ``git merge``), real ``git commit --fixup``, and
range-mode merge exclusion.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import check_commit_message as ccm

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent / "scripts" / "check-commit-message.py"
CASES = json.loads((HERE / "commit_message_cases.json").read_text(encoding="utf-8"))["cases"]


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_golden_corpus(case):
    types = tuple(case["types"].split(",")) if "types" in case else ccm.DEFAULT_TYPES
    result = ccm.check_message(
        case["input"], case["name"], types, autosquash_ok=(case["mode"] == "file")
    )
    assert result == case["expected"], case.get("why", "")


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=True
    )


def _run_script(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args], cwd=cwd, capture_output=True, text=True
    )


@pytest.fixture()
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-b", "main")
    _git(r, "config", "user.email", "test@example.com")
    _git(r, "config", "user.name", "Test")
    (r / "f").write_text("1\n")
    _git(r, "add", "f")
    _git(r, "commit", "-m", "feat: initial")
    return r


def test_file_mode_skips_during_merge(repo: Path):
    """git fires commit-msg for merges too; v1 blocked them and stranded the repo."""
    _git(repo, "checkout", "-b", "feature")
    (repo / "f").write_text("feature\n")
    _git(repo, "commit", "-am", "feat: feature change")
    _git(repo, "checkout", "main")
    (repo / "f").write_text("main\n")
    _git(repo, "commit", "-am", "feat: main change")
    merge = subprocess.run(
        ["git", "-C", str(repo), "merge", "feature"], capture_output=True, text=True
    )
    assert merge.returncode != 0, "expected a conflict so MERGE_HEAD exists"

    msg = repo / "msg"
    msg.write_text("Merge branch 'feature'\n")
    proc = _run_script(repo, str(msg))
    assert proc.returncode == 0
    assert "merge in progress" in proc.stderr


def test_file_mode_accepts_real_fixup_subject(repo: Path):
    """`git commit --fixup` must not be blocked by the local hook."""
    subject = _git(repo, "log", "-1", "--format=%s").stdout.strip()
    msg = repo / "msg"
    msg.write_text(f"fixup! {subject}\n")
    assert _run_script(repo, str(msg)).returncode == 0


def test_range_mode_rejects_fixup():
    """An escaped fixup! on a validated range means the autosquash was forgotten."""
    assert ccm.check_message("fixup! feat: x\n", "t", ccm.DEFAULT_TYPES, autosquash_ok=False) == 1


def test_range_mode_skips_merge_commits(repo: Path):
    base = _git(repo, "rev-parse", "HEAD").stdout.strip()
    _git(repo, "checkout", "-b", "feature")
    (repo / "g").write_text("x\n")
    _git(repo, "add", "g")
    _git(repo, "commit", "-m", "feat: on feature")
    _git(repo, "checkout", "main")
    (repo / "h").write_text("y\n")
    _git(repo, "add", "h")
    _git(repo, "commit", "-m", "feat: on main")
    _git(repo, "merge", "--no-ff", "feature", "-m", "Merge branch 'feature'")

    proc = _run_script(repo, "--range", f"{base}..HEAD")
    assert proc.returncode == 0, proc.stderr
    assert "checked 2 commit message(s)" in proc.stderr  # the merge is excluded


def test_range_mode_unresolvable_range_is_graceful(repo: Path):
    """A force-push rewrites history; the old tip must not produce a traceback."""
    proc = _run_script(repo, "--range", "0000000000000000000000000000000000000001..HEAD")
    assert proc.returncode == 1
    assert "cannot resolve range" in proc.stderr
    assert "Traceback" not in proc.stderr


def test_range_mode_rejects_malformed_range(repo: Path):
    """Equals form reaches validate_range; the two-token form argparse refuses first."""
    proc = _run_script(repo, "--range=--upload-pack=/bin/sh..HEAD")
    assert proc.returncode == 1
    assert "malformed range" in proc.stderr
