---
description: Show or change the current Lane scope
---
Run `sh "${CLAUDE_PLUGIN_ROOT}/hooks/run.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/lane.py" show` and report
the mode, intent, allow list, and how many expansions there have been.

If the user also named files or a change they want:

- same task, more files → `expand --allow "<glob>" --reason "<why>"`
- different task → `declare --intent "<one line>" --allow "<glob>"`

Never widen the scope without stating the reason, and prefer exact files over folders.
