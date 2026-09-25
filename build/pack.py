"""
WRITING THE v2 PACK. Infrastructure only: files, the language file, the manifest.

EVERY BUILD STARTS FROM NOTHING. v1 wrote into a pack that kept whatever earlier runs had
left there -- renamed items stayed on disk, and old language lines outlived their items.
Here begin() empties the pack, everything is written fresh, and finish() writes the
language file once, from what this build said. A removed item is simply gone.
"""
import json
import os
import shutil

import settings

_lang = {}


def begin():
    shutil.rmtree(settings.PACK, ignore_errors=True)
    os.makedirs(settings.PACK)
    _lang.clear()
    write(os.path.join(settings.PACK, "manifest.json"), {
        "Group": settings.PACK_GROUP, "Name": settings.PACK_NAME, "Version": "0.0.1",
        "Description": "Kweetchen Kaos: co-op restaurants built from theme content.",
        "Authors": [{"Name": "Chromecide"}], "Website": "https://chromecide.com",
        "ServerVersion": ">=0.6.8 <0.8.0", "Dependencies": {"Hytale:AssetModule": "*"},
        "OptionalDependencies": {}, "DisabledByDefault": False,
        "IncludesAssetPack": True, "Main": "unused.NoPluginHere"})


def out(*parts):
    """A path under pack/Server, with its folder made."""
    path = os.path.join(settings.PACK, "Server", *parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def common(*parts):
    """A path under pack/Common (textures the pack ships), with its folder made."""
    path = os.path.join(settings.PACK, "Common", *parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def write_png(path, width, height, pixel):
    """A plain RGBA PNG: pixel(x, y) -> (r, g, b, a)."""
    import struct
    import zlib
    rows = b"".join(b"\x00" + b"".join(bytes(pixel(x, y)) for x in range(width))
                    for y in range(height))
    chunk = lambda kind, data: (struct.pack(">I", len(data)) + kind + data
                                + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff))
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n"
                 + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
                 + chunk(b"IDAT", zlib.compress(rows)) + chunk(b"IEND", b""))


def write(path, data):
    with open(path, "w") as fh:
        json.dump(data, fh, indent=2)
        fh.write("\n")


def write_item(game_id, data):
    write(out("Item", "Items", settings.NAMESPACE, f"{game_id}.json"), data)


def say(key, text):
    """A language line: `key` without the "server." the game puts in front."""
    if key in _lang and _lang[key] != text:
        raise ValueError(f"language key {key} said two different things")
    _lang[key] = text


def finish():
    path = out("Languages", "en-US", "server.lang")
    with open(path, "w") as fh:
        fh.write("\n".join(f"{k} = {v}" for k, v in sorted(_lang.items())) + "\n")
