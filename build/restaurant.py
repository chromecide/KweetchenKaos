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
import systems
from systems import pads, queue, seating, shift

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
    system wrote, inline; positioned at the middle of `box` (room coordinates)."""
    rules = json.load(open(pack.out("TriggerVolumes", "Effects", f"{effect}.json")))
    (x0, y0, z0), (x1, y1, z1) = box
    cx, cy, cz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
    tv = {"Shape": {"Type": "Box", "Min": {"X": x0 - cx, "Y": y0 - cy, "Z": z0 - cz},
                    "Max": {"X": x1 - cx, "Y": y1 - cy, "Z": z1 - cz}},
          "Conditions": rules["Conditions"], "Effects": rules["Effects"],
          "Enabled": True, "TargetTypes": list(targets), "Tags": dict(tags),
          "Name": name, "PrefabIndex": 0, **(extra or {})}
    return {"Components": {
        "TriggerVolume": tv,
        "Transform": {"Position": {"X": cx, "Y": cy, "Z": cz},
                      "Rotation": {"Pitch": 0.0, "Yaw": 0.0, "Roll": 0.0}}}}


def build(model, layout_id, debug=True, patience=None, exit_on_lose=False):
    """(room prefab dict, problems, info): the layout dressed, carrying its systems."""
    meta, room = load_layout(layout_id)
    problems = []
    # Built as part of a run: stations that behave differently between days (crates) read
    # the shift.
    model["in_run"] = True
    by_role = {st["role"]: sid for sid, st in model["stations"].items()
               if not st.get("upgrade_of") and st["role"] != "crate"}
    turns = [rot for rot, _ in seating.TABLE_AT]

    roles = guests.roles(model)
    q = queue.ids(model)
    built_q = queue.build(model, roles, debug, patience=patience)
    seating_effect = seating.build(model, debug)
    guests.build(model, debug)
    shift_tags = shift.build(model, {e["serves"]: guests.role_id(model, e) for e in model["menu"]},
                             debug, exit_on_lose=exit_on_lose)
    pads.build(model, debug)

    out_blocks, entities, used, queue_cells, pad_numbers = [], [], set(), [], set()
    arrival = None
    for b in room["blocks"]:
        name = _slot(b["name"])
        if name is None:
            out_blocks.append(b)
            continue
        at = lambda block, dx=0, dz=0, dy=0, rotation=None: dict(
            {"x": b["x"] + dx, "y": b["y"] + dy, "z": b["z"] + dz, "name": block},
            **({"rotation": rotation} if rotation is not None else {}))
        if name.startswith("station_"):
            role = name[len("station_"):]
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
        elif name.startswith("pad_"):
            n = int(name.split("_")[1])
            pad_numbers.add(n)
            out_blocks.append(at(pads.ids(model)["pad"](n)))
            entities.append(pads.pad_entity(n, b["x"], b["y"], b["z"]))
        elif name == "sign":
            out_blocks.append(at(shift.ids(model)["sign"]))
        elif name == "arrival":
            arrival = (b["x"], b["y"], b["z"])
            out_blocks.append(at(layouts.floor_at(room["blocks"], b["x"], b["y"], b["z"])))

    for role, sid in by_role.items():
        if sid not in used:
            problems.append(f"no {role} slot: the room has no "
                            f"{model['stations'][sid]['label'].lower()}")
    missing = set(pads.numbers(model)) - pad_numbers
    if missing:
        problems.append(f"no offer pad slot for pad(s) {sorted(missing)}")
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
        problems.append("no open sign slot: the day can't be opened")

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

    # THE ROOM'S OWN VOLUMES: every system over the room (its plot and a little round it).
    box = ((-ROOM_MARGIN, -8, -ROOM_MARGIN),
           (ROOM_SIZE + ROOM_MARGIN, 40, ROOM_SIZE + ROOM_MARGIN))
    crates = [sid for sid, st in model["stations"].items()
              if st["role"] == "crate" and not st.get("upgrade_of")]
    for sid in sorted(used) + crates:
        effect = systems.for_station(model, sid).build(model, sid, debug)
        entities.append(_carried(f"station_{sid}", effect,
                                 systems.tags_for(model, sid, {"station": sid}), box))
    qi, si = queue.ids(model), shift.ids(model)
    entities.append(_carried("queue", qi["world_effect"], {"queue": "system"}, box))
    if area:
        entities.append(_carried("queue_area", qi["area_effect"],
                                 {"queuearea": "1", "qpatience": str(built_q["patience"])},
                                 area, targets=("Npc",)))
    entities.append(_carried("seating", seating_effect,
                             {"seating": "system", "refused": "0", "guestreset": "1"}, box))
    entities.append(_carried("shift", si["effect"], shift_tags, box))
    entities.append(_carried("shift_service_lock", si["lock"], {"servicelock": "1"}, box,
                             extra={"Enabled": False, "RulesActive": True,
                                    "Rules": [{"Type": "NoBuild"}, {"Type": "NoDestroy"}]}))
    entities.append(_carried("pads", pads.ids(model)["world_effect"], {"pads": "system"}, box))

    prefab = dict(room, blocks=out_blocks, entities=entities)
    return prefab, problems, {"name": meta["name"], "area": area, "arrival": arrival}
