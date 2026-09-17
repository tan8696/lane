# Lane

**A task-scoped edit guard for Claude Code.** Your agent declares which files a task needs, Lane
blocks writes outside that set, and audits the final diff against it.

Hooks run outside the model's control, so it is enforcement, not a prompt asking nicely.

```
You:   fix the login redirect
Agent: declared scope — src/auth/login.ts, tests/auth/login.test.ts
       ✓ edited src/auth/login.ts
       ⛔ blocked: src/utils/format.ts is outside the scope for this task
Lane:  Summary: 1 file changed, all on-intent. 0 unrelated changes.
```

---

## Install

Inside Claude Code:

```
/plugin marketplace add tan8696/lane
/plugin install lane@lane-marketplace
```

Or from your shell:

```bash
claude plugin marketplace add tan8696/lane
claude plugin install lane@lane-marketplace
```

**Restart Claude Code after installing.** Hooks bind at session start — the session you installed
from is not guarded, the next one is.

To try it without installing anything:

```bash
git clone https://github.com/tan8696/lane && cd lane
claude --plugin-dir ./plugins/lane
```

## Turn it on for a repo

**Lane does nothing until a repo opts in.** Installing it never changes how your other repos behave —
no output, no hooks firing, no surprises. In the repo you want guarded:

```
/lane-init
```

