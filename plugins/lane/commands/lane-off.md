---
description: Turn Lane off for this repository
---
Run `sh "${CLAUDE_PLUGIN_ROOT}/hooks/run.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/lane.py" off`.

This asks the user for approval at the prompt. That is deliberate — an agent must not be able to
disable its own guard. Once it succeeds, confirm Lane is off for this repo and mention that
`lane.py init` turns it back on. Declared scopes are left untouched.
