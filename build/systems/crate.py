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
reads as the crate filling back up. An UPGRADED crate (a variant with upgrade_of; none is
offered today -- a research desk would bring one) glows, and the restocking top listens
for the glow and grows faster (glow.py) -- the same top blocks on either crate.

A crate a player puts down gets its top by itself (BLOCK_PLACED); a crate picked up takes
its top with it. The spike setup and layouts place the top with the crate.

ONLY DURING SERVICE, in a run: between days a crate gives nothing (and says so), or players
could cook the whole next day's food before opening. It reads the shift's "open" tag the way
the pads read the purse (signals.shift_reads) -- naming no shift. A crate that isn't part of
a run (a kitchen spike with no shift) is always open.
"""
import blocks
import clock
import glow
import settings
import signals
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
    in_run = model.get("in_run", False)
    open_now = [signals.shift_reads("BLOCK_USED", "open", "Exactly", 1)] if in_run else []
    for n, (dy, where) in enumerate(((1.0, [v.at(crates), v.at([b["ready"]], dy=1)]),
                                     (0.0, [v.at([b["ready"]]), v.at(crates, dy=-1)]))):
        if in_run:
            rules.add(90 + n, where + [signals.shift_reads("BLOCK_USED", "open", "Exactly", 0)],
                      [v.say(f"kk.{station_id}.closed",
                             f"The {label.lower()} is closed - crates open when the day does.")])
        rules.add(100 + n, where + open_now,
                  [v.give(item["game_id"]), v.place(b["restocking"], dy=dy), v.sound(1.1)]
                  + rep("take", f"{item['label']} taken - restocking"))

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
