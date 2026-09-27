#!/usr/bin/env python3
"""
LAYOUTS: rooms built by hand, with SLOT blocks where the theme's things go.

A layout is theme-agnostic. You build the room (walls, floor, whatever blocks you like) in
the AUTHORING WORLD, and put a plain SLOT block wherever something of the restaurant's
goes: a stove slot, a counter slot, chair slots, queue spots, the pool, the offer pads, the
sign. When a restaurant is built, each slot becomes that theme's block -- a stove slot is a
stove in the kitchen and a cauldron in witchery. You live with the ugly room while building
it (docs/content-schema.md, Layouts).

ONE AUTHORING WORLD PER LAYOUT, each with a single plot, so no world gets crowded:

    /kk author border          the border (below)
    /kk author hq              HQ
    /kk author practice        the practice room
    /kk author floorplan 7     a restaurant room: floorplans 1 to FLOORPLANS
    /kk slots      hand over the slot blocks -- all of them; "/kk slots hq" just HQ's
                   (the arrival, portals 1-8), "/kk slots plot" just a room's
    /kk save floorplan 7       save that world's plot (K2_Save_Floorplan_07). It goes into
                               that world first, so it can only save the world it names.
    /kk restore floorplan 7    put it back as it was LAST SAVED, throwing away changes since
                               (there once it has a save)

Each world is creative and persistent. /kk author marks the plot's edges every time you go:
a line of edge blocks one block OUTSIDE what is saved, so it never touches a build.

A room plot is 32 x 32 (two chunks square), its corner at 0, 0; build inside it, floor and
all -- everything from ROOM_BELOW under the floor up to AUTHOR_HEIGHT above it is saved. The
world has real ground (stone, dirt, grass at FLOOR), so gravel rests and you can dig down.

THE BORDER is a BACKDROP: a ring one chunk thick round a room-sized hole, 64 x 64 in all.
Build scenery on the ring (up to BORDER_HEIGHT); its edge line runs outside the ring, and a
second one marks the hole from just inside it. The hole is left out when the border is
imported, and every world pastes the border round its room (world.json "border"). The
border saves BORDER_BELOW under the floor: sculpt the underside of a floating island there
(under the hole too, below the room's own ground).

ZONES are drawn, not placed: draw a trigger volume with the game's volume tool and name it.
Today there is one, "queue" -- the area where guests wait (the spots and the pool). The
queue's patience counts only guests inside it, so a seated guest must be outside it. No
door, ever: a closed door blocks NPC pathfinding.

SAVES ARE RESCUED, then IMPORTED. `prefab save` writes into the DEPLOYED mod folder, which
every deploy wipes, so deploy.py copies K2_Save_* home (content/layouts/_saves/) first.
Importing turns a save into a layout:

    python3 build/layouts.py import floorplan_07 corner_pass "Corner pass"

which re-anchors it (a save comes back CENTRE-anchored; everything else is corner-anchored
0..31, so it is shifted), keeps the zones you drew, lists the slots it found, and writes
content/layouts/corner_pass/.
"""
import json
import glob
import os
import re
import shutil
import sys

import blocks
import pack
import settings

CHUNK = 16
LAYOUT = 2 * CHUNK            # a plot is 32 x 32 blocks
AUTHOR_HEIGHT = 48             # saved above a room's floor: tall enough for a room up a tree
# THE AUTHORING WORLDS, one per layout: the border, HQ, the practice room, and the
# floorplans (restaurant rooms), numbered 1 to FLOORPLANS. Each is its own world with one
# plot, so a room is built and saved on its own.
FLOORPLANS = 99
# THE GROUND: stone, then dirt, then the grass the plot stands on at FLOOR -- deep enough to
# dig into and for gravel to rest on. A plot saves some of the ground under its floor too
# (a room ROOM_BELOW deep, the border BORDER_BELOW -- room for an island's underside); an
# import puts the floor back at y 0, so what is under it is at negative y.
FLOOR = 32
ROOM_BELOW, BORDER_BELOW = 3, 16
GROUND = [{"From": 0, "To": FLOOR - 3, "BlockType": "Rock_Stone"},
          {"From": FLOOR - 3, "To": FLOOR, "BlockType": "Soil_Dirt"},
          {"From": FLOOR, "To": FLOOR + 1, "BlockType": "Soil_Grass"}]
