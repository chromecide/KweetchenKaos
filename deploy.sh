#!/bin/sh
# Build v2 and deploy it to the scratch server, BESIDE v1 (its ids are namespaced K2_),
# then restart the server and report anything the game rejected.
#
#   ./deploy.sh [SPIKE]      build the kitchen theme with SPIKE mounted in the spike world
#                            (default board), deploy, restart
#
# Lessons carried over from v1's deploy (kitchen-poc/tools/deploy.sh), rewritten rather than shared:
#   * the server is up if its UDP port is taken -- never pgrep for the jar name (it matches
#     the console wrapper and this script itself)
#   * stop it with a signal to the JVM, not by writing "stop" to the console fifo (the
#     write blocks forever if nothing is reading)
#   * a clean boot is not a clean deploy: items log "Failed to decode asset", roles log
#     "FAIL:", some failures name only the asset key -- so match our namespace, not the path
set -e
V2="$(cd "$(dirname "$0")" && pwd)"
SERVER="$HOME/hytale-mods/lowtalk-firstrun"
MOD="Chromecide_KwitchenKaos"

python3 "$V2/build/build.py" --spike "${1:-board}" > /tmp/kwitchenkaos_build.txt || { cat /tmp/kwitchenkaos_build.txt; exit 1; }
tail -1 /tmp/kwitchenkaos_build.txt

cd "$SERVER"
if lsof -nP -iUDP:5520 >/dev/null 2>&1; then
  pid=$(lsof -nP -iUDP:5520 -t 2>/dev/null | head -1)
  echo "stopping server (pid $pid)..."
  kill "$pid" 2>/dev/null || true
  n=0
  while lsof -nP -iUDP:5520 >/dev/null 2>&1; do
    n=$((n + 1)); [ "$n" -gt 60 ] && { echo "server did not stop"; exit 1; }
    sleep 2
  done
  pkill -f "tail -f console.in" 2>/dev/null || true
fi

rm -rf "mods/$MOD"
cp -R "$V2/pack" "mods/$MOD"
echo "deployed $MOD"

./run.sh | tail -1
clean() { sed 's/\x1b\[[0-9;]*m//g'; }
bad=$(grep -E "SEVERE.*(FAIL:|Failed to decode asset|Failed to validate asset)" server.log | clean | grep -E "KwitchenKaos|K2_" || true)
dropped=$(grep -E "Skipping unrecognized trigger (effect|condition|rule)" server.log | clean | grep -E "KwitchenKaos|K2_" || true)
missing=$(grep -E "Failed to find block '" server.log | clean | grep "K2_" | sort -u || true)
[ -n "$bad" ] && { echo "KWITCHENKAOS ASSETS REJECTED:"; echo "$bad" | sed 's/^/  /'; }
[ -n "$dropped" ] && { echo "KWITCHENKAOS TRIGGER EFFECTS DROPPED:"; echo "$dropped" | sed 's/^/  /'; }
[ -n "$missing" ] && { echo "KWITCHENKAOS PREFAB BLOCKS MISSING:"; echo "$missing" | sed 's/^/  /'; }
[ -z "$bad$dropped$missing" ] && echo "KwitchenKaos: nothing rejected"
exit 0
