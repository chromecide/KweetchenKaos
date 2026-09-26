"""
WHAT THE PADS CAN CARRY, read from the content. Infrastructure: both the pad system (which
shows and sells them) and the shift (which announces them) need the same list, and a
system may not import another -- so the list lives here.

    catalogue(model)   what can be offered: stations and upgrade kits (rules offers.json),
                       each with the item it gives, its price, weights and look
    crates(model)      every crate a delivery can bring (plain crates; upgrades come by kit)

A station's placeable block is its own id -- the rule every station system keeps
(systems/__init__.py) -- so a bought station is `game_id(prefix, station id)`.
"""
import settings


def catalogue(model):
    """Every offer: a STATION (a plain one, or one already upgraded -- a dishwasher, a fast
    stove), an upgrade KIT, or a FIXTURE (a chair). The item given is the block the station's
    own system says you place (a rack's is its count, Rack_6, not "Rack")."""
    import systems
    prefix, items, st = model["theme"]["prefix"], model["items"], model["stations"]
    fixtures = model["fixtures"]["looks"]
    out = []
    for o in model["rules"]["offers"]["catalogue"]:
        if "station" in o:
            key = o["station"]
            out.append(dict(o, key=key, label=st[key]["label"],
                            item=systems.for_station(model, key).free_block(model, key),
                            look=st[key]["look"], cube=True))
        elif "kit" in o:
            kit = items[f"{o['kit']}_kit"]
            # Its own key: an upgraded station can be on offer ready-made as well as by kit.
            out.append(dict(o, key=f"{o['kit']}_kit", label=kit["label"], item=kit["game_id"],
                            look=kit["look"], cube=False))
        else:
            key = o["fixture"]
            if key != "chair":
                raise ValueError(f"offers.json: no fixture '{key}' can be offered (only chair)")
            # A chair places its own table when it's put down (seating.py), as when moved.
            out.append(dict(o, key=key, label="Chair", item=settings.game_id(prefix, "chair"),
                            look=fixtures["chair"], cube=False))
    return out


def crates(model):
    return [sid for sid, s in model["stations"].items()
            if s["role"] == "crate" and not s.get("upgrade_of")]


def pad_numbers(model):
    return sorted(int(n) for n in model["rules"]["offers"]["pads"])
