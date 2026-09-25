"""
A RESTAURANT: a layout's room, dressed in a theme, running under a rules set.

    layout (content/layouts/<id>/)   the room as built, with SLOT blocks
    theme                            what each slot becomes
    rules                            how the run plays

This takes the room and SWAPS EVERY SLOT for the theme's block, adding what goes with it:

    station slot (a role)   the theme's station for that role
    chair slot              a chair facing the same way, and its table in front
    queue spot / pool       the queue's blocks, each with its own volume
    offer pad               the pad, with its own volume
    sign                    the shift's open sign

and mounts every system over the room: the stations, the queue (its patience over the
queue ZONE -- drawn in the layout, or worked out from the spots and pool if not), seating,
the guests, the shift and the pads. What comes out is a room and a list of volumes; the
spike world pastes and mounts them today, HQ's plots will later.

A slot the theme has nothing for, or a room missing something the rules need (no stove,
no pads), is reported -- the room still builds, so you can see it.
"""
import json
import os

import guests
import settings
import systems
import volumes as v
from systems import pads, queue, seating, shift

ZONE_MARGIN = 1          # a worked-out queue zone reaches this far round the spots and pool


def load_layout(layout_id):
    root = os.path.join(settings.CONTENT, "layouts", layout_id)
    meta = json.load(open(os.path.join(root, "layout.json")))
    room = json.load(open(os.path.join(root, "room.prefab.json")))
    return meta, room


def _slot(name):
    """K2_Slot_Station_Heat -> "station_heat"; anything else -> None."""
    pre = f"{settings.NAMESPACE}_Slot_"
    return name[len(pre):].lower() if name.startswith(pre) else None


def build(model, layout_id, origin=(0, 0, 0), debug=True, patience=None):
    """(room prefab dict, volumes, problems) for the layout at world `origin`."""
    meta, room = load_layout(layout_id)
    ox, oy, oz = origin
    problems = []
    by_role = {st["role"]: sid for sid, st in model["stations"].items()
               if not st.get("upgrade_of") and st["role"] != "crate"}
    turns = [rot for rot, _ in seating.TABLE_AT]

    roles = guests.roles(model)
    q = queue.ids(model)
    built_q = queue.build(model, roles, debug, patience=patience)
    seating.build(model, debug)
    guests.build(model, debug)
    tags = shift.build(model, {e["serves"]: guests.role_id(model, e) for e in model["menu"]},
                       debug)
    pads.build(model, debug)

    out_blocks, entities, used_roles, queue_cells, pad_numbers = [], [], set(), [], set()
    for b in room["blocks"]:
        name = _slot(b["name"])
        if name is None:
            out_blocks.append(b)
            continue
        at = lambda block, dx=0, dz=0, dy=0, rotation=None: dict(
            {"x": b["x"] + dx, "y": b["y"] + dy, "z": b["z"] + dz, "name": block},
            **({"rotation": rotation} if rotation is not None else {}))
        # Entities in the room are placed relative to it (the paste adds its origin);
        # the queue zone is in world coordinates.
        wx, wy, wz = b["x"] + ox, b["y"] + oy, b["z"] + oz
        if name.startswith("station_"):
            role = name[len("station_"):]
            sid = by_role.get(role)
            if sid is None:
                problems.append(f"a {role} slot at ({b['x']}, {b['y']}, {b['z']}), but the "
                                f"theme has no {role} station")
                continue
            used_roles.add(sid)
            for dy, block in systems.for_station(model, sid).layout(model, sid):
                out_blocks.append(at(block, dy=dy))
        elif name == "chair":
            facing = turns[b.get("rotation", 0) % 4]
            for dx, dz, block, turn in seating.layout(model, facing):
                out_blocks.append(at(block, dx, dz, rotation=turn))
        elif name.startswith("queue_"):
            i = int(name.split("_")[1])
            out_blocks.append(at(q["free"](i)))
            entities.append(queue.spot_entity(b["x"], b["y"], b["z"]))
            queue_cells.append((wx, wy, wz))
        elif name == "pool":
            out_blocks.append(at(q["pool"]))
            entities.append(queue.pool_entity(b["x"], b["y"], b["z"]))
            queue_cells.append((wx, wy, wz))
        elif name.startswith("pad_"):
            n = int(name.split("_")[1])
            pad_numbers.add(n)
            out_blocks.append(at(pads.ids(model)["pad"](n)))
            entities.append(pads.pad_entity(n, b["x"], b["y"], b["z"]))
        elif name == "sign":
            out_blocks.append(at(shift.ids(model)["sign"]))

    for role, sid in by_role.items():
        if sid not in used_roles:
            problems.append(f"no {role} slot: the room has no {model['stations'][sid]['label'].lower()}")
    missing = set(pads.numbers(model)) - pad_numbers
    if missing:
        problems.append(f"no offer pad slot for pad(s) {sorted(missing)}")

    # THE QUEUE ZONE: drawn, or worked out round the spots and pool.
    zone = meta.get("zones", {}).get("queue")
    if zone:
        p, sh = zone["position"], zone["shape"]
        area = ((p["X"] + ox + sh["Min"]["X"], p["Y"] + oy + sh["Min"]["Y"], p["Z"] + oz + sh["Min"]["Z"]),
                (p["X"] + ox + sh["Max"]["X"], p["Y"] + oy + sh["Max"]["Y"], p["Z"] + oz + sh["Max"]["Z"]))
    elif queue_cells:
        xs, ys, zs = zip(*queue_cells)
        area = ((min(xs) - ZONE_MARGIN, min(ys) - 1, min(zs) - ZONE_MARGIN),
                (max(xs) + 1 + ZONE_MARGIN, max(ys) + 4, max(zs) + 1 + ZONE_MARGIN))
    else:
        problems.append("no queue spots, so no queue")
        area = ((0, 0, 0), (0, 0, 0))

    # Stations: every one the room uses, and every crate (deliveries bring them).
    mounted = list(used_roles) + [sid for sid, st in model["stations"].items()
                                  if st["role"] == "crate" and not st.get("upgrade_of")]
    volumes = [v.volume(f"restaurant_{sid}",
                        systems.for_station(model, sid).build(model, sid, debug), {"station": sid})
               for sid in mounted]
    volumes += queue.volumes(model, area, built_q["patience"]) + seating.volumes(model)
    volumes += shift.volumes(model, tags) + pads.volumes(model)

    prefab = dict(room, blocks=out_blocks, entities=entities)
    return prefab, volumes, problems, {"name": meta["name"], "area": area}
