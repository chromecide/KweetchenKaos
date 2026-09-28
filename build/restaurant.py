"""
A RESTAURANT: a layout's room, dressed in a theme, running under a rules set -- ONE prefab
that carries everything it needs. Paste it anywhere and it works.

    layout (content/layouts/<id>/)   the room as built, with SLOT blocks
    theme                            what each slot becomes
    rules                            how the run plays

The room's SLOTS are swapped for the theme's blocks:

    station slot (a role)   the theme's station for that role
    chair slot              a chair facing the same way, and its table in front
    queue spot / pool       the queue's blocks, each with its own volume
    offer pad               the pad, with its own volume
    sign                    the shift's open sign

and THE ROOM CARRIES ITS OWN VOLUMES: every system -- the stations, the queue, its patience
area, seating, the shift and its service lock, the pads -- goes into the prefab as a volume
entity, positioned relative to the room. Nothing lives at fixed world coordinates, so there
is nothing to line up: wherever the room is pasted (a spike, an HQ plot), its systems come
with it and sit on it.

TWO THINGS THAT MAKE THAT WORK:
  * A pasted volume's rules are INLINE. A volume that names an effect file resolves it only
    when the world loads, so one pasted later would do nothing. The systems still write their
    effect files (the spike worlds mount those); here the same rules are read back and put
    inside each volume.
  * Each volume's POSITION is the middle of the room. A signal's reach -- 64 blocks -- is
    measured from the sending volume's position, so every system reaches the whole room.

The queue's patience area is the queue ZONE: drawn in the layout, or worked out round the
spots and pool if not. A slot the theme has nothing for, or a room missing something the
rules need, is reported -- the room still builds, so you can see it.
"""
import json
import os

import blocks
import guests
import layouts
import pack
import settings
import signals
import systems
import volumes as v
from systems import franchise, hazards, moods, pads, queue, records, seating, shift
from systems import practice as practice_system

ZONE_MARGIN = 1          # a worked-out queue zone reaches this far round the spots and pool
ROOM_SIZE, ROOM_MARGIN = 32, 4


def load_layout(layout_id):
    root = os.path.join(settings.CONTENT, "layouts", layout_id)
    meta = json.load(open(os.path.join(root, "layout.json")))
    room = json.load(open(os.path.join(root, "room.prefab.json")))
    return meta, room


def _slot(name):
    """K2_Slot_Station_Heat -> "station_heat"; anything else -> None."""
    pre = f"{settings.NAMESPACE}_Slot_"
    return name[len(pre):].lower() if name.startswith(pre) else None


def _carried(name, effect, tags, box, targets=("Player",), extra=None):
    """A system's volume as a room entity: its rules read back from the effect file the
    system wrote, inline; positioned at the middle of `box` (room coordinates). Tracks
    `targets` only if its rules need it (volumes.targets_for)."""
    rules = v.effect_rules(effect)
    (x0, y0, z0), (x1, y1, z1) = box
    cx, cy, cz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
    tv = {"Shape": {"Type": "Box", "Min": {"X": x0 - cx, "Y": y0 - cy, "Z": z0 - cz},
                    "Max": {"X": x1 - cx, "Y": y1 - cy, "Z": z1 - cz}},
          "Conditions": rules["Conditions"], "Effects": rules["Effects"],
          "Enabled": True, "TargetTypes": v.targets_for(rules, targets), "Tags": dict(tags),
          "Name": name, "PrefabIndex": 0, **(extra or {})}
    return {"Components": {
        "TriggerVolume": tv,
        "Transform": {"Position": {"X": cx, "Y": cy, "Z": cz},
                      "Rotation": {"Pitch": 0.0, "Yaw": 0.0, "Roll": 0.0}}}}


