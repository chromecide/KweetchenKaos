"""
WHAT THE PADS CAN CARRY, read from the content. Infrastructure: both the pad system (which
shows and sells them) and the shift (which announces them) need the same list, and a
system may not import another -- so the list lives here.

    catalogue(model)   what can be offered (rules offers.json): stations -- plain, or already
                       upgraded -- and the chair, each with the item it gives, price, weights
    crates(model)      every crate a delivery can bring (plain crates)

A station's placeable block is its own id -- the rule every station system keeps
(systems/__init__.py) -- so a bought station is `game_id(prefix, station id)`.
"""
import settings


FIXTURES = {"chair": "Chair", "mat": "Mat", "mat_rubber": "Rubber mat"}


def catalogue(model):
    """Every offer: a STATION (a plain one, or one already upgraded -- a dishwasher, a fast
    stove) or a FIXTURE (a chair). Each shows on its pad as a blueprint; buying it gives the
    block the station's own system says you place (a rack's is its count, Rack_6, not
    "Rack")."""
    import systems
    prefix, items, st = model["theme"]["prefix"], model["items"], model["stations"]
    fixtures = model["fixtures"]["looks"]
    out = []
    for o in model["rules"]["offers"]["catalogue"]:
        if "station" in o:
            key = o["station"]
            out.append(dict(o, key=key, label=st[key]["label"],
                            item=systems.for_station(model, key).free_block(model, key),
                            look=st[key]["look"]))
        else:
            key = o["fixture"]
            if key not in FIXTURES:
                raise ValueError(f"offers.json: no fixture '{key}' can be offered "
                                 f"({', '.join(FIXTURES)})")
            # A chair places its own table when it's put down (seating.py), as when moved;
            # a mat goes down clean (hazards.py).
            out.append(dict(o, key=key, label=FIXTURES[key],
                            item=settings.game_id(prefix, "mat_1" if key == "mat" else key),
                            look=fixtures[key]))
    return out


def crates(model):
    return [sid for sid, s in model["stations"].items()
            if s["role"] == "crate" and not s.get("upgrade_of")]


def pad_numbers(model):
    return sorted(int(n) for n in model["rules"]["offers"]["pads"])
