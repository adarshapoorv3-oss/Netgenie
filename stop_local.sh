#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
for pidfile in .run/*.pid; do
  [ -f "$pidfile" ] || continue
  pid=$(cat "$pidfile")
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid"
    echo "Stopped $(basename "$pidfile" .pid) (pid $pid)"
  fi
  rm -f "$pidfile"
done
