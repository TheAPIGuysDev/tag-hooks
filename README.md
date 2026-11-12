# tag-hooks

Shared pre-commit hooks: commit-message validation for repositories that release with
[release-please](https://github.com/googleapis/release-please), and a worktree-safe
gitleaks scan.

## Set up in one command

```bash
pre-commit install --install-hooks
```

That's it. No authentication, no tokens, no accounts. You need `python3`, which you
almost certainly already have.

From then on, a commit with a badly-formatted message is rejected **before** it exists,
with a message telling you what to fix:

```
$ git commit -m "fixed the login bug"
Validate commit message for release-please compatibility.................Failed
  .git/COMMIT_EDITMSG: commit subject does not match conventional-commit format
    got: 'fixed the login bug'
    expected: <type><optional-scope>!?: <description>
    valid types: fix, feat, chore, docs, refactor, perf, test, ci, build, revert, style
```

Fix it and commit again:

```bash
git commit -m "fix(auth): reject expired sessions on refresh"
```

Don't have `pre-commit`? `pipx install pre-commit` (or `brew install pre-commit`). If you
skip all this, nothing breaks — CI still checks your commits when you open a pull
request. You'll just find out later instead of sooner.

## Why the format matters

release-please picks the version number and writes `CHANGELOG.md` from your commit
subjects. A malformed subject doesn't fail anything — it silently produces **no version
bump**, and your change quietly never appears in a release.

`fix:` bumps the patch version. `feat:` bumps the minor. Everything else lands in the
changelog without moving the version.

## Writing a good subject

```
feat(billing): add annual prepay discount
fix: stop retaining driver logs after container removal
docs(pricing): record the 2026 rate card
chore(deps): bump astro from 6.3.3 to 7.1.1
```

The scope in parentheses is optional. `!` before the colon marks a breaking change
(`feat!: drop v1 endpoints`).

A few cases behave in ways worth knowing:

| If you… | What happens |
| --- | --- |
| are mid-merge (`git merge`) | skipped — git generates those subjects, they aren't yours to format |
| use `git commit --fixup` | allowed locally, so `git rebase --autosquash` still works. Rejected in CI, because one reaching `main` means the squash was forgotten |
| use the Revert button on the forge | rejected. release-please can't parse `Revert "…"` either, so it would vanish from the changelog. Write `revert(scope): what you reverted` |
| write `Breaking change:` in the body | rejected. Only the exact `BREAKING CHANGE: ` or `BREAKING-CHANGE: ` is recognised — a miscased footer ships a breaking change as a silent minor bump |

---

## Adding it to a repository

Two layers. **CI is the gate; the local hook is convenience** — a fresh clone, a new
contributor or an automated agent won't have installed it.

### CI: nothing to add inside TheAPIGuysDev

The organization ruleset **`commit-gate`** runs
[`.github/workflows/commit-gate.yml`](.github/workflows/commit-gate.yml) from this
repository, pinned by SHA, on every pull request into the default branch of every
TheAPIGuysDev repository. Only forks of outside projects are excluded, because their
upstream syncs carry upstream's commits. The check shows on the pull request as
**Commit gate**, and the pull request can't merge until it passes. New repositories are
covered from their first pull request.

All that's left per repository is optional: the [local hook](#local), and
[`.github/commit-types`](#extra-commit-types) if the repo needs more types than the
default list.

### CI outside the org ruleset

For a repository outside TheAPIGuysDev, or an excluded fork, add a caller. Inside the
org it's redundant, since the ruleset already runs the same action.

```yaml
name: Commit messages

on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read

jobs:
  validate:
    name: Validate commit messages
    runs-on: ubuntu-latest
    timeout-minutes: 5
    steps:
      - uses: actions/checkout@<sha> # v4
        with:
          fetch-depth: 0
      - uses: TheAPIGuysDev/tag-hooks/.github/actions/commit-message-gate@<sha> # v1.0.0
```

`fetch-depth: 0` is required — the check works over a commit *range*, which a shallow
checkout can't resolve.

Then make that job a **required status check** on your default branch. A workflow that
runs but isn't required doesn't gate anything.

### Local

```yaml
# .pre-commit-config.yaml
default_install_hook_types: [pre-commit, commit-msg]

repos:
  - repo: https://github.com/TheAPIGuysDev/tag-hooks
    rev: <sha> # v1.0.0
    hooks:
      - id: commit-message-format
```

`default_install_hook_types` matters: a plain `pre-commit install` wires only the
pre-commit stage and silently skips `commit-msg`, so the hook would never fire.

### Extra commit types

The default list is `fix, feat, chore, docs, refactor, perf, test, ci, build, revert,
style`. A repo needing more passes its own — **never** by editing this script.

For the org gate, commit `.github/commit-types` holding the **complete** list, separated
by commas, spaces or newlines, with `#` comments allowed:

```
# .github/commit-types
fix, feat, chore, docs, refactor, perf, test, ci, build, revert, style
intake   # client intake records
```

The gate reads it from the pull request's **base** commit, so a pull request can't widen
the list for its own commits. A change to the list applies to the pull requests opened
or updated after it merges. Review a change to this file the way you'd review a change to
CI: a merged change widens the gate for every later pull request. The file must hold
lowercase words only and stay under 4 KB. Anything else fails the check, as does an API
error reading it.

For a per-repo caller and the local hook:

```yaml
        with:
          types: fix,feat,chore,docs,refactor,perf,test,ci,build,revert,style,intake
```

```yaml
        hooks:
          - id: commit-message-format
            args: ["--types=fix,feat,...,intake"]
```

Keep the CI list, the local list and your PR-title lint in step. Lists that disagree
produce the confusing case where a commit passes one check and fails the other.

### Pinning

Pin by **commit SHA with a version comment**, not by tag — tags are mutable, a SHA isn't.

```yaml
rev: 0123456789abcdef0123456789abcdef01234567 # v1.0.0
```

Bumping a pin runs new code in your CI and on developer machines. Review the diff rather
than treating it as routine.

The org ruleset pins `commit-gate.yml` the same way. A change merged here does nothing
until the ruleset's pinned SHA is bumped, and that bump is an org ruleset change that
gets reviewed like any other.

## Secret scanning in worktrees: `gitleaks-staged`

The upstream `gitleaks-docker` pre-commit hook mounts only `$PWD` into the container.
In a git **linked worktree** `.git` is a file pointing at
`<main>/.git/worktrees/<name>`, which doesn't exist in the container. gitleaks logs
`fatal: not a git repository`, scans zero commits, exits 0, and pre-commit prints
**Passed**. Every commit made from a worktree is effectively unscanned.

`gitleaks-staged` fixes that: it runs a pinned gitleaks image, mounting the worktree
and the git common dir (read-only) at their host paths, and scans the staged changes.
It fails if docker is missing or gitleaks can't read the repository, rather than
passing silently. A repo's `.gitleaksignore` and inline `gitleaks:allow` still work.

```yaml
repos:
  - repo: https://github.com/TheAPIGuysDev/tag-hooks
    rev: <sha> # vX.Y.Z
    hooks:
      - id: gitleaks-staged
```

Remove the upstream `gitleaks/gitleaks` / `gitleaks-docker` block when adopting it.
Requires docker. The image is pinned by digest in `scripts/gitleaks-staged.sh`; when
you bump it, bump the gitleaks image in your CI job to the same digest so the local
hook and the gate agree.

## Behaviour is pinned by tests

`tests/commit_message_cases.json` is a golden corpus of 26 cases. A consuming repo can run
it against the revision it has pinned — that's how behavioural drift gets caught, rather
than by reading diffs.

```bash
python3 -m pytest tests/
```

## Licence

MIT. See [LICENSE](LICENSE).
