"""
THE WORLD: HQ, and the restaurants its portals lead to (content/world/world.json).

    /kk hq                  go to HQ (one shared world; everyone who goes is together)
    walk into a portal      you and whoever walks in after you land in THAT restaurant's
                            run -- a fresh one when nobody is in it
    OUT OF BUSINESS         a few seconds later, everyone goes back to HQ, onto its
                            arrival spot; the empty restaurant is torn down

HQ IS A LAYOUT, built by hand in the authoring world with two HQ slots: an ARRIVAL slot
(where players appear) and PORTAL slots 1-8 (layouts.PORTALS). world.json hangs a restaurant (theme + layout +
rules) on a portal number.

HOW THE GAME DOES IT (the Instances plugin; the shipped Forgotten Temple portal works the
same way):
  * A PORTAL is a block whose CollisionEnter runs TeleportInstance: stepping on it sends you
    into a new instance of that restaurant's world. With no InstanceKey, the BLOCK remembers
    the world it opened, so everyone who steps on the same portal joins the same run while
    it exists; once it is torn down, the next step opens a fresh one. Each player's return
    point is HQ's ARRIVAL slot (PersonalReturnPoint, each portal's offset to the arrival).
  * Leaving is ExitInstance (shift.py's loss rule), which uses that return point.
  * A RESTAURANT'S WORLD is flat and empty. The first player to arrive triggers a volume that
    pastes the dressed room (restaurant.py) -- which carries all its own systems, so there is
    nothing else to set up. The world is removed once it has been empty a little while.
  * HQ is built the same way: pasted when the first player arrives.
"""
import glob
import json
import os

import blocks
import clock
import content
import layouts
import pack
import restaurant
from systems import franchise, records
import settings
import volumes as v

NS = settings.NAMESPACE
HQ = f"{NS}_HQ"
# Where a room or HQ is pasted in its own world: its floor at AT, and the ground it brought
# (and a border's underside, layouts.BORDER_BELOW deep) below -- above the world's bottom.
AT = (32, 32, 32)
FRONT = (16.0, 2.0, -4.0)    # a restaurant's arrival, relative to its room: in front of it
# Feet on top of the arrival block. The room is pasted only once a player is in the world, so
# over a void there is nothing under them for a moment: arrive standing, not dropping in.
STAND = 1.0
ARRIVAL_CATCH = (1.0, 3.0)   # seconds after arriving that a player is put back on the arrival
PORTAL_LOOK = {"model": "Blocks/Miscellaneous/Platform_Magic_Exit.blockymodel",
               "texture": "Blocks/Miscellaneous/Platform_Magic_Blue2.png",
               "icon": "Icons/ItemsGenerated/Portal_Return.png"}


def load():
    return json.load(open(os.path.join(settings.CONTENT, "world", "world.json")))


# THE GROUND a world stands on (world.json "ground"): grass to the horizon, or nothing at all
# -- the room floats in the sky (the game's own Void generator: no blocks, only sky).
GROUNDS = {"flat": {"Type": "Flat", "Layers": [{"From": 0, "To": 1, "BlockType": "Soil_Grass"}]},
           # TINT: the colour grass (and anything else tinted by its chunk) takes. Void's is
           # none -- black -- so a border's grass came out black; this is Flat's own default.
           "void": {"Type": "Void", "Tint": "#5b9e28"}}


def _instance(name, spawn, volumes_, comment, clock_on, ground, weather=None, keep_key=None,
              empty_after=20.0):
    """`empty_after`: seconds empty before the world is removed; None: never removed."""
    pack.write(pack.out("Instances", name, "instance.bson"), {
        "$Comment": comment, "Version": 2,
        "WorldGen": GROUNDS[ground],
        # world.json "weather": one shipped weather, held for good (no rain rolling in).
        **({"ForcedWeather": weather} if weather else {}),
        "SpawnProvider": {"Id": "Global", "SpawnPoint": {
            "X": spawn[0], "Y": spawn[1], "Z": spawn[2], "Pitch": 0.0, "Yaw": 0.0, "Roll": 0.0}},
        "GameMode": "Adventure", "GameTime": "0001-01-01T12:00:00Z", "IsGameTimePaused": True,
        **(clock.WORLD_TIME if clock_on else {}),
        "IsSpawningNPC": False, "IsSpawnMarkersEnabled": False, "IsBlockSpawnersEnabled": False,
        "DeleteOnRemove": True, "DeleteOnUniverseStart": True,
        "Plugin": {"Instance": dict(
            {"RemovalConditions": ([] if empty_after is None else
                                   [{"Type": "WorldEmpty", "TimeoutSeconds": empty_after}])},
            **({"InstanceKey": keep_key} if keep_key else {}))}})
    pack.write(pack.out("Instances", name, "resources", "TriggerVolumeData.json"),
               {"Volumes": {f"5b1ce000-0000-4000-8000-{i:012d}": vol
                            for i, vol in enumerate(volumes_, start=1)}})


