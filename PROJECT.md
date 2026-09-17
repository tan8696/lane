# Lane

**A task-scoped edit guard for Claude Code.** The agent declares which files a task needs, writes
outside that scope are blocked, and the final diff is audited against the declared intent.

Status: v0.1.0, unreleased. Phases P0-P7 complete, 21/21 tests green, benchmarked.

---

## 1. The problem it was built for

Coding agents make **orthogonal edits**. You ask for a login fix and also get a renamed util, three
reformatted files and an "improved" config. The PR balloons from 20 lines to 400, review becomes the
bottleneck, unrelated edits break things nobody tested, and developers start babysitting the agent —
which cancels the speed gain.

What already exists answers a different question:

| Existing | Answers |
|---|---|
| CLAUDE.md prompt rules | "please stay focused" — advisory, the model can ignore it |
| Permission deny rules, HarnessGuard, agent-guard | "is this path *ever* writable?" — same answer for every task |
| Code review bots | "is this diff good?" — after the damage is in the branch |

Lane answers **"is this edit part of what I asked for, right now?"** — a per-task boundary, enforced
by hooks that run outside the model's control.

## 2. What the evidence actually says

This matters more than the pitch, so it comes second, not last.

A benchmark was built (`bench/`) that runs each task twice — bare, then under Lane — in a throwaway
seeded repo, and measures diff size, lines changed in files the task did not need, whether the fix
actually works, and wall time. Two designs: an easy set (single-line bugs, 6-file repo) and a hard
set (11-file repo with cross-module coupling, vague bug-report prompts naming no file, one genuinely
multi-file fix, 6–7 **bait files per task outside the scope**, and a second turn inviting the agent
to look around).

**Across 8 baseline task-runs on both designs: zero drive-by edits, and none of ~26 planted bait
files touched.** The premise did not reproduce. The second-turn transcripts show why — the agent
notices the adjacent problems and *offers* rather than acting:

> "If your VAT rules require tax on the post-discount total, that's a separate issue from today's
> fix. Want me to look into that too?"

So the honest claim is **not** "−70% off-intent lines". There was nothing to reduce. What the data
supports is: **Lane costs nothing measurable** — identical pass rate, identical diff size — and what
it gives you is a declared boundary plus an audit trail of what was touched.

**A later 24-cell run (3 repeats, unsandboxed) found the only drift in the exercise:** 2 of 12
baseline runs wrote a regression test in a file outside the scope. None of the planted bait was ever
touched. So what Lane intercepts in practice is the agent adding a test for the bug it just fixed,
turning a silent write into an explicit ask — a feature if you review every line, a cost if you
wanted the test. Hence: a scope should normally include the matching tests, and the suggester now
proposes them.

Still untested: other agents and older models, genuinely long autonomous sessions, and repeats at
larger n. See `bench/README.md`.

## 3. How it works

```
user gives a task
  → UserPromptSubmit: if this session has no scope, suggest files from the prompt
  → agent declares:   lane.py declare --intent "fix login" --allow "src/auth/"
  → user approves once
  → agent edits
       PreToolUse:  in scope? yes → write.  no → ask / deny, with how to expand
       PostToolUse: record what was touched
  → agent tries to stop
       Stop: classify the diff against the scope, write the report, block once if unrelated
  → report.md, paste-ready for the PR
```

| Component | Event | Job | Can block |
|---|---|---|---|
| `session_start.py` | SessionStart | inject the rules and the CLI path | no |
| `suggest_scope.py` | UserPromptSubmit | propose a scope from the prompt's keywords | no |
| `pre_tool.py` | PreToolUse | check every write against the scope | **yes** |
| `post_tool.py` | PostToolUse | log touched files, record user-approved exceptions | no |
| `stop_audit.py` | Stop | classify the diff, write the report, block once | **yes** |
| `lane.py` | CLI via Bash | init / off / declare / expand / show / audit / clear / revert / export / ci | — |

**State** lives in `.git/lane/`, so it is per-repo and never committed. `scope.json` holds the
intent, the allow list, the files that were already dirty before the task started (so the user's own
work is never blamed), and any expansions with their stated reasons.

**Modes.** `off` (the default until a repo runs `lane init`), `ask` (out-of-scope writes prompt the
user), `strict` (denied outright — for unattended runs). `LANE_MODE` overrides the per-repo setting
in both directions.

## 4. How it was built

