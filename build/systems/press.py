"""
THE PRESS SYSTEM: put one thing on a station, press it N times, get another thing.

One system for every station whose role is `press` or `wash` -- in the kitchen theme the
chopping board and the sink. It knows nothing about food: the theme's press steps for
that station say what goes on, what comes off, and how many presses.

    press the free station holding an input  ->  it sits on top; the countdown starts
    press the station, or what's on it       ->  one press; the hint counts down
    the last press                           ->  leave_on: the output REPLACES the input on
                                                 top, and the station waits to be emptied;
                                                 otherwise the output goes straight to you
    press a finished station (leave_on)      ->  you pick the output up; the station is free

THE STATION CARRIES THE COUNT; what sits on top is only a picture. The station's own block
is a ladder -- free, then _Left_N ... _Left_1 (presses still to go), then _Done -- so the
blocks are shared by everything the station takes: N ladder blocks plus one picture per
item, not items x presses. An input that needs fewer presses starts lower down. Only the
last press looks at what is on top, to know what to make.

Every rule starts from a DIFFERENT station block, and a replaced block only lands at the
end of the tick, so a press can never be counted twice and no lock is needed.

Once something is on, it is pressed through: taking it back half done would need a press
to mean something else.
"""
import blocks
import clock
import settings
import volumes as v

ROLES = ("press", "wash")
NEEDS_CLOCK = True      # an AUTO upgrade (the dishwasher) washes by growth


def ids(model, station_id):
    """The game ids this system makes for one station."""
    prefix = model["theme"]["prefix"]
    gid = lambda local: settings.game_id(prefix, local)
    return {"free": gid(station_id),
            "left": lambda n: gid(f"{station_id}_left_{n}"),
            "done": gid(f"{station_id}_done"),
            "on": lambda item: gid(f"{station_id}_on_{item}"),
            "effect": gid(f"{station_id}_system")}


def free_block(model, station_id):
    return ids(model, station_id)["free"]


def layout(model, station_id):
    return [(0, free_block(model, station_id))]


