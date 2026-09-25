#!/usr/bin/env python3
"""
Build Kweetchen Kaos and install it on your Hytale server. See docs/getting-started.md.

    python3 deploy.py                  build the game (HQ and its restaurants), install it
    python3 deploy.py SPIKE [RULES]    build a test world instead (see build/spike.py), e.g.
                                       python3 deploy.py kitchen, python3 deploy.py run practice

The server folder comes from local.cfg (copy local.cfg.example): SERVER=/path/to/server, the
folder holding mods/. KK_SERVER in the environment wins over it.

If the server folder has a run.sh (a start script), the server is stopped, the pack installed,
the server started again, and its log checked for anything the game rejected. Without one,
the pack is installed and you restart the server yourself.

Lessons from earlier deploy scripts:
  * the server is up while its UDP port is taken -- never look for the jar by name (it matches
    the console wrapper, and the game client, whose command line names it too)
  * stop it with a signal to the JVM, not by writing "stop" to its console (the write blocks
    for ever if nothing is reading)
  * a clean boot is not a clean deploy: items log "Failed to decode asset", roles log
    "FAIL:", some failures name only the asset key -- so match our namespace, not the path
"""
import glob
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "build"))
import settings  # noqa: E402  (after the path)

MOD = f"{settings.PACK_GROUP}_{settings.PACK_NAME}"
PORT = 5520
BUILD_LOG = os.path.join(tempfile.gettempdir(), "kweetchenkaos_build.txt")


def port_taken():
    """The server is up while its UDP port is taken."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind(("0.0.0.0", PORT))
        return False
    except OSError:
        return True
    finally:
        s.close()


def stop_server():
    """Signal the process holding the port, and wait for it to let go (up to two minutes)."""
    try:
        pid = subprocess.run(["lsof", "-nP", f"-iUDP:{PORT}", "-t"], capture_output=True,
                             text=True).stdout.split()[0]
    except (FileNotFoundError, IndexError):
        sys.exit(f"The server is running on UDP {PORT} but its process couldn't be found "
                 f"(needs lsof). Stop it yourself and deploy again.")
    print(f"stopping server (pid {pid})...")
    try:
        os.kill(int(pid), signal.SIGTERM)
    except ProcessLookupError:
        pass
    for _ in range(60):
        if not port_taken():
            break
        time.sleep(2)
    else:
        sys.exit("server did not stop")
    # The start script feeds the console through "tail -f console.in"; a stale one races the
    # next start for it.
    subprocess.run(["pkill", "-f", "tail -f console.in"], capture_output=True)


def build(spike, rules):
    with open(BUILD_LOG, "w") as out:
        code = subprocess.run([sys.executable, os.path.join(HERE, "build", "build.py"),
                               "--spike", spike, "--rules", rules], stdout=out,
                              stderr=subprocess.STDOUT).returncode
    text = open(BUILD_LOG).read()
    if code:
        print(text)
        sys.exit(code)
    print(text.rstrip().splitlines()[-1])


def install(server):
    mods = os.path.join(server, "mods")
    installed = os.path.join(mods, MOD)
    # RESCUE LAYOUT SAVES first: /kk save writes them into the INSTALLED pack, which is
    # replaced next. Losing a hand-built room to that is the trap the first version fell into.
    saves = glob.glob(os.path.join(installed, "Server", "Prefabs", "K2_Save_*.prefab.json"))
    if saves:
        keep = os.path.join(HERE, "content", "layouts", "_saves")
        os.makedirs(keep, exist_ok=True)
        for f in saves:
            shutil.copy2(f, keep)
        print(f"rescued layout saves: {len(saves)}")
    os.makedirs(mods, exist_ok=True)
    shutil.rmtree(installed, ignore_errors=True)
    shutil.copytree(settings.PACK, installed)
    print(f"installed {MOD} in {mods}")


def check_log(server):
    """What the game refused, from the server log: our namespace only."""
    path = os.path.join(server, "server.log")
    if not os.path.exists(path):
        print("(no server.log to check)")
        return
    lines = [re.sub(r"\x1b\[[0-9;]*m", "", ln) for ln in open(path, errors="replace")]
    ours = lambda ln: "KweetchenKaos" in ln or "K2_" in ln
    found = [
        ("ASSETS REJECTED", [ln for ln in lines if re.search(
            r"SEVERE.*(FAIL:|Failed to decode asset|Failed to validate asset)", ln) and ours(ln)]),
        ("TRIGGER EFFECTS DROPPED", [ln for ln in lines if re.search(
            r"Skipping unrecognized trigger (effect|condition|rule)", ln) and ours(ln)]),
        ("PREFAB BLOCKS MISSING", sorted({ln for ln in lines
                                          if "Failed to find block '" in ln and "K2_" in ln})),
    ]
    bad = False
    for title, hits in found:
        if hits:
            bad = True
            print(f"KWEETCHEN KAOS {title}:")
            for ln in hits:
                print(f"  {ln.rstrip()}")
    if not bad:
        print("Kweetchen Kaos: nothing rejected")


def main(argv):
    server = settings.SERVER
    if not server or not os.path.isdir(server):
        sys.exit("Set SERVER in local.cfg to your Hytale server folder (copy local.cfg.example).\n"
                 f"  now: '{server or 'not set'}'")
    spike = argv[0] if argv else "world"
    rules = argv[1] if len(argv) > 1 else "standard"
    build(spike, rules)

    run = os.path.join(server, "run.sh")
    restart = os.access(run, os.X_OK)
    if restart and port_taken():
        stop_server()
    install(server)
    if not restart:
        print("Now restart your Hytale server to load it.")
        return 0
    started = subprocess.run([run], cwd=server, capture_output=True, text=True)
    print((started.stdout.strip().splitlines() or [""])[-1])
    check_log(server)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