BORDER = CHUNK                # a border plot's ring is one chunk thick
BORDER_HEIGHT = 48
BORDER_EDGE = f"{settings.NAMESPACE}_Border_Edge"
EDGE_TINT = "#e0c020"
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
# HQ's PORTALS: one per room size, each picking one of that size's rooms at random as a
# run starts (world.py), and one to the practice room. A room's size is a slot in it. The
# STARTER is a tiny room, good for one player.
SIZES = ["starter", "small", "medium", "large"]
PORTALS = ["practice"] + SIZES
SIZE_TINT = "#e0e040"
BARRIER_TINT = "#ff40ff"
BARRIER = "Barrier"             # what a barrier slot becomes: the game's invisible wall
SLOTS = (
    [(f"station_{role}", f"Slot: {what}", STATION_TINT)
     for role, what in (("press", "board (press)"), ("combine", "counter (combine)"),
                        ("heat", "stove (heat)"), ("wash", "sink (wash)"), ("bin", "bin"),
                        ("rack", "plate rack (starts with plates)"),
                        ("call", "booking desk"), ("tool", "mop stand"))]
    + [("chair", "Slot: chair (its table goes in front)", SEAT_TINT)]
    + [(f"queue_{i}", f"Slot: queue spot {i}" + (" (the front)" if i == 1 else ""), QUEUE_TINT)
       for i in range(1, 5)]
    + [("pool", "Slot: queue pool (guests arrive here)", QUEUE_TINT)]
    + [(f"pad_{n}", f"Slot: offer pad {n}", PAD_TINT) for n in range(1, 5)]
    + [("sign", "Slot: open sign", SIGN_TINT)]
    # Any layout: where players appear (HQ or a restaurant; it becomes the floor round it).
    + [("arrival", "Slot: arrival (players appear here)", ARRIVAL_TINT)]
    # A PRACTICE room (systems/practice.py): where the "call a guest" block goes -- a room
    # with one is built as a practice kitchen.
    + [("practice_call", "Slot: call a guest (makes this a practice room)", QUEUE_TINT)]
    # Any layout: an invisible wall in game. The game's own Barrier can hardly be seen while
    # building, so it's built as this and becomes a Barrier (barrier()).
    + [("barrier", "Slot: barrier (an invisible wall in game)", BARRIER_TINT)]
    # A restaurant room: its SIZE, one of these -- which HQ portal it's picked from.
    + [(f"size_{s}", f"Slot: room size - {s} (picked by HQ's {s} portal)", SIZE_TINT)
       for s in SIZES]
    # HQ only: a walk-in portal per size, and to the practice room.
    + [(f"portal_{k}", f"Slot: HQ portal - " + ("the practice room" if k == "practice"
                                                 else f"{k} rooms"), PORTAL_TINT)
       for k in PORTALS])
# PRACTICE rooms only: a CRATE per ingredient (a run's crates are delivered; a practice
# room has nothing to deliver them) -- from the theme, like the shelves.
CRATE_SLOTS = []
# HQ only: a FRANCHISE SHELF per item a player can bank (systems/franchise.py) -- worked out
# from the theme and rules when the slots are written (write_slots), so kept apart from SLOTS.
SHELF_TINT = "#c08a3a"
SHELF_SLOTS = []
# A portal slot is the portal pad itself (world.py puts the portal where it stands).
PORTAL_LOOK = {"model": "Blocks/Miscellaneous/Platform_Magic_Exit.blockymodel",
               "texture": "Blocks/Miscellaneous/Platform_Magic_Blue2.png",
               "icon": "Icons/ItemsGenerated/Portal_Return.png"}
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


