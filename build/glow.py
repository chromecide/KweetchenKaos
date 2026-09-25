"""
GLOW: how an upgraded station changes the speed of whatever grows on it. Infrastructure.

Proven in the POC's heat probe (probe_heat.py): crop growth has MODIFIERS, and one kind
reads the LIGHT at the growing block. So an upgraded station GLOWS in a pure colour, and
every stage block that should react carries a modifier listening for that colour:

    fast   the station glows blue; a stage block listening for blue >= 14 grows x2
    safe   the station glows green; the one stage that listens (well done) all but stops,
           so a dish on a safety stove never burns

The same stage blocks go on every station -- no per-station copies. Light fades about a
level a block, so a dish on the station NEXT to a glowing one sits at 13 and gets nothing;
ordinary torchlight never reaches 14 blue, and sunlight is ruled out of the range.

The theme sets the colours, thresholds and multipliers (theme.json "glow").
"""
import pack
import settings

NO_SUN = {"Min": 99.0, "Max": 99.0}     # daylight can't reach this: glow only


def modifier_id(model, kind):
    return settings.game_id(model["theme"]["prefix"], f"glow_{kind}")


def write(model):
    """The theme's growth modifiers. Returns {kind: modifier id}."""
    out = {}
    for kind, g in model["theme"].get("glow", {}).items():
        if kind.startswith("$"):
            continue
        ranges = {c: {"Min": 0, "Max": 127} for c in ("Red", "Green", "Blue")}
        ranges[g["channel"]] = {"Min": g["min"], "Max": 127}
        mid = modifier_id(model, kind)
        pack.write(pack.out("Farming", "Modifiers", f"{mid}.json"), {
            "$Comment": f"x{g['times']} while {g['channel'].lower()} light >= {g['min']} at "
                        f"the growing block. See build/glow.py.",
            "Type": "LightLevel", "Modifier": g["times"],
            "ArtificialLight": ranges, "Sunlight": NO_SUN, "RequireBoth": False})
        out[kind] = mid
    return out


def light(model, kind):
    """The BlockType setting that makes a station glow `kind`."""
    return {"Radius": 0, "Color": model["theme"]["glow"][kind]["colour"]}
