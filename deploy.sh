#!/bin/sh
# Build Kweetchen Kaos and install it on your Hytale server. See docs/getting-started.md.
#
#   ./deploy.sh                    build the game (HQ and its restaurants), install it
#   ./deploy.sh SPIKE [RULES]      build a test world instead (see build/spike.py), e.g.
#                                  ./deploy.sh kitchen, ./deploy.sh run practice
#
# The server folder comes from local.cfg (copy local.cfg.example): SERVER=/path/to/server,
# the folder holding mods/. KK_SERVER in the environment wins over it.
#
# If the server folder has a run.sh (a start script), the server is stopped, the pack
# installed, the server started again, and its log checked for anything the game rejected.
# Without one, the pack is installed and you restart the server yourself.
#
# Lessons from earlier deploy scripts:
#   * the server is up if its UDP port is taken -- never pgrep for the jar name (it matches
#     the console wrapper and this script itself)
#   * stop it with a signal to the JVM, not by writing "stop" to the console fifo (the
#     write blocks forever if nothing is reading)
#   * a clean boot is not a clean deploy: items log "Failed to decode asset", roles log
#     "FAIL:", some failures name only the asset key -- so match our namespace, not the path
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
MOD="Chromecide_KweetchenKaos"
PORT=5520

if [ -f "$HERE/local.cfg" ]; then
  SERVER_CFG=$(sed -n 's/^SERVER=//p' "$HERE/local.cfg" | tail -1 | sed 's/^"//; s/"$//')
fi
SERVER="${KK_SERVER:-$SERVER_CFG}"
case "$SERVER" in "~"*) SERVER="$HOME${SERVER#\~}" ;; esac
if [ -z "$SERVER" ] || [ ! -d "$SERVER" ]; then
  echo "Set SERVER in local.cfg to your Hytale server folder (copy local.cfg.example)."
  echo "  now: '${SERVER:-not set}'"
  exit 1
fi

python3 "$HERE/build/build.py" --spike "${1:-world}" --rules "${2:-standard}" > /tmp/kweetchenkaos_build.txt \
  || { cat /tmp/kweetchenkaos_build.txt; exit 1; }
tail -1 /tmp/kweetchenkaos_build.txt

cd "$SERVER"
restart=false
[ -x run.sh ] && restart=true

if $restart && lsof -nP -iUDP:$PORT >/dev/null 2>&1; then
  pid=$(lsof -nP -iUDP:$PORT -t 2>/dev/null | head -1)
  echo "stopping server (pid $pid)..."
  kill "$pid" 2>/dev/null || true
  n=0
  while lsof -nP -iUDP:$PORT >/dev/null 2>&1; do
    n=$((n + 1)); [ "$n" -gt 60 ] && { echo "server did not stop"; exit 1; }
    sleep 2
  done
  pkill -f "tail -f console.in" 2>/dev/null || true
fi

# RESCUE LAYOUT SAVES first: /kk save writes them into the INSTALLED pack, which the next line
# replaces. Losing a hand-built room to that is the trap the first version fell into.
if ls "mods/$MOD/Server/Prefabs/"K2_Save_*.prefab.json >/dev/null 2>&1; then
  mkdir -p "$HERE/content/layouts/_saves"
  cp "mods/$MOD/Server/Prefabs/"K2_Save_*.prefab.json "$HERE/content/layouts/_saves/"
  echo "rescued layout saves: $(ls "mods/$MOD/Server/Prefabs/"K2_Save_*.prefab.json | wc -l | tr -d ' ')"
fi
mkdir -p mods
rm -rf "mods/$MOD"
cp -R "$HERE/pack" "mods/$MOD"
echo "installed $MOD in $SERVER/mods"

if ! $restart; then
  echo "Now restart your Hytale server to load it."
  exit 0
fi

./run.sh | tail -1
clean() { sed 's/\x1b\[[0-9;]*m//g'; }
bad=$(grep -E "SEVERE.*(FAIL:|Failed to decode asset|Failed to validate asset)" server.log | clean | grep -E "KweetchenKaos|K2_" || true)
dropped=$(grep -E "Skipping unrecognized trigger (effect|condition|rule)" server.log | clean | grep -E "KweetchenKaos|K2_" || true)
missing=$(grep -E "Failed to find block '" server.log | clean | grep "K2_" | sort -u || true)
[ -n "$bad" ] && { echo "KWEETCHEN KAOS ASSETS REJECTED:"; echo "$bad" | sed 's/^/  /'; }
[ -n "$dropped" ] && { echo "KWEETCHEN KAOS TRIGGER EFFECTS DROPPED:"; echo "$dropped" | sed 's/^/  /'; }
[ -n "$missing" ] && { echo "KWEETCHEN KAOS PREFAB BLOCKS MISSING:"; echo "$missing" | sed 's/^/  /'; }
[ -z "$bad$dropped$missing" ] && echo "Kweetchen Kaos: nothing rejected"
exit 0
