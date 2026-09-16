# Hook contract — observed, not documented

_P0 spike, 2026-09-17. Claude Code **v2.1.143**, Windows 11, Python 3.14.7, git 2.55._

> **Re-verified on v2.1.273** (same day, after an auto-update — 130 releases later): PreToolUse
> `allow, deny, ask, defer`, Stop's top-level `decision: ["approve","block"]` + `reason`, and
> `stop_hook_active` in Stop's input are all unchanged. Note when re-checking: grep patterns tied to
> minified identifiers rot between builds (`h.enum(...)` became `q(...)`), so match on the stable
> literal strings, not the surrounding code.

Method: strings extracted from the shipped binary (`grep -a -o -E '...' ~/.local/bin/claude`) plus
hook scripts driven with synthetic stdin against throwaway git repos. **The binary is the oracle** —
the published docs were wrong on two points below.

## Verified contract

| Item | Observed | Source |
|---|---|---|
| PreToolUse decision values | `allow`, `deny`, `ask`, `defer` | binary: `Unknown hook permissionDecision type: … Valid types are: allow, deny, ask, defer` |
| PreToolUse output shape | `{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":…,"permissionDecisionReason":…}}` | binary zod schema |
| `updatedInput` | honored for `allow` and `ask` — a hook can **rewrite** the tool call | binary: `Hook … modified tool input keys: […]` |
| `defer` | print-mode only; ignored in interactive with a warning | binary: `returned permissionDecision=defer in interactive mode; ignoring` |
| Stop block shape | top-level `{"decision":"block","reason":"…"}` | binary: `decision: h.enum(["approve","block"]), reason` |
| Stop input | `stop_hook_active: boolean` at top level, plus `last_assistant_message` | binary: `hook_event_name: literal("Stop"), stop_hook_active: boolean, last_assistant_message` |
| SessionStart | plain stdout is appended to context | docs + binary |
| Permission modes | `default`, `acceptEdits`, `auto`, `bypassPermissions`, `dontAsk`, `plan` | binary: `EXTERNAL_PERMISSION_MODES` |
| Windows hook shell | Git Bash when present, else PowerShell | docs |

### Docs were wrong

- A docs summary claimed **`ask` is not a valid** `permissionDecision`. It is valid in v2.1.143.
- The same summary claimed Stop blocks via `hookSpecificOutput`. It does not — Stop uses the
  **top-level** `decision`/`reason` pair, which is what the starter kit already emits.
- The blueprint's warning that listing `hooks` in `plugin.json` double-loads is **outdated**:
  declaring it now *disables* auto-discovery instead.

### Still open

**Does `permissionDecision:"ask"` still prompt when the session is in `acceptEdits`?**
Static evidence is strong (a hook `ask` yields a dedicated `hookPermissionResult{behavior:"ask", message}`
rather than folding into the normal flow) but not conclusive. Needs a 2-minute live test:
turn on accept-edits, trigger an out-of-scope edit, see whether a prompt appears.
Either way P2 must read `permission_mode` from stdin, because `bypassPermissions` definitely skips prompts
and would silently launder out-of-scope writes into `approved_outside`.

## P0 results

`claude plugin validate` passes for both the plugin and the marketplace manifest
(one cosmetic warning: marketplace has no `description`).

Test suite: **6/6 green on Windows** after two fixes, both the same root cause —
non-ASCII crossing a cp1252 boundary:

1. `lane_core._save/_load`, `stop_audit.py`, `lane.py audit` called `read_text`/`write_text`
   with no `encoding=`, so the emoji in the report hit cp1252 and raised `UnicodeEncodeError`
   **after** truncating `report.md` to zero bytes. Fixed with explicit `encoding="utf-8"` at the
   four I/O sites plus one `sys.stdout.reconfigure` in `lane_core`.
2. `tests/test_lane.py` decoded child stdout with `text=True` (locale codec) and got `None` back
   when decoding failed. Fixed with `encoding="utf-8"`. This one was a test bug — the real consumer
   (Claude Code, Node) reads UTF-8.

Enforcement checklist, driven with synthetic hook JSON against a temp repo:

| Case | Decision | Wanted |
|---|---|---|
| no scope declared, edit in repo | `deny` | deny |
| in-scope edit | pass | pass |
| out-of-scope edit, `LANE_MODE=ask` | `ask` | ask |
| write into `.git/` | `deny` | deny |
| `echo hi > src/db.py` (out of scope) | `ask` | ask |
| `pytest -q 2>&1 \| tail -5` | pass | pass |
| agent self-approving `lane.py declare` | `ask` | ask |
| out-of-scope edit, `LANE_MODE=strict` | `deny` | deny |
| **`black .`** | **pass** | ask — **gap confirmed** |
| **`git checkout -- src/db.py`** | **pass** | ask — **gap confirmed** |

Stop audit end-to-end: correctly blocks once, classifies an out-of-scope edit and an untracked
file as unrelated, leaves pre-existing user WIP unblamed, and writes a readable `report.md`.

### Measurements

- **PreToolUse latency: 146 ms/call** (10-run average, warm). Paid on every Edit/Write/Bash.
  Python startup dominates; two `git` spawns per call are the removable part.
  _(P1 removed both git spawns and added the `sh` launcher: now 131 ms/call, of which 86 ms is bare
  interpreter startup and 32 ms is the wrapper.)_
- **`C:\Users\Tanish` is itself a git repo**, so every path under the home directory — including
  `%TEMP%` — resolves to a repo root. With Lane installed user-wide and no scope declared it would
  deny every write anywhere on this machine. This is plan defect #1, confirmed on real hardware.
- The deny message emits the CLI path with Windows backslashes
  (`python3 "D:\github\claude plugin\...\lane.py"`) into a command meant for bash. It happens to work,
  but it should be posix.

## Probe

`tools/probe_hook.py` appends every hook payload to `$LANE_PROBE_LOG` (default `~/.lane-probe.jsonl`),
never prints, never blocks. Wire it into any event in project `.claude/settings.json` to capture real
payloads instead of guessing:

```json
{"hooks":{"PreToolUse":[{"hooks":[{"type":"command",
  "command":"python \"D:/github/claude plugin/tools/probe_hook.py\""}]}]}}
```
