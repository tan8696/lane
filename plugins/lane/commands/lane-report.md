---
description: Show Lane's scope report for the current task
---
Run `sh "${CLAUDE_PLUGIN_ROOT}/hooks/run.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/lane.py" audit`.

Lead with the report's Summary line, then three bullets: what changed on-intent, what was flagged
(unrelated, whitespace-only, approved-outside), and any scope expansions with their reasons.

The report is markdown and is written to `.git/lane/report.md`, so offer it as a paste-ready block
for the PR description if the user is about to open one.
