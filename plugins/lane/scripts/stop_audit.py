#!/usr/bin/env python3
"""Stop: audit the diff vs scope; block once if unapproved out-of-scope changes exist."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lane_core as L

data = json.load(sys.stdin)
root = L.repo_root(data.get("cwd") or os.getcwd())
if not root or L.mode(root) == "off":
    sys.exit(0)
scope = L.load_scope(root)
if not scope or not L.session_ok(root, scope, data.get("session_id")):
    sys.exit(0)

t = L.load_touched(root)
changed = (L.dirty_files(root) - set(scope.get("baseline_dirty", []))) | set(t["files"])
changed = {f for f in changed if not L.is_protected(f)}

ignore = L.IGNORE_DEFAULT | set(scope.get("ignore", []))
ignored = sorted(f for f in changed if os.path.basename(f) in ignore)
changed -= set(ignored)

on, ws, approved, unrelated = [], [], [], []
for f in sorted(changed):
    if f in t["approved_outside"]:
        approved.append(f)
    elif not L.in_scope(f, scope):
        unrelated.append(f)
    elif L.whitespace_only(root, f):
        ws.append(f)
    else:
        on.append(f)


def sec(title, xs):
    return f"\n### {title} ({len(xs)})\n" + ("".join(f"- `{x}`\n" for x in xs) or "- none\n")


report = (f"## Lane scope report\n**Intent:** {scope['intent']}  \n**Allow:** {', '.join(scope['allow'])}\n"
          + sec("✅ On-intent", on) + sec("⚠️ Whitespace-only", ws)
          + sec("🟡 Approved outside scope", approved) + sec("❌ Unrelated", unrelated)
          + sec("🔇 Ignored (generated)", ignored)
          + "".join(f"\n> expanded {e['allow']}: {e['reason']}" for e in scope["expansions"]))
(L.state_dir(root, create=True) / "report.md").write_text(report, encoding="utf-8")

# block once; stop_hook_active prevents infinite loops.
# Whitespace-only changes are in-scope by definition here, so they are reported, not blocked —
# blocking them false-fires whenever the task legitimately touches indentation.
if unrelated and not data.get("stop_hook_active"):
    print(json.dumps({"decision": "block", "reason": (
        f"Lane audit: unrelated changes {unrelated}. "
        "Revert them (`git checkout -- <file>`, or delete if new) unless the user asked for them. "
        "If genuinely required, expand scope with a reason. Then finish.")}))
sys.exit(0)
