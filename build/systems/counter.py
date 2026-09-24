"""
THE COUNTER SYSTEM: any counter holds any one thing, and combines things the Plate Up way.

    press a free counter holding something   ->  it goes down on the counter
    press it (or what's on it) holding
    something that combines with it          ->  they combine; the result stays on the counter
    press it (or what's on it), holding
    nothing that combines with it            ->  you pick it up

Combining is how recipes are assembled AND how food is plated: dough + chopped filling
makes an unbaked pie; a clean plate + a cooked pie makes the served dish. The counter
knows none of that -- it reads the theme's combine steps for this station, and each works
both ways round (plate down and pie in hand, or pie down and plate in hand).

ANYTHING can sit on a counter: every item in the theme gets a picture block for it.

NO LOCK. v1 needed a busy tag, because pressing a counter with a pie on it while holding a
plate matched both "combine" and "pick up". Here "pick up" itself says "and you're not
holding anything that combines with this" (an item count of at most zero), so the two
can never both match. The pick-up rules also come BEFORE the combine rules: a combine
takes the held item at once, and a pick-up checked after it would see empty hands.

THE COUNTER HAS A BUSY STATE because a volume can't ask "is the cell above empty". A
replaced block lands at the end of the tick, so a put-down can't also be a pick-up.
"""
import blocks
import settings
import volumes as v

ROLES = ("combine",)


def ids(model, station_id):
    prefix = model["theme"]["prefix"]
    gid = lambda local: settings.game_id(prefix, local)
    return {"free": gid(station_id), "busy": gid(f"{station_id}_busy"),
            "on": lambda item: gid(f"{station_id}_on_{item}"),
            "effect": gid(f"{station_id}_system")}


def free_block(model, station_id):
    return ids(model, station_id)["free"]


def layout(model, station_id):
    return [(0, free_block(model, station_id))]


def build(model, station_id, debug=True):
    st, items = model["stations"][station_id], model["items"]
    b = ids(model, station_id)
    label, words, look = st["label"], st["words"], st["look"]
    name = lambda iid: items[iid]["label"]
    game = lambda iid: items[iid]["game_id"]
    note = f"{label}. See build/systems/counter.py."

    combines = [s for s in model["steps"]
                if s["type"] == "combine" and s["station"] == station_id]
    # Each combine both ways round: (on the counter, in hand, result).
    pairs = [(a, h, s["output"]) for s in combines
             for a, h in (tuple(s["inputs"]), tuple(reversed(s["inputs"])))]
    partners = {iid: [h for a, h, _ in pairs if a == iid] for iid in items}

    blocks.station_block(b["free"], label, look, words["free"], note)
    blocks.station_block(b["busy"], f"{label} (in use)", look, words["free"], note,
                         sides=look.get("busy_sides"))
    for iid, item in items.items():
        blocks.display_block(b["on"](iid), f"{name(iid)} (on the {label.lower()})",
                             item["look"], words["on_top"].format(label=name(iid)), note)
    shown = [b["on"](i) for i in items]

    rules = v.Entries()
    rep = lambda key, text: v.report(f"kk.{station_id}.{key}", f"[{station_id}] {text}", debug)
    n = iter(range(100, 100000))

    def either(on_top, conditions, effects, extra):
        """Pressing the counter, or what's on it. `effects` take the counter's height."""
        for dy, where in ((0.0, [v.at([b["busy"]]), v.at([on_top], dy=1)]),
                          (-1.0, [v.at([on_top]), v.at([b["busy"]], dy=-1)])):
            rules.add(next(n), where + conditions, [e(dy) for e in effects] + extra)

    # PUT DOWN, one rule per item.
    for iid in items:
        rules.add(next(n), [v.at([b["free"]]), v.holding(game(iid))],
                  [v.cell([b["free"]], b["busy"]), v.place(b["on"](iid)), v.sound(0.9)]
                  + rep(f"put.{iid}", f"{name(iid)} put down"))

    # PICK UP -- before the combines (see the top of this file).
    for iid in items:
        either(b["on"](iid),
               [v.not_holding(game(p)) for p in partners[iid]],
               [lambda dy, iid=iid: v.cell([b["on"](iid)], "Empty", dy=dy + 1),
                lambda dy: v.cell([b["busy"]], b["free"], dy=dy)],
               [v.give(game(iid)), v.sound(1.1)] + rep(f"take.{iid}", f"{name(iid)} picked up"))

    # COMBINE: what's on top becomes the result; the counter stays busy.
    for on, held, result in pairs:
        either(b["on"](on), [v.holding(game(held))],
               [lambda dy, on=on, result=result: v.cell([b["on"](on)], b["on"](result),
                                                        dy=dy + 1)],
               [v.sound(1.3)]
               + rep(f"combine.{on}.{held}", f"{name(on)} + {name(held)} -> {name(result)}"))

    # BREAKING: a picture broken frees its counter; a counter broken takes its picture.
    rules.add(90, [v.at(shown, event="BLOCK_BROKEN")],
              [v.cell([b["busy"]], b["free"], dy=-1, event="BLOCK_BROKEN")])
    rules.add(91, [v.at([b["free"], b["busy"]], event="BLOCK_BROKEN")],
              [v.cell(shown, "Empty", dy=1, event="BLOCK_BROKEN")])

    rules.write(b["effect"], f"The {label.lower()}: holds one thing, combines. "
                             f"See build/systems/counter.py.")
    return b["effect"]
