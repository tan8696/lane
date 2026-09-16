# Lane — build plan

_Task-scoped edit guard for Claude Code. Plan written 2026-09-17, from the two product artifacts + `lane-starter-kit_1.zip`._

---

## 1. The problem, as understood

Coding agents make **orthogonal edits**: you ask for a login fix, you get a renamed util, three reformatted files and an "improved" config. Existing tooling answers *"is this path ever writable?"* (static permission rules, HarnessGuard, CLAUDE.md prompts) or *"is this diff good?"* (review bots, too late). Nobody answers **"is this edit part of what I asked for, right now?"**

Lane's answer: turn each task into a declared contract (`intent` + `allow` globs), enforce it on every write via `PreToolUse`, and audit the final diff against it via `Stop`. Hooks run outside the model's control, so it's enforcement, not advice.

**The non-obvious thing about this product:** the demo-able part (the block) is the part that makes people uninstall, and the boring part (the Stop audit) is the part that actually works. The block is heuristic and evadable (`python -c`, formatters, any tool it doesn't parse). The audit sees the real git diff, cannot be evaded, and produces the PR artifact teams actually want. This plan weights effort accordingly — the original roadmap does the opposite.

---

## 2. Ground truth verified against the binary

The blueprint warns "hook JSON fields evolve — re-check before each release." Checked against the shipped binary (`~/.local/bin/claude`, v2.1.143), not the docs:

| Assumption in the kit | Verdict | Evidence |
|---|---|---|
| `permissionDecision: "ask"` prompts the user | **valid** | binary: `Valid types are: allow, deny, ask, defer` |
| `permissionDecision: "deny"` blocks | valid | same |
| Stop blocks via top-level `{"decision":"block","reason":...}` | valid | binary schema: `decision: h.enum(["approve","block"]), reason` |
| `stop_hook_active` is a top-level **input** field | valid | binary: `hook_event_name: literal("Stop"), stop_hook_active: boolean` |
| SessionStart plain stdout goes into context | valid | docs + binary |
| `hooks/hooks.json` auto-discovered; listing it in `plugin.json` double-loads | **outdated** — current behavior: declaring it in the manifest *disables* auto-discovery. Not a bug either way; the kit omits it. |
| `python3` works on this machine | resolves to Python 3.14.5 (Store alias); real Python at `C:\Python314` is 3.14.7. Hooks run through **Git Bash** on Windows. |

Web docs were **wrong on two of these** (a doc summary claimed `ask` is invalid and that Stop uses `hookSpecificOutput`). Trust the binary — `grep -a -o` on `~/.local/bin/claude` is the oracle.

Capabilities the current design doesn't use yet:

- `PreToolUse` supports **`updatedInput`** — rewrite a tool call instead of denying it (e.g. narrow a MultiEdit to its in-scope edits).
- Stop input carries **`last_assistant_message`** — free intent signal for the audit, no LLM needed.
- A **`PermissionRequest`** hook event exists — a cleaner future integration point than intercepting PreToolUse.
- `${CLAUDE_PLUGIN_DATA}` — persistent cross-repo dir for config/stats.

---

## 3. Honest read of the starter kit

~350 lines, architecture is right: `.git/lane/` state, deny-with-instructions (the deny message is what actually teaches the agent, not the SKILL.md), `baseline_dirty` so the user's WIP isn't blamed, `approved_outside` inferred from "PostToolUse only fires if the write happened." Keep all of that.

Ten real defects, ordered by how much they hurt:

| # | Defect | Consequence |
|---|---|---|
| 1 | **No scope means deny everything**, in every git repo, with no off switch | Install it globally and it breaks every repo you open. #1 uninstall cause. **Confirmed in P0:** `C:\Users\Tanish` is itself a git repo, so every path under home — including `%TEMP%` — resolves to a repo root and would be denied. |
| 2 | **Scope never expires and isn't bound to a session or task** | Task 2 runs under task 1's scope. Silent under-enforcement — the failure mode you can't see. |
| 3 | **State is per-repo, not per-session** | Two Claude windows on one repo clobber each other's scope. |
| 4 | ~~**`ask` may be auto-approved** in `acceptEdits`/`bypassPermissions`~~ | **Disproven 2026-09-17.** Headless runs under both `--permission-mode acceptEdits` and `--permission-mode bypassPermissions` were blocked: the out-of-scope file was never created and `approved_outside` stayed empty. Hook decisions outrank permission modes, so nothing is laundered. The planned `permission_mode` coupling is cut. |
| 5 | `fnmatch` — `*` matches `/` | `src/*.ts` silently allows `src/a/b/c.ts`. Scope is looser than it looks. |
| 6 | `rel()` returns `None` for unresolvable paths, which is treated as "outside repo" and **passes** | Any Windows path quirk (case, UNC, symlinked temp) silently disables enforcement. Fail-open in the wrong direction. |
| 7 | Bash detector misses `git checkout/restore/apply`, `prettier --write`, `black`, `ruff format`, `gofmt -w`, `eslint --fix`, `find -delete` | Formatters are *literally the reported failure mode* ("reformatted 3 files") and they're not detected. **Proven in P0:** `black .` and `git checkout -- src/db.py` both pass PreToolUse untouched. |
| 8 | Stop blocks on **whitespace-only in-scope** changes | False block when the task legitimately touches indentation. |
| 9 | Every `load_scope()` spawns a second `git` subprocess (`state_dir` calls `rev-parse`) | 2 git spawns + Python startup on *every* Edit/Write/Bash. **Measured in P0: 146 ms/call** on this box (I estimated 300–600 ms; the real number is lower but still paid on every tool call). |
| 10 | No rename detection (`-M`), no ignore list for lockfiles/generated files | `package-lock.json` shows as unrelated on every npm install. |
| 11 | Deny message emits the CLI path with Windows backslashes into a command meant for bash | `python3 "D:\github\...\lane.py"` works by luck; should be posix. Found in P0. |
| 12 | All file I/O used the locale codec, so the report's emoji crashed on cp1252 | **Fixed in P0** — `encoding="utf-8"` at 4 I/O sites + `sys.stdout.reconfigure` in `lane_core`. |

None are architectural. All fit inside the existing ~350 lines.

**Status after P2:** #1, #5, #6, #9, #11, #12 closed in P1; #2, #3, #7, #8, #10 closed in P2; #4 disproven
and cut. Remaining: rename detection (deliberately dropped — see P2 status) and the hunk-level audit
(#10's coarse half), which is P6.

---

## 4. The phases

Effort in focused hours; at 10–15 h/week the calendar follows.

### P0 — Spike: prove it runs on this machine (3–4 h, day 1)

Hook contract is already verified above, so this shrinks to runtime reality.

- Extract kit into `D:\github\claude plugin`, `git init`, run `claude plugin validate ./plugins/lane`.
- Run the 6 tests with `python` (not `python3`) on Windows; record what breaks (temp-dir `relative_to`, path case, line endings).
- Load with `claude --plugin-dir`, run the blueprint's 9-item manual checklist on a scratch repo.
- **The one unknown left:** does `permissionDecision: "ask"` still prompt when `acceptEdits` is on? Test it. If not, defect #4 is real and P2 must read `permission_mode`.
- Add a throwaway probe hook that dumps raw stdin to a file — useful all project long.

**Exit:** tests green on Windows; checklist passes; `docs/hook-contract.md` records what was observed, not what the docs claim.

**Status: done 2026-09-17.** 6/6 tests green on Windows after a UTF-8 fix (defect #12); both manifests validate; enforcement checklist passes all 8 intended cases; defects #1 and #7 confirmed on real hardware; latency measured. Full results in `docs/hook-contract.md`. **One item deferred:** the live `ask`-under-`acceptEdits` test needs an interactive session — see "Still open" in that doc.

### P1 — Cross-platform + the off switch (6–8 h, week 1)

Nothing else matters if it can't be safely installed.

- Interpreter resolution: `python3` fails on many Windows boxes even though it works here. Exec-form hooks or a resolver.
- Path layer: `normcase` comparison, explicit "unresolvable is not the same as outside repo" (defect #6), posix output, CRLF.
- **`LANE_MODE=off|ask|strict`, defaulting to off until the repo opts in** (defect #1). Opt-in via `lane init` or a `.lane/` marker.
- Replace `fnmatch` with segment-aware globbing (defect #5).
- Kill the double `git` spawn; cache repo root (defect #9).
- GitHub Actions matrix: ubuntu / macos / windows.

**Exit:** green CI on 3 OSes; installing Lane in a repo that hasn't opted in changes nothing.

**Status: done 2026-09-17.** 8/8 tests green on Windows (2 new: off-by-default, glob segments). Opt-in via `lane.py init`; `off`/`ask`/`strict` with `LANE_MODE` overriding in both directions; in an un-opted-in repo every hook exits silently. Hot path is now subprocess-free (walk-up repo detection, `.git` read directly) — **146 → 131 ms/call** end-to-end through the launcher, of which 86 ms is bare Python startup and 32 ms is the `sh` wrapper, so Lane's own work is ~13 ms. `fnmatch` replaced with a segment-aware glob (`*` stops at `/`, `**` crosses, `**/` matches zero dirs). CI matrix (ubuntu/macos/windows + a 3.9 floor job) added but **not yet run — it has never executed on macOS or Linux.** Deferred to P2: `-S -E` means Lane must stay stdlib-only; the launcher no longer verifies the interpreter actually runs, so a broken `python3` surfaces as a visible hook error rather than a silent pass.

### P2 — Correctness: the holes that make enforcement a lie (10–14 h, weeks 1–2)

- **Session-scoped state**: `.git/lane/sessions/<session_id>/` plus a `latest` pointer. Fixes defects #2 and #3 in one change.
- **New-task detection**: `UserPromptSubmit` hook, where a new user turn invalidates the scope (or asks to confirm reuse).
- ~~**`permission_mode` coupling**~~ — **cut**: measurement showed hooks already outrank permission modes (defect #4). With no human to ask, an `ask` resolves to a block, so headless runs are strict by default anyway.
- **Bash detector v2**: formatters, `git checkout/restore/apply/stash`, `find -delete`, `xargs`, heredocs (defect #7).
- **Audit v2**: rename detection via `git diff -M`, an `ignore` list in scope for lockfiles/generated files, whitespace-only downgraded from block to warn (defects #8, #10).

**Exit:** one week of dogfooding on real daily work with **zero false blocks**, and every invented evasion caught by the Stop audit even when the pre-write block misses it.

**Status: code done 2026-09-17, exit criterion NOT met.** 12/12 tests green. Shipped: session binding, Bash detector v2, audit v2. Three live `claude -p` runs — two blocked out-of-scope writes (under `acceptEdits` and `bypassPermissions`), one in-scope task completed with zero prompts and a clean report, with the session stamped from a real id. **The dogfood week has not happened** — that is still the real gate, and three scripted runs are not a substitute.

Two deliberate cuts, both because no failure could be demonstrated:

- **Forced re-declare on each new user message** (the planned `UserPromptSubmit` invalidation). Users send several messages per task ("continue", "also fix the test"), so invalidating per message would make the agent re-declare constantly — the exact friction that gets Lane uninstalled. The existing deny already teaches the agent to re-declare the moment a new task touches a file outside the old scope. The residual gap is narrow: a new task touching *only* files the old scope already allows runs under a stale intent label, which is a reporting inaccuracy, not an enforcement hole.
- **Rename detection (`git diff -M`).** A rename within scope shows both names in scope; a rename that moves a file out of scope is already flagged as unrelated. No failing case, so no code.

**Session binding, how it works:** Claude Code exposes no session id to Bash commands (only bridge/cloud variants exist), so the CLI can't stamp itself. `declare` writes `session: null` and the first *hook* to see the scope stamps it; a different session is then denied and told to declare its own. This fixes both the cross-session leak (#3) and the enforcement half of staleness (#2) in ~10 lines, without per-session state directories.

### P3 — Make declaring scope cost nothing (6–8 h, week 3)

Friction is the product risk, not correctness.

- Scope suggestion: `UserPromptSubmit` to keyword `git grep` to proposed globs, so declare is one keystroke instead of a paragraph.
- `/lane-scope` (view/edit), `/lane-off`, improve `/lane-report`.
- Report formatted as a paste-ready PR block.

**Exit:** median task needs one approval and zero scope edits; scope-approvals-needing-edits under 30%.

### P4 — Evidence (8–10 h, week 4)

Can't launch on "−70% off-intent lines" without having measured it.

- `bench/`: 20 fixed tasks on a demo repo, run with and without Lane. Measure diff size, off-intent lines, false blocks, and **hook latency overhead**.
- **Disable the headroom plugin for benchmark runs** (`claude plugin disable headroom`). It adds a PreToolUse hook on every Bash call (measured 663 ms/call, vs Lane's 146 ms) and its proxy compresses context — both confound exactly what P4 measures.
- Publish the real numbers even if they're −40%, not −70%.

**Exit:** a table worth defending on HN.

### P5 — Ship v0.1 (6–8 h, week 5)

README plus a 30-second GIF (block, rescope, report), honest **Known Limits** section ("guardrail, not sandbox"), `v0.1.0` tag, marketplace install path tested from a clean machine, submit to awesome-claude-code lists, Show HN / r/ClaudeAI / X / Dev.to.

**Exit:** 50 installs, first external issue.

### P6 — Hunk-level + revert (12–16 h, weeks 6–8)

Only after P5 shows people keep it installed.

- `git diff -U0` parsing, per-hunk classification (file-level is coarse and produces most remaining false flags).
- `/lane-revert` via `git apply -R` on extracted hunks.
- Optional LLM judge: off by default, cheap model, cached, with `last_assistant_message` as free context.
- Symbol scopes (tree-sitter) — lowest value per hour; do last.

### P7 — Team / CI (later, gated on traction)

GitHub Action posting the scope report and failing on unrelated hunks; `.lane/policy.json` org rules; Codex adapter (verify its hook support first — if thin, wrap the CLI and set sandbox writable roots from the scope); dashboard. **Do not start before P5 proves retention.**

---

## 5. Changes from the original roadmap

- **Codex adapter moves from Phase 3 to P7.** Cross-agent is a positioning story, not a week-7 build. One agent working perfectly beats two working badly.
- **LLM judge moves later and stays off by default.** Heuristics plus hunk-level parsing get most of the way; the judge adds cost, latency and nondeterminism to a hot path.
- **Symbol-level scopes drop to last.** High effort (tree-sitter per language), narrow payoff.
- **A dogfood week is a gate, not a nice-to-have.** "0 false blocks on 3 repos" should be measured by living with it, not by scripted tasks.
- **Two claims need verifying before they enter launch copy**: the "Karpathy Jan 2026 post" and especially "200k+ GitHub stars" for the CLAUDE.md skill — that star count is implausible for a skill repo (it would be top-10 on GitHub overall). If a reviewer catches it on HN it costs the launch. Check it, or cut it.
- **Name check still open**: "Lane" on GitHub / npm / crates.

---

## 6. Open decisions

1. **Default mode.** Recommend `off` until a repo opts in; the doc implies always-on. Always-on is a better demo and a worse install.
2. **Windows-first or Linux-first?** Dev box is Windows; audience is mostly macOS/Linux. Recommend developing on Windows (hardest case) and CI'ing all three — about 2 h extra in P1, saves a class of launch bugs.
3. **Ship the GitHub marketplace repo at P0 (public, WIP) or at P5 (polished)?** Public early gets Phase-0 validation signal for free.
4. **Market-validation track in parallel, or build-first?** Doesn't block any phase, but should start week 1 if wanted.

---

## 7. Total

**~55–70 focused hours to a public v0.1** (P0–P5), about 5 weeks at 12 h/week. Matches the blueprint's "6–10 weeks part-time" with less slack, because the hook-contract research is done and the starter kit is real.

**First three actions:** extract the kit into the repo and `git init`; make the 6 tests pass on Windows; run the manual checklist and write down every false block.
