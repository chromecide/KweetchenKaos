"""
THE BIN SYSTEM: throw food away. Plates are never lost.

    press a bin holding food                ->  it's gone
    press a bin holding a plated dish       ->  the food is gone; its DIRTY PLATE sits on
                                                the bin, and the bin is busy until you take it
    press the plate on the bin (or the bin) ->  you take the dirty plate; the bin is free
    press a bin holding a plate             ->  nothing: plates are never binned

What happens to each item is the item's own "bin" setting in the theme: destroy (the
default), refuse, or leaves <item> (plated dishes, made so when plating is built in).
Plates are finite -- nothing in the kitchen destroys one -- so a restaurant can't run out
by accident.
"""
import blocks
import settings
import volumes as v

ROLES = ("bin",)


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
    note = f"{label}. See build/systems/bin.py."

    destroy = [i for i, it in items.items() if it["bin"] == "destroy"]
    refuse = [i for i, it in items.items() if it["bin"] == "refuse"]
    leaves = {i: it["bin"]["leaves"] for i, it in items.items() if isinstance(it["bin"], dict)}

    blocks.station_block(b["free"], label, look, words["free"], note, tint=look.get("tint"))
    blocks.station_block(b["busy"], f"{label} (plate on it)", look, words["busy"], note,
                         tint=look.get("busy_tint"))
    left = list(dict.fromkeys(leaves.values()))
    for iid in left:
        blocks.display_block(b["on"](iid), f"{name(iid)} (on the {label.lower()})",
                             items[iid]["look"], words["on_top"].format(label=name(iid)), note)
    shown = [b["on"](i) for i in left]

    rules = v.Entries()
    rep = lambda key, text: v.report(f"kk.{station_id}.{key}", f"[{station_id}] {text}", debug)
    n = iter(range(100, 100000))

    for iid in destroy:
        rules.add(next(n), [v.at([b["free"]]), v.holding(game(iid))],
                  [v.sound(0.6)] + rep(f"gone.{iid}", f"{name(iid)} binned"))
    for iid, plate in leaves.items():
        rules.add(next(n), [v.at([b["free"]]), v.holding(game(iid))],
                  [v.cell([b["free"]], b["busy"]), v.place(b["on"](plate)), v.sound(0.6)]
                  + rep(f"left.{iid}", f"{name(iid)} binned - {name(plate).lower()} left on it"))
    if debug:
        for iid in refuse:
            rules.add(next(n), [v.at([b["free"]]), v.has(game(iid))],
                      rep(f"refused.{iid}", f"{name(iid)} can't be binned"))

    # TAKE the plate off: press it, or the busy bin under it.
    for iid in left:
        for dy, where in ((0.0, [v.at([b["on"](iid)]), v.at([b["busy"]], dy=-1)]),
                          (1.0, [v.at([b["busy"]]), v.at([b["on"](iid)], dy=1)])):
            rules.add(next(n), where,
                      [v.give(game(iid)), v.cell([b["on"](iid)], "Empty", dy=dy),
                       v.cell([b["busy"]], b["free"], dy=dy - 1), v.sound(1.1)]
                      + rep(f"take.{iid}", f"{name(iid)} taken - {label.lower()} free"))

    rules.add(90, [v.at(shown, event="BLOCK_BROKEN")],
              [v.cell([b["busy"]], b["free"], dy=-1, event="BLOCK_BROKEN")])
    rules.add(91, [v.at([b["free"], b["busy"]], event="BLOCK_BROKEN")],
              [v.cell(shown, "Empty", dy=1, event="BLOCK_BROKEN")])

    rules.write(b["effect"], f"The {label.lower()}: food goes, plates stay. "
                             f"See build/systems/bin.py.")
    return b["effect"]