def barrier(b):
    """A barrier slot is a Barrier in the built game, a builder's light an invisible light
    (LIGHTS); any other block is itself."""
    if b["name"] == slot_id("barrier"):
        return dict(b, name=BARRIER)
    if b["name"].startswith(LIGHT_FROM) and b["name"][len(LIGHT_FROM):] in LIGHTS:
        return dict(b, name=light_id(b["name"][len(LIGHT_FROM):]))
    return b


# INVISIBLE LIGHTS. The game has no invisible light source: its builder lights
# (Build_Lightsource_<colour>) are glowing cubes. So a layout is built with those -- you
# can see where they are -- and each becomes one of these in the game: no look, nothing to
# bump into, the same light. Colours as the game's own builder lights give.
LIGHT_FROM = "Build_Lightsource_"
LIGHTS = {"White": "#eee", "Yellow": "#a98", "YellowLight": "#aa8", "Orange": "#a72",
          "Red": "#811", "Pink": "#618", "Blue": "#778", "Cyan": "#599", "Green": "#485"}


def light_id(colour):
    return f"{settings.NAMESPACE}_Light_{colour}"


def write_lights():
    for colour, rgb in LIGHTS.items():
        blocks.item(light_id(colour), f"Invisible light ({colour.lower()})",
                    f"Icons/ItemsGenerated/{LIGHT_FROM}{colour}.png",
                    {"Material": "Empty", "DrawType": "Empty", "Opacity": "Transparent",
                     "Light": {"Color": rgb}},
                    f"A builder's light ({LIGHT_FROM}{colour}), made invisible. "
                    f"See build/layouts.py.")


def slot_id(name):
    return f"{settings.NAMESPACE}_Slot_" + "_".join(p.capitalize() for p in name.split("_"))


def sources():
    """Every authoring world, by its key: "border", "hq", "practice", "floorplan_01" ..."""
    return ["border", "hq", "practice"] + [f"floorplan_{n:02d}" for n in range(1, FLOORPLANS + 1)]


def spoken(src):
    """How a world is named in a command: "floorplan 7"."""
    return f"floorplan {int(src.rsplit('_', 1)[1])}" if src.startswith("floorplan_") else src


def title(src):
    return "_".join(p.capitalize() for p in src.split("_"))


def is_border(src):
    return src == "border"


def below(src):
    """How deep under the floor a world's plot saves."""
    return BORDER_BELOW if is_border(src) else ROOM_BELOW


def plot_box(src):
    """(x1, z1, x2, z2, y1, y2): what a world's plot saves -- the border's, its ring too --
    from below() under the floor up. The plot (the border's HOLE) has its corner at 0, 0."""
    y1 = FLOOR - below(src)
    if is_border(src):
        return (-BORDER, -BORDER, LAYOUT + BORDER - 1, LAYOUT + BORDER - 1,
                y1, FLOOR + BORDER_HEIGHT - 1)
    return 0, 0, LAYOUT - 1, LAYOUT - 1, y1, FLOOR + AUTHOR_HEIGHT - 1


def _rect(a, b, c, d):
    """Commands drawing a line of edge blocks round the rectangle (a, b)-(c, d), on the floor."""
    out = []
    for p1, p2 in (((a, b), (c, b)), ((a, d), (c, d)), ((a, b), (a, d)), ((c, b), (c, d))):
        out += [f"pos1 --x={p1[0]} --y={FLOOR} --z={p1[1]}",
                f"pos2 --x={p2[0]} --y={FLOOR} --z={p2[1]}",
                f"set {BORDER_EDGE}"]
    return out