That writes `.git/lane/enabled`, which is local to your clone and never committed. `/lane-off`
reverses it. To opt a repo in for *everyone* on the team, commit a `.lane/policy.json` instead
(see [Teams](#teams-policy-and-the-pr-check)).

## Use it

You mostly do not. The agent reads the scope instructions from the session context and declares its
own; you see the declaration and the audit. The slash commands are for when you want to steer:

| Command | What it does |
|---|---|
| `/lane-init` | opt this repo in |
| `/lane-scope` | show the current scope, or declare/expand one |
| `/lane-report` | the audit for the current task, paste-ready for a PR |
| `/lane-revert` | undo what Lane flagged as unrelated (dry run first) |
| `/lane-off` | opt this repo out |

Declaring and expanding always prompt **you**, so an agent cannot quietly widen its own guardrails.

---

## How it works

Five hooks, ~500 lines of Python, no dependencies.

| Hook | Event | What it does |
|---|---|---|
| `session_start.py` | `SessionStart` | tells the agent Lane is on, the mode, and the current scope |
| `suggest_scope.py` | `UserPromptSubmit` | reads the prompt, proposes the files it probably needs |
| `pre_tool.py` | `PreToolUse` | **the enforcement point** — allow, ask, or deny the write |
| `post_tool.py` | `PostToolUse` | records what was actually touched |
| `stop_audit.py` | `Stop` | diffs the working tree against the scope, writes the report |

`pre_tool.py` matches `Write`, `Edit`, `MultiEdit`, `NotebookEdit` and `Bash`. Bash is checked
heuristically: redirects, `rm`/`mv`/`cp`/`sed -i`, in-place formatters (`black`, `prettier --write`,
`ruff format`, `gofmt -w`), working-tree `git` commands, `find -delete`, and wrappers like
`sudo`/`xargs`.

Everything lives in `.git/lane/`, so state is per-repo, per-clone, and never committed.

### Modes

| `LANE_MODE` | Out-of-scope write | Use when |
|---|---|---|
| `off` | ignored — Lane does nothing, says nothing | repo hasn't opted in (the default) |
| `ask` | you get an approval prompt | normal interactive work (default once opted in) |
| `strict` | denied outright, no prompt | unattended or CI runs |

`LANE_MODE` overrides the per-repo setting in both directions.

Unattended runs have nobody to ask, which would leave an agent unable to declare its first scope. So
either **declare the scope before launching the agent** (preferred — the operator sets the boundary),
or set `LANE_ALLOW_SELF_SCOPE=1` to let the agent declare and expand on its own. That flag never
covers `clear` or `off`: disabling the guard is not the same as choosing a scope to work under.

### Scope matching

| Pattern | Matches |
|---|---|
| `src/auth/` | everything under that folder |
| `src/*.py` | `src/a.py` — **not** `src/deep/mod.py` (`*` stops at `/`) |
| `src/**/*.py` | any depth (`**/` also matches zero directories) |

A scope is **bound to the session that first uses it**: a second Claude session in the same repo
can't inherit it and is told to declare its own. The audit ignores generated files
(`package-lock.json`, `Cargo.lock`, `go.sum`, …); add more with an `ignore` list in `scope.json`.

### The CLI

The slash commands wrap this. You can call it directly — the full path is printed in the session
context, or from a clone:

```bash
python3 plugins/lane/scripts/lane.py <command>
```

```
init                                enable Lane for this repo
off                                 disable it
declare --intent "..." --allow GLOB [--allow GLOB ...]
expand  --allow GLOB --reason "..."
show                                current mode + scope
audit                               the last report (also at .git/lane/report.md)
clear                               drop the scope, keep the repo enabled
revert  [--yes] [--include-whitespace]
export                              write .lane/scope.json for committing
ci      --base origin/main          the PR check
```

`revert` is a dry run unless you pass `--yes`. `--include-whitespace` also drops whitespace-only
hunks inside files the task legitimately changed — that is drive-by reformatting, and it is the one
thing a file-level audit cannot separate out on its own.

---

## Teams: policy and the PR check

Two committed files turn Lane from a personal habit into a repo rule.

**`.lane/policy.json`** — repo-wide, and no agent can expand its way past it:

```json
{
  "never": ["infra/**", "migrations/**", ".github/workflows/**"],
  "require_scope": true
}
```

A committed policy also opts the repo in, so every developer's agent is guarded without each of them
running `/lane-init`. A `never` path is refused at write time with a message saying so, and `expand`
cannot override it — only a human editing the policy can.

**`.lane/scope.json`** — the scope that was declared for a change. `lane.py export` writes it from
the active session so you can commit it with the work.

Then, in CI:

```bash
python3 plugins/lane/scripts/lane.py ci --base origin/main
```

It diffs the branch against the base, checks every touched file against the policy and the declared
scope, prints a markdown report, and exits non-zero on a violation. Copy
[`docs/lane-pr.yml`](docs/lane-pr.yml) into `.github/workflows/` to run it on every PR — the report
goes to the job summary, so it needs no token and no comment permissions.

**This half is agent-agnostic.** It reads the git diff, not the agent's tool calls, so it works the
same for Codex, Cursor, or a human who forgot what they were doing.

---

## What it measurably does

Benchmarked in `bench/` — every task run twice, bare and under Lane, in a throwaway seeded repo with
planted temptation files:

| design | arm | passed | off-intent lines/task | bait files touched | sec/task |
|---|---|---|---|---|---|
| easy | baseline | 4/4 | 0.0 | 0 | 33 |
| easy | lane | 3/3 | 0.0 | 0 | 21 |
| hard | baseline | 13/13 | **0.9** | 0 | 67 |
| hard | lane | 12/12 | **0.0** | 0 | 55 |

**Lane cost nothing measurable** — same pass rate, same diff size, and the hooks add ~130 ms per tool
call. The hard rows aggregate a 24-cell repeat run (3 per cell, unsandboxed); the easy rows are a
single pass.

**And the honest part:** that 0.9 is not diffuse sloppiness. It is **2 of 13 baseline runs writing a
regression test** in a file outside the declared scope, 6 lines each. None of the ~26 planted baits —
unused imports, `# TODO: delete this module`, `DEBUG = True`, README typos — was ever touched. So
what Lane actually intercepted was the agent adding a test for the bug it had just fixed, turning a
silent write into an explicit ask:

> "there's no regression test for a DE billing / non-DE shipping case, so this bug could silently
> resurface. Want me to add one to `tests/test_cart.py`? That'd be a small scope expansion beyond
> `src/pricing.py`, so I'd flag it to Lane first if you'd like it done."

That is a feature if you review every line and hate surprise files, and a cost if you wanted the
test — which is why **a scope should normally include the matching tests**, and the suggester
proposes them.

So the claim this project makes is a guarantee, not a smaller diff: **a declared boundary and an
audit trail of what was touched, at no measurable cost.** Not "−70% off-intent lines" — that was the
original pitch, and the benchmark did not support it.

Read [`bench/README.md`](bench/README.md) before quoting any of this; it lists what the benchmark
does not cover. Reproduce it with:

```bash
python bench/run.py --tasks-file tasks-hard.json --repeat 3
```

## Known limits

- **A guardrail, not a sandbox.** It keeps a cooperative but sloppy agent in line. `python -c` can
  still write files without being caught before the fact — the Stop audit is the backstop.
- **Bash write detection is heuristic.** Paths arriving through a pipe, or writes from `python -c`,
  are invisible to it.
- **`ask` mode needs a human.** Use `strict` for unattended runs.
- **Scope is path-level.** You allow files and globs, not functions. Within an allowed file the audit
  flags whitespace-only hunks but does not judge whether a hunk matches your intent — that would need
  a model in the loop, which is deliberately not built.
- **Evidence is one model, short tasks.** Other agents, older models, and genuinely long autonomous
  sessions are untested.

## Requirements

git, Python 3.9+, no third-party dependencies. On Windows the hooks run through Git Bash, which ships
with Git — Lane already needs git, so there is nothing extra to install. The launcher takes the first
of `python3`, `python`, `py` on `PATH`, preferring a real install over Windows' Microsoft Store alias
stub.

## Development

```bash
git clone https://github.com/tan8696/lane && cd lane
python -m unittest discover -s tests -t tests -v   # 22 tests, no deps
```

| Path | What |
|---|---|
| `plugins/lane/scripts/lane_core.py` | the shared engine: scope matching, git plumbing, classification |
| `plugins/lane/scripts/pre_tool.py` | enforcement |
| `plugins/lane/hooks/hooks.json` | hook wiring |
| `bench/` | the benchmark harness and seed repos |
| `docs/hook-contract.md` | the hook contract, verified against the shipped binary |
| [`PROJECT.md`](PROJECT.md) | why it exists and how it was built |
| [`PLAN.md`](PLAN.md) | the build plan, with every phase's real outcome — including what got disproven |

Restart Claude Code after changing hooks; skill and command edits apply immediately.

This repo has a committed `.lane/policy.json`, so **Lane guards its own development** — a
fresh clone is already opted in, and `bench/results*.json` is off limits to any agent, because
those are recorded measurements and nothing should be able to rewrite the evidence.

Issues and PRs welcome — especially benchmark runs on other models, which is the gap this project
most needs filled.

## License

MIT
