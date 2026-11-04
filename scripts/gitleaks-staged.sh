#!/usr/bin/env bash
# Scan staged changes with a pinned gitleaks image, correctly inside git
# linked worktrees.
#
# Why this exists: the upstream `gitleaks-docker` hook mounts only $PWD. In a
# linked worktree `.git` is a file pointing at <main>/.git/worktrees/<name>,
# which does not exist in the container, so gitleaks logs "not a git
# repository", scans nothing and exits 0. This script mounts the worktree
# and the git common dir at their host paths so those pointers resolve.
#
# Bump IMAGE together with any CI job that scans with gitleaks.
set -euo pipefail

IMAGE='ghcr.io/gitleaks/gitleaks:v8.30.1@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f'

command -v docker >/dev/null 2>&1 || {
  echo "gitleaks-staged: docker is required but was not found on PATH" >&2
  exit 1
}

top=$(git rev-parse --show-toplevel)
top=$(cd "$top" && pwd -P)
common=$(git rev-parse --git-common-dir)
common=$(cd "$common" && pwd -P)

out=$(mktemp)
trap 'rm -f "$out"' EXIT

rc=0
docker run --rm \
  -e GIT_CONFIG_COUNT=2 \
  -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0="$top" \
  -e GIT_CONFIG_KEY_1=safe.directory -e GIT_CONFIG_VALUE_1="$common" \
  -v "$top:$top" \
  -v "$common:$common:ro" \
  --workdir "$top" \
  "$IMAGE" \
  git --pre-commit --staged --redact --verbose --no-banner --exit-code 1 \
  >"$out" 2>&1 || rc=$?

cat "$out"

# gitleaks exits 0 even when git itself failed, so treat these as hard errors.
if grep -Eqi 'not a git repository|fatal:|failed to (scan|get|run)|ERR ' "$out"; then
  echo "gitleaks-staged: gitleaks could not read the repository; refusing to report a pass" >&2
  exit 1
fi
exit "$rc"