def _border(world, r=None):
    """The border prefab for a world (world.json "border", a restaurant may override; "none"
    for none): written once, returned with its ring width. (None, 0) when there is none."""
    bid = (r or {}).get("border", world.get("border"))
    if not bid or bid == "none":
        return None, 0
    folder = os.path.join(settings.CONTENT, "layouts", bid)
    meta = json.load(open(os.path.join(folder, "layout.json")))
    if meta.get("kind") != "border":
        raise SystemExit(f"world.json: border '{bid}' is not a border plot's layout")
    name = f"{NS}_Border_" + "_".join(p.capitalize() for p in bid.split("_"))
    room = json.load(open(os.path.join(folder, "room.prefab.json")))
    room["blocks"] = [layouts.barrier(b) for b in room["blocks"]]
    pack.write(pack.out("Prefabs", f"{name}.prefab.json"),
               dict(room, entities=[], **{"$Comment": f"Border: {meta['name']}. "
                                                      f"See build/world.py."}))
    return name, meta["ring"]


def _paste_on_arrival(name, prefab, text, border=(None, 0), welcome=None, spawn=None,
                      on_arrive=None):
    """A volume that pastes `prefab` at AT the first time a player is in the world -- and
    its BORDER round it, after (the border's hole is the room's plot). `spawn`: where every
    arriving player is put back, a moment after arriving. `text`: a chat line
    then (None: none). `welcome` (title, subtitle): shown to EVERY player as they arrive --
    ENTER is the arriving player's own event, so the title reaches them."""
    effect = f"{name}_Arrival"
    rules = v.Entries()
    if spawn:
        # BACK ON THE ARRIVAL SPOT, a moment after arriving: the first player lands before
        # the room is pasted, and an arrival up a tree left them falling to the ground. Every
        # arriving player is put back on it (harmless when the room was already there).
        rules.add(3, [], [{"Type": "Teleport", "Event": "ENTER", "Delay": d, "ResetVelocity": True,
                           "Position": {"X": float(spawn[0]), "Y": float(spawn[1]),
                                        "Z": float(spawn[2])}} for d in ARRIVAL_CATCH])
    if on_arrive:
        # Root interactions run on each arriving player: their bests (systems/records.py),
        # their franchise pick reset (systems/franchise.py).
        rules.add(4, [], [{"Type": "RunRootInteraction", "Event": "ENTER", "RootInteraction": r,
                           "Delay": 2.0} for r in ([on_arrive] if isinstance(on_arrive, str)
                                                   else on_arrive)])
    if welcome:
        rules.add(2, [], [v.title(f"kk.world.{name.lower()}.title", welcome[0],
                                  f"kk.world.{name.lower()}.title.sub", welcome[1],
                                  event="ENTER", seconds=5.0)])
    rules.add(1, [{"Type": "TagCondition", "Event": "ENTER", "Source": "Self", "TagKey": "built",
                   "Comparison": "Exactly", "TagValue": "0"}],
              # The ROOM first -- it holds the arrival spot -- then the border (scenery).
              [{"Type": "PastePrefab", "Event": "ENTER", "Prefab": prefab,
                "Origin": "WorldAbsolute",
                "Position": {"X": float(AT[0]), "Y": float(AT[1]), "Z": float(AT[2])},
                "ShowParticles": False},
               {"Type": "ModifyTags", "Event": "ENTER", "Operation": "Set", "TagKey": "built",
                "TagValue": "1"},
              ] + ([{"Type": "PastePrefab", "Event": "ENTER", "Prefab": border[0],
                     "Origin": "WorldAbsolute",
                     "Position": {"X": float(AT[0] - border[1]), "Y": float(AT[1]),
                                  "Z": float(AT[2] - border[1])},
                     "ShowParticles": False}] if border[0] else [])
              + ([v.say(f"kk.world.{name.lower()}", text, event="ENTER")] if text else []))
    rules.write(effect, "Pastes the room when the first player arrives. See build/world.py.")
    return v.volume(f"{name}_arrival", effect, {"built": "0"})


