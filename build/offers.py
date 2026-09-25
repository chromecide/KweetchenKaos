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
    prefix, items, st = model["theme"]["prefix"], model["items"], model["stations"]
    out = []
    for o in model["rules"]["offers"]["catalogue"]:
        if "station" in o:
            key = o["station"]
            out.append(dict(o, key=key, label=st[key]["label"],
                            item=settings.game_id(prefix, key), look=st[key]["look"], cube=True))
        else:
            key = o["kit"]
            kit = items[f"{key}_kit"]
            out.append(dict(o, key=key, label=kit["label"], item=kit["game_id"],
                            look=kit["look"], cube=False))
    return out


def crates(model):
    return [sid for sid, s in model["stations"].items()
            if s["role"] == "crate" and not s.get("upgrade_of")]


def pad_numbers(model):
    return sorted(int(n) for n in model["rules"]["offers"]["pads"])
