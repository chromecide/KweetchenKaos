#!/usr/bin/env python3
"""
LAYOUTS: rooms built by hand, with SLOT blocks where the theme's things go.

A layout is theme-agnostic. You build the room (walls, floor, whatever blocks you like) in
the AUTHORING WORLD, and put a plain SLOT block wherever something of the restaurant's
goes: a stove slot, a counter slot, chair slots, queue spots, the pool, the offer pads, the
sign. When a restaurant is built, each slot becomes that theme's block -- a stove slot is a
stove in the kitchen and a cauldron in witchery. You live with the ugly room while building
it (docs/content-schema.md, Layouts).

    /kk author     open the authoring world (creative, and it keeps what you build)
    /kk grid       lay the plots' floors -- ONCE, when the world is new: it is destructive
    /kk slots      hand over the slot blocks (the arrival, and HQ portals 1-4)
    /kk save       save every plot as a prefab (K2_Save_01, _02, ...)

THE PLOTS. Each plot is 32 x 32 (two chunks square), a gravel forecourt down the front
edge for the queue and a plank floor behind it for the room, plots six chunks apart so no
guest can see or walk into the next. Build inside a plot; everything above the floor up to
AUTHOR_HEIGHT is saved.

ZONES are drawn, not placed: draw a trigger volume with the game's volume tool and name it.
Today there is one, "queue" -- the area where guests wait (the spots and the pool). The
queue's patience counts only guests inside it, so a seated guest must be outside it. No
door, ever: a closed door blocks NPC pathfinding.

SAVES ARE RESCUED, then IMPORTED. `prefab save` writes into the DEPLOYED mod folder, which
every deploy wipes, so deploy.sh copies K2_Save_* home (content/layouts/_saves/) first.
Importing turns a save into a layout:

    python3 build/layouts.py import 1 corner_pass "Corner pass"

which re-anchors it (a save comes back CENTRE-anchored; everything else is corner-anchored
0..31, so it is shifted), keeps the zones you drew, lists the slots it found, and writes
content/layouts/corner_pass/.
"""
import json
import os
import sys

import blocks
import pack
import settings

CHUNK = 16
LAYOUT = 2 * CHUNK            # a plot is 32 x 32 blocks
PITCH = 6 * CHUNK             # plots are 96 blocks apart on x
FORECOURT = 6                 # the front 6 rows of a plot: where the queue goes
AUTHOR_HEIGHT = 16
PLOTS = 4
AUTHOR = f"{settings.NAMESPACE}_Author"
SAVE_PREFIX = f"{settings.NAMESPACE}_Save_"
SAVES = os.path.join(settings.CONTENT, "layouts", "_saves")

# THE SLOTS, theme-agnostic: a station slot is a ROLE (the theme has one station per role),
# the rest are fixtures. Tinted by kind so a room reads at a glance.
STATION_TINT, SEAT_TINT, QUEUE_TINT, PAD_TINT, SIGN_TINT = \
    "#e08a30", "#3c7ad0", "#40a060", "#8a6ad0", "#d04040"
PORTAL_TINT, ARRIVAL_TINT = "#30c8d8", "#f0f0f0"
SLOTS = (
    [(f"station_{role}", f"Slot: {what}", STATION_TINT)
     for role, what in (("press", "board (press)"), ("combine", "counter (combine)"),
                        ("heat", "stove (heat)"), ("wash", "sink (wash)"), ("bin", "bin"),
                        ("rack", "plate rack (starts with plates)"))]
    + [("chair", "Slot: chair (its table goes in front)", SEAT_TINT)]
    + [(f"queue_{i}", f"Slot: queue spot {i}" + (" (the front)" if i == 1 else ""), QUEUE_TINT)
       for i in range(1, 5)]
    + [("pool", "Slot: queue pool (guests arrive here)", QUEUE_TINT)]
    + [(f"pad_{n}", f"Slot: offer pad {n}", PAD_TINT) for n in range(1, 5)]
    + [("sign", "Slot: open sign", SIGN_TINT)]
    # Any layout: where players appear (HQ or a restaurant; it becomes the floor round it).
    + [("arrival", "Slot: arrival (players appear here)", ARRIVAL_TINT)]
    # HQ only: a walk-in portal per restaurant (world.json says which).
    + [(f"portal_{n}", f"Slot: HQ portal {n} (restaurant {n} in world.json)", PORTAL_TINT)
       for n in range(1, 5)])
CHAIR_LOOK = {"model": "Blocks/Decorative_Sets/Tavern/Chair.blockymodel",
              "texture": "Blocks/Decorative_Sets/Tavern/Chair_Texture.png",
              "icon": "Icons/ItemsGenerated/Furniture_Tavern_Chair.png"}
SLOT_LOOK = {"sides": "BlockTextures/Calcite_Brick_Smooth.png",
             "top": "BlockTextures/Calcite_Brick_Decorative_Top.png", "sound": "Stone"}