def build(model, layout_id, debug=True, patience=None, exit_on_lose=False, label=None,
          record_as=None):
    """(room prefab dict, problems, info): the layout dressed, carrying its systems.
    `record_as`: whose best a run here counts toward (records.py) -- an HQ portal's, so
    every room it picks shares one; the layout's own without."""
    meta, room = load_layout(layout_id)
    problems = []
    # A PRACTICE ROOM (systems/practice.py) is one with a "call a guest" slot: no shift, pads,
    # records or franchise -- guests come by themselves, every one in the practice mood, the
    # stations locked in place, and its crates laid out by crate slots (nothing delivers them).
    practice = any(_slot(b["name"]) == "practice_call" for b in room["blocks"])
    # Built as part of a run: stations that behave differently between days (crates) read
    # the shift. A practice room has no days: its crates are always open.
    model["in_run"] = not practice
    if practice:
        model["mood_chances"] = {"practice": 1.0}
    # Hazards are on in every restaurant: a station that causes one (a sink's spill) needs
    # to know before it's built.
    model["hazards"] = True
    by_role = {st["role"]: sid for sid, st in model["stations"].items()
               if not st.get("upgrade_of") and st["role"] != "crate"}
    turns = [rot for rot, _ in seating.TABLE_AT]

    roles = guests.roles(model)
    q = queue.ids(model)
    # The moods first: the queue rolls them and the guests read them (systems/moods.py).
    # None in play yet in a restaurant -- customer cards will bring them.
    moods.build(model)
    built_q = queue.build(model, roles, debug, patience=patience)
    seating_effect = seating.build(model, debug)
    guests.build(model, debug)
    v.take_companions()           # nothing left over from another build
    roles_by = {e["serves"]: guests.role_id(model, e) for e in model["menu"]}
    shift_tags, shift_pacing = None, []
    if practice:
        practice_system.build(model, roles_by, debug)
    else:
        shift_tags = shift.build(model, roles_by, debug, exit_on_lose=exit_on_lose)
        shift_pacing = v.take_companions()        # its per-day pacing volumes, its tokens
        # Each player's best here, remembered on the player (systems/records.py): its
        # recorder is a companion beside the shift.
        records.build(model, record_as or layout_id, label or meta["name"])
        shift_pacing += v.take_companions()
        # The franchise (systems/franchise.py) before the pads: they read its cards.
        franchise.build(model)
        pads.build(model, debug)
    v.take_companions()           # nothing left over from another build
    hazards_effect = hazards.build(model, debug)
    hazard_drops = v.take_companions()        # its drops, each in a volume of its own

    # `built` is the room as the creator left it; `out_blocks` what the slots became. One
    # cell holds ONE block, or the game refuses the whole prefab ("Block is already present
    # in column") -- so what the slots make wins, and each block it displaces is noted: a
    # chair's table put where a rug lay, say.
    built, out_blocks, entities, used, queue_cells, pad_numbers = [], [], [], set(), [], set()
    crate_cells = set()
    arrival = None
    for b in room["blocks"]:
        name = _slot(b["name"])
        if name is None:
            built.append(layouts.barrier(b))
            continue
        at = lambda block, dx=0, dz=0, dy=0, rotation=None: dict(
            {"x": b["x"] + dx, "y": b["y"] + dy, "z": b["z"] + dz, "name": block},
            **({"rotation": rotation} if rotation is not None else {}))
        if name.startswith("station_"):
            role = name[len("station_"):]
            if practice and role == "call":
                continue        # a practice room has no booking desk (no days to call into)
            sid = by_role.get(role)
            if sid is None:
                problems.append(f"a {role} slot at ({b['x']}, {b['y']}, {b['z']}), but the "
                                f"theme has no {role} station")
                continue
            used.add(sid)
            turn = blocks.turn_index(model["stations"][sid]["look"])
            for dy, block in systems.for_station(model, sid).layout(model, sid):
                # The station itself stands turned if its look says so; what sits on it doesn't.
                out_blocks.append(at(block, dy=dy, rotation=turn if dy == 0 else None))
        elif name == "chair":
            facing = turns[b.get("rotation", 0) % 4]
            for dx, dz, block, turn in seating.layout(model, facing):
                out_blocks.append(at(block, dx, dz, rotation=turn))
        elif name.startswith("queue_"):
            out_blocks.append(at(q["free"](int(name.split("_")[1]))))
            entities.append(queue.spot_entity(b["x"], b["y"], b["z"]))
            queue_cells.append((b["x"], b["y"], b["z"]))
        elif name == "pool":
            out_blocks.append(at(q["pool"]))
            entities.append(queue.pool_entity(b["x"], b["y"], b["z"]))
            queue_cells.append((b["x"], b["y"], b["z"]))
        elif name.startswith("pad_") and not practice:        # no offers in practice
            n = int(name.split("_")[1])
            pad_numbers.add(n)
            out_blocks.append(at(pads.ids(model)["pad"](n)))
            entities.append(pads.pad_entity(n, b["x"], b["y"], b["z"]))
        elif name == "sign":
            # A practice room's sign turns its guests on and off (systems/practice.py).
            out_blocks.append(at(practice_system.ids(model)["sign"] if practice
                                 else shift.ids(model)["sign"]))
        elif name.startswith("crate_"):
            # A CRATE SLOT (one per ingredient): the crate, in a practice room -- a run's
            # crates are delivered, so a normal room ignores them.
            sid = name
            if not practice:
                problems.append(f"a {sid} slot at ({b['x']}, {b['y']}, {b['z']}): crate slots "
                                f"are for practice rooms (a run delivers its crates) -- left out")
            elif sid not in model["stations"]:
                problems.append(f"a {sid} slot, but the theme has no such crate")
            else:
                crate_cells.add(sid)
                for dy, block in systems.for_station(model, sid).layout(model, sid):
                    out_blocks.append(at(block, dy=dy))
        elif name == "practice_call":
            out_blocks.append(at(practice_system.ids(model)["call"]))
        elif name == "practice_any" or name.startswith("practice_dish_"):
            # THE RECIPE PICKER (practice rooms only).
            pi = practice_system.ids(model)
            d = name[len("practice_dish_"):]
            if not practice:
                problems.append(f"a {name} slot: the recipe picker is for practice rooms -- left out")
            elif name != "practice_any" and d not in model["dishes"]:
                problems.append(f"a {name} slot, but the theme has no dish '{d}'")
            else:
                out_blocks.append(at(pi["any"] if name == "practice_any" else pi["dish"](d)))
        elif name == "barrier":
            out_blocks.append(at(layouts.BARRIER))
        elif name == "arrival":
            arrival = (b["x"], b["y"], b["z"])
            out_blocks.append(at(layouts.floor_at(room["blocks"], b["x"], b["y"], b["z"])))
        elif name.startswith("size_"):
            # Which HQ portal picks this room (world.py reads it): nothing in game (air).
            pass

    for role, sid in by_role.items():
        if sid not in used and not (practice and role == "call"):
            problems.append(f"no {role} slot: the room has no "
                            f"{model['stations'][sid]['label'].lower()}")
    missing = set(pads.numbers(model)) - pad_numbers
    if missing and not practice:
        problems.append(f"no offer pad slot for pad(s) {sorted(missing)}")
    if practice:
        # Every crate the menu needs, since nothing will deliver one.
        needed = sorted({c for d in model["dishes"].values() for c in d["needs"]} - crate_cells)
        if needed:
            problems.append(f"practice room: no crate slot for {', '.join(needed)} -- dishes "
                            f"needing them can't be made")
    # The fixtures a run can't do without.
    names = [_slot(b["name"]) for b in room["blocks"]]
    if "chair" not in names:
        problems.append("no chair slots: guests will queue but have nowhere to sit")
    spots = {n for n in names if n and n.startswith("queue_")}
    if len(spots) < 4:
        problems.append(f"queue spots missing: {sorted({f'queue_{i}' for i in range(1, 5)} - spots)}")
    if "pool" not in names:
        problems.append("no queue pool slot: guests have nowhere to arrive")
    if "sign" not in names:
        problems.append("no open sign slot: " + ("its guests can't be switched on" if practice
                                                 else "the day can't be opened"))

    # THE QUEUE ZONE, in room coordinates: drawn, or worked out round the spots and pool.
    zone = meta.get("zones", {}).get("queue")
    if zone:
        p, sh = zone["position"], zone["shape"]
        area = tuple(tuple(p[k] + sh[side][k] for k in "XYZ") for side in ("Min", "Max"))
    elif queue_cells:
        xs, ys, zs = zip(*queue_cells)
        area = ((min(xs) - ZONE_MARGIN, min(ys) - 1, min(zs) - ZONE_MARGIN),
                (max(xs) + 1 + ZONE_MARGIN, max(ys) + 4, max(zs) + 1 + ZONE_MARGIN))
    else:
        problems.append("no queue spots, so no queue")
        area = None

    # THE ROOM'S OWN VOLUMES: every system over the room (its plot and a little round it),
    # as tall as the theme's rooms (layouts.room_height).
    box = ((-ROOM_MARGIN, -8, -ROOM_MARGIN),
           (ROOM_SIZE + ROOM_MARGIN, layouts.room_height(model) + 8, ROOM_SIZE + ROOM_MARGIN))
    crates = [sid for sid, st in model["stations"].items()
              if st["role"] == "crate" and not st.get("upgrade_of")]
    v.take_companions()           # nothing left over from another build
    for sid in sorted(used) + crates:
        effect = systems.for_station(model, sid).build(model, sid, debug)
        entities.append(_carried(f"station_{sid}", effect,
                                 systems.tags_for(model, sid, {"station": sid}), box))
        # Its companion volumes (volumes.companion): its hazard drops, each in its own.
        for n, (eff, tags) in enumerate(v.take_companions()):
            entities.append(_carried(f"station_{sid}_{n}", eff, tags, box))
    qi, si = queue.ids(model), shift.ids(model)
    entities.append(_carried("queue", qi["world_effect"], {"queue": "system"}, box))
    if area:
        entities.append(_carried("queue_area", qi["area_effect"],
                                 {"queuearea": "1", "qpatience": str(built_q["patience"])},
                                 area, targets=("Npc",)))
    entities.append(_carried("seating", seating_effect,
                             {"seating": "system", "refused": "0", "guestreset": "1"}, box))
    if practice:
        pi = practice_system.ids(model)
        entities.append(_carried("practice", pi["effect"], {"practice": "1", "focus": "0",
                                                                   "open": "0"}, box))
        # The lock, on for good: nothing picked up, broken, or carried out of practice.
        entities.append(_carried("practice_lock", pi["lock"], {"servicelock": "1"}, box,
                                 extra={"Enabled": True, "RulesActive": True,
                                        "Rules": [{"Type": "NoBuild"}, {"Type": "NoDestroy"}]}))
    else:
        entities.append(_carried("shift", si["effect"], shift_tags, box))
        for n, (eff, tags) in enumerate(shift_pacing):
            entities.append(_carried(f"shift_{n}", eff, tags, box))
        entities.append(_carried("shift_service_lock", si["lock"], {"servicelock": "1"}, box,
                                 extra={"Enabled": False, "RulesActive": True,
                                        "Rules": [{"Type": "NoBuild"}, {"Type": "NoDestroy"}]}))
        entities.append(_carried("pads", pads.ids(model)["world_effect"], {"pads": "system"}, box))
    entities.append(_carried("hazards", hazards_effect,
                             {signals.HAZARD_KEY: "system", **signals.RESET_TAGS}, box))
    for n, (eff, tags) in enumerate(hazard_drops):
        entities.append(_carried(f"hazards_{n}", eff, tags, box))

    taken = {(b["x"], b["y"], b["z"]) for b in out_blocks}
    for b in built:
        if (b["x"], b["y"], b["z"]) in taken:
            problems.append(f"{b['name']} at ({b['x']}, {b['y']}, {b['z']}) was replaced by "
                            f"what a slot makes there (a chair's table, or on top of a station)")
    out_blocks = [b for b in built if (b["x"], b["y"], b["z"]) not in taken] + out_blocks
    prefab = dict(room, blocks=out_blocks, entities=entities)
    return prefab, problems, {"name": meta["name"], "area": area, "arrival": arrival,
                              "practice": practice}
