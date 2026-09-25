#!/usr/bin/env python3
"""
BUILD v2: read a theme, check it, report it, write the pack.

    python3 build/build.py                 build the kitchen theme
    python3 build/build.py --check         read and check only; write nothing
    python3 build/build.py --theme NAME    another theme
    python3 build/build.py --spike NAME    which system the spike world mounts (default board)
    python3 build/build.py --rules NAME    which rules set (default standard; "practice" to test)
    python3 build/build.py --spike world   build HQ and the restaurants (content/world/world.json)

The REPORT is the point for a person: every menu entry, and the whole chain that makes
it, from crate to plate, in plain words. If the report reads right, the theme is right.

Systems are rewritten one at a time; each is mounted in the spike world (build/spike.py)
until the layouts can mount them for real.
"""
import sys

import check
import content
import items
import layouts
import pack
import spike
import world


def producers(model):
    """{item: how it is made}, for walking a dish back to its crates."""
    made = {}
    for s in model["steps"]:
        if s["type"] == "heat":
            for st in s["stages"]:
                if st["gives"] != s["input"] and st["gives"] not in made:
                    made[st["gives"]] = ("heat", s, st)
        else:
            made.setdefault(s["output"], (s["type"], s, None))
    return made


def chain(model, target):
    """The steps that make `target`, in the order you'd do them, as lines of text."""
    made, lines, seen = producers(model), [], set()
    name = lambda i: model["items"][i]["label"]
    station = lambda s: model["stations"][s["station"]]["label"]

    def walk(iid):
        if iid in seen:
            return
        seen.add(iid)
        how = made.get(iid)
        if iid == model["vessel"]["clean"]["id"]:
            # Plates start in the restaurant; washing only brings dirty ones back.
            lines.append(f"{name(iid)}: from the restaurant's stack (dirty ones are "
                         f"washed at the {station(how[1])})")
            return
        if how is None:
            src = model["items"][iid].get("source")
            lines.append(f"{name(iid)}: from a {src}" if src else f"{name(iid)}: to hand")
            return
        kind, s, st = how
        if kind == "source":
            lines.append(f"{name(iid)}: from the {station(s).lower()}")
            return
        if kind == "press":
            walk(s["input"])
            lines.append(f"{station(s)}, {s['presses']} presses: {name(s['input'])} -> "
                         f"{name(iid)}")
        elif kind == "combine":
            for i in s["inputs"]:
                walk(i)
            lines.append(f"{station(s)}: {name(s['inputs'][0])} + {name(s['inputs'][1])} "
                         f"-> {name(iid)}")
        else:
            walk(s["input"])
            ladder = " -> ".join(x["word"] + (f" {x['seconds']:g}s" if x["seconds"] else "")
                                 for x in s["stages"])
            lines.append(f"{station(s)} ({ladder}): {name(s['input'])}, taken off "
                         f"{st['word']} -> {name(iid)}")

    walk(target)
    return lines


def report(model):
    t = model["theme"]
    print(f"THEME {t['name']}: {len(model['items'])} items, {len(model['steps'])} steps, "
          f"{len(model['menu'])} menu entries, stations: "
          + ", ".join(f"{s['label']} ({s['role']})" for s in model["stations"].values()))
    r = model["rules"]
    grow = r.get("day_growth") or {}
    print(f"RULES {r['name']}: {r['day_seconds']}s days"
          + (f" (+{grow['seconds']}s every {grow['every_days']} days)" if grow.get("seconds") else "")
+ f"; guests: {r['guests']['day_1']} on day 1, +{r['guests']['per_day']} a day, "
          f"+{r['guests']['per_card']} per recipe card"
          + f"; recipe cards every {r['cards']['every_days']} days")
    for d in model["dishes"].values():
        print(f"DISH {d['label']}: {'a starter (chosen on day 0)' if d['unlock'] == 'start' else 'a recipe card'}"
              f"; needs " + ", ".join(model["stations"][c]["label"].lower() for c in d["needs"]))
    for e in model["menu"]:
        print(f"\n  {e['label']}: {e['price']} coins, waits {e['order_patience']}s to "
              f"order and {e['food_patience']}s for food, eats for {e['eat_seconds']}s")
        for line in chain(model, e["serves"]):
            print(f"    {line}")


def main(argv):
    theme = argv[argv.index("--theme") + 1] if "--theme" in argv else "kitchen"
    try:
        rules = argv[argv.index("--rules") + 1] if "--rules" in argv else "standard"
        model = content.load(theme, rules)
    except content.ContentError as e:
        print(f"THEME {theme} could not be read:")
        print("\n".join(f"  - {p}" for p in e.problems))
        return 1
    problems = check.check(model)
    if problems:
        print(f"THEME {theme} has {len(problems)} problem(s):")
        print("\n".join(f"  - {p}" for p in problems))
        return 1
    report(model)
    if "--check" in argv:
        return 0
    name = argv[argv.index("--spike") + 1] if "--spike" in argv else "board"
    pack.begin()
    n = items.write_all(model)
    # The layout workshop is always there, whatever the spike.
    layouts.write_slots()
    layouts.write_authoring()
    if name == "world":
        # HQ and the restaurants in content/world/world.json -- /kk hq to go.
        summary, notes = world.build()
        pack.finish()
        print(f"\nwrote pack: {n} items; the WORLD: /kk hq")
        for line in summary:
            print(f"  {line}")
        for line in notes:
            print(f"  NOTE: {line}")
        return 0
    note, kit = spike.build(model, name)
    pack.finish()
    print(f"\nwrote pack: {n} items; spike world mounts {note}; kit: "
          + ", ".join(f"{c}x {i}" for i, c in kit))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