def build(model, station_id, debug=True):
    """Write one press station's blocks and volume effect; return the effect's name."""
    st = model["stations"][station_id]
    items = model["items"]
    table = [s for s in model["steps"] if s["type"] == "press" and s["station"] == station_id]
    assert table, f"{station_id} has no press steps"
    b = ids(model, station_id)
    label, words, look = st["label"], st["words"], st["look"]
    leave_on = st.get("leave_on", False)
    top = max(s["presses"] for s in table)
    name = lambda iid: items[iid]["label"]
    game = lambda iid: items[iid]["game_id"]
    note = f"{label}. See build/systems/press.py."

    # The ladder. Only the free station would ever be movable (rearranging comes later);
    # anything holding something stays put.
    blocks.station_block(b["free"], label, look, words["free"], note, movable=True)
    for n in range(1, top + 1):
        blocks.station_block(b["left"](n), f"{label} (in use)", look,
                             words["busy"].format(n=n, s="" if n == 1 else "s",
                                                  es="" if n == 1 else "es"), note,
                             sides=look.get("busy_sides"))
    if leave_on:
        blocks.station_block(b["done"], f"{label} (done)", look, words["done"], note,
                             sides=look.get("busy_sides"))

    # What sits on top: each input while it is being pressed, and (leave_on) each output
    # waiting to be picked up. Pressing the picture counts as pressing the station --
    # small models are hard to aim at.
    inputs = list(dict.fromkeys(s["input"] for s in table))
    outputs = list(dict.fromkeys(s["output"] for s in table)) if leave_on else []
    assert not set(inputs) & set(outputs), f"{station_id}: an item is both input and output"
    for iid in inputs:
        blocks.display_block(b["on"](iid), f"{name(iid)} (on the {label.lower()})",
                             items[iid]["look"], words["on_top"], note)
    for iid in outputs:
        blocks.display_block(b["on"](iid), f"{name(iid)} (on the {label.lower()})",
                             items[iid]["look"], words["done"], note)
    shown_in = [b["on"](i) for i in inputs]
    shown_out = [b["on"](i) for i in outputs]
    ladder = [b["left"](n) for n in range(1, top + 1)] + ([b["done"]] if leave_on else [])

    rules = v.Entries()
    rep = lambda key, text, to_log=True: v.report(f"kk.{station_id}.{key}",
                                                  f"[{station_id}] {text}", debug, to_log=to_log)

    def either(station_block, on_top, effects, extra=()):
        """The same rule twice: pressing the station, and pressing what's on it. `effects`
        take the station's height (0 or -1 from the pressed block); `extra` don't care."""
        for dy, where in ((0.0, [v.at([station_block]), v.at(on_top, dy=1)]),
                          (-1.0, [v.at(on_top), v.at([station_block], dy=-1)])):
            rules.add(len(rules.conditions) + 1000, where,
                      [e(dy) for e in effects] + list(extra))

    # PUT ON: the station starts at this input's own press count.
    for s in table:
        rules.add(100 + inputs.index(s["input"]),
                  [v.at([b["free"]]), v.holding(game(s["input"]))],
                  [v.cell([b["free"]], b["left"](s["presses"])),
                   v.place(b["on"](s["input"])), v.sound(0.8)]
                  + rep(f"on.{s['input']}", f"{name(s['input'])} on - start pressing"))

    # PRESS: one rung down. What is on top isn't looked at.
    for n in range(2, top + 1):
        either(b["left"](n), shown_in, [
            lambda dy, n=n: v.cell([b["left"](n)], b["left"](n - 1), dy=dy),
            lambda dy, n=n: v.sound(1.4 + 0.1 * (top - n), volume=0.9)],
            # Chat only: the log takes a line a second, and presses would crowd out the
            # milestones (on, made, picked up).
            rep(f"press.{n}", f"press - {n - 1} to go", to_log=False))

    # THE LAST PRESS: the only one that asks what is on top.
    for s in table:
        shown = b["on"](s["input"])
        if leave_on:
            effects = [lambda dy, s=s, shown=shown: v.cell([shown], b["on"](s["output"]), dy=dy + 1),
                       lambda dy: v.cell([b["left"](1)], b["done"], dy=dy),
                       lambda dy: v.sound(1.0)]
            text = f"{name(s['output'])} made - left on the {label.lower()}"
        else:
            effects = [lambda dy, s=s: v.give(game(s["output"])),
                       lambda dy, shown=shown: v.cell([shown], "Empty", dy=dy + 1),
                       lambda dy: v.cell([b["left"](1)], b["free"], dy=dy),
                       lambda dy: v.sound(1.0)]
            text = f"{name(s['output'])} made - handed over"
        either(b["left"](1), [shown], effects, rep(f"made.{s['output']}", text))

    # PICK UP what was made (leave_on).
    for iid in outputs:
        shown = b["on"](iid)
        either(b["done"], [shown], [
            lambda dy, iid=iid: v.give(game(iid)),
            lambda dy, shown=shown: v.cell([shown], "Empty", dy=dy + 1),
            lambda dy: v.cell([b["done"]], b["free"], dy=dy),
            lambda dy: v.sound(1.2)],
            rep(f"taken.{iid}", f"{name(iid)} picked up - free"))

    # BREAKING: a picture broken frees its station; a station broken takes its picture.
    rules.add(900, [v.at(shown_in + shown_out, event="BLOCK_BROKEN")],
              [v.cell(ladder, b["free"], dy=-1, event="BLOCK_BROKEN")])
    rules.add(901, [v.at([b["free"]] + ladder, event="BLOCK_BROKEN")],
              [v.cell(shown_in + shown_out, "Empty", dy=1, event="BLOCK_BROKEN")])

    # ITS HAZARD (the station's "hazard": a spill for the sink, scraps for the board): a
    # chance each press, dropped round the station. Pressing what's on top is the station
    # one below.
    v.station_hazard(rules, 8000, "hazard", model, st, [v.at(ladder)])
    v.station_hazard(rules, 8100, "hazardtop", model, st, [v.at(shown_in)], dy=-1.0)

    _auto_variants(model, station_id, table, rules, debug)

    rules.write(b["effect"], f"The {label.lower()}: a press station. See build/systems/press.py.")
    return b["effect"]


