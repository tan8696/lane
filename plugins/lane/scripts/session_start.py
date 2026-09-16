#!/usr/bin/env python3
"""SessionStart: stdout is added to Claude's context."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lane_core as L

data = json.load(sys.stdin)
root = L.repo_root(data.get("cwd") or os.getcwd())
if not root or L.mode(root) == "off":
    sys.exit(0)  # repo has not opted in: say nothing, enforce nothing
s = L.load_scope(root)
cur = f"Current scope: '{s['intent']}' allow={s['allow']}" if s else "No scope declared yet."
print(f"""[Lane] This repo enforces task-scoped edits (mode: {L.mode(root)}).
- Before your FIRST file change for a new task, declare the smallest scope that fits:
  {L.RUN} declare --intent "<one line>" --allow "<glob>" [--allow "<glob>" ...]
- Need more later? Ask, with a reason:
  {L.RUN} expand --allow "<glob>" --reason "<why>"
- Edits outside scope need user approval. No drive-by formatting, renames, or refactors.
- Never write to .git/.
{cur}""")
