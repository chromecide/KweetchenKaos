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
    /kk grid [n]   mark the plots' edges (the first n; PLOTS without) -- OUTSIDE what is
                   saved, so it never touches a build: safe to run again, and to add plots
    /kk slots      hand over the slot blocks -- all of them; "/kk slots hq" just HQ's
                   (the arrival, portals 1-4), "/kk slots plot" just a restaurant plot's
    /kk save [n]   save the plots as prefabs (K2_Save_00, _01, ...; the first n)
    /kk restore    paste the kept layouts back into their plots (RESTORE below) -- for a
                   new authoring world
    /kk restore n  put plot n back as it was LAST SAVED, throwing away changes since

THE PLOTS, in a row along x, six chunks apart so no guest can see or walk into the next:

    plot 0         the BORDER plot (below)
    plot 1         HQ
    plots 2-9      restaurant layouts

A room plot is 32 x 32 (two chunks square); build inside it, floor and all -- everything
from ROOM_BELOW under the floor up to AUTHOR_HEIGHT above it is saved. The world has real
ground (stone, dirt, grass at FLOOR), so gravel rests and you can dig down. /kk grid draws a line of EDGE blocks round each
plot one block OUTSIDE it, so the markers are never saved and the grid never touches what
is inside: more plots can be added (PLOTS) and the grid run again at any time.

THE BORDER PLOT is a BACKDROP: a ring one chunk thick round a room-sized hole, 64 x 64 in
all. Build scenery on the ring (up to BORDER_HEIGHT); its edge line runs outside the ring,
and a second one marks the hole from just inside it. The hole is left out when the border is
imported, and every world pastes the border round its room (world.json "border"):

    python3 build/layouts.py import 0 meadow "Meadow"      -> content/layouts/meadow/

