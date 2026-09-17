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

c = L.classify(root, scope, L.load_touched(root))
on, ws, approved, unrelated, ignored = c["on"], c["ws"], c["approved"], c["unrelated"], c["ignored"]
ws_hunks = c["ws_hunks"]


def sec(title, xs):
    return f"\n### {title} ({len(xs)})\n" + ("".join(f"- `{x}`\n" for x in xs) or "- none\n")


summary = (f"{len(on)} on-intent, {len(unrelated)} unrelated, {len(approved)} approved outside, "
           f"{len(ws)} whitespace-only, {len(ignored)} ignored")
report = (f"## Lane scope report\n**Intent:** {scope['intent']}  \n"
          f"**Allow:** {', '.join(scope['allow'])}  \n**Summary:** {summary}\n"
          + sec("✅ On-intent", on) + sec("⚠️ Whitespace-only", ws)
          + sec("🟡 Approved outside scope", approved) + sec("❌ Unrelated", unrelated)
          + sec("🔇 Ignored (generated)", ignored))
if ws_hunks:
    n = sum(len(v) for v in ws_hunks.values())
    report += (f"\n### 🧹 Whitespace-only hunks inside on-intent files ({n})\n"
               + "".join(f"- `{f}` ({len(h)} hunk{'s' if len(h) > 1 else ''})\n"
                         for f, h in sorted(ws_hunks.items()))
               + "\nDrop them with `lane.py revert --include-whitespace`.\n")
report += "".join("\n> expanded `" + "`, `".join(e["allow"]) + "`: " + e["reason"] + "\n"
                  for e in scope["expansions"])
(L.state_dir(root, create=True) / "report.md").write_text(report, encoding="utf-8")

# block once; stop_hook_active prevents infinite loops.
# Whitespace-only changes are in-scope by definition here, so they are reported, not blocked —
# blocking them false-fires whenever the task legitimately touches indentation.
if unrelated and not data.get("stop_hook_active"):
    print(json.dumps({"decision": "block", "reason": (
        f"Lane audit: unrelated changes {unrelated}. "
        "Revert them (`lane.py revert`, or `git checkout -- <file>`) unless the user asked for "
        "them. If genuinely required, expand scope with a reason. Then finish.")}))
sys.exit(0)
