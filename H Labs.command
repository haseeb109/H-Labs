#!/bin/zsh
# H Labs - UMF Case Factory launcher for the Mac (double-click me). Same menu as H Labs.bat on Windows (tools/launcher.py),
# so what you test on the Mac is exactly what the team runs on Windows. First time / broken install: Setup Mac.command.
DIR="${0:A:h}"
cd "$DIR" || exit 1
export PYTHONUTF8=1 PYTHONIOENCODING=utf-8
PY="$DIR/.venv/bin/python3"
if [[ ! -x "$PY" ]]; then
  echo
  echo "  H Labs is not set up in this folder yet. Double-click  'Setup Mac.command'  first."
  echo
  read -r "?Press Enter..."
  exit 1
fi
"$PY" tools/launcher.py