def _lay_edges(src):
    """Commands marking a world's plot: a line one block OUTSIDE what it saves -- and for
    the border, a second just inside its hole (the hole is dropped on import)."""
    x1, z1, x2, z2, _, _ = plot_box(src)
    out = _rect(x1 - 1, z1 - 1, x2 + 1, z2 + 1)
    if is_border(src):
        out += _rect(0, 0, LAYOUT - 1, LAYOUT - 1)
    return out


def write_slots(model=None):
    """The slot blocks. Each shows its name when you look at it (a hint needs an F action,
    so they all have one that does nothing). With a `model`, a STATION slot looks like that
    theme's station -- a stove slot is an iron stove with its trim -- so a room reads as it
    will play; the fixtures keep their tinted markers."""
    blocks.write_noop()
    write_lights()
    stations = {}
    for st in (model or {}).get("stations", {}).values():
        if not st.get("upgrade_of"):
            stations.setdefault(st["role"], st)
    blocks.station_block(BORDER_EDGE, "Plot edge", SLOT_LOOK,
                         "Plot edge (outside what is saved)",
                         "Marks a plot's edge. See build/layouts.py.", tint=EDGE_TINT,
                         use=False)
    if model and model.get("rules"):
        from systems import franchise
        SHELF_SLOTS[:] = [(f"shelf_{key}", f"Slot: franchise shelf - {label}", SHELF_TINT)
                          for key, label, _, _ in franchise.items(model)]
    if model and model.get("stations"):
        CRATE_SLOTS[:] = [(sid, f"Slot: crate - {model['items'][st['ingredient']]['label']} "
                                f"(practice rooms)", STATION_TINT)
                          for sid, st in sorted(model["stations"].items())
                          if st["role"] == "crate" and not st.get("upgrade_of")]
    for name, label, tint in SLOTS + SHELF_SLOTS + CRATE_SLOTS:
        if name.startswith("crate_") and name in (model or {}).get("stations", {}):
            # A crate slot looks like its crate.
            st = model["stations"][name]
            look = {k: v for k, v in st["look"].items() if k in ("sides", "top", "trim", "sound")}
            blocks.station_block(slot_id(name), label, look, label,
                                 "A layout slot. See build/layouts.py.", tint=st["look"].get("tint"),
                                 keyed=False)
            continue
        if name == "chair":
            # A chair has a FACING (its table goes in front), so its slot is a chair.
            block = {"CustomModel": CHAIR_LOOK["model"],
                     "CustomModelTexture": [{"Texture": CHAIR_LOOK["texture"], "Weight": 1}],
                     "DrawType": "Model", "Material": "Solid", "Opacity": "Transparent",
                     "HitboxType": "Chair_Small", "Tint": [tint], "VariantRotation": "NESW",
                     "BlockSoundSetId": "Wood", "PhysicalMaterialId": "Wood",
                     "InteractionHint": blocks.hint(slot_id(name), label, keyed=False),
                     "Interactions": {"Use": blocks.NOOP}}
            blocks.item(slot_id(name), label, CHAIR_LOOK["icon"], block,
                        "A layout slot. See build/layouts.py.")
        elif name.startswith("portal_"):
            # A portal slot is the portal's own pad, so it is placed exactly where the
            # portal will be (it takes the slot's place in game).
            block = dict(blocks.block_for(PORTAL_LOOK), Material="Solid", HitboxType="Pad_Portal",
                         Tint=[tint], InteractionHint=blocks.hint(slot_id(name), label, keyed=False),
                         Interactions={"Use": blocks.NOOP})
            blocks.item(slot_id(name), label, PORTAL_LOOK["icon"], block,
                        "A layout slot. See build/layouts.py.")
        elif name.startswith("station_") and name[len("station_"):] in stations:
            st = stations[name[len("station_"):]]
            # Its free look: no turn (you place it the way you like) and no in-use states.
            look = {k: v for k, v in st["look"].items() if k in ("sides", "top", "trim", "sound")}
            blocks.station_block(slot_id(name), label, look, label,
                                 "A layout slot. See build/layouts.py.", tint=st["look"].get("tint"),
                                 keyed=False)
        else:
            blocks.station_block(slot_id(name), label, SLOT_LOOK, label,
                                 "A layout slot. See build/layouts.py.", tint=tint, keyed=False)


