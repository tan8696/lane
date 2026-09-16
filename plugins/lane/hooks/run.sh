#!/bin/sh
# Launch a Lane script with whatever Python actually works.
#
# Never probe by running an interpreter: starting one just to test it costs ~300ms on Windows,
# on every single tool call. `command -v` is a shell builtin and free, and `exec` means this
# wrapper adds no process of its own.
#
# Windows caveat: WindowsApps\python3 may be a Microsoft Store alias stub that sits on PATH but
# refuses to run. Prefer a real install, but still use the Store one if it is all there is.
#
# -S -E: skip site-packages and ignore PYTHON* env. Lane is stdlib-only, this shaves ~17ms off
# every call and stops a stray PYTHONPATH from shadowing our modules. Drop it if Lane ever grows
# a dependency.
for py in python3 python py; do
  p=$(command -v "$py" 2>/dev/null) || continue
  case "$p" in
    *WindowsApps*) store="${store:-$py}"; continue ;;
  esac
  exec "$py" -S -E "$@"
done
[ -n "$store" ] && exec "$store" -S -E "$@"
echo "lane: no python found (tried python3, python, py)" >&2
exit 1
