"""
THE PAD SYSTEM: numbered pads out front where, between days, things arrive for the kitchen.

    the shift says PLACE     ->  each pad live today picks an OFFER (a station or an upgrade
                                 kit), weighted for the stage of the run, and shows it
    press an offer           ->  enough in the purse: you get it, the price comes off;
                                 not enough: the shift says so, nothing changes
    the shift DELIVERS       ->  a crate appears on one pad, free: press to take it
    the shift shows a CARD   ->  a recipe card on one pad: press to choose it -- the dish
                                 goes on the menu, and the shift delivers any crates it needs
    the shift says CLEAR     ->  unbought offers and unchosen cards vanish. Deliveries stay
                                 until taken: they are yours.

Ported from the POC's offer system (proven by its economy probe): the purse read and paid
from the shift's volume through signals.py; "not enough" checked BEFORE "buy" (buying takes
the money at once, and a later check would see the reduced purse); a per-pad `sold` tag
so one offer never sells twice in a tick; the weighted pick as a chain -- option k with
chance w_k / (weight still left), stopped by an instant `picked` tag. Deliveries and cards
are new: a pad holding a delivery is `busy`, and offers never land on it.

PADS ARE A FIXTURE: each carries its own volume (inline rules -- a pasted volume can't
resolve an effect asset), and a pad placed by hand gets it pasted on. The pad system knows
no shift: it reads the purse and the day through signals.py, and hears PLACE, CLEAR,
DELIVER and CARD on the pad channels.

What it can carry (the catalogue, the crates) comes from build/offers.py, shared with the
shift.
"""
import copy

import blocks
import offers
import pack
import settings
import signals
import volumes as v

FIXTURE = "pads"


def ids(model):
    prefix = model["theme"]["prefix"]
    gid = lambda local: settings.game_id(prefix, local)
    return {"pad": lambda n: gid(f"pad_{n}"),
            "offer": lambda key: gid(f"pad_offer_{key}"),
            "delivery": lambda crate: gid(f"pad_delivery_{crate}"),
            "card": lambda dish: gid(f"pad_card_{dish}"),
            "prefab": lambda n: gid(f"pad_{n}_volume"),
            "world_effect": gid("pads_system")}


def numbers(model):
    return offers.pad_numbers(model)


catalogue, crates = offers.catalogue, offers.crates


