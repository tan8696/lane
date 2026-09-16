"""Shared logic for Lane hooks + CLI. Stdlib only."""
import json
import os
import re
import shlex
import subprocess
import sys
import time
from pathlib import Path

# Windows shells default to cp1252; the report uses emoji and hook output must be UTF-8 JSON.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PLUGIN_ROOT = Path(os.environ.get("CLAUDE_PLUGIN_ROOT") or Path(__file__).resolve().parent.parent)
# posix: these are printed into commands the agent runs through bash
CLI = (PLUGIN_ROOT / "scripts" / "lane.py").as_posix()
# same launcher the hooks use, so the agent never has to guess python3 vs python
RUN = 'sh "{}" "{}"'.format((PLUGIN_ROOT / "hooks" / "run.sh").as_posix(), CLI)
FILE_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit"}
MUTATORS = {"rm", "mv", "touch", "mkdir", "rmdir", "tee", "truncate"}
MODES = ("off", "ask", "strict")

# Formatters are the reported failure mode ("it reformatted 3 files"), so they must be caught.
FMT_ALWAYS = {"black", "isort", "rustfmt", "swiftformat"}          # rewrite files with no flag
FMT_ON_FLAG = {"prettier", "eslint", "ruff", "dotnet", "gofmt", "goimports",
               "clang-format", "autopep8", "yapf", "ktlint", "biome"}
WRITE_FLAGS = {"-i", "--in-place", "-w", "--write", "--fix", "-F", "format"}
GIT_MUTATORS = {"checkout", "restore", "switch", "apply", "stash", "clean", "reset", "rm", "mv"}
CMD_PREFIXES = {"xargs", "sudo", "env", "time", "nohup", "nice"}
# Generated files the audit should not blame the agent for.
IGNORE_DEFAULT = {"package-lock.json", "npm-shrinkwrap.json", "yarn.lock", "pnpm-lock.yaml",
                  "poetry.lock", "Cargo.lock", "uv.lock", "go.sum", "composer.lock", "Gemfile.lock"}


def git(root, *args):
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)


def repo_root(cwd):
    """Nearest ancestor holding .git, or None. No subprocess: this runs on every tool call."""
    try:
        p = Path(cwd).resolve()
    except OSError:
        return None
    for d in (p, *p.parents):
        if (d / ".git").exists():
            return d
    return None


def state_dir(root, create=False):
    """`.git/lane/` — per repo, never committed. In worktrees/submodules `.git` is a pointer file."""
    g = root / ".git"
    if g.is_file():
        g = Path(g.read_text(encoding="utf-8").split("gitdir:", 1)[1].strip())
        if not g.is_absolute():
            g = (root / g).resolve()
    d = g / "lane"
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d


def mode(root):
    """off unless this repo opted in via `lane.py init`. An explicit LANE_MODE always wins."""
    m = (os.environ.get("LANE_MODE") or "").strip().lower()
    if m in MODES:
        return m
    return "ask" if (state_dir(root) / "enabled").exists() else "off"


def session_ok(root, scope, sid):
    """Bind a scope to the first session that uses it, so a second session can't inherit it.

    The CLI cannot do this itself: Claude Code exposes no session id to Bash commands, only to
    hooks. So `declare` writes session=None and the first hook to see the scope stamps it.
    """
    if not sid:
        return True  # no session in the payload (CLI, tests): nothing to bind against
    if scope.get("session") is None:
        scope["session"] = sid
        save_scope(root, scope)
        return True
    return scope["session"] == sid


def _load(root, name, default):
    try:
        return json.loads((state_dir(root) / name).read_text(encoding="utf-8"))
    except (FileNotFoundError, NotADirectoryError, json.JSONDecodeError):
        return default


def _save(root, name, data):
    (state_dir(root, create=True) / name).write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_scope(root):
    return _load(root, "scope.json", None)


def save_scope(root, scope):
    _save(root, "scope.json", scope)


def load_touched(root):
    return _load(root, "touched.json", {"files": [], "approved_outside": []})


def save_touched(root, t):
    _save(root, "touched.json", t)


