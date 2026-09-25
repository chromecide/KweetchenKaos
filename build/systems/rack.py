"""
THE RACK SYSTEM: where clean plates are kept.

    press a rack                         ->  you take a clean plate (if it has one)
    press a rack holding a clean plate   ->  it goes back in (if there's room)
    look at a rack                       ->  it says how many it holds

Ported from the POC's plate rack (proven). THE COUNT IS THE BLOCK: one block per count,
0..capacity, so each rack keeps its own -- run one dry and you walk to another, and two
players at two racks never share a number. The top block has no "put back", so capacity
grows sideways: more racks, not bigger ones. Only the block type carries a hint, so the
look-at count exists because the count is a block.

NO LOCK. In the POC one press both put a plate back and took it out again: the put-back
emptied the hand at once, and the take-out, checked next, saw empty hands. Here "take"
requires NOT holding a plate and runs BEFORE "put back" (rules run in number order), so a
press is one or the other. Nothing destroys a plate, so there is no restock: plates are
finite, and the rack a layout places starts with the theme's `start` count.
"""
import blocks
import settings
import volumes as v

ROLES = ("rack",)


def ids(model, station_id):
    prefix = model["theme"]["prefix"]
    gid = lambda local: settings.game_id(prefix, local)
    return {"holding": lambda n: gid(f"{station_id}_{n}"), "effect": gid(f"{station_id}_system")}


def free_block(model, station_id):
    """The rack as a layout or a purchase gives it: with the theme's starting plates."""
    return ids(model, station_id)["holding"](model["stations"][station_id].get("start", 0))


def layout(model, station_id):
    return [(0, free_block(model, station_id))]


def build(model, station_id, debug=True):
    st = model["stations"][station_id]
    b = ids(model, station_id)
    cap, look, words = st["capacity"], st["look"], st["words"]
    plate = model["items"][model["vessel"]["clean"]["id"]]["game_id"]
    note = f"{st['label']}. See build/systems/rack.py."
    for n in range(cap + 1):
        text = (words["empty"] if n == 0 else words["full"] if n == cap else words["free"])
        # Every count is movable: a carried rack keeps its plates (the block IS the count).
        blocks.station_block(b["holding"](n), f"{st['label']} ({n})", look,
                             text.format(n=n, s="" if n == 1 else "s"), note, movable=True)

    rules = v.Entries()
    rep = lambda key, text: v.report(f"kk.{station_id}.{key}", f"[{station_id}] {text}", debug,
                                     to_log=False)
    # TAKE first (see the top of this file).
    for n in range(1, cap + 1):
        rules.add(100 + n, [v.at([b["holding"](n)]), v.not_holding(plate)],
                  [v.give(plate), v.cell([b["holding"](n)], b["holding"](n - 1)), v.sound(1.1)]
                  + rep(f"take.{n}", f"a plate taken - {n - 1} left"))
    for n in range(0, cap):
        rules.add(200 + n, [v.at([b["holding"](n)]), v.holding(plate)],
                  [v.cell([b["holding"](n)], b["holding"](n + 1)), v.sound(0.9)]
                  + rep(f"back.{n}", f"a plate put back - {n + 1} now"))
    rules.write(b["effect"], f"The {st['label'].lower()}: take and put back clean plates. "
                             f"See build/systems/rack.py.")
    return b["effect"]
