# Changelog

## v0.1.0 — unreleased

First release. A task-scoped edit guard: declare what a task may touch, enforce it on every write,
audit the diff at the end.

### Features

- **Per-task scope** — `lane init` to opt a repo in, then `declare --intent … --allow …`. State
  lives in `.git/lane/`, so it is per-repo and never committed.
- **Enforcement** — `PreToolUse` checks every `Write`/`Edit`/`MultiEdit`/`NotebookEdit` and Bash
  mutation against the scope. Modes: `off` (default until a repo opts in), `ask`, `strict`.
- **Bash write detection** — redirects, `rm`/`mv`/`cp`/`sed -i`, in-place formatters (`black`,
  `prettier --write`, `ruff format`, `gofmt -w`, …), working-tree `git` commands, `find -delete`,
  and wrappers such as `sudo`/`xargs`/`env`.
- **Stop audit** — classifies the diff as on-intent, whitespace-only, approved-outside, unrelated or
  ignored; writes `report.md` with a summary line that pastes straight into a PR description; blocks
  once if anything is unrelated.
- **Scope suggestions** — `UserPromptSubmit` proposes files from the prompt's keywords when the
  session has no scope yet, and stays quiet otherwise.
- **Commands** — `/lane-report`, `/lane-scope`, `/lane-off`.
- **Session binding** — a scope belongs to the session that first used it; a second session is told
  to declare its own rather than inheriting.
- **Unattended runs** — `LANE_ALLOW_SELF_SCOPE=1` lets an agent declare or expand without a human.
  It never covers `clear` or `off`.

### Notes

- Requires git and Python 3.9+. No third-party dependencies. On Windows, hooks run through Git Bash.
- Benchmarked against an unguarded baseline: identical pass rate and identical diff size, so Lane is
  not measurably costly. It also produced no measurable *reduction*, because the baseline made no
  drive-by edits to begin with. See `bench/README.md` before quoting any number.
