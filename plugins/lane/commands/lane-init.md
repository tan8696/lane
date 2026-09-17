---
description: Turn Lane on for this repository
---
Run `sh "${CLAUDE_PLUGIN_ROOT}/hooks/run.sh" "${CLAUDE_PLUGIN_ROOT}/scripts/lane.py" init`.

Lane does nothing in a repo that has not opted in, so this is the first thing a new user runs.
It writes `.git/lane/enabled`, which is local and never committed — it opts in this clone only.

Afterwards, tell the user:
- the mode it reported (`ask` by default: out-of-scope writes prompt them; `LANE_MODE=strict` denies),
- that hooks bind at session start, so **they must restart Claude Code** for enforcement to begin if
  the plugin was installed during this session,
- that `/lane-off` reverses it.

If they want every developer on the repo guarded without each of them running this, point them at a
committed `.lane/policy.json` instead — that opts the repo in for everyone.
