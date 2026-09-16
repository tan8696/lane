#!/usr/bin/env python3
"""UserPromptSubmit: when this session has no usable scope, propose one from the prompt.

stdout lands in the agent's context, so this is a hint, not enforcement. It stays silent whenever
a usable scope already exists — suggesting on every message is noise, and noise gets Lane removed.
"""
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lane_core as L

# words that match half the repo and tell us nothing about which files the task needs
STOP = {"please", "should", "would", "could", "there", "their", "about", "also", "just", "like",
        "using", "with", "from", "into", "when", "then", "have", "need", "want", "make", "this",
        "that", "them", "these", "those", "your", "mine", "code", "file", "files", "line", "lines",
        "work", "working", "instead", "because", "after", "before", "while", "here"}
MAX_WORDS = 5
MAX_FILES = 6

data = json.load(sys.stdin)
if data.get("source", "user") != "user":
    sys.exit(0)  # sdk/system/loop injections are not a new human task
root = L.repo_root(data.get("cwd") or os.getcwd())
if not root or L.mode(root) == "off":
    sys.exit(0)

sid = data.get("session_id")
scope = L.load_scope(root)
if scope and (not sid or scope.get("session") in (None, sid)):
    sys.exit(0)  # this session already has a scope to work under

words, seen = [], set()
for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}", (data.get("prompt") or "")[:500]):
    lw = w.lower()
    if lw not in STOP and lw not in seen:
        seen.add(lw)
        words.append(w)
    if len(words) >= MAX_WORDS:
        break

hits = {}
tracked = L.git(root, "ls-files").stdout.splitlines()
for w in words:
    for f in L.git(root, "grep", "-l", "-i", "-F", "-e", w).stdout.splitlines()[:20]:
        hits[f] = hits.get(f, 0) + 1
    for f in tracked:  # a filename match is a stronger signal than a content match
        if w.lower() in f.lower():
            hits[f] = hits.get(f, 0) + 2

best = [f for f, _ in sorted(hits.items(), key=lambda kv: (-kv[1], kv[0]))[:MAX_FILES]]
allow = " ".join(f'--allow "{f}"' for f in best) or '--allow "<glob>"'
found = "\n".join(f"  {f}" for f in best) or "  (no obvious match — pick the files yourself)"
print(f"""[Lane] No scope for this task yet. Files that look related:
{found}
Declare before your first edit, trimming this to what the task actually needs:
  {L.RUN} declare --intent "<one line>" {allow}""")