def floor_at(blocks_, x, y, z, default="Wood_Softwood_Planks"):
    """What a floor slot becomes: the commonest block beside it on the same level, so the
    slot disappears into the floor it was set in."""
    near = {(x + dx, y, z + dz) for dx, dz in ((1, 0), (-1, 0), (0, 1), (0, -1))}
    names = [b["name"] for b in blocks_ if (b["x"], b["y"], b["z"]) in near
             and not b["name"].startswith(f"{settings.NAMESPACE}_Slot_")]
    return max(set(names), key=names.count) if names else default


def slot_id(name):
    return f"{settings.NAMESPACE}_Slot_" + "_".join(p.capitalize() for p in name.split("_"))


def plot_origin(i):
    """The corner of plot i (0-based)."""
    return i * PITCH, 0


def write_slots():
    for name, label, tint in SLOTS:
        if name == "chair":
            # A chair has a FACING (its table goes in front), so its slot is a chair.
            block = {"CustomModel": CHAIR_LOOK["model"],
                     "CustomModelTexture": [{"Texture": CHAIR_LOOK["texture"], "Weight": 1}],
                     "DrawType": "Model", "Material": "Solid", "Opacity": "Transparent",
                     "HitboxType": "Chair_Small", "Tint": [tint], "VariantRotation": "NESW",
                     "BlockSoundSetId": "Wood", "PhysicalMaterialId": "Wood"}
            blocks.item(slot_id(name), label, CHAIR_LOOK["icon"], block,
                        "A layout slot. See build/layouts.py.")
        else:
            blocks.station_block(slot_id(name), label, SLOT_LOOK, label,
                                 "A layout slot. See build/layouts.py.", tint=tint, use=False)


def write_authoring():
    """The authoring world and its commands."""
    manifest = json.load(open(os.path.join(settings.PACK, "manifest.json")))
    pack_id = f"{manifest['Group']}:{manifest['Name']}"
    pack.write(pack.out("Instances", AUTHOR, "instance.bson"), {
        "$Comment": "The layout workshop: creative, and PERSISTENT -- what you build here is "
                    "still here tomorrow. See build/layouts.py.",
        "Version": 2,
        "WorldGen": {"Type": "Flat", "Layers": [{"From": 0, "To": 1, "BlockType": "Soil_Grass"}]},
        "SpawnProvider": {"Id": "Global", "SpawnPoint": {
            "X": LAYOUT / 2, "Y": 2.0, "Z": FORECOURT / 2, "Pitch": 0.0, "Yaw": 0.0,
            "Roll": 0.0}},
        "GameMode": "Creative", "GameTime": "0001-01-01T12:00:00Z", "IsGameTimePaused": True,
        "IsSpawningNPC": False, "IsSpawnMarkersEnabled": False, "IsBlockSpawnersEnabled": False,
        "DeleteOnRemove": False, "DeleteOnUniverseStart": False,
        "Plugin": {"Instance": {"InstanceKey": AUTHOR.lower()}}})
    enter = [f"instances spawn {AUTHOR}", "wait 4", "gamemode creative"]
    grid, save = list(enter), []
    for i in range(PLOTS):
        x, z = plot_origin(i)
        x2, z2 = x + LAYOUT - 1, z + LAYOUT - 1
        grid += [f"pos1 --x={x} --y=0 --z={z}", f"pos2 --x={x2} --y=0 --z={z + FORECOURT - 1}",
                 "set Soil_Gravel",
                 f"pos1 --x={x} --y=0 --z={z + FORECOURT}", f"pos2 --x={x2} --y=0 --z={z2}",
                 "set Wood_Softwood_Planks"]
        save += [f"pos1 --x={x} --y=0 --z={z}", f"pos2 --x={x2} --y={AUTHOR_HEIGHT - 1} --z={z2}",
                 # --entities, or the zones you drew are left out of the save.
                 f"prefab save {SAVE_PREFIX}{i + 1:02d} --overwrite --entities --pack={pack_id}"]
    macros = [("KKAuthor", "kk author", "Open the layout authoring world", enter),
              ("KKGrid", "kk grid", "Lay the authoring plots' floors (destructive: once)", grid),
              ("KKSave", "kk save", "Save every authoring plot as a prefab", save),
              ("KKSlots", "kk slots", "Hand over the layout slot blocks",
               [f"give {slot_id(n)}" for n, _, _ in SLOTS for _ in range(4 if n == "chair" else 1)])]
    # MOVE plot 1's build to plot 2 (so HQ can have plot 1), from its rescued save. A save
    # is CENTRE-anchored, so it is pasted at the plot's centre cell (+15, +15). paste writes
    # only into LOADED chunks, so stand in plot 2 first; then plot 1 is cleared and its floor
    # laid again.
    raw = os.path.join(SAVES, f"{SAVE_PREFIX}01.prefab.json")
    if os.path.exists(raw):
        import shutil
        shutil.copy(raw, pack.out("Prefabs", f"{SAVE_PREFIX}01.prefab.json"))
        (x1, z1), (x2, z2) = plot_origin(0), plot_origin(1)
        half = LAYOUT // 2 - 1
        macros.append(("KKPlot1to2", "kk plot1to2",
                       "Move plot 1's saved build to plot 2 and clear plot 1", [
            f"tp {x2 + LAYOUT // 2} 2 {z2 + LAYOUT // 2}", "wait 5",
            f"prefab load {SAVE_PREFIX}01", "wait 1",
            f"paste {x2 + half} 0 {z2 + half}", "wait 5",
            f"tp {x1 + LAYOUT // 2} 20 {z1 + LAYOUT // 2}", "wait 3",
            f"pos1 --x={x1} --y=0 --z={z1}",
            f"pos2 --x={x1 + LAYOUT - 1} --y={AUTHOR_HEIGHT - 1} --z={z1 + LAYOUT - 1}",
            "set Empty",
            f"pos1 --x={x1} --y=0 --z={z1}",
            f"pos2 --x={x1 + LAYOUT - 1} --y=0 --z={z1 + FORECOURT - 1}", "set Soil_Gravel",
            f"pos1 --x={x1} --y=0 --z={z1 + FORECOURT}",
            f"pos2 --x={x1 + LAYOUT - 1} --y=0 --z={z1 + LAYOUT - 1}", "set Wood_Softwood_Planks"]))
    for file, name, desc, commands in macros:
        key = f"commands.{name.replace(' ', '.')}.desc"
        pack.say(key, desc)
        pack.write(pack.out("MacroCommands", f"{file}.json"), {
            "$Comment": f"{desc}. See build/layouts.py.", "Name": name,
            "Description": f"server.{key}", "Commands": commands})


