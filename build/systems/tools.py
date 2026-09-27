"""
THE TOOL SYSTEM: a stand that keeps a tool -- the mop, for the hazards (systems/hazards.py).

    press the stand (or the tool on it)  ->  you take the tool; the stand is empty
    press the empty stand with the tool  ->  it goes back
    press the empty stand without it     ->  it says the tool is out

NOT A CUBE: the empty stand is a tinted mat on the floor ("stand"), and with its tool on it
the block IS the tool, standing there ("on_top") -- one block either way, nothing floating
above. Only a stand with its tool on it moves -- an empty one stays put, so the tool always
has somewhere to come back to.

A station file with role "tool" names the item it keeps ("holds"), the stand's look
("stand") and the tool's ("on_top"); its cube "look" is only the authoring slot's. Every layout should have one (a "mop stand" slot): without it there's no mop, and
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
            "effect": gid(f"{station_id}_system")}


def free_block(model, station_id):
    return ids(model, station_id)["free"]


def layout(model, station_id):
    return [(0, ids(model, station_id)["free"])]


def _block(game_id, label, look, hint_text, comment, hitbox, movable=False):
    """A stand block drawn as a model: walked through, pressed, and (with its tool) carried."""
    block = dict(blocks.block_for(look), HitboxType=hitbox,
                 InteractionHint=blocks.hint(game_id, hint_text), Interactions={"Use": blocks.NOOP})
    blocks.item(game_id, label, look.get("icon", blocks.STATION_ICON), block, comment, movable)


def build(model, station_id, debug=True):
    st = model["stations"][station_id]
    b = ids(model, station_id)
    label, look, words = st["label"], st["look"], st["words"]
    tool = model["items"][st["holds"]]
    note = f"{label}. See build/systems/tools.py."
    _block(b["free"], label, dict(st["on_top"], icon=look.get("icon")), words["free"], note,
           "Full", movable=True)
    _block(b["empty"], f"{label} (empty)", dict(st["stand"], icon=look.get("icon")),
           words["empty"], note, "Block_Flat")

    rules = v.Entries()
    rep = lambda key, text: v.report(f"kk.{station_id}.{key}", f"[{station_id}] {text}", debug)
    # TAKE: the tool standing there.
    rules.add(100, [v.at([b["free"]])],
              [v.give(tool["game_id"]), v.cell([b["free"]], b["empty"]), v.sound(1.1)]
              + rep("taken", f"{tool['label'].lower()} taken"))
    # PUT BACK.
    rules.add(110, [v.at([b["empty"]]), v.holding(tool["game_id"])],
              [v.cell([b["empty"]], b["free"]), v.sound(0.9)]
              + rep("back", f"{tool['label'].lower()} put back"))
    rules.add(111, [v.at([b["empty"]]), v.not_holding(tool["game_id"])],
              [v.say(f"kk.{station_id}.out", words["out"])])
    rules.write(b["effect"], f"The {label.lower()}: keeps the {tool['label'].lower()}. "
                             f"See build/systems/tools.py.")
    return b["effect"]