def slot_kit(name):
    """Which kits a slot is in: "hq" (the arrival, portals) and "plot" (everything a
    restaurant layout uses -- the arrival too)."""
    if name in ("arrival", "barrier"):
        return {"hq", "plot"}
    return {"hq"} if name.startswith(("portal_", "shelf_")) else {"plot"}


def _give(slots, kit=None):
    return [f"give {slot_id(n)}" for n, _, _ in slots if kit is None or kit in slot_kit(n)
            for _ in range(4 if n == "chair" else 1)]


def world_name(src):
    return f"{AUTHOR}_{title(src)}"


def write_authoring(release=False):
    """The authoring worlds and their commands. `release`: without this project's own
    saves -- no /kk restore (they're the author's working copies, not the game)."""
    manifest = json.load(open(os.path.join(settings.PACK, "manifest.json")))
    pack_id = f"{manifest['Group']}:{manifest['Name']}"
    macros = [("KKSlots", "kk slots", "Hand over every slot block",
               _give(SLOTS + SHELF_SLOTS + CRATE_SLOTS)),
              ("KKSlotsHq", "kk slots hq", "Hand over HQ's slot blocks (arrival, portals, "
                                           "franchise shelves)",
               _give(SLOTS + SHELF_SLOTS, "hq")),
              ("KKSlotsPlot", "kk slots plot", "Hand over a restaurant room's slot blocks "
                                               "(and a practice room's)",
               _give(SLOTS + CRATE_SLOTS, "plot"))]
    for src in sources():
        name, said = world_name(src), spoken(src)
        pack.write(pack.out("Instances", name, "instance.bson"), {
            "$Comment": f"Authoring world: {said}. Creative, and PERSISTENT -- what you build "
                        f"here is still here tomorrow. See build/layouts.py.",
            "Version": 2,
            "WorldGen": {"Type": "Flat", "Layers": GROUND},
            "SpawnProvider": {"Id": "Global", "SpawnPoint": {
                # In front of the plot, outside its edge (the border's: outside its ring).
                "X": LAYOUT / 2, "Y": FLOOR + 2.0,
                "Z": -4.0 - (BORDER if is_border(src) else 0), "Pitch": 0.0, "Yaw": 0.0,
                "Roll": 0.0}},
            "GameMode": "Creative", "GameTime": "0001-01-01T12:00:00Z", "IsGameTimePaused": True,
            "IsSpawningNPC": False, "IsSpawnMarkersEnabled": False, "IsBlockSpawnersEnabled": False,
            "DeleteOnRemove": False, "DeleteOnUniverseStart": False,
            "Plugin": {"Instance": {"InstanceKey": name.lower()}}})
        enter = [f"instances spawn {name}", "wait 4", "gamemode creative"]
        x1, z1, x2, z2, y1, y2 = plot_box(src)
        over = [f"tp {(x1 + x2) // 2} {FLOOR + 30} {(z1 + z2) // 2}", "wait 3"]
        # AUTHOR: into the world, the plot's edges marked (outside what is saved, so safe
        # every time; set writes only into LOADED chunks, so from over the plot), and back
        # in front of it.
        macros.append((f"KKAuthor{title(src)}", f"kk author {said}",
                       f"Open the authoring world for {said}",
                       enter + over + _lay_edges(src)
                       + [f"tp {LAYOUT // 2} {FLOOR + 2} {z1 - 5}"]))
        # SAVE: into that world first, so it can only ever save the world it names.
        # --entities, or the zones you drew are left out of the save.
        macros.append((f"KKSave{title(src)}", f"kk save {said}", f"Save {said}",
                       enter + over + [f"pos1 --x={x1} --y={y1} --z={z1}",
                                       f"pos2 --x={x2} --y={y2} --z={z2}",
                                       f"prefab save {SAVE_PREFIX}{title(src)} --overwrite "
                                       f"--entities --pack={pack_id}"]))
        # RESTORE: the plot back to its LAST SAVE, throwing away what was built since. The
        # saves go into the pack (a deploy wipes the server's copy). Only for a world that
        # HAS a save: a macro carries on past a failed step, so with no save to paste it
        # would clear the plot and leave it empty. Load first, then clear the whole box,
        # ground and all (the save holds every block of it), then paste -- a save is
        # anchored at the centre on x and z and at the BOTTOM on y.
        save = None if release else latest_save(src, quiet=True)
        if save:
            shutil.copy2(save, pack.out("Prefabs", os.path.basename(save)))
            macros.append((f"KKRestore{title(src)}", f"kk restore {said}",
                           f"Put {said} back as it was last saved", enter + over + [
                f"prefab load {SAVE_PREFIX}{title(src)}", "wait 1",
                f"pos1 --x={x1} --y={y1} --z={z1}", f"pos2 --x={x2} --y={y2} --z={z2}",
                "set Empty",
                f"paste {x1 + (x2 - x1) // 2} {y1} {z1 + (z2 - z1) // 2}", "wait 3"]))
    for file, name, desc, commands in macros:
        key = f"commands.{name.replace(' ', '.')}.desc"
        pack.say(key, desc)
        pack.write(pack.out("MacroCommands", f"{file}.json"), {
            "$Comment": f"{desc}. See build/layouts.py.", "Name": name,
            "Description": f"server.{key}", "Commands": commands})


