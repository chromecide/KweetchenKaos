"""
THE HEAT SYSTEM: put something on a stove and it changes by itself -- and burns.

    press a free stove holding something it cooks   ->  it goes on top, at its first stage
    ...wait                                         ->  it moves through the ladder's stages
                                                        on its own (unbaked, cooked, well
                                                        done, burnt), each its own look
    press it (or the stove under it)                ->  you take it off at whatever stage
                                                        it has reached; the stove is free
    press a free stove holding a part-cooked one    ->  it goes back on at that stage and
                                                        carries on (cooked, well done)

The theme's heat steps say what goes on and which ladder it follows; the ladder says the
stages, their times and what you get at each. The stove knows no food.

THE CLOCK IS THE ENGINE'S OWN GROWTH (clock.py): every stage is a block, and growth swaps
each for the next after its time -- nothing ticks, nothing can drift, and a pie keeps
cooking whether anyone is near or not. A world with a stove must run its clock.

UPGRADES (fast stove, safety stove) are the theme's variants of this station: the same
dishes on the same stage blocks, only the stove block differs -- it GLOWS (glow.py), and
the stage blocks listen. An upgraded stove is bought ready-made (a blueprint on the pads).
"""
import blocks
import clock
import glow
import settings
import volumes as v

ROLES = ("heat",)
NEEDS_CLOCK = True


def variants(model, station_id):
    """The station and its upgrades: [(station id, station)] -- the station first."""
    return [(station_id, model["stations"][station_id])] + [
        (sid, s) for sid, s in model["stations"].items() if s.get("upgrade_of") == station_id]


def ids(model, station_id):
    prefix = model["theme"]["prefix"]
    gid = lambda local: settings.game_id(prefix, local)
    return {"free": gid(station_id), "busy": gid(f"{station_id}_busy"),
            "free_of": lambda sid: gid(sid), "busy_of": lambda sid: gid(f"{sid}_busy"),
            "on": lambda step, stage: gid(f"{station_id}_{step['owner']}_{stage}"),
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
    note = f"{label}. See build/systems/heat.py."
    heats = [s for s in model["steps"] if s["type"] == "heat" and s["station"] == station_id]

    mods = glow.write(model)
    kinds = variants(model, station_id)
    for sid, vs in kinds:
        lit = glow.light(model, vs["glow"]) if vs.get("glow") else None
        blocks.station_block(b["free_of"](sid), vs["label"], vs["look"], vs["words"]["free"],
                             note, tint=vs["look"].get("tint"), light=lit, movable=True)
        blocks.station_block(b["busy_of"](sid), f"{vs['label']} (in use)", vs["look"],
                             vs["words"]["busy"], note, sides=vs["look"].get("busy_sides"),
                             top=vs["look"].get("busy_top"), tint=vs["look"].get("tint"),
                             light=lit)
    frees = [b["free_of"](sid) for sid, _ in kinds]
    busies = [b["busy_of"](sid) for sid, _ in kinds]
    # Every free -> busy (and back) pair; only the one matching the block present applies.
    to_busy = lambda dy=0.0: [v.cell([f], bz, dy=dy) for f, bz in zip(frees, busies)]
    to_free = lambda dy=0.0: [v.cell([bz], f, dy=dy) for f, bz in zip(frees, busies)]

    on_top = []
    for h in heats:
        stage_blocks = [b["on"](h, st_["id"]) for st_ in h["stages"]]
        for st_, block in zip(h["stages"], stage_blocks):
            # Every stage speeds up on a fast stove; the safety stage holds on a safe one.
            listen = [mods[k] for k in ("fast",) if k in mods] + (
                [mods["safe"]] if st_.get("safety") and "safe" in mods else [])
            grow = clock.growth(stage_blocks, [x["seconds"] for x in h["stages"]],
                                modifiers=listen)
            text = words["on_top"].format(label=h["owner_label"], stage=st_["word"])
            blocks.display_block(block, f"{h['owner_label']} ({st_['word']}, on the "
                                        f"{label.lower()})", dict(st_["look"],
                                        icon=items[h["input"]]["look"]["icon"]), text,
                                 note, extra=grow)
        on_top += stage_blocks

    rules = v.Entries()
    rep = lambda key, text: v.report(f"kk.{station_id}.{key}", f"[{station_id}] {text}", debug)
    n = iter(range(100, 100000))

    for h in heats:
        stages = h["stages"]
        # PUT ON: the input starts at the first stage; a taken-off item that the ladder
        # lets back on resumes at its own stage. Resumable: any stage that makes its own
        # item, except the first and the last (the unbaked pie IS the first stage, and
        # burnt is shared and final).
        starts = [(h["input"], stages[0])] + [
            (st_["gives"], st_) for st_ in stages[1:-1] if st_["gives"] != h["input"]]
        for held, st_ in starts:
            rules.add(next(n), [v.at(frees), v.holding(game(held))],
                      [*to_busy(), v.place(b["on"](h, st_["id"])),
                       v.sound(1.2, 0.8, "SFX_Campfire_Processing")]
                      + rep(f"on.{held}", f"{name(held)} on - {st_['word']}"))
        # TAKE OFF at any stage: press what's on top, or the stove under it.
        for st_ in stages:
            block = b["on"](h, st_["id"])
            for dy, where in ((0.0, [v.at([block]), v.at(busies, dy=-1)]),
                              (1.0, [v.at(busies), v.at([block], dy=1)])):
                rules.add(next(n), where,
                          [v.give(game(st_["gives"])),
                           v.cell([block], "Empty", dy=dy),
                           *to_free(dy - 1),
                           v.sound(0.9)]
                          + rep(f"off.{h['owner']}.{st_['id']}",
                                f"{h['owner_label']} taken off {st_['word']} -> "
                                f"{name(st_['gives'])}"))

    # ITS HAZARD (a scorch mark) when BURNT food comes off -- the last stage of every
    # ladder -- round the stove. Pressing the burnt food is the stove one below.
    burnt = [b["on"](h, h["stages"][-1]["id"]) for h in heats]
    v.station_hazard(b["effect"], "hazard", model, st, [v.at(burnt), v.at(busies, dy=-1)],
                     dy=-1.0)
    v.station_hazard(b["effect"], "hazardtop", model, st, [v.at(busies), v.at(burnt, dy=1)])

    # BREAKING: a dish broken frees its stove; a stove broken takes its dish.
    rules.add(90, [v.at(on_top, event="BLOCK_BROKEN")],
              [dict(c, Event="BLOCK_BROKEN") for c in to_free(-1)])
    rules.add(91, [v.at(frees + busies, event="BLOCK_BROKEN")],
              [v.cell(on_top, "Empty", dy=1, event="BLOCK_BROKEN")])

    rules.write(b["effect"], f"The {label.lower()}: cooks and burns by itself. "
                             f"See build/systems/heat.py.")
    return b["effect"]
