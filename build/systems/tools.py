"""
THE TOOL SYSTEM: a stand that keeps a tool -- the mop, for the hazards (systems/hazards.py).

    press the stand (or the tool on it)  ->  you take the tool; the stand is empty
    press the empty stand with the tool  ->  it goes back
    press the empty stand without it     ->  it says the tool is out

The tool on top is a picture (like the booking desk's book): it goes with the stand when the
stand is carried. Only a stand with its tool on it moves -- an empty one stays put, so the
tool always has somewhere to come back to.

A station file with role "tool" names the item it keeps ("holds") and how it shows on top
("on_top"). Every layout should have one (a "mop stand" slot): without it there's no mop, and
messes can't be cleaned.
"""
import blocks
import settings
import volumes as v

ROLES = ("tool",)


def ids(model, station_id):
    prefix = model["theme"]["prefix"]
    gid = lambda local: settings.game_id(prefix, local)
    return {"free": gid(station_id), "empty": gid(f"{station_id}_empty"),
            "top": gid(f"{station_id}_top"), "effect": gid(f"{station_id}_system")}


def free_block(model, station_id):
    return ids(model, station_id)["free"]


def layout(model, station_id):
    return [(0, ids(model, station_id)["free"]), (1, ids(model, station_id)["top"])]


def build(model, station_id, debug=True):
    st = model["stations"][station_id]
    b = ids(model, station_id)
    label, look, words = st["label"], st["look"], st["words"]
    tool = model["items"][st["holds"]]
    note = f"{label}. See build/systems/tools.py."
    blocks.station_block(b["free"], label, look, words["free"], note, movable=True)
    blocks.station_block(b["empty"], f"{label} (empty)", look, words["empty"], note)
    blocks.display_block(b["top"], f"{tool['label']} (on the {label.lower()})", st["on_top"],
                         words["free"], note)

    rules = v.Entries()
    rep = lambda key, text: v.report(f"kk.{station_id}.{key}", f"[{station_id}] {text}", debug)
    # TAKE: the stand, or the tool on it (small models are hard to aim at).
    for n, (dy, where) in enumerate(((0.0, [v.at([b["free"]])]),
                                     (-1.0, [v.at([b["top"]]), v.at([b["free"]], dy=-1)]))):
        rules.add(100 + n, where,
                  [v.give(tool["game_id"]), v.cell([b["top"]], "Empty", dy=dy + 1),
                   v.cell([b["free"]], b["empty"], dy=dy), v.sound(1.1)]
                  + rep("taken", f"{tool['label'].lower()} taken"))
    # PUT BACK.
    rules.add(110, [v.at([b["empty"]]), v.holding(tool["game_id"])],
              [v.cell([b["empty"]], b["free"]), v.place(b["top"]), v.sound(0.9)]
              + rep("back", f"{tool['label'].lower()} put back"))
    rules.add(111, [v.at([b["empty"]]), v.not_holding(tool["game_id"])],
              [v.say(f"kk.{station_id}.out", words["out"])])
    # CARRIED: put down, the tool goes back on top; picked up, it goes with it.
    rules.add(200, [v.at([b["free"]], event="BLOCK_PLACED")],
              [v.place(b["top"], event="BLOCK_PLACED")])
    rules.add(201, [v.at([b["free"]], event="BLOCK_BROKEN")],
              [v.cell([b["top"]], "Empty", dy=1, event="BLOCK_BROKEN")])
    rules.write(b["effect"], f"The {label.lower()}: keeps the {tool['label'].lower()}. "
                             f"See build/systems/tools.py.")
    return b["effect"]
