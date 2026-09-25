"""
THE RACK SYSTEM: where clean plates are kept -- one sits on top whenever it has any.

    a rack with plates shows one on top
    press the plate (or the rack)          ->  you take a clean plate; the last one leaves
                                               the top empty
    press the rack (or the plate on it)
    holding a clean plate                  ->  it goes back in; an empty rack shows a plate
                                               on top again
    look at the rack                       ->  it says how many it holds

THE COUNT IS THE BLOCK (ported from the POC's proven rack): one rack block per count,
0..capacity, so each rack keeps its own -- run one dry and you walk to another. The full
block has no "put back", so capacity grows sideways: more racks. Only a block type carries a
hint, so the look-at count exists because the count is a block. The plate on top is only a
picture of "has plates", like a crate's ingredient; it's there from 1 plate up.

A LOCK, and it is needed here (unlike the counter). The same rack block both gives a plate
and takes one, and one press was doing both: "take" handed a plate into the empty hand at
once, the rack's own block only changes at the end of the tick, so "put back" -- checked next
-- saw a rack with room and a plate in hand, and took it straight back (the count went down,
no plate). Order can't fix it either way round. So, as the POC found: the rule that fires
claims `busy` (a TAG, which is live for every later rule of the same press), the others
require it clear, and the last rule clears it -- nothing is left claimed.

A rack is MOVABLE at any count: the carried block is the count, so it keeps its plates. Put
down with plates, it shows its plate again; picked up, the plate goes with it.

Plates are finite -- nothing destroys one -- so there is no restock: a layout's rack starts
with the theme's `start` count.
"""
import blocks
import settings
import volumes as v

ROLES = ("rack",)
TAGS = {"busy": "0"}     # the lock; a volume must carry a tag before a rule can read it


def ids(model, station_id):
    prefix = model["theme"]["prefix"]
    gid = lambda local: settings.game_id(prefix, local)
    return {"holding": lambda n: gid(f"{station_id}_{n}"), "top": gid(f"{station_id}_plate"),
            "effect": gid(f"{station_id}_system")}


def free_block(model, station_id):
    """The rack as a layout or a purchase gives it: with the theme's starting plates."""
    return ids(model, station_id)["holding"](model["stations"][station_id].get("start", 0))


def layout(model, station_id):
    b, start = ids(model, station_id), model["stations"][station_id].get("start", 0)
    return [(0, b["holding"](start))] + ([(1, b["top"])] if start > 0 else [])


def build(model, station_id, debug=True):
    st = model["stations"][station_id]
    b = ids(model, station_id)
    cap, look, words = st["capacity"], st["look"], st["words"]
    clean = model["items"][model["vessel"]["clean"]["id"]]
    plate = clean["game_id"]
    note = f"{st['label']}. See build/systems/rack.py."
    racks = [b["holding"](n) for n in range(cap + 1)]
    for n in range(cap + 1):
        text = (words["empty"] if n == 0 else words["full"] if n == cap else words["free"])
        blocks.station_block(racks[n], f"{st['label']} ({n})", look,
                             text.format(n=n, s="" if n == 1 else "s"), note, movable=True)
    blocks.display_block(b["top"], f"{clean['label']} (on the rack)", clean["look"],
                         words.get("on_top", "Press to take a clean plate"), note)

    rules = v.Entries()
    rep = lambda key, text, event="BLOCK_USED": v.report(
        f"kk.{station_id}.{key}", f"[{station_id}] {text}", debug, event=event)

    free = {"Type": "TagCondition", "Event": "BLOCK_USED", "Source": "Self", "TagKey": "busy",
            "Comparison": "Exactly", "TagValue": "0"}
    claim = {"Type": "ModifyTags", "Event": "BLOCK_USED", "Operation": "Set", "TagKey": "busy",
             "TagValue": "1"}

    def either(n, conditions, effects, extra):
        """Pressing the rack (top above it), or the plate on top (rack below). `effects`
        take the rack's height (0 or -1 from the pressed block)."""
        where = [(0.0, [v.at([racks[n]])]), (-1.0, [v.at([b["top"]]), v.at([racks[n]], dy=-1)])]
        for dy, at in where:
            rules.add(len(rules.conditions) + 100, at + conditions + [free],
                      [claim] + [e(dy) for e in effects] + list(extra))

    # TAKE first (see the top of this file).
    for n in range(1, cap + 1):
        effects = [lambda dy, n=n: v.cell([racks[n]], racks[n - 1], dy=dy)]
        if n == 1:
            effects.append(lambda dy: v.cell([b["top"]], "Empty", dy=dy + 1))
        either(n, [v.not_holding(plate)], effects,
               [v.give(plate), v.sound(1.1)] + rep(f"take.{n}", f"a plate taken - {n - 1} left"))
    # PUT BACK.
    for n in range(0, cap):
        effects = [lambda dy, n=n: v.cell([racks[n]], racks[n + 1], dy=dy)]
        if n == 0:
            effects.append(lambda dy: v.place(b["top"], dy=dy + 1))
        either(n, [v.holding(plate)], effects,
               [v.sound(0.9)] + rep(f"back.{n}", f"a plate put back - {n + 1} now"))
    # The press is over: release the lock, whatever happened. LAST, and on any rack press.
    rules.add(4999, [v.at(racks + [b["top"]])],
              [{"Type": "ModifyTags", "Event": "BLOCK_USED", "Operation": "Set",
                "TagKey": "busy", "TagValue": "0"}])
    # CARRIED: put down with plates, it shows its plate; picked up, the plate goes with it.
    rules.add(5000, [v.at(racks[1:], event="BLOCK_PLACED")],
              [v.place(b["top"], event="BLOCK_PLACED")])
    # A TURNED rack (look "turn"): put down, the client picks a rotation from how the player
    # faces -- so it is swapped for itself with the look's turn set. Every other swap keeps
    # the rotation it has.
    if look.get("turn"):
        rules.add(5002, [v.at(racks, event="BLOCK_PLACED")],
                  [dict(v.cell([r], r, dy=0.0, event="BLOCK_PLACED"), **blocks.turn_fields(look))
                   for r in racks])
    rules.add(5001, [v.at(racks, event="BLOCK_BROKEN")],
              [v.cell([b["top"]], "Empty", dy=1, event="BLOCK_BROKEN")])
    rules.write(b["effect"], f"The {st['label'].lower()}: clean plates, one on show. "
                             f"See build/systems/rack.py.")
    return b["effect"]
