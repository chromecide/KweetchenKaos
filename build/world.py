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
PICK_MAX = 40                # rooms a random pick can choose among (_paste_on_arrival)
PORTAL_LOOK = layouts.PORTAL_LOOK


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
                      on_arrive=None, choices=None, debug=False):
    """A volume that pastes a room at AT the first time a player is in the world -- and
    its BORDER round it, after (the border's hole is the room's plot). `spawn`: where every
    arriving player is put back, a moment after arriving. `text`: a chat line
    then (None: none). `welcome` (title, subtitle): shown to EVERY player as they arrive --
    ENTER is the arriving player's own event, so the title reaches them.

    `choices`: A RANDOM ROOM instead of `prefab` -- [{"prefab", "spawn", "welcome", "label"}],
    one picked as the world is made (a fair pick: each in turn at 1/(choices left), the
    first that lands pastes and stops the pick). The pick is kept (`pick` = its number, 1 up),
    so every later arrival is put on THAT room's arrival spot and shown its welcome."""
    if choices is None:
        choices = [{"prefab": prefab, "spawn": spawn, "welcome": welcome, "label": name}]
    if len(choices) > PICK_MAX:
        raise SystemExit(f"{name}: {len(choices)} rooms to pick from -- at most {PICK_MAX}")
    effect = f"{name}_Arrival"
    tag = lambda key, value: {"Type": "ModifyTags", "Event": "ENTER", "Operation": "Set",
                              "TagKey": key, "TagValue": str(value)}
    has = lambda key, value: {"Type": "TagCondition", "Event": "ENTER", "Source": "Self",
                              "TagKey": key, "Comparison": "Exactly", "TagValue": str(value)}
    rules = v.Entries()
    # THE FIRST ARRIVAL makes the room: marks it built, and starts the pick.
    rules.add(1, [has("built", 0)], [tag("built", 1), tag("going", 1)])
    for k, c in enumerate(choices):
        left = len(choices) - k
        chance = ([] if left == 1 else
                  [{"Type": "RandomChanceCondition", "Event": "ENTER", "Chance": round(1.0 / left, 4)}])
        # The ROOM first -- it holds the arrival spot -- then the border (scenery).
        rules.add(10 + k, [has("going", 1)] + chance,
                  [{"Type": "PastePrefab", "Event": "ENTER", "Prefab": c["prefab"],
                    "Origin": "WorldAbsolute",
                    "Position": {"X": float(AT[0]), "Y": float(AT[1]), "Z": float(AT[2])},
                    "ShowParticles": False},
                   tag("pick", k + 1), tag("going", 0)]
                  + ([{"Type": "PastePrefab", "Event": "ENTER", "Prefab": border[0],
                       "Origin": "WorldAbsolute",
                       "Position": {"X": float(AT[0] - border[1]), "Y": float(AT[1]),
                                    "Z": float(AT[2] - border[1])},
                       "ShowParticles": False}] if border[0] else [])
                  + ([v.say(f"kk.world.{name.lower()}", text, event="ENTER")] if text else [])
                  + v.report(f"kk.world.{name.lower()}.pick.{k + 1}",
                             f"[world] {name}: picked {c['label']} ({k + 1} of {len(choices)})",
                             debug, event="ENTER"))
        # EVERY ARRIVAL, on the picked room: its welcome, and back on its arrival spot a
        # moment after arriving -- the first player lands before the room is pasted, and an
        # arrival up a tree left them falling to the ground (harmless once it's there).
        effects = []
        if c.get("welcome"):
            key = f"kk.world.{name.lower()}.title" + (f".{k + 1}" if len(choices) > 1 else "")
            effects.append(v.title(key, c["welcome"][0], f"{key}.sub", c["welcome"][1],
                                   event="ENTER", seconds=5.0))
        if c.get("spawn"):
            sx, sy, sz = c["spawn"]
            effects += [{"Type": "Teleport", "Event": "ENTER", "Delay": d, "ResetVelocity": True,
                         "Position": {"X": float(sx), "Y": float(sy), "Z": float(sz)}}
                        for d in ARRIVAL_CATCH]
        if effects:
            rules.add(10 + PICK_MAX + k, [has("pick", k + 1)], effects)
    if on_arrive:
        # Root interactions run on each arriving player: their bests (systems/records.py),
        # their franchise pick reset (systems/franchise.py).
        rules.add(10 + 2 * PICK_MAX, [],
                  [{"Type": "RunRootInteraction", "Event": "ENTER", "RootInteraction": r,
                    "Delay": 2.0} for r in ([on_arrive] if isinstance(on_arrive, str)
                                            else on_arrive)])
    rules.write(effect, "Pastes the room when the first player arrives. See build/world.py.")
    return v.volume(f"{name}_arrival", effect, {"built": "0", "going": "0", "pick": "0"})


