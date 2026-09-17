#!/usr/bin/env python3
"""Lane CLI: init | off | declare | expand | show | audit | clear | revert | export | ci"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lane_core as L


def main():
    p = argparse.ArgumentParser(prog="lane")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("declare")
    d.add_argument("--intent", required=True)
    d.add_argument("--allow", action="append", required=True)
    e = sub.add_parser("expand")
    e.add_argument("--allow", action="append", required=True)
    e.add_argument("--reason", required=True)
    r = sub.add_parser("revert")
    r.add_argument("--yes", action="store_true", help="actually do it (default is a dry run)")
    r.add_argument("--include-whitespace", action="store_true",
                   help="also drop whitespace-only hunks inside on-intent files")
    c = sub.add_parser("ci")
    c.add_argument("--base", help="base ref, e.g. origin/main")
    c.add_argument("--require-scope", action="store_true", help="fail if no .lane/scope.json")
    for n in ("show", "audit", "clear", "init", "off", "export"):
        sub.add_parser(n)
    a = p.parse_args()

    root = L.repo_root(os.getcwd())
    if not root:
        sys.exit("lane: not inside a git repo")

    if a.cmd == "declare":
        L.save_scope(root, {
            "intent": a.intent,
            "allow": a.allow,
            "created": L.now(),
            "session": None,  # stamped by the first hook that sees it; see lane_core.session_ok
            "baseline_dirty": sorted(L.dirty_files(root)),  # user's pre-existing changes, not blamed
            "expansions": [],
        })
        L.save_touched(root, {"files": [], "approved_outside": []})
        print(f"lane: scope set -> {a.intent} | {a.allow}")
    elif a.cmd == "expand":
        s = L.load_scope(root)
        if not s:
            sys.exit("lane: no scope declared")
        s["allow"] += a.allow
        s["expansions"].append({"allow": a.allow, "reason": a.reason, "at": L.now()})
        L.save_scope(root, s)
        print(f"lane: scope expanded -> {a.allow}")
    elif a.cmd == "init":
        (L.state_dir(root, create=True) / "enabled").write_text("", encoding="utf-8")
        print(f"lane: enabled for {root} (mode: {L.mode(root)}). Turn off with: lane.py off")
    elif a.cmd == "off":
        (L.state_dir(root) / "enabled").unlink(missing_ok=True)
        print("lane: disabled for this repo")
    elif a.cmd == "show":
        s = L.load_scope(root)
        print(f"mode: {L.mode(root)}")
        print("lane: no scope" if not s else
              f"intent: {s['intent']}\nallow: {s['allow']}\nexpansions: {len(s['expansions'])}\n"
              f"session: {s.get('session') or '(unbound until first edit)'}")
    elif a.cmd == "export":
        s = L.load_scope(root)
        if not s:
            sys.exit("lane: no scope declared")
        (root / ".lane").mkdir(exist_ok=True)
        (root / ".lane" / "scope.json").write_text(json.dumps(
            {"intent": s["intent"], "allow": s["allow"], "expansions": s["expansions"]}, indent=2),
            encoding="utf-8")
        print("lane: wrote .lane/scope.json — commit it so CI can check the diff against it")
    elif a.cmd == "ci":
        # Runs in CI, where there is no session and no .git/lane state: everything it needs is
        # committed (.lane/policy.json, .lane/scope.json) or in the diff itself.
        rng = f"{a.base}...HEAD" if a.base else "HEAD~1...HEAD"
        d = L.git(root, "diff", "--name-only", rng)
        if d.returncode != 0:
            sys.exit(f"lane: cannot diff {rng} ({d.stderr.strip()[:120]})")
        # .lane/ is Lane's own committed metadata; it is never part of a task's scope
        files = [f for f in d.stdout.splitlines() if f and not f.startswith(".lane/")]
        policy = L.load_policy(root)
        try:
            declared = json.loads((root / ".lane" / "scope.json").read_text(encoding="utf-8"))
        except (FileNotFoundError, NotADirectoryError, OSError, json.JSONDecodeError):
            declared = None
        bad = [(f, g) for f in files for g in (L.policy_denies(f, policy),) if g]
        # a policy violation is the stronger statement; do not also list it as out-of-scope
        banned = {f for f, _ in bad}
        outside = ([f for f in files if f not in banned and not L.in_scope(f, declared)]
                   if declared else [])
        scope_line = (f"{declared['intent']} — `{'`, `'.join(declared['allow'])}`" if declared
                      else "_none committed — run `lane.py export` and commit `.lane/scope.json`_")
        out = f"## Lane PR check\n\n**Files changed:** {len(files)}  \n**Declared scope:** {scope_line}\n"
        if bad:
            out += f"\n### ❌ Policy violations ({len(bad)})\n"
            out += "".join(f"- `{f}` — policy forbids `{g}`\n" for f, g in bad)
        if outside:
            out += f"\n### ❌ Outside the declared scope ({len(outside)})\n"
            out += "".join(f"- `{f}`\n" for f in outside)
        if declared and declared.get("expansions"):
            out += "\n" + "".join(
                "> expanded `" + "`, `".join(e["allow"]) + "`: " + e["reason"] + "\n"
                for e in declared["expansions"])
        if not (bad or outside):
            out += "\n✅ Every changed file is inside the declared scope and allowed by policy.\n"
        print(out)
        if (a.require_scope or policy.get("require_scope")) and not declared:
            print("❌ No `.lane/scope.json` committed, and a scope is required.")
            sys.exit(1)
        sys.exit(1 if (bad or outside) else 0)
    elif a.cmd == "revert":
        s = L.load_scope(root)
        if not s:
            sys.exit("lane: no scope declared")
        c = L.classify(root, s, L.load_touched(root))
        plan = []
        for f in c["unrelated"]:
            tracked = L.git(root, "ls-files", "--error-unmatch", "--", f).returncode == 0
            plan.append(("restore" if tracked else "delete", f, None))
        if a.include_whitespace:
            plan += [("unformat", f, h) for f, h in sorted(c["ws_hunks"].items())]
        if not plan:
            print("lane: nothing to revert")
            return
        for kind, f, hunks in plan:
            print(f"  {kind:8} {f}" + (f"  ({len(hunks)} whitespace-only hunks)" if hunks else ""))
        if not a.yes:
            print("lane: dry run — nothing changed. Re-run with --yes to apply.")
            return
        for kind, f, hunks in plan:
            if kind == "restore":
                L.git(root, "checkout", "--", f)
            elif kind == "delete":
                (root / f).unlink(missing_ok=True)
            else:
                header = L.split_patch(L.file_patch(root, f))[0]
                ok, err = L.git_apply_reverse(root, header + "".join(hunks))
                if not ok:
                    print(f"  ! left {f} alone: {err[:120]}")
        print("lane: reverted")
    elif a.cmd == "audit":
        f = L.state_dir(root) / "report.md"
        print(f.read_text(encoding="utf-8") if f.exists() else "lane: no report yet")
    elif a.cmd == "clear":
        for n in ("scope.json", "touched.json", "report.md"):
            (L.state_dir(root) / n).unlink(missing_ok=True)
        print("lane: cleared")


if __name__ == "__main__":
    main()