def _rules(model, n, debug):
    p, items, st = ids(model), model["items"], model["stations"]
    words = model["fixtures"]["words"]
    stages = model["rules"]["stages"]
    first = model["rules"]["offers"]["pads"][str(n)]
    cat = catalogue(model)
    offers = [p["offer"](c["key"]) for c in cat]
    deliveries = [p["delivery"](c) for c in crates(model)]
    cards = [p["card"](d) for d in model["dishes"]]
    rules = v.Entries()
    tag = lambda event, key, value, cmp="Exactly": {
        "Type": "TagCondition", "Event": event, "Source": "Self", "TagKey": key,
        "Comparison": cmp, "TagValue": str(value)}
    set_ = lambda event, key, value: {"Type": "ModifyTags", "Event": event, "Operation": "Set",
                                      "TagKey": key, "TagValue": str(value)}
    put = lambda block: {"Type": "PlaceBlock", "Event": "SIGNAL_RECEIVED", "BlockType": block,
                         "Position": {"X": 0.0, "Y": 1.0, "Z": 0.0}, "Origin": "VolumeOrigin",
                         "ReplaceMode": "Always"}
    rep = lambda key, text, event: v.report(f"kk.pad{n}.{key}", f"[pad {n}] {text}", debug,
                                            event=event, to_log=False)
    num = iter(range(100, 100000))

    # PLACE: a weighted chain per stage of the run. Not on a pad holding a delivery.
    for stage in stages:
        weighted = [(c, c["weights"][stage["id"]]) for c in cat if c["weights"][stage["id"]] > 0]
        left = sum(w for _, w in weighted)
        for c, w in weighted:
            chance = w / left
            left -= w
            rules.add(next(num), [
                signals.heard(signals.OFFERS, signals.PLACE),
                signals.shift_reads("SIGNAL_RECEIVED", signals.DAY, "AtLeast",
                                    max(stage["from"], first)),
                signals.shift_reads("SIGNAL_RECEIVED", signals.DAY, "AtMost", stage["to"]),
                tag("SIGNAL_RECEIVED", "picked", 0), tag("SIGNAL_RECEIVED", "busy", 0),
                {"Type": "RandomChanceCondition", "Event": "SIGNAL_RECEIVED",
                 "Chance": round(min(1.0, chance), 4)}],
                [set_("SIGNAL_RECEIVED", "picked", 1), set_("SIGNAL_RECEIVED", "sold", 0),
                 put(p["offer"](c["key"]))]
                + rep(f"offer.{c['key']}", f"offers: {c['label']} ({c['price']} coins)",
                      "SIGNAL_RECEIVED"))
    rules.add(800, [signals.heard(signals.OFFERS, signals.PLACE)],
              [set_("SIGNAL_RECEIVED", "picked", 0)])
    # CLEAR: unbought offers and unchosen cards go; deliveries stay.
    rules.add(810, [signals.heard(signals.OFFERS, signals.CLEAR)],
              [{"Type": "ReplaceBlockType", "Event": "SIGNAL_RECEIVED",
                "FromBlockTypes": offers + cards, "ToBlockType": "Empty"}])
    # DELIVER a crate, or show a CARD -- addressed to this pad by number.
    for c in crates(model):
        rules.add(next(num), [signals.heard(signals.DELIVER, c)],
                  [put(p["delivery"](c)), set_("SIGNAL_RECEIVED", "busy", 1)]
                  + rep(f"delivered.{c}", f"delivered: {st[c]['label'].lower()}",
                        "SIGNAL_RECEIVED"))
    for d in model["dishes"]:
        rules.add(next(num), [signals.heard(signals.CARD, d)],
                  [put(p["card"](d)), set_("SIGNAL_RECEIVED", "sold", 0)])

    # BUY -- "not enough" FIRST (see the top of this file).
    for c in cat:
        o = p["offer"](c["key"])
        rules.add(next(num), [v.at([o]), tag("BLOCK_USED", "sold", 0),
                              signals.shift_reads("BLOCK_USED", signals.MONEY, "AtMost",
                                                  c["price"] - 1)],
                  [signals.from_volume("BLOCK_USED", signals.SHORT, c["key"])])
    for c in cat:
        o = p["offer"](c["key"])
        rules.add(next(num), [v.at([o]), tag("BLOCK_USED", "sold", 0),
                              signals.shift_reads("BLOCK_USED", signals.MONEY, "AtLeast",
                                                  c["price"])],
                  [set_("BLOCK_USED", "sold", 1),
                   signals.shift_changes("BLOCK_USED", signals.MONEY, "Increment", -c["price"]),
                   v.give(c["item"]), v.cell([o], "Empty"),
                   signals.from_volume("BLOCK_USED", signals.BOUGHT, c["key"]), v.sound(1.3)])
    # TAKE a delivery: it's free.
    for c in crates(model):
        d = p["delivery"](c)
        rules.add(next(num), [v.at([d])],
                  [set_("BLOCK_USED", "busy", 0), v.give(settings.game_id(
                      model["theme"]["prefix"], c)), v.cell([d], "Empty"), v.sound(1.2)]
                  + rep(f"taken.{c}", f"{st[c]['label'].lower()} taken", "BLOCK_USED"))
    # CHOOSE a card: the shift puts the dish on the menu and delivers what it needs.
    for dish in model["dishes"]:
        cd = p["card"](dish)
        rules.add(next(num), [v.at([cd]), tag("BLOCK_USED", "sold", 0)],
                  [set_("BLOCK_USED", "sold", 1),
                   signals.from_volume("BLOCK_USED", signals.CHOSE, dish), v.sound(1.4)])

    rules.add(990, [v.at([p["pad"](m) for m in numbers(model)], event="BLOCK_BROKEN")],
              [{"Type": "DeleteVolume", "Event": "BLOCK_BROKEN"}])
    return rules


