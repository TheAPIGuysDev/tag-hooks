"""Behaviour tests for scripts/gitleaks-staged.sh.

The scan tests need docker (and pull the pinned gitleaks image); they are
skipped where docker is unavailable. The no-docker test always runs.
"""
import os
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "gitleaks-staged.sh"
SECRET = 'access_group_id = "b801b330-4071-70ad-e4d3-b5b6bf47cc12"\n'
needs_docker = pytest.mark.skipif(shutil.which("docker") is None, reason="docker not available")


def git(cwd, *args):
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=cwd, check=True, capture_output=True,
    )


def run(cwd, env=None):
    return subprocess.run([str(SCRIPT)], cwd=cwd, capture_output=True, text=True, env=env)


@pytest.fixture
def repos(tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    git(main, "init", "-q", "-b", "main")
    (main / "README").write_text("hi\n")
    git(main, "add", ".")
    git(main, "commit", "-qm", "init")
    wt = tmp_path / "wt"
    git(main, "worktree", "add", "-q", str(wt), "-b", "feat")
    return main, wt


def test_fails_loudly_without_docker(repos):
    main, _ = repos
    git_dir = os.path.dirname(shutil.which("git"))
    bash_dir = os.path.dirname(shutil.which("bash"))
    env = {"PATH": f"{git_dir}:{bash_dir}"}
    if shutil.which("docker", path=env["PATH"]):
        pytest.skip("docker lives next to git/bash; cannot hide it")
    result = run(main, env=env)
    assert result.returncode != 0
    assert "docker is required" in result.stderr


@needs_docker
@pytest.mark.parametrize("which", ["main", "wt"])
def test_secret_is_caught_in_checkout_and_linked_worktree(repos, which):
    cwd = dict(zip(["main", "wt"], repos))[which]
    (cwd / "f.tf").write_text(SECRET)
    git(cwd, "add", "f.tf")
    result = run(cwd)
    assert result.returncode != 0
    assert "generic-api-key" in result.stdout


@needs_docker
def test_clean_and_allowlisted_pass_in_worktree(repos):
    _, wt = repos
    assert run(wt).returncode == 0
    (wt / "f.tf").write_text(SECRET.rstrip("\n") + "  # gitleaks:allow\n")
    git(wt, "add", "f.tf")
    assert run(wt).returncode == 0