def import_save(plot, layout_id, name):
    """A rescued save -> content/layouts/<layout_id>/ (corner-anchored, slots listed)."""
    src = os.path.join(SAVES, f"{SAVE_PREFIX}{plot:02d}.prefab.json")
    data = json.load(open(src))
    placed = data.get("blocks") or []
    if not placed:
        raise SystemExit(f"plot {plot}: nothing was built there")
    shift = LAYOUT // 2 - 1       # the save's anchor is the selection's centre
    if min(b["x"] for b in placed) >= 0:
        raise SystemExit(f"plot {plot}: already corner-anchored -- not a fresh save")
    for b in placed:
        b["x"] += shift
        b["z"] += shift
    assert all(0 <= b["x"] < LAYOUT and 0 <= b["z"] < LAYOUT for b in placed), \
        "blocks fall outside the plot after re-anchoring: the save anchor isn't where assumed"
    # FLUIDS TOO. A save lists a fluid for every block -- "Empty" for nearly all of them --
    # and the first import shifted the blocks but not these: the paste then wrote "no
    # fluid" over a room-sized patch half a plot away, clearing the ground there (the hole
    # a player fell through). Real fluids are shifted with the blocks; empty ones carry
    # nothing and are dropped.
    fluids = [dict(f, x=f["x"] + shift, z=f["z"] + shift)
              for f in data.get("fluids") or [] if f.get("name") != "Empty"]
    data["fluids"] = fluids
    zones = {}
    for e in data.get("entities", []):
        tv, tr = e.get("Components", {}).get("TriggerVolume"), e.get("Components", {}).get("Transform")
        if tv and tr and tv.get("Name"):
            pos = dict(tr["Position"], X=tr["Position"]["X"] + shift, Z=tr["Position"]["Z"] + shift)
            zones[tv["Name"].strip().lower()] = {"position": pos, "shape": tv["Shape"]}
    data["anchorX"] = data["anchorY"] = data["anchorZ"] = 0
    data["entities"] = []
    slots = {}
    for b in placed:
        if b["name"].startswith(f"{settings.NAMESPACE}_Slot_"):
            slots.setdefault(b["name"], 0)
            slots[b["name"]] += 1
    out = os.path.join(settings.CONTENT, "layouts", layout_id)
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "room.prefab.json"), "w") as fh:
        json.dump(data, fh)
    with open(os.path.join(out, "layout.json"), "w") as fh:
        json.dump({"id": layout_id, "name": name, "from_plot": plot, "zones": zones}, fh, indent=2)
        fh.write("\n")
    print(f"layout {layout_id}: {len(placed)} blocks, zones {sorted(zones) or 'none'}")
    for s, n in sorted(slots.items()):
        print(f"  {n}x {s}")
    if "queue" not in zones:
        print("  NOTE: no 'queue' zone drawn -- the queue's patience needs one")


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "import":
        import_save(int(sys.argv[2]), sys.argv[3], " ".join(sys.argv[4:]) or sys.argv[3])
    else:
        print(__doc__)
