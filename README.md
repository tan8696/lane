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

## Workflow

```bash
lane.py declare --intent "fix login redirect" --allow "src/auth/login.ts" --allow "tests/auth/"
lane.py expand  --allow "src/utils/url.ts" --reason "redirect builder lives here"
lane.py show     # current mode + scope
lane.py audit    # last scope report (also written to .git/lane/report.md)
lane.py clear    # drop scope, keep the repo enabled
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

## Known limits

- **A guardrail, not a sandbox.** It keeps a cooperative but sloppy agent in line. `python -c` can
  still write files without being caught before the fact — the Stop audit is the backstop.
- **Bash write detection is heuristic.** It catches redirects, `rm`/`mv`/`cp`/`sed -i`, in-place
  formatters (`black`, `prettier --write`, `ruff format`, `gofmt -w`, …), working-tree `git`
  commands, `find -delete`, and wrappers like `sudo`/`xargs`. Paths arriving through a pipe, or
  writes from `python -c`, are invisible to it — the Stop audit is the backstop.
- **`ask` mode needs a human.** Use `strict` for unattended runs.
- **The audit is file-level**, not hunk-level, so it is coarse.