def latest_save(src, quiet=False):
    """A world's last save (src: "hq", "floorplan_07" ...), kept in content/layouts/_saves/
    -- or None. A save made since the last deploy is still only in the server's copy of the
    mod (the deploy rescues it): it is taken from there first, or this would give the
    previous save."""
    path = os.path.join(SAVES, f"{SAVE_PREFIX}{title(src)}.prefab.json")
    live = os.path.join(DEPLOYED_PREFABS, os.path.basename(path)) if DEPLOYED_PREFABS else ""
    if live and os.path.exists(live) and (not os.path.exists(path)
                                 or os.path.getmtime(live) > os.path.getmtime(path)):
        os.makedirs(SAVES, exist_ok=True)
        shutil.copy2(live, path)
        if not quiet:
            print(f"{spoken(src)}: took the newer save from the server")
    return path if os.path.exists(path) else None


# What a room needs to be PLAYABLE: every kind of station, and the fixtures a run can't do
# without. A saved plot with all of them is picked up by itself (reimport); one with some is
# said to be unfinished.
NEEDED = (["station_press", "station_combine", "station_heat", "station_wash", "station_bin",
           "station_rack", "station_call", "chair", "pool", "sign"] + [f"queue_{i}" for i in range(1, 5)])
# A PRACTICE room needs its kitchen and front of house and the call slot -- no sign, pads or
# booking desk (its crates are warned about when it's built).
PRACTICE_NEEDED = ([n for n in NEEDED if n not in ("sign", "station_call")] + ["practice_call"])


def room_slots(save_path):
    """The slot names a save holds ("chair", "station_heat"...)."""
    pre = f"{settings.NAMESPACE}_Slot_"
    return {b["name"][len(pre):].lower() for b in json.load(open(save_path)).get("blocks") or []
            if b["name"].startswith(pre)}


