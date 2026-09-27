"""
WHERE THINGS ARE, for the v2 build. Paths and the one naming rule, nothing else.

NAMESPACE keeps v2 apart from v1 while both packs load on the same scratch server: every
game id v2 makes starts with it (K2_Kitchen_Pumpkin, not Kitchen_Pumpkin), so nothing
collides. It is a build setting, not content -- a theme never sees it -- and it can be
dropped once v1 is retired.
"""
import os

V2 = os.path.normpath(os.path.join(os.path.dirname(__file__), os.pardir))
CONTENT = os.path.join(V2, "content")
PACK = os.path.join(V2, "pack")

NAMESPACE = "K2"
PACK_GROUP, PACK_NAME = "Chromecide", "KweetchenKaos"
VERSION = "0.3.0"               # the pack's version; release.py names the zip after it

# THIS MACHINE: local.cfg (not committed; copy local.cfg.example) says where the Hytale
# server is and, optionally, the game's Assets.zip. KK_SERVER / KK_ASSETS in the environment
# win over it. deploy.py reads the same file.
def _local():
    cfg = {}
    path = os.path.join(V2, "local.cfg")
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                cfg[k.strip()] = os.path.expanduser(v.strip().strip('"'))
    for k in ("SERVER", "ASSETS"):
        if os.environ.get(f"KK_{k}"):
            cfg[k] = os.path.expanduser(os.environ[f"KK_{k}"])
    return cfg


_LOCAL = _local()
SERVER = _LOCAL.get("SERVER")    # the server folder (holds mods/); None if not set

# The shipped assets, to check every model, texture and icon a theme names really exists.
# Where the launcher keeps them on each system; local.cfg's ASSETS wins. Missing: the check
# is skipped, with a warning.
_ASSET_GUESSES = [
    "~/Library/Application Support/Hytale/install/release/package/game/latest/Assets.zip",
    os.path.join(os.environ.get("APPDATA", "~"), "Hytale", "install", "release", "package",
                 "game", "latest", "Assets.zip"),
    "~/.local/share/Hytale/install/release/package/game/latest/Assets.zip",
]
ASSETS_ZIP = _LOCAL.get("ASSETS") or next(
    (os.path.expanduser(p) for p in _ASSET_GUESSES if os.path.exists(os.path.expanduser(p))),
    None)


def game_id(prefix, local):
    """pumpkin_pie_cooked in the kitchen theme -> K2_Kitchen_Pumpkin_Pie_Cooked."""
    return "_".join([NAMESPACE, prefix] + [p.capitalize() for p in local.split("_")])
