"""Simulates Claude Code hook calls against a temp git repo. Run: python3 -m unittest tests/test_lane.py"""
import json, os, subprocess, sys, tempfile, unittest
from pathlib import Path

S = Path(__file__).resolve().parent.parent / "plugins/lane/scripts"


def run(script, payload=None, cwd=None, args=(), env=None):
    return subprocess.run([sys.executable, str(S / script), *args], input=json.dumps(payload or {}),
                          capture_output=True, text=True, encoding="utf-8", cwd=cwd,
                          env={**os.environ, **env} if env else None)


class LaneTest(unittest.TestCase):
    def setUp(self):
        self.d = Path(tempfile.mkdtemp())
        for c in (["init", "-q"], ["config", "user.email", "t@t"], ["config", "user.name", "t"]):
            subprocess.run(["git", *c], cwd=self.d, check=True)
        (self.d / "src").mkdir()
        (self.d / "src/auth.py").write_text("x = 1\n")
        (self.d / "src/db.py").write_text("y = 2\n")
        subprocess.run(["git", "add", "."], cwd=self.d, check=True)
        subprocess.run(["git", "commit", "-qm", "init"], cwd=self.d, check=True)
        self.assertEqual(run("lane.py", cwd=self.d, args=["init"]).returncode, 0)  # opt this repo in

    def pre(self, tool, ti, sid=None):
        payload = {"tool_name": tool, "tool_input": ti, "cwd": str(self.d)}
        if sid:
            payload["session_id"] = sid
        out = run("pre_tool.py", payload).stdout
        return json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out.strip() else "pass"

    def report(self):
        return (self.d / ".git/lane/report.md").read_text(encoding="utf-8")

    def declare(self, *allow):
        a = ["declare", "--intent", "fix login"] + [x for g in allow for x in ("--allow", g)]
        self.assertEqual(run("lane.py", cwd=self.d, args=a).returncode, 0)

    def test_no_scope_denies(self):
        self.assertEqual(self.pre("Edit", {"file_path": str(self.d / "src/auth.py")}), "deny")

    def test_scope_enforced(self):
        self.declare("src/auth.py")
        self.assertEqual(self.pre("Edit", {"file_path": str(self.d / "src/auth.py")}), "pass")
        self.assertEqual(self.pre("Edit", {"file_path": "src/db.py"}), "ask")
        self.assertEqual(self.pre("Write", {"file_path": str(self.d / ".git/lane/scope.json")}), "deny")
        self.assertEqual(self.pre("Bash", {"command": "echo hi > src/db.py"}), "ask")
        self.assertEqual(self.pre("Bash", {"command": "sed -i 's/a/b/' src/db.py && ls"}), "ask")
        self.assertEqual(self.pre("Bash", {"command": "pytest -q 2>&1 | tail -5"}), "pass")
        self.assertEqual(self.pre("Bash", {"command": "python3 /x/lane.py expand --allow a --reason b"}), "ask")

    def test_off_unless_opted_in(self):
        run("lane.py", cwd=self.d, args=["off"])
        self.assertEqual(self.pre("Edit", {"file_path": str(self.d / "src/auth.py")}), "pass")
        self.assertEqual(run("session_start.py", {"cwd": str(self.d)}).stdout.strip(), "")

    def test_star_does_not_cross_directories(self):
        self.declare("src/*.py")
        self.assertEqual(self.pre("Edit", {"file_path": str(self.d / "src/auth.py")}), "pass")
        self.assertEqual(self.pre("Edit", {"file_path": str(self.d / "src/deep/mod.py")}), "ask")
        self.declare("src/**/*.py")
        self.assertEqual(self.pre("Edit", {"file_path": str(self.d / "src/deep/mod.py")}), "pass")

    def test_folder_scope(self):
        self.declare("src/")
        self.assertEqual(self.pre("Write", {"file_path": str(self.d / "src/new/mod.py")}), "pass")
        self.assertEqual(self.pre("Write", {"file_path": str(self.d / "README.md")}), "ask")

    def test_stop_audit(self):
        (self.d / "notes.txt").write_text("user wip\n")  # pre-existing user change
        self.declare("src/auth.py")
        (self.d / "src/auth.py").write_text("x = 42\n")
        (self.d / "src/db.py").write_text("y = 2   \n")  # sneaky out-of-scope edit
        out = run("stop_audit.py", {"cwd": str(self.d)}).stdout
        self.assertEqual(json.loads(out)["decision"], "block")
        self.assertIn("src/db.py", out)
        self.assertNotIn("notes.txt", out)
        again = run("stop_audit.py", {"cwd": str(self.d), "stop_hook_active": True}).stdout
        self.assertEqual(again.strip(), "")

    def test_approved_outside_not_blocked(self):
        self.declare("src/auth.py")
        (self.d / "src/db.py").write_text("y = 3\n")
        run("post_tool.py", {"tool_name": "Edit", "tool_input": {"file_path": "src/db.py"}, "cwd": str(self.d)})
        self.assertEqual(run("stop_audit.py", {"cwd": str(self.d)}).stdout.strip(), "")
        self.assertIn("Approved outside scope (1)", run("lane.py", cwd=self.d, args=["audit"]).stdout)

    def test_scope_is_session_bound(self):
        self.declare("src/auth.py")
        f = {"file_path": str(self.d / "src/auth.py")}
        self.assertEqual(self.pre("Edit", f, sid="sess-A"), "pass")  # stamps the scope
        self.assertEqual(self.pre("Edit", f, sid="sess-B"), "deny")  # a second session can't inherit
        self.assertEqual(self.pre("Edit", f, sid="sess-A"), "pass")  # owner still works

    def test_bash_detects_formatters_and_git(self):
        self.declare("src/auth.py")
        self.assertEqual(self.pre("Bash", {"command": "black ."}), "ask")
        self.assertEqual(self.pre("Bash", {"command": "prettier --write src/db.py"}), "ask")
        self.assertEqual(self.pre("Bash", {"command": "git checkout -- src/db.py"}), "ask")
        self.assertEqual(self.pre("Bash", {"command": "sudo rm src/db.py"}), "ask")
        self.assertEqual(self.pre("Bash", {"command": "git checkout -b feature"}), "pass")  # a branch
        self.assertEqual(self.pre("Bash", {"command": "black --check ."}), "pass")  # reads only
        self.assertEqual(self.pre("Bash", {"command": "npm test"}), "pass")

    def test_lockfiles_ignored_by_audit(self):
        self.declare("src/auth.py")
        (self.d / "src/auth.py").write_text("x = 42\n")
        (self.d / "package-lock.json").write_text('{"a": 1}\n')
        self.assertEqual(run("stop_audit.py", {"cwd": str(self.d)}).stdout.strip(), "")  # no block
        self.assertIn("package-lock.json", self.report())  # listed, as ignored

    def test_whitespace_only_warns_but_does_not_block(self):
        self.declare("src/auth.py")
        (self.d / "src/auth.py").write_text("x = 1   \n")  # in scope, whitespace-only
        self.assertEqual(run("stop_audit.py", {"cwd": str(self.d)}).stdout.strip(), "")
        self.assertIn("Whitespace-only (1)", self.report())

    def test_suggests_scope_only_when_needed(self):
        ask = {"cwd": str(self.d), "prompt": "the auth check is wrong", "source": "user"}
        out = run("suggest_scope.py", ask).stdout
        self.assertIn("src/auth.py", out)  # matched on filename
        self.assertIn("declare --intent", out)
        self.assertEqual(run("suggest_scope.py", dict(ask, source="system")).stdout.strip(), "")
        self.declare("src/auth.py")
        self.assertEqual(run("suggest_scope.py", ask).stdout.strip(), "")  # quiet once scoped

    def test_report_has_summary_line(self):
        self.declare("src/auth.py")
        (self.d / "src/auth.py").write_text("x = 42\n")
        run("stop_audit.py", {"cwd": str(self.d)})
        self.assertIn("**Summary:** 1 on-intent, 0 unrelated", self.report())

    def test_self_scope_gate(self):
        cli = (S / "lane.py").as_posix()
        def bash(cmd, env=None):
            return run("pre_tool.py", {"tool_name": "Bash", "tool_input": {"command": cmd},
                                       "cwd": str(self.d)}, env=env).stdout
        declare = f'python "{cli}" declare --intent x --allow y'
        self.assertIn('"ask"', bash(declare))  # attended: the user approves scope changes
        self.assertEqual(bash(declare, {"LANE_ALLOW_SELF_SCOPE": "1"}).strip(), "")  # unattended
        # disabling the guard is never self-approvable, flag or not
        self.assertIn('"ask"', bash(f'python "{cli}" off', {"LANE_ALLOW_SELF_SCOPE": "1"}))

    def test_revert_dry_run_then_apply(self):
        self.declare("src/auth.py")
        (self.d / "src/auth.py").write_text("x = 42\n")          # in scope, keep
        (self.d / "src/db.py").write_text("y = 999\n")           # unrelated, tracked
        (self.d / "stray.txt").write_text("drive-by\n")          # unrelated, untracked
        dry = run("lane.py", cwd=self.d, args=["revert"]).stdout
        self.assertIn("restore", dry)
        self.assertIn("delete", dry)
        self.assertIn("dry run", dry)
        self.assertEqual((self.d / "src/db.py").read_text(), "y = 999\n")  # unchanged by a dry run
        run("lane.py", cwd=self.d, args=["revert", "--yes"])
        self.assertEqual((self.d / "src/db.py").read_text(), "y = 2\n")    # restored
        self.assertFalse((self.d / "stray.txt").exists())                  # deleted
        self.assertEqual((self.d / "src/auth.py").read_text(), "x = 42\n")  # in-scope work kept

    def test_whitespace_hunk_inside_scoped_file(self):
        f = self.d / "src/wide.py"
        f.write_text("def one():\n    return 1\n\n\ndef two():\n    return 2\n")
        subprocess.run(["git", "add", "-A"], cwd=self.d, check=True)
        subprocess.run(["git", "commit", "-qm", "wide"], cwd=self.d, check=True)
        self.declare("src/wide.py")
        # a real change at the top, a pure reformat at the bottom: two hunks, one file, in scope
        f.write_text("def one():\n    return 111\n\n\ndef two():\n        return 2\n")
        run("stop_audit.py", {"cwd": str(self.d)})
        self.assertIn("Whitespace-only hunks inside on-intent files (1)", self.report())
        out = run("lane.py", cwd=self.d, args=["revert", "--include-whitespace", "--yes"]).stdout
        self.assertIn("unformat", out)
        self.assertEqual(f.read_text(), "def one():\n    return 111\n\n\ndef two():\n    return 2\n")

    def test_session_start(self):
        out = run("session_start.py", {"cwd": str(self.d)}).stdout
        self.assertIn("declare --intent", out)


if __name__ == "__main__":
    unittest.main()