def _instance_name(kind):
    return f"{NS}_R_{kind.capitalize()}"


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


def pools(world):
    """{portal kind: [layout id]}: which rooms each HQ portal picks from -- a room's size
    slot says (layouts.SIZES), a practice room goes to the practice portal. Every layout but
    the border and HQ is a room. Returns (pools, notes)."""
    out, notes = {k: [] for k in layouts.PORTALS}, []
    for meta_path in sorted(glob.glob(os.path.join(settings.CONTENT, "layouts", "*", "layout.json"))):
        meta = json.load(open(meta_path))
        lid = meta["id"]
        if lid == world["hq"] or meta.get("kind") == "border" or lid.startswith("_"):
            continue
        _, room = restaurant.load_layout(lid)
        have = {n for n in (restaurant._slot(b["name"]) for b in room["blocks"]) if n}
        # layout.json "size" stands in for the slot (a room built before size slots).
        sizes = [s for s in layouts.SIZES if f"size_{s}" in have] or \
            ([meta["size"]] if meta.get("size") in layouts.SIZES else [])
        if "practice_call" in have:
            out["practice"].append(lid)
        elif len(sizes) == 1:
            out[sizes[0]].append(lid)
        elif sizes:
            notes.append(f"layout {lid} has more than one size slot ({', '.join(sizes)}) -- "
                         f"left out; keep one")
        else:
            notes.append(f"layout {lid} has no size slot -- no portal picks it")
    return out, notes


