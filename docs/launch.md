# Launch copy (drafts)

Every claim here is one the benchmark supports. The reduction number from the original roadmap
(−70% off-intent lines) is **not** usable: the unguarded baseline produced zero off-intent lines, so
there is nothing to reduce. Leading with it would fall apart the first time a skeptic ran `bench/`.

The pitch that survives: **a declared boundary, and proof the agent stayed inside it, at no
measurable cost.**

---

## Show HN

**Title:** Show HN: Lane – a per-task edit boundary for Claude Code, enforced by hooks

> Coding agents sometimes edit things nobody asked them to. The usual fixes are advisory (a
> CLAUDE.md rule the model can ignore) or static (path allow-lists that are identical for every
> task). Lane is neither: at the start of a task the agent declares an intent and an allow-list, a
> PreToolUse hook blocks writes outside it, and a Stop hook audits the final git diff against the
> declared intent and writes a report you can paste into the PR.
>
> The honest part: I built a benchmark before writing the launch post, and it did not find the
> problem I built this for. Across 8 baseline runs — including an 11-file repo, vague bug reports
> naming no file, bait files planted outside the scope, and a follow-up turn inviting the agent to
> look around — the unguarded agent made zero drive-by edits. It noticed the adjacent problems and
> asked instead of acting.
>
> So I'm not claiming smaller diffs. What Lane gives you is a boundary you declared and an audit
> trail proving the change stayed inside it, at no measurable cost (identical pass rate, identical
> diff size). That's worth something for team PRs and unattended runs; it may not be worth much for
> one developer watching a single task. Benchmark, seeds and raw results are in the repo — I'd
> genuinely like to see it run against other agents and longer sessions, where I suspect the
> original problem still lives.

## r/ClaudeAI

> **I built a per-task edit guard for Claude Code, then benchmarked it and found the problem it
> solves may not exist (for Sonnet, on short tasks)**
>
> Lane makes the agent declare which files a task needs before it edits, blocks anything outside
> that, and audits the final diff. Install is two `/plugin` commands, it's off until a repo opts in,
> and it has no dependencies.
>
> I also built a benchmark that runs each task with and without it. Baseline drive-by edits: zero,
> across two repo designs, including one with bait files planted specifically to tempt it. So I'm
> publishing "costs nothing, gives you an audit trail" rather than a reduction number.
>
> If you've actually watched Claude Code wander during a long session, I'd love a repro — the
> harness takes a seed repo and a task file.

## Dev.to

**Title:** I benchmarked my own plugin and it disproved my premise

Angle: the value of checking before launching. Cover the hook-contract verification (published docs
were wrong twice; the shipped binary is the oracle), the home-directory-is-a-git-repo discovery, and
the benchmark that killed the headline claim. Close on what survives.

## Awesome-list submission

> **[Lane](https://github.com/USER/lane-kit)** — per-task edit scope for Claude Code: the agent
> declares what a task may touch, writes outside it are blocked, and the final diff is audited
> against the declared intent. Off by default per repo, no dependencies.

## Assets still to record

- 30-second terminal capture: out-of-scope edit blocked → scope expanded with a reason → Stop audit
  → report. Record it in a scratch repo, not a real one.
- A screenshot of `report.md` in a PR description.
- Link `bench/README.md` directly from the README so the numbers are one click away.