| Phase | What it delivered |
|---|---|
| **P0** Spike | Verified the hook contract against the shipped binary instead of the docs (the docs were wrong twice). Fixed a cp1252 crash that truncated the report to zero bytes on Windows. Measured latency. |
| **P1** Cross-platform | Off by default with per-repo opt-in; subprocess-free hot path (146 → 131 ms/call); segment-aware globs replacing `fnmatch`; an interpreter launcher that prefers a real Python over Windows' Store alias; CI matrix. |
| **P2** Correctness | Scopes bound to the session that first uses them; formatter and working-tree `git` detection; lockfiles ignored by the audit; whitespace-only changes warn instead of blocking. |
| **P3** Friction | Scope suggester on UserPromptSubmit; `/lane-scope`, `/lane-off`, `/lane-report`; a summary line that makes the report paste-ready; `LANE_ALLOW_SELF_SCOPE` for unattended runs. |
| **P4** Evidence | The benchmark above, and the finding that the headline claim cannot be supported. |
| **P5** Ship prep | `PROJECT.md`, `CHANGELOG.md`, evidence in the README, launch drafts, `v0.1.0` tag. Install path verified end to end, including that the plugin still works when relocated to a versioned cache path. |
| **P6** Hunk-level | `git diff -U0` parsing and a shared `classify()` used by both the audit and `revert`; whitespace-only hunks inside on-intent files reported separately; `lane.py revert` (dry run by default) to restore, delete or reverse-apply just the reformat hunks. |
| **P7** Teams | A committed `.lane/policy.json` of `never` paths that no scope can expand past (and whose presence opts the repo in); `lane.py export` to commit the declared scope; `lane.py ci --base <ref>` to audit a PR diff against both; a workflow template in `docs/lane-pr.yml`. |

### Decisions worth knowing

- **The binary is the oracle.** Published docs claimed `ask` was not a valid `permissionDecision`
  and that Stop blocks via `hookSpecificOutput`. Both wrong; the shipped binary says otherwise.
  Every contract claim in `docs/hook-contract.md` was checked against it.
- **Off by default.** The home directory on the dev machine is itself a git repo, so an always-on
  install would have denied every write under `C:\Users\…`, including `%TEMP%`.
- **Hooks outrank permission modes.** Measured: out-of-scope writes were blocked under both
  `acceptEdits` and `bypassPermissions`, so nothing gets laundered as "user-approved". A planned
  mitigation was deleted rather than built.
- **No forced re-declare per message.** Users send several messages per task; invalidating the scope
  each time is the friction that gets a plugin uninstalled. The deny message already teaches the
  agent to re-declare the moment a new task strays.
- **The audit matters more than the block.** The pre-write block is heuristic and evadable
  (`python -c` can always write a file). The Stop audit reads the real git diff, cannot be evaded,
  and produces the artifact a reviewer actually wants.

## 5. What it will do next

P5 (ship prep), P6 (hunk-level audit and `revert`) and P7 (team policy and the PR check) are done;
what is left is publishing and evidence, not code.

- **Publish** — record the demo, push the repo and the `v0.1.0` tag, submit to the awesome lists.
  Drafts are in `docs/launch.md`, written to the guarantee rather than a reduction number.
- **More evidence** — other models, genuinely long autonomous sessions, and repeats at scale.
  `bench/run.py --repeat N --model X` is wired for it.
- **Deferred: the Codex adapter.** Its hook API could not be verified from here, and the team half
  of Lane already works for any agent — `lane ci` reads the git diff, not the agent's tool calls.
  A per-agent adapter only buys pre-write blocking, which the evidence values least.
- **Cut: the LLM hunk judge and symbol-level scopes.** The measured drive-by rate does not justify
  a model in the audit loop, and nothing observed needed sub-file granularity.

Given the P4 result, the PR check is the strongest reason for this to exist: a team gets a
machine-readable statement of what a change was allowed to touch, and proof it stayed inside it.

## 6. Repo layout

```
.claude-plugin/marketplace.json   this repo acts as the marketplace
plugins/lane/
  .claude-plugin/plugin.json      manifest
  hooks/hooks.json                hook wiring (auto-discovered)
  hooks/run.sh                    picks a working Python, no per-call probing
  scripts/                        lane_core, lane (CLI), and the four hooks
  skills/scope/SKILL.md           teaches the agent the workflow
  commands/                       /lane-report, /lane-scope, /lane-off
bench/                            benchmark harness, two seed repos, results
docs/hook-contract.md             what the hook API actually does, verified
tests/test_lane.py                15 tests, nothing beyond unittest
PLAN.md                           the build plan, with every phase's real outcome
```

Requirements: git, Python 3.9+, no third-party dependencies. On Windows the hooks run through Git
Bash, which ships with Git.
