# tag-hooks

Shared commit-message validation for repositories that release with
[release-please](https://github.com/googleapis/release-please).

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

### CI

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
style`. A repo needing more passes its own — **never** by editing this script:

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

## Behaviour is pinned by tests

`tests/commit_message_cases.json` is a golden corpus of 26 cases. A consuming repo can run
it against the revision it has pinned — that's how behavioural drift gets caught, rather
than by reading diffs.

```bash
python3 -m pytest tests/
```

## Licence

MIT. See [LICENSE](LICENSE).
