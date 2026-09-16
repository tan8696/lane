#!/usr/bin/env python3
"""Throwaway probe: append every hook payload to a JSONL log. Never blocks, never prints.

Wire it into any event (project .claude/settings.json) to see what Claude Code really sends:
  {"hooks":{"PreToolUse":[{"hooks":[{"type":"command",
    "command":"python \"D:/github/claude plugin/tools/probe_hook.py\""}]}]}}
Log path: $LANE_PROBE_LOG, else ~/.lane-probe.jsonl
"""
import json
import os
import sys
import time
from pathlib import Path

raw = sys.stdin.read()
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    data = {"_unparsed": raw}
data["_probe_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
log = Path(os.environ.get("LANE_PROBE_LOG") or Path.home() / ".lane-probe.jsonl")
with log.open("a", encoding="utf-8") as f:
    f.write(json.dumps(data) + "\n")