def _instance_name(r):
    return f"{NS}_R_" + "_".join(p.capitalize() for p in r["id"].split("_"))


PLACEHOLDER = f"{NS}_Portal_Placeholder"


def _placeholder_portal():
    """A portal that looks the part and goes nowhere: for the hq spike, to see every portal
    slot filled while lining them up."""
    block = dict(blocks.block_for(PORTAL_LOOK), Material="Solid", HitboxType="Pad_Portal",
                 InteractionHint=blocks.hint(PLACEHOLDER, "Portal slot - no restaurant yet",
                                             keyed=False),
                 Interactions={"Use": blocks.NOOP})
    blocks.item(PLACEHOLDER, "Portal (placeholder)", PORTAL_LOOK["icon"], block,
                "A stand-in portal for the hq spike. See build/world.py.")


def register_layouts(world):
    """Every restaurant LAYOUT not yet in world.json is added to it, on the next free portal,
    with the first theme and the standard rules -- and world.json is written back, so it can
    be renamed, re-themed or moved to another portal there. Border and HQ layouts are not
    restaurants. Returns notes for the build report."""
    notes = []
    listed = {r["layout"] for r in world["restaurants"]}
    taken = {r["portal"] for r in world["restaurants"]}
    theme = sorted(os.listdir(os.path.join(settings.CONTENT, "themes")))[0]
    for meta_path in sorted(glob.glob(os.path.join(settings.CONTENT, "layouts", "*", "layout.json"))):
        meta = json.load(open(meta_path))
        lid = meta["id"]
        if lid in listed or lid == world["hq"] or meta.get("kind") == "border" or lid.startswith("_"):
            continue
        free = next((n for n in range(1, layouts.PORTALS + 1) if n not in taken), None)
        if free is None:
            notes.append(f"layout {lid} isn't in world.json: every HQ portal is taken")
            continue
        world["restaurants"].append({"id": lid, "name": meta["name"], "theme": theme,
                                     "layout": lid, "rules": "standard", "portal": free})
        taken.add(free)
        notes.append(f"added '{meta['name']}' ({lid}) to world.json on portal {free}")
    if any(n.startswith("added") for n in notes):
        path = os.path.join(settings.CONTENT, "world", "world.json")
        with open(path, "w") as fh:
            json.dump(world, fh, indent=2)
            fh.write("\n")
    return notes


