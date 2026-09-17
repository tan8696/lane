---
description: Revert the changes Lane flagged as unrelated
---
Run `sh "${CLAUDE_PLUGIN_ROOT}/hooks/run.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/lane.py" revert` first.
That is a dry run: it only prints what it would do. Show the user that plan verbatim.

Only once they agree, re-run it with `--yes`. Add `--include-whitespace` to also drop whitespace-only
hunks inside files the task legitimately changed — that is drive-by reformatting, and it is the one
thing a file-level audit cannot separate out on its own.

This is destructive: `restore` throws away working-tree changes to a tracked file, and `delete`
removes an untracked file. Never pass `--yes` on your own initiative, and never use it to undo work
the user actually asked for — if a flagged change was wanted, expand the scope with a reason instead.