def _entity(model, n, debug):
    rules = _rules(model, n, debug)
    return {"Components": {
        "TriggerVolume": {"Shape": {"Type": "Box", "Min": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                                    "Max": {"X": 1.0, "Y": 2.0, "Z": 1.0}},
                          "Conditions": rules.conditions, "Effects": rules.effects,
                          "Enabled": True, "TargetTypes": ["Player"],
                          "Tags": {signals.PADS_KEY: signals.PADS_VALUE,
                                   signals.PAD_KEY: str(n), "picked": "0", "sold": "1",
                                   "busy": "0"},
                          "Name": f"pad_{n}", "PrefabIndex": 0},
        "Transform": {"Position": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                      "Rotation": {"Pitch": 0.0, "Yaw": 0.0, "Roll": 0.0}}}}


_entities = {}


def build(model, debug=True):
    p, looks, words = ids(model), model["fixtures"]["looks"], model["fixtures"]["words"]
    note = "An offer pad. See build/systems/pads.py."
    pad = looks["pad"]
    for n in numbers(model):
        first = model["rules"]["offers"]["pads"][str(n)]
        blocks.station_block(p["pad"](n), f"Offer pad {n}", pad,
                             words["pad"].format(n=n) + f" - offers from day {first}", note,
                             tint=pad.get("tint"), use=False)
    for c in catalogue(model):
        text = words["offer"].format(label=c["label"], price=c["price"])
        if c["cube"]:
            blocks.station_block(p["offer"](c["key"]), f"{c['label']} (on offer)", c["look"],
                                 text, note, tint=c["look"].get("tint"))
        else:
            blocks.display_block(p["offer"](c["key"]), f"{c['label']} (on offer)", c["look"],
                                 text, note)
    for c in crates(model):
        s = model["stations"][c]
        icon = model["items"][s["ingredient"]]["look"]["icon"]
        blocks.station_block(p["delivery"](c), f"{s['label']} (delivered)",
                             dict(s["look"], icon=icon),
                             words["delivery"].format(label=s["label"]), note)
    for d, dish in model["dishes"].items():
        blocks.display_block(p["card"](d), f"Recipe card: {dish['label']}", looks["card"],
                             words["card"].format(label=dish["label"]), note)

    world = v.Entries()
    for n in numbers(model):
        _entities[n] = _entity(model, n, debug)
        pack.write(pack.out("Prefabs", f"{p['prefab'](n)}.prefab.json"), {
            "$Comment": f"Offer pad {n}'s own volume. See build/systems/pads.py.",
            "version": 8, "blockIdVersion": 11, "anchorX": 0, "anchorY": 0, "anchorZ": 0,
            "blocks": [], "entities": [_entities[n]]})
        world.add(10 + n, [v.at([p["pad"](n)], event="BLOCK_PLACED")],
                  [{"Type": "PastePrefab", "Event": "BLOCK_PLACED", "Prefab": p["prefab"](n),
                    "Origin": "Event", "ShowParticles": False}])
    world.write(p["world_effect"], "Offer pads placed by hand get their volumes. "
                                   "See build/systems/pads.py.")


def pad_entity(n, x, y, z):
    e = copy.deepcopy(_entities[n])
    e["Components"]["Transform"]["Position"] = {"X": float(x), "Y": float(y), "Z": float(z)}
    return e


def volumes(model):
    return [v.volume("pads", ids(model)["world_effect"], {"pads": "system"})]