The border saves BORDER_BELOW under the floor: sculpt the underside of a floating island
there (under the hole too, below the room's own ground).

RESTORE: the imported layouts named in RESTORE are pasted back into their plots by
/kk restore (they are corner-anchored, so each goes at its plot's corner).

ZONES are drawn, not placed: draw a trigger volume with the game's volume tool and name it.
Today there is one, "queue" -- the area where guests wait (the spots and the pool). The
queue's patience counts only guests inside it, so a seated guest must be outside it. No
door, ever: a closed door blocks NPC pathfinding.

SAVES ARE RESCUED, then IMPORTED. `prefab save` writes into the DEPLOYED mod folder, which
every deploy wipes, so deploy.py copies K2_Save_* home (content/layouts/_saves/) first.
Importing turns a save into a layout:

    python3 build/layouts.py import 3 corner_pass "Corner pass"

which re-anchors it (a save comes back CENTRE-anchored; everything else is corner-anchored
0..31, so it is shifted), keeps the zones you drew, lists the slots it found, and writes
content/layouts/corner_pass/.
"""
import json
import os
import shutil
import sys

import blocks
import pack
import settings

CHUNK = 16
LAYOUT = 2 * CHUNK            # a plot is 32 x 32 blocks
PITCH = 6 * CHUNK             # plots are 96 blocks apart on x
AUTHOR_HEIGHT = 16
PLOTS = 10                    # plot 0 the border, 1 HQ, 2-9 layouts; more can be added
MAX_PLOTS = 32
# THE GROUND: stone, then dirt, then the grass the plots stand on at FLOOR -- deep enough to
# dig into and for gravel to rest on. A plot saves some of the ground under its floor too
# (a room ROOM_BELOW deep, the border BORDER_BELOW -- room for an island's underside); an
# import puts the floor back at y 0, so what is under it is at negative y.
FLOOR = 32
ROOM_BELOW, BORDER_BELOW = 3, 16
GROUND = [{"From": 0, "To": FLOOR - 3, "BlockType": "Rock_Stone"},
          {"From": FLOOR - 3, "To": FLOOR, "BlockType": "Soil_Dirt"},
          {"From": FLOOR, "To": FLOOR + 1, "BlockType": "Soil_Grass"}]                # "/kk grid 20", "/kk save 20": up to this many
BORDER = CHUNK                # a border plot's ring is one chunk thick
BORDER_PLOTS = {0}            # which plots are borders
BORDER_HEIGHT = 48
BORDER_EDGE = f"{settings.NAMESPACE}_Border_Edge"
EDGE_TINT = "#e0c020"
RESTORE = {0: "backdrop", 1: "hq", 2: "test_room"}   # plot -> the layout pasted back
AUTHOR = f"{settings.NAMESPACE}_Author"
SAVE_PREFIX = f"{settings.NAMESPACE}_Save_"
SAVES = os.path.join(settings.CONTENT, "layouts", "_saves")
# Where /kk save writes: the server's copy of the pack (local.cfg SERVER).
DEPLOYED_PREFABS = (os.path.join(settings.SERVER, "mods",
                                 f"{settings.PACK_GROUP}_{settings.PACK_NAME}", "Server", "Prefabs")
                    if settings.SERVER else None)

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
    """The corner of plot i -- for a border plot, the corner of its HOLE."""
    return i * PITCH, 0


def below(i):
    """How deep under the floor plot i saves."""
    return BORDER_BELOW if i in BORDER_PLOTS else ROOM_BELOW


def plot_box(i):
    """(x1, z1, x2, z2, y1, y2): what plot i saves -- a border plot, its ring too -- from
    below(i) under the floor up."""
    x, z = plot_origin(i)
    y1 = FLOOR - below(i)
    if i in BORDER_PLOTS:
        return (x - BORDER, z - BORDER, x + LAYOUT + BORDER - 1, z + LAYOUT + BORDER - 1,
                y1, FLOOR + BORDER_HEIGHT - 1)
    return x, z, x + LAYOUT - 1, z + LAYOUT - 1, y1, FLOOR + AUTHOR_HEIGHT - 1


def _rect(a, b, c, d):
    """Commands drawing a line of edge blocks round the rectangle (a, b)-(c, d), on the floor."""
    out = []
    for p1, p2 in (((a, b), (c, b)), ((a, d), (c, d)), ((a, b), (a, d)), ((c, b), (c, d))):
        out += [f"pos1 --x={p1[0]} --y={FLOOR} --z={p1[1]}",
                f"pos2 --x={p2[0]} --y={FLOOR} --z={p2[1]}",
                f"set {BORDER_EDGE}"]
    return out


def _lay_edges(i):
    """Commands marking plot i: a line one block OUTSIDE what it saves -- and for a border
    plot, a second just inside its hole (the hole is dropped on import)."""
    x1, z1, x2, z2, _, _ = plot_box(i)
    out = _rect(x1 - 1, z1 - 1, x2 + 1, z2 + 1)
    if i in BORDER_PLOTS:
        hx, hz = plot_origin(i)
        out += _rect(hx, hz, hx + LAYOUT - 1, hz + LAYOUT - 1)
    return out


def write_slots():
    blocks.station_block(BORDER_EDGE, "Plot edge", SLOT_LOOK,
                         "Plot edge (outside what is saved)",
                         "Marks a plot's edge. See build/layouts.py.", tint=EDGE_TINT,
                         use=False)
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


def slot_kit(name):
    """Which kits a slot is in: "hq" (the arrival, portals) and "plot" (everything a
    restaurant layout uses -- the arrival too)."""
    if name == "arrival":
        return {"hq", "plot"}
    return {"hq"} if name.startswith("portal_") else {"plot"}


def _give(slots, kit=None):
    return [f"give {slot_id(n)}" for n, _, _ in slots if kit is None or kit in slot_kit(n)
            for _ in range(4 if n == "chair" else 1)]


def write_authoring():
    """The authoring world and its commands."""
    manifest = json.load(open(os.path.join(settings.PACK, "manifest.json")))
    pack_id = f"{manifest['Group']}:{manifest['Name']}"
    pack.write(pack.out("Instances", AUTHOR, "instance.bson"), {
        "$Comment": "The layout workshop: creative, and PERSISTENT -- what you build here is "
                    "still here tomorrow. See build/layouts.py.",
        "Version": 2,
        "WorldGen": {"Type": "Flat", "Layers": GROUND},
        "SpawnProvider": {"Id": "Global", "SpawnPoint": {
            # In front of HQ's plot (plot 1), outside its edge.
            "X": PITCH + LAYOUT / 2, "Y": FLOOR + 2.0, "Z": -4.0, "Pitch": 0.0, "Yaw": 0.0,
            "Roll": 0.0}},
        "GameMode": "Creative", "GameTime": "0001-01-01T12:00:00Z", "IsGameTimePaused": True,
        "IsSpawningNPC": False, "IsSpawnMarkersEnabled": False, "IsBlockSpawnersEnabled": False,
        "DeleteOnRemove": False, "DeleteOnUniverseStart": False,
        "Plugin": {"Instance": {"InstanceKey": AUTHOR.lower()}}})
    enter = [f"instances spawn {AUTHOR}", "wait 4", "gamemode creative"]
    def grid(n):
        out = list(enter)
        for i in range(n):
            x1, z1, x2, z2, _, _ = plot_box(i)
            # set writes only into LOADED chunks: stand over each plot first.
            out += [f"tp {(x1 + x2) // 2} {FLOOR + 30} {(z1 + z2) // 2}", "wait 3",
                    *_lay_edges(i)]
        return out

    def save(n):
        out = []
        for i in range(n):
            x1, z1, x2, z2, y1, y2 = plot_box(i)
            # Stand over the plot first: its chunks must be loaded to be read.
            out += [f"tp {(x1 + x2) // 2} {FLOOR + 30} {(z1 + z2) // 2}", "wait 3",
                    f"pos1 --x={x1} --y={y1} --z={z1}", f"pos2 --x={x2} --y={y2} --z={z2}",
                    # --entities, or the zones you drew are left out of the save.
                    f"prefab save {SAVE_PREFIX}{i:02d} --overwrite --entities --pack={pack_id}"]
        return out

    macros = [("KKAuthor", "kk author", "Open the layout authoring world", enter),
              ("KKGrid", "kk grid", f"Mark the {PLOTS} authoring plots' edges (safe to rerun)",
               grid(PLOTS)),
              ("KKSave", "kk save", f"Save the {PLOTS} authoring plots as prefabs", save(PLOTS)),
              ("KKSlots", "kk slots", "Hand over every slot block", _give(SLOTS)),
              ("KKSlotsHq", "kk slots hq", "Hand over HQ's slot blocks (arrival, portals)",
               _give(SLOTS, "hq")),
              ("KKSlotsPlot", "kk slots plot", "Hand over a restaurant plot's slot blocks",
               _give(SLOTS, "plot"))]
    # "/kk grid 20", "/kk save 20": the same for the first n plots -- a macro can't loop,
    # so each count is its own subcommand.
    for n in range(1, MAX_PLOTS + 1):
        macros += [(f"KKGrid{n}", f"kk grid {n}", f"Mark the first {n} plots' edges", grid(n)),
                   (f"KKSave{n}", f"kk save {n}", f"Save the first {n} plots", save(n))]
    # RESTORE: the kept layouts pasted back at their plots' corners (they are corner-
    # anchored). paste writes only into LOADED chunks, so stand in each plot first.
    restore = list(enter)
    for plot, lid in sorted(RESTORE.items()):
        src = os.path.join(settings.CONTENT, "layouts", lid, "room.prefab.json")
        name = f"{settings.NAMESPACE}_Restore_Plot_{plot}"
        pack.write(pack.out("Prefabs", f"{name}.prefab.json"),
                   dict(json.load(open(src)), **{"$Comment": f"Layout {lid}, for /kk restore. "
                                                            f"See build/layouts.py."}))
        x1, z1, x2, z2, _, _ = plot_box(plot)
        # An imported layout has its floor at y 0 (the ground under it below).
        restore += [f"tp {(x1 + x2) // 2} {FLOOR + 30} {(z1 + z2) // 2}", "wait 5",
                    f"prefab load {name}", "wait 1", f"paste {x1} {FLOOR} {z1}", "wait 3"]
    macros.append(("KKRestore", "kk restore",
                   "Paste the kept layouts back into their plots", restore))
    # "/kk restore 3": plot 3 back to its LAST SAVE, throwing away what was built since. The
    # saves go into the pack (a deploy wipes the server's copy). Only for plots that HAVE a
    # save: a macro carries on past a failed step, so with no save to paste it would clear
    # the plot and leave it empty. Load first, then clear the whole box, ground and all (the
    # save holds every block of it), then paste -- a save is anchored at the centre on x and z
    # and at the BOTTOM on y, so at the box's centre cell on its lowest layer.
    for n in range(MAX_PLOTS):
        src = latest_save(n, quiet=True)
        if src is None:
            continue
        shutil.copy2(src, pack.out("Prefabs", os.path.basename(src)))
        x1, z1, x2, z2, y1, y2 = plot_box(n)
        macros.append((f"KKRestore{n}", f"kk restore {n}",
                       f"Put plot {n} back as it was last saved", list(enter) + [
            f"tp {(x1 + x2) // 2} {FLOOR + 30} {(z1 + z2) // 2}", "wait 5",
            f"prefab load {SAVE_PREFIX}{n:02d}", "wait 1",
            f"pos1 --x={x1} --y={y1} --z={z1}", f"pos2 --x={x2} --y={y2} --z={z2}",
            "set Empty",
            f"paste {x1 + (x2 - x1) // 2} {y1} {z1 + (z2 - z1) // 2}", "wait 3"]))
    for file, name, desc, commands in macros:
        key = f"commands.{name.replace(' ', '.')}.desc"
        pack.say(key, desc)
        pack.write(pack.out("MacroCommands", f"{file}.json"), {
            "$Comment": f"{desc}. See build/layouts.py.", "Name": name,
            "Description": f"server.{key}", "Commands": commands})


def latest_save(plot, quiet=False):
    """Plot's last save, kept in content/layouts/_saves/ -- or None. A save made since the
    last deploy is still only in the server's copy of the mod (the deploy rescues it): it is
    taken from there first, or this would give the previous save."""
    src = os.path.join(SAVES, f"{SAVE_PREFIX}{plot:02d}.prefab.json")
    live = os.path.join(DEPLOYED_PREFABS, os.path.basename(src)) if DEPLOYED_PREFABS else ""
    if live and os.path.exists(live) and (not os.path.exists(src)
                                 or os.path.getmtime(live) > os.path.getmtime(src)):
        shutil.copy2(live, src)
        if not quiet:
            print(f"plot {plot}: took the newer save from the server")
    return src if os.path.exists(src) else None


def import_save(plot, layout_id, name):
    """A rescued save -> content/layouts/<layout_id>/ (corner-anchored, slots listed)."""
    src = latest_save(plot)
    if src is None:
        raise SystemExit(f"plot {plot}: never saved")
    data = json.load(open(src))
    placed = data.get("blocks") or []
    if not placed:
        raise SystemExit(f"plot {plot}: nothing was built there")
    border = plot in BORDER_PLOTS
    size = LAYOUT + 2 * BORDER if border else LAYOUT
    shift = size // 2 - 1         # the save's anchor is the selection's centre
    if min(b["x"] for b in placed) >= 0:
        raise SystemExit(f"plot {plot}: already corner-anchored -- not a fresh save")
    # A save starts below(plot) under the floor, so its bottom layer is the world's ground
    # (dirt or stone). One whose bottom is a floor was saved before the ground went in.
    bottom = [b["name"] for b in placed if b["y"] == 0]
    if not bottom or max(set(bottom), key=bottom.count) not in ("Soil_Dirt", "Rock_Stone"):
        raise SystemExit(f"plot {plot}: saved before the authoring world had ground under "
                         f"its floor -- save it again")
    down = below(plot)
    for b in placed:
        b["x"] += shift
        b["z"] += shift
        b["y"] -= down
    if border:
        # THE HOLE is where the room goes, its ground too: nothing of the border's is kept
        # there -- except what is under the room's ground (an island's underside).
        hole = lambda c: (BORDER <= c["x"] < BORDER + LAYOUT and BORDER <= c["z"] < BORDER + LAYOUT
                          and c["y"] >= -ROOM_BELOW)
        placed[:] = [dict(b, name="Soil_Grass") if b["name"] == BORDER_EDGE else b
                     for b in placed if not hole(b)]
        data["blocks"] = placed
    assert all(0 <= b["x"] < size and 0 <= b["z"] < size for b in placed), \
        "blocks fall outside the plot after re-anchoring: the save anchor isn't where assumed"
    # FLUIDS TOO. A save lists a fluid for every block -- "Empty" for nearly all of them --
    # and the first import shifted the blocks but not these: the paste then wrote "no
    # fluid" over a room-sized patch half a plot away, clearing the ground there (the hole
    # a player fell through). Real fluids are shifted with the blocks; empty ones carry
    # nothing and are dropped.
    fluids = [dict(f, x=f["x"] + shift, z=f["z"] + shift, y=f["y"] - down)
              for f in data.get("fluids") or [] if f.get("name") != "Empty"]
    if border:
        fluids = [f for f in fluids if not hole(f)]
    data["fluids"] = fluids
    zones = {}
    for e in data.get("entities", []):
        tv, tr = e.get("Components", {}).get("TriggerVolume"), e.get("Components", {}).get("Transform")
        if tv and tr and tv.get("Name"):
            pos = dict(tr["Position"], X=tr["Position"]["X"] + shift, Y=tr["Position"]["Y"] - down,
                       Z=tr["Position"]["Z"] + shift)
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
        json.dump(dict({"id": layout_id, "name": name, "from_plot": plot, "zones": zones},
                       **({"kind": "border", "ring": BORDER} if border else {})), fh, indent=2)
        fh.write("\n")
    print(f"layout {layout_id}: {len(placed)} blocks, zones {sorted(zones) or 'none'}")
    for s, n in sorted(slots.items()):
        print(f"  {n}x {s}")
    if "queue" not in zones and not border:
        print("  NOTE: no 'queue' zone drawn -- the queue's patience needs one")


if __name__ == "__main__":
    if len(sys.argv) >= 4 and sys.argv[1] == "import":
        import_save(int(sys.argv[2]), sys.argv[3], " ".join(sys.argv[4:]) or sys.argv[3])
    else:
        print(__doc__)
