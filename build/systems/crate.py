"""
THE CRATE SYSTEM: where raw ingredients come from. Never runs out.

    a crate shows its ingredient sitting on top
    press the ingredient (or the crate)   ->  you take it; the top empties
    ...restock_seconds later              ->  the next one appears on top by itself

One crate per ingredient whose source is "crate" -- content.py expands the theme's crate
template, so a new ingredient brings its own crate with no work here.

RESTOCKING IS GROWTH, like the stove (clock.py): the top is a block that grows from
"restocking" (the ingredient, tiny) to "ready" (full size) in restock_seconds. A volume
can't see an empty cell, so "restocking" has to be a real block -- and a tiny ingredient
reads as the crate filling back up. An UPGRADED crate (hold the fast crate kit and press
a crate) glows, and the restocking top listens for the glow and grows twice as fast
(glow.py) -- the same top blocks on either crate.

A crate a player puts down gets its top by itself (BLOCK_PLACED); a crate picked up takes
its top with it. The spike setup and layouts place the top with the crate.
"""
import blocks
import clock
import glow
import settings
import volumes as v

ROLES = ("crate",)
NEEDS_CLOCK = True
RESTOCK_SCALE = 0.3     # the restocking ingredient, as a fraction of its ready size


def ids(model, station_id):
    prefix = model["theme"]["prefix"]
    gid = lambda local: settings.game_id(prefix, local)
    return {"free": gid(station_id), "of": lambda sid: gid(sid),
            "ready": gid(f"{station_id}_ready"),
            "restocking": gid(f"{station_id}_restocking"),
            "effect": gid(f"{station_id}_system")}


def free_block(model, station_id):
    return ids(model, station_id)["free"]


def layout(model, station_id):
    b = ids(model, station_id)
    return [(0, b["free"]), (1, b["ready"])]


def build(model, station_id, debug=True):
    st, items = model["stations"][station_id], model["items"]
    b = ids(model, station_id)
    iid = st["ingredient"]
    item = items[iid]
    label, words, look = st["label"], st["words"], st["look"]
    note = f"{label}. See build/systems/crate.py."
    seconds = st.get("restock_seconds", model["theme"]["defaults"]["restock_seconds"])

    mods = glow.write(model)
    kinds = [(station_id, st)] + [(sid, s) for sid, s in model["stations"].items()
                                  if s.get("upgrade_of") == station_id]
    for sid, vs in kinds:
        blocks.station_block(b["of"](sid), vs["label"], dict(vs["look"], icon=item["look"]["icon"]),
                             vs["words"]["free"], note, tint=vs["look"].get("tint"),
                             light=glow.light(model, vs["glow"]) if vs.get("glow") else None,
                             movable=True)
    crates = [b["of"](sid) for sid, _ in kinds]
    grow = clock.growth([b["restocking"], b["ready"]], [seconds, None],
                        modifiers=[mods["fast"]] if "fast" in mods else None)
    small = dict(item["look"], scale=item["look"].get("scale", 1) * RESTOCK_SCALE)
    blocks.display_block(b["restocking"], f"{item['label']} (restocking)", small,
                         words["restocking"], note, extra=grow)
    blocks.display_block(b["ready"], f"{item['label']} (in the crate)", item["look"],
                         words["on_top"], note, extra=grow)

    rules = v.Entries()
    rep = lambda key, text: v.report(f"kk.{station_id}.{key}", f"[{station_id}] {text}", debug)
    tops = [b["ready"], b["restocking"]]

    # TAKE: press what's on top, or the crate under it. The top goes back to restocking,
    # placed fresh so its growth starts again.
    for n, (dy, where) in enumerate(((1.0, [v.at(crates), v.at([b["ready"]], dy=1)]),
                                     (0.0, [v.at([b["ready"]]), v.at(crates, dy=-1)]))):
        rules.add(100 + n, where,
                  [v.give(item["game_id"]), v.place(b["restocking"], dy=dy), v.sound(1.1)]
                  + rep("take", f"{item['label']} taken - restocking"))

    # UPGRADE: hold the kit and press a plain crate -- it becomes the fast one; its top
    # carries on as it was.
    for k, (sid, vs) in enumerate(kinds[1:]):
        kit = items[vs["kit_item"]]
        rules.add(150 + k, [v.at([b["free"]]), v.holding(kit["game_id"])],
                  [v.cell([b["free"]], b["of"](sid)), v.sound(1.5)]
                  + rep(f"upgraded.{sid}", f"upgraded to a {vs['label'].lower()}"))
    # The kit pressed on an already-fast crate: say so.
    for k, (sid, vs) in enumerate(kinds[1:]):
        kit = items[vs["kit_item"]]
        rules.add(170 + k, [v.at(crates[1:]), v.has(kit["game_id"])],
                  [v.say("kk.crate.kit_wrong", "[crate] That crate is already upgraded.")])
    # A crate put down grows its own top; a crate picked up (broken) takes its top.
    rules.add(200, [v.at(crates, event="BLOCK_PLACED")],
              [v.place(b["restocking"], event="BLOCK_PLACED")]
              + v.report(f"kk.{station_id}.placed", f"[{station_id}] placed - restocking",
                         debug, event="BLOCK_PLACED"))
    rules.add(201, [v.at(crates, event="BLOCK_BROKEN")],
              [v.cell(tops, "Empty", dy=1, event="BLOCK_BROKEN")])

    rules.write(b["effect"], f"The {label.lower()}: a never-ending supply. "
                             f"See build/systems/crate.py.")
    return b["effect"]
