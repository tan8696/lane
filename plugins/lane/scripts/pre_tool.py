#!/usr/bin/env python3
"""PreToolUse: enforce scope on file writes and shell mutations."""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lane_core as L


def decide(decision, reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


data = json.load(sys.stdin)
tool, ti = data.get("tool_name"), data.get("tool_input") or {}
cwd = data.get("cwd") or os.getcwd()
root = L.repo_root(cwd)
if not root:
    sys.exit(0)  # fail open outside git

MODE = L.mode(root)
if MODE == "off":
    sys.exit(0)  # repo has not opted in (`lane.py init`); Lane stays out of the way

if tool == "Bash":
    cmd = ti.get("command", "")
    m = re.search(r"lane\.py\S*\s+(declare|expand|clear|off|revert)\b", cmd)
    if m:
        # Unattended runs have nobody to ask, so an agent could never declare its first scope.
        # LANE_ALLOW_SELF_SCOPE=1 lets it declare/expand on its own — never `clear` or `off`,
        # because disabling the guard is not the same as choosing a scope to work under.
        if m.group(1) in ("declare", "expand") and os.environ.get("LANE_ALLOW_SELF_SCOPE") == "1":
            sys.exit(0)
        decide("ask", f"Lane: approve scope change?\n{cmd}")  # agent can't self-approve
    raw = L.bash_write_targets(cmd, cwd)
elif tool in L.FILE_TOOLS:
    raw = [ti.get("file_path") or ti.get("notebook_path")]
else:
    sys.exit(0)

paths = [r for r in (L.rel(root, cwd, p) for p in raw) if r is not None]
if not paths:
    sys.exit(0)  # nothing inside repo; Claude Code's own permissions apply
if any(L.is_protected(r) for r in paths):
    decide("deny", "Lane: writes to .git/ are not allowed.")

policy = L.load_policy(root)
for r in paths:
    g = L.policy_denies(r, policy)
    if g:
        decide("deny", f"Lane policy: {r} is off limits ({L.POLICY_FILE} forbids '{g}'). "
                       "This is a repo-wide rule, not a task scope — it cannot be expanded away. "
                       "If the change is genuinely needed, a human has to edit the policy.")

scope = L.load_scope(root)
if not scope:
    decide("deny", f'Lane: no scope declared. First run:\n{L.RUN} declare --intent "..." --allow "<glob>"')
if not L.session_ok(root, scope, data.get("session_id")):
    decide("deny", f'Lane: the active scope "{scope["intent"]}" belongs to another session. '
                   f'Declare one for this task:\n{L.RUN} declare --intent "..." --allow "<glob>"')

outside = [r for r in paths if not L.in_scope(r, scope)]
if not outside:
    sys.exit(0)

reason = (f"Lane: {outside} is outside task scope '{scope['intent']}' (allow={scope['allow']}). "
          f'If truly required: {L.RUN} expand --allow "<glob>" --reason "<why>"')
decide("deny" if MODE == "strict" else "ask", reason)
