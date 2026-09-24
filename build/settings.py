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
PACK_GROUP, PACK_NAME = "Chromecide", "KwitchenKaos"

# The shipped assets, to check every model, texture and icon a theme names really exists.
ASSETS_ZIP = os.path.expanduser(
    "~/Library/Application Support/Hytale/install/release/package/game/latest/Assets.zip")


def game_id(prefix, local):
    """pumpkin_pie_cooked in the kitchen theme -> K2_Kitchen_Pumpkin_Pie_Cooked."""
    return "_".join([NAMESPACE, prefix] + [p.capitalize() for p in local.split("_")])
