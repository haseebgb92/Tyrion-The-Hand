#!/usr/bin/env bash
# Stop the Tyrion server started by launch.sh, without touching other processes.
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if systemctl --user is-active --quiet tyrion-hand.service; then
  systemctl --user stop tyrion-hand.service
  echo "Tyrion user service stopped (remains enabled for next login)"
  exit 0
fi
PIDFILE="$BASE/data/server.pid"
if [ ! -r "$PIDFILE" ]; then echo "No Tyrion PID recorded"; exit 0; fi
PID="$(cat "$PIDFILE")"
if ! [[ "$PID" =~ ^[0-9]+$ ]]; then echo "Invalid PID"; exit 1; fi
if [ ! -r "/proc/$PID/cmdline" ]; then rm -f "$PIDFILE"; echo "Already stopped"; exit 0; fi
if tr '\0' '\n' < "/proc/$PID/cmdline" | grep -Fxq 'tyrion.server'; then
  kill "$PID"
  echo "Stopped Tyrion background service"
else
  echo "PID does not belong to Tyrion; refusing to stop it"
  exit 1
fi