def rel(root, cwd, p):
    """Repo-relative posix path, or None if the path is genuinely outside the repo."""
    if not p:
        return None
    pp = Path(p).expanduser()
    if not pp.is_absolute():
        pp = Path(cwd) / pp
    try:
        rp = pp.resolve()
    except OSError:
        return None
    try:
        return rp.relative_to(root).as_posix()
    except ValueError:
        pass
    # Windows: 8.3 short names and drive-letter case can survive resolve(). Compare normcased
    # before calling it "outside the repo" — that verdict means "pass", so a wrong None fails open.
    a, b = os.path.normcase(str(rp)), os.path.normcase(str(root)).rstrip("\\/")
    if a.startswith(b + os.sep) or a.startswith(b + "/"):
        return Path(str(rp)[len(b):].lstrip("\\/")).as_posix()
    return None


_GLOB_RE = {}


def _glob_re(g):
    """Glob to regex. Unlike fnmatch, `*` stops at `/`; `**` crosses directories."""
    r = _GLOB_RE.get(g)
    if r is None:
        out, i = [], 0
        while i < len(g):
            if g.startswith("**/", i):
                out.append("(?:.*/)?")  # zero or more directories
                i += 3
            elif g.startswith("**", i):
                out.append(".*")
                i += 2
            elif g[i] == "*":
                out.append("[^/]*")
                i += 1
            elif g[i] == "?":
                out.append("[^/]")
                i += 1
            else:
                out.append(re.escape(g[i]))
                i += 1
        r = _GLOB_RE[g] = re.compile("".join(out) + r"\Z")
    return r


def in_scope(r, scope):
    for g in scope.get("allow", []):
        g = g[2:] if g.startswith("./") else g
        if g.endswith("/") and r.startswith(g):  # folder scope
            return True
        if _glob_re(g).match(r):
            return True
    return False


def is_protected(r):
    return r == ".git" or r.startswith(".git/")


def dirty_files(root):
    """Modified (vs HEAD) + untracked files, repo-relative."""
    out = set()
    d = git(root, "diff", "--name-only", "HEAD")
    if d.returncode != 0:  # no commits yet
        d = git(root, "diff", "--name-only", "--cached")
    out.update(x for x in d.stdout.splitlines() if x)
    out.update(x for x in git(root, "diff", "--name-only").stdout.splitlines() if x)
    out.update(x for x in git(root, "ls-files", "--others", "--exclude-standard").stdout.splitlines() if x)
    return out


def whitespace_only(root, f):
    changed = git(root, "diff", "HEAD", "--quiet", "--", f).returncode == 1
    return changed and git(root, "diff", "HEAD", "-w", "--quiet", "--", f).returncode == 0


NO_WRITE_FLAGS = {"--check", "--diff", "--dry-run", "--list-different", "-l"}


def bash_write_targets(cmd, cwd=None):
    """Best-effort list of paths a shell command may write/delete. Stop audit is the backstop."""
    cwd = cwd or os.getcwd()
    targets = [m.group(1) for m in re.finditer(r"(?<![0-9&<>])>>?\s*([^\s;&|<>]+)", cmd)]
    for seg in re.split(r"&&|\|\||;|\|", cmd):
        try:
            toks = shlex.split(seg)
        except ValueError:
            continue
        # look through wrappers: `xargs rm`, `sudo black .`, `env FOO=1 prettier -w .`
        while toks and os.path.basename(toks[0]) in CMD_PREFIXES:
            toks = toks[1:]
            while toks and "=" in toks[0] and not toks[0].startswith("-"):
                toks = toks[1:]
        if not toks:
            continue
        c = os.path.basename(toks[0])
        rest = toks[1:]
        args = [t for t in rest if not t.startswith("-") and t not in (">", ">>")]
        if c in MUTATORS:
            targets += args
        elif c == "cp" and args:
            targets.append(args[-1])
        elif c == "sed" and any(t.startswith("-i") for t in rest) and args:
            targets.append(args[-1])
        elif c == "git" and rest and rest[0] in GIT_MUTATORS:
            # `git checkout -b feat` looks the same as `git checkout -- feat.py`; only flag real paths
            targets += [a for a in args[1:] if (Path(cwd) / a).exists()]
        elif c == "find" and ("-delete" in rest or "-exec" in rest):
            targets += args[:1] or ["."]
        elif (c in FMT_ALWAYS or (c in FMT_ON_FLAG and any(t in WRITE_FLAGS for t in rest))) \
                and not any(t in NO_WRITE_FLAGS for t in rest):
            # a formatter with no path given rewrites everything under cwd
            targets += [a for a in args if a != "format"] or ["."]
    return list(dict.fromkeys(t for t in targets if t and not t.startswith("/dev/")))


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S")