def build(debug=True, fill_portals=False):
    """`fill_portals`: every portal slot gets a portal -- a placeholder where no restaurant
    is hung (the hq spike: `python3 deploy.py hq`)."""
    if fill_portals:
        _placeholder_portal()
    world = load()
    notes = register_layouts(world)
    portal_of, practice_rooms = {}, set()
    for r in world["restaurants"]:
        model = content.load(r["theme"], r["rules"])
        room, problems, info = restaurant.build(model, r["layout"], debug=debug,
                                                exit_on_lose=True, label=r["name"])
        notes += [f"{r['name']}: {p}" for p in problems]
        inst = _instance_name(r)
        prefab = f"{inst}_Room"
        pack.write(pack.out("Prefabs", f"{prefab}.prefab.json"),
                   dict(room, **{"$Comment": f"{r['name']}: {info['name']} in {r['theme']}, "
                                             f"{r['rules']} rules. See build/world.py."}))
        if info["arrival"]:
            ax, ay, az = info["arrival"]
            spawn = (AT[0] + ax + 0.5, AT[1] + ay + STAND, AT[2] + az + 0.5)
        else:
            notes.append(f"{r['name']}: no arrival slot -- players arrive in front of the room")
            spawn = (AT[0] + FRONT[0], AT[1] + FRONT[1], AT[2] + FRONT[2])
        # A title for each player as they arrive (their own event, so it reaches them), not
        # a chat line: the restaurant's name, and the rules it plays under.
        rules_name = model["rules"].get("name", r["rules"])
        if info.get("practice"):
            # A PRACTICE room: nothing counts, so no best to show and no pick to reset.
            practice_rooms.add(r["layout"])
            arrive = _paste_on_arrival(inst, prefab, None, _border(world, r),
                                       welcome=(f"Welcome to {r['name']}",
                                                "Practice - guests come by themselves, nothing counts"),
                                       spawn=spawn)
        else:
            arrive = _paste_on_arrival(inst, prefab, None, _border(world, r),
                                       welcome=(f"Welcome to {r['name']}", f"{rules_name} rules"),
                                       spawn=spawn,
                                       on_arrive=[records.show(model, r["layout"], r["name"]),
                                                  model["franchise"]["reset"]])
        _instance(inst, spawn, [arrive],
                  f"The restaurant '{r['name']}'. See build/world.py.", clock_on=True,
                  ground=r.get("ground", world.get("ground", "flat")),
                  weather=r.get("weather", world.get("weather")))
        portal_of[r["portal"]] = (r, inst)

    # HQ: its layout with the HQ slots swapped: portals on the floor above their slots,
    # the arrival marked by where players spawn.
    meta = json.load(open(os.path.join(settings.CONTENT, "layouts", world["hq"], "layout.json")))
    room = json.load(open(os.path.join(settings.CONTENT, "layouts", world["hq"], "room.prefab.json")))
    out, arrival, portal_at = [], None, {}
    # THE FRANCHISE STOREROOM (systems/franchise.py): each shelf slot the HQ layout holds
    # becomes that item's shelf, with the item on it, and gets a volume of its own.
    hq_model = (content.load(world["restaurants"][0]["theme"], world["restaurants"][0]["rules"])
                if world["restaurants"] else None)
    shelves, shelf_keys = {}, set()
    if hq_model:
        fr_roots = franchise.build(hq_model)
        shelves = {layouts.slot_id(f"shelf_{k}"): (k, blk)
                   for k, blk in franchise.shelf_blocks(hq_model).items()}
    for b in room["blocks"]:
        name = b["name"]
        if name in shelves:
            key, (shelf, top) = shelves[name]
            out += [dict(b, name=shelf), {"x": b["x"], "y": b["y"] + 1, "z": b["z"], "name": top}]
            shelf_keys.add(key)
            continue
        if name == layouts.slot_id("arrival"):
            arrival = (b["x"], b["y"], b["z"])
            out.append(dict(b, name=layouts.floor_at(room["blocks"], b["x"], b["y"], b["z"])))
        elif name.startswith(layouts.slot_id("portal_")[:-1]):
            n = int(name.rsplit("_", 1)[1])
            out.append(dict(b, name=layouts.floor_at(room["blocks"], b["x"], b["y"], b["z"])))
            # A fence joining up to the pad beside it swallowed the pad (seen in game): say so.
            if any(c["name"].startswith(("Wood_", "Metal_", "Rock_")) and "Fence" in c["name"]
                   and (c["x"] - b["x"], c["y"] - b["y"] - 1, c["z"] - b["z"]) in
                   ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1))
                   for c in room["blocks"]):
                notes.append(f"HQ: portal slot {n} has a fence right beside it -- the fence can "
                             f"hide the portal; keep it a block clear")
            if n in portal_of:
                out.append({"x": b["x"], "y": b["y"] + 1, "z": b["z"], "name": f"{NS}_Portal_{n}"})
                portal_at[n] = (b["x"], b["y"] + 1, b["z"])
            elif fill_portals:
                out.append({"x": b["x"], "y": b["y"] + 1, "z": b["z"], "name": PLACEHOLDER})
            else:
                notes.append(f"HQ: portal slot {n} has no restaurant in world.json")
        else:
            out.append(layouts.barrier(b))
    for n in portal_of:
        if not any(b["name"] == f"{NS}_Portal_{n}" for b in out):
            notes.append(f"HQ: no portal slot {n} for '{portal_of[n][0]['name']}'")
    if arrival is None:
        notes.append("HQ: no arrival slot -- players arrive at the plot's front")
        arrival = (16, 0, 2)
    # THE PORTALS: one block per restaurant, stepped on to go. Each remembers where its
    # players come back to -- the ARRIVAL, where HQ's own spawn is: a return point is the
    # portal block (its hitbox middle) plus PositionOffset, so each portal's offset is the
    # way from it to the arrival.
    for n, (r, inst) in portal_of.items():
        key = f"{NS}_Portal_{n}"
        px, py, pz = portal_at.get(n, arrival)
        back = {"X": float(arrival[0] - px), "Y": 0.1, "Z": float(arrival[2] - pz)}
        block = dict(blocks.block_for(PORTAL_LOOK), Material="Solid", HitboxType="Pad_Portal",
                     AmbientSoundEventId="SFX_Portal_Neutral",
                     InteractionHint=blocks.hint(key, f"{r['name']} - step on to play", keyed=False),
                     Interactions={"CollisionEnter": {"Interactions": [{
                         "Type": "TeleportInstance", "InstanceName": inst,
                         "OriginSource": "Block", "PositionOffset": back,
                         "Rotation": {"Pitch": 0.0, "Yaw": 0.0, "Roll": 0.0},
                         "PersonalReturnPoint": True, "CloseOnBlockRemove": False,
                         "Next": {"Type": "Simple", "Effects": {
                             "LocalSoundEventId": "SFX_Portal_Neutral_Teleport_Local"}}}]}})
        blocks.item(key, f"Portal: {r['name']}", PORTAL_LOOK["icon"], block,
                    f"HQ portal to {r['name']}. See build/world.py.")
    pack.write(pack.out("Prefabs", f"{HQ}_Room.prefab.json"),
               dict(room, blocks=out, entities=[], fluids=[],
                    **{"$Comment": f"HQ: {meta['name']}. See build/world.py."}))
    spawn = (AT[0] + arrival[0] + 0.5, AT[1] + arrival[1] + STAND, AT[2] + arrival[2] + 0.5)
    real = [(r["layout"], r["name"]) for r in world["restaurants"]
            if r["layout"] not in practice_rooms]
    best = records.show_all(hq_model, real) if real else None
    # The shelves' volumes, over HQ's room: one each (a shelf's rules are its own).
    hq_box = ((AT[0] - 8, AT[1] - 16, AT[2] - 8), (AT[0] + 48, AT[1] + 48, AT[2] + 48))
    shelf_volumes = [v.volume(f"shelf_{k}", franchise.shelf_volume(hq_model, k, fr_roots),
                              {"took": "0"}, box=hq_box) for k in sorted(shelf_keys)]
    _instance(HQ, spawn, [_paste_on_arrival(HQ, f"{HQ}_Room", None, _border(world),
                                            welcome=("Welcome to Kweetchen Kaos",
                                                     "Step on a portal to play"),
                                            spawn=spawn, on_arrive=best)] + shelf_volumes,
              "HQ: where runs start. One shared world. See build/world.py.", clock_on=False,
              ground=world.get("ground", "flat"), weather=world.get("weather"),
              # NEVER REMOVED: a run's players come back to it. With an "empty" timeout it was
              # removed the moment the last player stepped through a portal, and losing then
              # sent everyone to the default world instead.
              keep_key=HQ.lower(), empty_after=None)
    pack.say("commands.kk.hq.desc", "Go to Kweetchen Kaos HQ")
    pack.write(pack.out("MacroCommands", "KKHq.json"), {
        "$Comment": "Go to HQ. See build/world.py.", "Name": "kk hq",
        "Description": "server.commands.kk.hq.desc",
        "Commands": [f"instances spawn {HQ}", "wait 4", "gamemode adventure"]})
    return [f"{r['name']} on portal {n}: {r['layout']} in {r['theme']}, {r['rules']} rules"
            for n, (r, _) in sorted(portal_of.items())], notes