def _auto_variants(model, station_id, table, rules, debug):
    """AN AUTO UPGRADE (the dishwasher): a variant of this station (`upgrade_of`, with
    `auto_seconds`) that does the pressing itself.

        (bought ready-made: a blueprint on the pads)
        press it holding an input           ->  it goes in; after auto_seconds it is done
                                                 by itself (GROWTH, like a stove or a crate)
        press it (or what's on it) once done ->  you take the output; it's free again

    Same steps as the station it upgrades (the sink's wash steps), same ladder-free blocks:
    free, busy, and on top a picture that grows from the input into the output."""
    items = model["items"]
    prefix = model["theme"]["prefix"]
    gid = lambda local: settings.game_id(prefix, local)
    autos = [(vid, vs) for vid, vs in model["stations"].items()
             if vs.get("upgrade_of") == station_id and "auto_seconds" in vs]
    for k, (vid, vs) in enumerate(autos):
        label, words, look = vs["label"], vs["words"], vs["look"]
        note = f"{label}. See build/systems/press.py (_auto_variants)."
        free, busy = gid(vid), gid(f"{vid}_busy")
        blocks.station_block(free, label, look, words["free"], note, movable=True)
        blocks.station_block(busy, f"{label} (in use)", look, words["busy"], note)
        rep = lambda key, text: v.report(f"kk.{vid}.{key}", f"[{vid}] {text}", debug)
        working, ready = [], []
        for s in table:
            w, r = gid(f"{vid}_on_{s['input']}"), gid(f"{vid}_ready_{s['output']}")
            grow = clock.growth([w, r], [vs["auto_seconds"], None])
            blocks.display_block(w, f"{items[s['input']]['label']} (in the {label.lower()})",
                                 items[s["input"]]["look"], words["busy"], note, extra=grow)
            blocks.display_block(r, f"{items[s['output']]['label']} (in the {label.lower()})",
                                 items[s["output"]]["look"], words["done"], note, extra=grow)
            working.append(w)
            ready.append(r)
            # IN: the input goes on top and starts working by itself.
            rules.add(3000 + len(rules.conditions), [v.at([free]), v.holding(items[s["input"]]["game_id"])],
                      [v.cell([free], busy), v.place(w), v.sound(0.8)]
                      + rep(f"in.{s['input']}", f"{items[s['input']]['label']} in"))
            # OUT, once done: press the station or what's on it.
            for dy, where in ((0.0, [v.at([busy]), v.at([r], dy=1)]),
                              (-1.0, [v.at([r]), v.at([busy], dy=-1)])):
                rules.add(3000 + len(rules.conditions), where,
                          [v.give(items[s["output"]]["game_id"]), v.cell([r], "Empty", dy=dy + 1),
                           v.cell([busy], free, dy=dy), v.sound(1.2)]
                          + rep(f"out.{s['output']}", f"{items[s['output']]['label']} taken"))
        # BREAKING: what's on top goes with it; a broken top frees it. Numbered per variant:
        # two rules sharing a number are ONE rule to the engine.
        rules.add(3950 + 2 * k, [v.at(working + ready, event="BLOCK_BROKEN")],
                  [v.cell([busy], free, dy=-1, event="BLOCK_BROKEN")])
        rules.add(3951 + 2 * k, [v.at([free, busy], event="BLOCK_BROKEN")],
                  [v.cell(working + ready, "Empty", dy=1, event="BLOCK_BROKEN")])
        # ITS HAZARD (a cheap dishwasher drips): a chance each time a clean plate comes out.
        v.station_hazard(rules, 8200 + 200 * k, f"hazard{k}", model, vs,
                         [v.at([busy]), v.at(ready, dy=1)])
        v.station_hazard(rules, 8300 + 200 * k, f"hazardtop{k}", model, vs,
                         [v.at(ready), v.at([busy], dy=-1)], dy=-1.0)
