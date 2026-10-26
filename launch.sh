#!/usr/bin/env bash
# Start Tyrion's local service on demand; open one desktop app-style window.
set -euo pipefail
BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE"
if ! /usr/bin/curl -fsS --max-time 1 http://127.0.0.1:17877/api/health >/dev/null 2>&1; then
  if systemctl --user list-unit-files tyrion-hand.service --no-legend 2>/dev/null | grep -q 'tyrion-hand.service'; then
    systemctl --user start tyrion-hand.service || true
  fi
  if ! /usr/bin/curl -fsS --max-time 1 http://127.0.0.1:17877/api/health >/dev/null 2>&1; then
    nohup /usr/bin/python3 -m tyrion.server >> "$BASE/data/server.log" 2>&1 < /dev/null &
  fi
fi
for attempt in 1 2 3 4 5 6 7 8 9 10; do
  if /usr/bin/curl -fsS --max-time 1 http://127.0.0.1:17877/api/health >/dev/null 2>&1; then break; fi
  sleep .25
done
if /usr/bin/python3 -c "import gi; gi.require_version('Gtk','3.0'); gi.require_version('WebKit2','4.1')" >/dev/null 2>&1; then
  exec /usr/bin/python3 -m tyrion.native
elif command -v google-chrome >/dev/null 2>&1; then
  exec google-chrome --app=http://127.0.0.1:17877/ --class=TyrionTheHand
elif command -v firefox >/dev/null 2>&1; then
  exec firefox --new-window http://127.0.0.1:17877/
else
  exec xdg-open http://127.0.0.1:17877/
fi
