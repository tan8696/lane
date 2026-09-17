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
        "work", "working", "instead", "because", "after", "before", "while", "here",
        # auxiliaries and filler: they ate the word budget and starved the one signal word
        "being", "been", "does", "doesn", "don", "isn", "aren", "wasn", "weren", "even", "ever",
        "every", "still", "really", "very", "much", "more", "most", "some", "such", "than",
        "though", "although", "what", "which", "where", "whether", "they", "were", "will",
        "seems", "seem", "looks", "look", "getting", "happens", "happen", "something", "anything"}
# generated or vendored: never worth proposing as a scope
SKIP = ("__pycache__/", "node_modules/", "/dist/", "/build/", ".min.", "site-packages/")
SKIP_SUFFIX = (".pyc", ".pyo", ".so", ".dll", ".class", ".lock", ".png", ".jpg", ".gif", ".pdf")
MAX_WORDS = 8
MAX_FILES = 6


def interesting(path):
    p = "/" + path
    return not (any(s in p for s in SKIP) or path.endswith(SKIP_SUFFIX))

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
# 4+ char words, plus short ALL-CAPS acronyms (VAT, API, SQL, JWT) - the length filter used
# to drop exactly the most identifying terms in a bug report.
for w in re.findall(r"[A-Za-z_][A-Za-z0-9_]{3,}|(?<![A-Za-z])[A-Z]{2,3}(?![A-Za-z])", (data.get("prompt") or "")[:500]):
    lw = w.lower()
    if lw not in STOP and lw not in seen:
        seen.add(lw)
        words.append(w)
    if len(words) >= MAX_WORDS:
        break

hits = {}
tracked = [f for f in L.git(root, "ls-files").stdout.splitlines() if interesting(f)]
for w in words:
    for f in L.git(root, "grep", "-l", "-i", "-F", "-e", w).stdout.splitlines()[:20]:
        if interesting(f):
            hits[f] = hits.get(f, 0) + 1
    for f in tracked:  # a filename match is a stronger signal than a content match
        if w.lower() in f.lower():
            hits[f] = hits.get(f, 0) + 2

best = [f for f, _ in sorted(hits.items(), key=lambda kv: (-kv[1], kv[0]))[:MAX_FILES]]

# A bug fix usually wants a regression test, and a scope without one forces the agent to either
# skip the test or stop and ask. Measured in bench/: that ask was the only thing Lane ever actually
# intercepted, so propose the tests up front instead of making the user approve them later.
from pathlib import PurePosixPath  # noqa: E402  (local to this heuristic)

stems = {PurePosixPath(f).stem.lower() for f in best}
tests = [f for f in tracked
         if f not in best and "test" in PurePosixPath(f).name.lower()
         and any(s and s in PurePosixPath(f).name.lower() for s in stems)]
if not tests:  # no name match: fall back to the repo's test folder, if it has one
    tests = sorted({str(PurePosixPath(f).parent) + "/" for f in tracked
                    if "test" in PurePosixPath(f).parent.name.lower()})[:1]
best += tests[:2]
allow = " ".join(f'--allow "{f}"' for f in best) or '--allow "<glob>"'
found = "\n".join(f"  {f}" for f in best) or "  (no obvious match — pick the files yourself)"
print(f"""[Lane] No scope for this task yet. Files that look related:
{found}
Declare before your first edit, trimming this to what the task actually needs:
  {L.RUN} declare --intent "<one line>" {allow}""")
