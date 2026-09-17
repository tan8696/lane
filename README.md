# Lane — task-scoped edit guard for Claude Code

Your agent edits what the task needs. Nothing else.

Lane makes the agent declare which files a task needs, blocks writes outside that scope, and audits
the final diff against it. Hooks run outside the model's control, so it is enforcement, not advice.

## Install

```bash
# one session
claude --plugin-dir ./plugins/lane

# or via this repo as a marketplace (inside Claude Code)
/plugin marketplace add <your-github-user>/lane-kit
/plugin install lane@lane-marketplace
```

Restart Claude Code (or `/reload-plugins`) after changing hooks — skill edits apply immediately,
hook edits do not.

## Opt in per repo

**Lane is off until a repo opts in**, so installing it never changes how your other repos behave:

```bash
python3 plugins/lane/scripts/lane.py init   # enable here (writes .git/lane/enabled)
python3 plugins/lane/scripts/lane.py off    # disable here
```

## Modes

| `LANE_MODE` | Out-of-scope write | Use when |
|---|---|---|
| `off` | ignored — Lane does nothing, says nothing | repo hasn't opted in (the default) |
| `ask` | you get an approval prompt | normal interactive work (default once opted in) |
| `strict` | denied outright, no prompt | unattended or CI runs |

`LANE_MODE` always overrides the per-repo setting, in both directions.

Declaring or expanding a scope always asks the user, so an agent cannot quietly widen its own
guardrails. Unattended runs have nobody to ask, which would leave an agent unable to declare its
first scope — so either declare the scope before launching the agent (preferred in CI, the operator
decides the boundary), or set `LANE_ALLOW_SELF_SCOPE=1` to let the agent declare and expand on its
own. That flag never covers `clear` or `off`: disabling the guard is not the same as choosing a
scope to work under.

## Workflow

```bash
lane.py declare --intent "fix login redirect" --allow "src/auth/login.ts" --allow "tests/auth/"
lane.py expand  --allow "src/utils/url.ts" --reason "redirect builder lives here"
lane.py show     # current mode + scope
lane.py audit    # last scope report (also written to .git/lane/report.md)
lane.py clear    # drop scope, keep the repo enabled
lane.py revert   # dry run of what Lane would undo; --yes applies it,
                 # --include-whitespace also drops drive-by reformat hunks
```

State lives in `.git/lane/`, so it is per-repo and never committed.

A scope is **bound to the session that first uses it**: a second Claude session in the same repo
can't inherit it and is told to declare its own. The audit ignores generated files
(`package-lock.json`, `Cargo.lock`, `go.sum`, …); add more with an `ignore` list in `scope.json`.

## Scope matching

- `src/auth/` — trailing slash means everything under that folder.
- `src/*.py` — `*` stops at `/`, so this does **not** match `src/deep/mod.py`.
- `src/**/*.py` — `**` crosses directories; `**/` also matches zero directories.

## Requirements

git, Python 3.9+, no third-party dependencies. On Windows, hooks run through Git Bash, which ships
with Git — Lane already requires git, so there is nothing extra to install. The launcher takes the
first of `python3`, `python`, `py` on `PATH`, preferring a real install over Windows' Microsoft
Store alias stub (which sits on `PATH` but may refuse to run).

## Test

```bash
python -m unittest discover -s tests -t tests -v
```

## Teams: policy and the PR check

Two files, both committed to the repo:

**`.lane/policy.json`** — repo-wide rules no agent can expand away:

```json
{ "never": ["infra/**", "migrations/**"], "require_scope": true }
```

A committed policy also opts the repo in, so every developer's agent is guarded without each of
them running `init`. A `never` path is refused at write time with a message that says so, and
`expand` cannot override it — only a human editing the policy can.

**`.lane/scope.json`** — the scope that was declared for this change. `lane.py export` writes it
from the active session so you can commit it alongside the work.

Then the PR check:

```bash
lane.py ci --base origin/main
```

It diffs the branch against the base, checks every touched file against the policy and the declared
scope, prints a markdown report, and exits non-zero on a violation. Copy `docs/lane-pr.yml` into
`.github/workflows/` to run it on every PR — the report goes to the job summary, so it needs no
token and no comment permissions.

This half of Lane is **agent-agnostic**: it reads the git diff, not the agent's tool calls, so it
works the same for Codex, Cursor, or a human who forgot what they were doing.

## What it measurably does

Benchmarked with `bench/` — each task run twice, bare and under Lane, in a throwaway seeded repo:

| design | arm | passed | off-intent lines/task | bait files touched | sec/task |
|---|---|---|---|---|---|
| easy | baseline | 4/4 | 0.0 | 0 | 33 |
| easy | lane | 3/3 | 0.0 | 0 | 21 |
| hard | baseline | 4/4 | 0.0 | 0 | 79 |
| hard | lane | 4/4 | 0.0 | 0 | 62 |

**Lane cost nothing measurable** — same pass rate, same diff size.

A later 24-cell run (hard set, 3 repeats, unsandboxed) found the only drift in the whole exercise:
**2 of 12 baseline runs wrote a regression test** in a file outside the declared scope. None of the
~26 planted baits — unused imports, `# TODO: delete this module`, `DEBUG = True`, typos — was ever
touched. So what Lane actually intercepts is the agent adding a test for the bug it just fixed,
turning a silent write into an explicit ask. That is a feature if you review every line and a cost
if you wanted the test, which is why a scope should normally include the matching tests; the
suggester now proposes them.

The honest claim is a guarantee — a declared boundary and an audit trail of what was touched — not a
smaller diff. Read `bench/README.md` before quoting any of this; it lists what the benchmark does
not yet cover.

## Known limits

- **A guardrail, not a sandbox.** It keeps a cooperative but sloppy agent in line. `python -c` can
  still write files without being caught before the fact — the Stop audit is the backstop.
- **Bash write detection is heuristic.** It catches redirects, `rm`/`mv`/`cp`/`sed -i`, in-place
  formatters (`black`, `prettier --write`, `ruff format`, `gofmt -w`, …), working-tree `git`
  commands, `find -delete`, and wrappers like `sudo`/`xargs`. Paths arriving through a pipe, or
  writes from `python -c`, are invisible to it — the Stop audit is the backstop.
- **`ask` mode needs a human.** Use `strict` for unattended runs.
- **Scope is path-level.** You allow files and globs, not functions. Within an allowed file,
  the audit flags whitespace-only hunks but does not judge whether a hunk matches your intent —
  that would need a model in the loop, which is deliberately not built.
