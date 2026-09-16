#!/usr/bin/env python3
"""PostToolUse: record touched files. Out-of-scope writes reaching here were user-approved."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lane_core as L

data = json.load(sys.stdin)
ti = data.get("tool_input") or {}
cwd = data.get("cwd") or os.getcwd()
root = L.repo_root(cwd)
if not root:
    sys.exit(0)
if L.mode(root) == "off":
    sys.exit(0)
scope = L.load_scope(root)
r = L.rel(root, cwd, ti.get("file_path") or ti.get("notebook_path"))
if not (scope and r):
    sys.exit(0)
if not L.session_ok(root, scope, data.get("session_id")):
    sys.exit(0)  # another session's scope; not ours to record against

t = L.load_touched(root)
if r not in t["files"]:
    t["files"].append(r)
if not L.in_scope(r, scope) and r not in t["approved_outside"]:
    t["approved_outside"].append(r)
L.save_touched(root, t)
