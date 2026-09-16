---
name: scope
description: Use at the start of any coding task in a repo with Lane installed, before the first file edit, and whenever an edit is blocked as out of scope. Declares or expands the task's edit scope.
---

# Lane scope

1. Read the task. List the minimum files that must change.
2. Declare scope using the CLI path from session context:
   `python3 "<CLI>" declare --intent "<one line>" --allow "<glob>" ...`
   - Prefer exact files. Use a folder (`src/auth/`) only when creating new files there.
   - Include test files you will touch.
3. Edit only in scope. No drive-by formatting, renames, or refactors.
4. Blocked, and the edit is genuinely needed → `expand --allow "<glob>" --reason "<why>"`.
   Not needed → drop the edit.
5. New task in the same session → declare again.