def reimport():
    """Import again every layout whose world has a save newer than the layout: each layout
    knows its world (layout.json "source"). What to run after /kk save.

    A world saved but never imported is picked up too -- the practice room or a floorplan,
    once it is a playable room (NEEDED), as its world's id: floorplan_07 / "Floorplan 7".
    Rename it with `import` (a new id) or in layout.json's name."""
    done = 0
    known = set()
    for meta_path in glob.glob(os.path.join(settings.CONTENT, "layouts", "*", "layout.json")):
        known.add(json.load(open(meta_path)).get("source"))
    for src in sources():
        if src in known:
            continue
        path = latest_save(src, quiet=True)
        if not path:
            continue
        have = room_slots(path)
        if not have:
            continue            # nothing built yet
        if src in ("border", "hq"):
            print(f"  NOTE: {src} is saved but no layout comes from it -- import it: "
                  f"python3 build/layouts.py import {src} <id> \"<Name>\"")
            continue
        missing = [n for n in (PRACTICE_NEEDED if "practice_call" in have else NEEDED)
                   if n not in have]
        if missing:
            print(f"  NOTE: {spoken(src)} isn't a playable room yet -- missing: {', '.join(missing)}")
            continue
        name = spoken(src).capitalize()
        print(f"{spoken(src)} -> {src} (new)")
        import_save(src, src, name)
        done += 1
    for meta_path in sorted(glob.glob(os.path.join(settings.CONTENT, "layouts", "*", "layout.json"))):
        meta = json.load(open(meta_path))
        src = meta.get("source")
        if src is None:
            continue
        path = latest_save(src, quiet=True)
        room = os.path.join(os.path.dirname(meta_path), "room.prefab.json")
        if path and (not os.path.exists(room) or os.path.getmtime(path) > os.path.getmtime(room)):
            print(f"{spoken(src)} -> {meta['id']}")
            import_save(src, meta["id"], meta["name"])
            done += 1
    print(f"{done} layout(s) re-imported" if done else "every layout is up to date with its world")


def import_save(plot, layout_id, name):
    """A rescued save -> content/layouts/<layout_id>/ (corner-anchored, slots listed).
    `plot`: the world it was saved in ("hq", "floorplan_07" ...)."""
    if plot not in sources():
        raise SystemExit(f"no authoring world '{plot}': border, hq, practice, "
                         f"floorplan_01 ... floorplan_{FLOORPLANS}")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", layout_id or ""):
        raise SystemExit(f"a layout id is lower case letters, digits and _, starting with a "
                         f"letter: '{layout_id}'")
    src = latest_save(plot)
    if src is None:
        raise SystemExit(f"{spoken(plot)}: never saved")
    data = json.load(open(src))
    placed = data.get("blocks") or []
    if not placed:
        raise SystemExit(f"{spoken(plot)}: nothing was built there")
    border = is_border(plot)
    size = LAYOUT + 2 * BORDER if border else LAYOUT
    shift = size // 2 - 1         # the save's anchor is the selection's centre
    if min(b["x"] for b in placed) >= 0:
        raise SystemExit(f"{spoken(plot)}: already corner-anchored -- not a fresh save")
    # A save starts below(plot) under the floor, so its bottom layer is the world's ground
    # (dirt or stone). One whose bottom is a floor was saved before the ground went in.
    bottom = [b["name"] for b in placed if b["y"] == 0]
    if not bottom or max(set(bottom), key=bottom.count) not in ("Soil_Dirt", "Rock_Stone"):
        raise SystemExit(f"{spoken(plot)}: saved before the authoring world had ground under "
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
        json.dump(dict({"id": layout_id, "name": name, "source": plot, "zones": zones},
                       **({"kind": "border", "ring": BORDER} if border else {})), fh, indent=2)
        fh.write("\n")
    print(f"layout {layout_id}: {len(placed)} blocks, zones {sorted(zones) or 'none'}")
    for s, n in sorted(slots.items()):
        print(f"  {n}x {s}")
    if "queue" not in zones and not border and any("Queue" in k for k in slots):
        print("  (no 'queue' zone drawn: the queue's area is worked out round its spots and pool)")


if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "reimport":
        reimport()
    elif len(sys.argv) >= 4 and sys.argv[1] == "import":
        import_save(sys.argv[2], sys.argv[3], " ".join(sys.argv[4:]) or sys.argv[3])
    else:
        print(__doc__)