def build(debug=True, fill_portals=False):
    """`fill_portals`: every portal slot gets a portal -- a placeholder where no room is
    there to pick yet (the hq spike: `python3 deploy.py hq`)."""
    if fill_portals:
        _placeholder_portal()
    world = load()
    rooms, notes = pools(world)
    portal_of = {}
    for kind in layouts.PORTALS:
        if world["portals"][kind].get("enabled", True) is False:
            notes.append(f"the {kind} portal is switched off (world.json)")
            continue
        if not rooms[kind]:
            notes.append(f"the {kind} portal has no rooms yet"
                         + ("" if kind == "practice" else f" (a room with a size_{kind} slot)"))
            continue
        p = world["portals"][kind]
        inst = _instance_name(kind)
        choices, model = [], None
        for lid in rooms[kind]:
            # A fresh model per room: a build fills it in for the room it dresses.
            model = content.load(p["theme"], p["rules"])
            room, problems, info = restaurant.build(model, lid, debug=debug, exit_on_lose=True,
                                                    label=p["name"], record_as=kind)
            notes += [f"{p['name']} / {info['name']}: {x}" for x in problems]
            prefab = f"{inst}_Room_" + "_".join(w.capitalize() for w in lid.split("_"))
            pack.write(pack.out("Prefabs", f"{prefab}.prefab.json"),
                       dict(room, **{"$Comment": f"{p['name']}: {info['name']} in {p['theme']}, "
                                                 f"{p['rules']} rules. See build/world.py."}))
            if info["arrival"]:
                ax, ay, az = info["arrival"]
                spawn = (AT[0] + ax + 0.5, AT[1] + ay + STAND, AT[2] + az + 0.5)
            else:
                notes.append(f"{info['name']}: no arrival slot -- players arrive in front of the room")
                spawn = (AT[0] + FRONT[0], AT[1] + FRONT[1], AT[2] + FRONT[2])
            # A title for each player as they arrive (their own event, so it reaches them):
            # the room picked, and the rules it plays under.
            sub = ("Practice - guests come by themselves, nothing counts" if kind == "practice"
                   else f"{p['name']} - {model['rules'].get('name', p['rules'])} rules")
            choices.append({"prefab": prefab, "spawn": spawn, "label": info["name"],
                            "welcome": (f"Welcome to {info['name']}", sub)})
        # A PRACTICE room: nothing counts, so no best to show and no pick to reset.
        on_arrive = (None if kind == "practice" else
                     [records.show(model, kind, p["name"]), model["franchise"]["reset"]])
        arrive = _paste_on_arrival(inst, None, None, _border(world, p), choices=choices,
                                   on_arrive=on_arrive, debug=debug)
        _instance(inst, choices[0]["spawn"], [arrive],
                  f"HQ's {p['name']} portal: one of {len(choices)} rooms. See build/world.py.",
                  clock_on=True, ground=p.get("ground", world.get("ground", "flat")),
                  weather=p.get("weather", world.get("weather")))
        portal_of[kind] = (p, inst, rooms[kind])

    # HQ: its layout with the HQ slots swapped: a portal in each portal slot's place,
    # the arrival marked by where players spawn.
    meta = json.load(open(os.path.join(settings.CONTENT, "layouts", world["hq"], "layout.json")))
    room = json.load(open(os.path.join(settings.CONTENT, "layouts", world["hq"], "room.prefab.json")))
    out, arrival, portal_at = [], None, {}
    # THE FRANCHISE STOREROOM (systems/franchise.py): each shelf slot the HQ layout holds
    # becomes that item's shelf, with the item on it, and gets a volume of its own.
    first = world["portals"][layouts.SIZES[0]]
    hq_model = content.load(first["theme"], first["rules"])
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
        elif name.startswith(layouts.slot_id("portal_x")[:-1]):
            if "filler" in b:
                # The pad is 3 x 3: a save lists its 8 filler cells too. Only the pad's own
                # cell becomes the portal (which brings its own fillers).
                continue
            n = name[len(layouts.slot_id("portal_x")) - 1:].lower()
            # The slot IS the pad (layouts.PORTAL_LOOK): the portal takes its place.
            # A fence joining up to the pad beside it swallowed the pad (seen in game): say so.
            if any(c["name"].startswith(("Wood_", "Metal_", "Rock_")) and "Fence" in c["name"]
                   and (c["x"] - b["x"], c["y"] - b["y"], c["z"] - b["z"]) in
                   ((1, 0, 0), (-1, 0, 0), (0, 0, 1), (0, 0, -1))
                   for c in room["blocks"]):
                notes.append(f"HQ: portal slot {n} has a fence right beside it -- the fence can "
                             f"hide the portal; keep it a block clear")
            if n in portal_of:
                out.append({"x": b["x"], "y": b["y"], "z": b["z"], "name": f"{NS}_Portal_{n.capitalize()}"})
                portal_at[n] = (b["x"], b["y"], b["z"])
            elif fill_portals:
                out.append({"x": b["x"], "y": b["y"], "z": b["z"], "name": PLACEHOLDER})
            else:
                pass                  # said above: no rooms for it yet
        else:
            out.append(layouts.barrier(b))
    for n in portal_of:
        if not any(b["name"] == f"{NS}_Portal_{n.capitalize()}" for b in out):
            notes.append(f"HQ: no {n} portal slot")
    if arrival is None:
        notes.append("HQ: no arrival slot -- players arrive at the plot's front")
        arrival = (16, 0, 2)
    # THE PORTALS: one block per kind, stepped on to go. Each remembers where its
    # players come back to -- the ARRIVAL, where HQ's own spawn is: a return point is the
    # portal block (its hitbox middle) plus PositionOffset, so each portal's offset is the
    # way from it to the arrival.
    for n, (r, inst, _) in portal_of.items():
        key = f"{NS}_Portal_{n.capitalize()}"
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
    real = [(k, portal_of[k][0]["name"]) for k in layouts.SIZES if k in portal_of]
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
    return [f"{r['name']} portal: {len(lids)} room(s) ({', '.join(lids)}) in {r['theme']}, "
            f"{r['rules']} rules" for n, (r, _, lids) in portal_of.items()], notes
