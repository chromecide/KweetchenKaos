"""
READING A THEME: a folder of small JSON files -> one resolved, checked model.

See docs/content-schema.md for the format. This file turns the files into plain dicts that the
rest of the build (items, and later the systems) can use without knowing where anything
came from:

    model["items"]     {local id: item}      every item, looks fully resolved
    model["steps"]     [step]                every press, combine and heat step
    model["stations"]  {id: station}
    model["menu"]      [menu entry]          defaults filled in
    model["theme"], model["vessel"]

Every item and step remembers the file it came from, so an error can say where to look.
Keys starting with "$" (like "$comment") are notes for people and are ignored.

Loading never stops at the first problem: it collects them all, so one build tells you
everything that is wrong. check.py then looks at the finished model as a whole.
"""
import glob
import json
import os

import settings


class ContentError(Exception):
    def __init__(self, problems):
        self.problems = problems
        super().__init__("\n".join(problems))


def _read(path):
    with open(path) as fh:
        return _strip_notes(json.load(fh))


def _strip_notes(value):
    if isinstance(value, dict):
        return {k: _strip_notes(v) for k, v in value.items() if not k.startswith("$")}
    if isinstance(value, list):
        return [_strip_notes(v) for v in value]
    return value


def load_theme(theme_id):
    root = os.path.join(settings.CONTENT, "themes", theme_id)
    problems = []
    rel = lambda p: os.path.relpath(p, settings.CONTENT)
    one = lambda name: _read(os.path.join(root, name))
    many = lambda folder: [(rel(p), _read(p))
                           for p in sorted(glob.glob(os.path.join(root, folder, "*.json")))]

    theme = one("theme.json")
    defaults = theme["defaults"]
    looks = {d["id"]: d for _, d in many("looks")}
    ladders = {d["id"]: d for _, d in many("ladders")}
    stations = {}
    for f, d in many("stations"):
        stations[d["id"]] = dict(d, file=f)

    items, steps, menu = {}, [], []

    def define(raw, where, owner_label=None):
        """Register an item written out in full; return its local id."""
        iid = raw["id"]
        if iid in items:
            problems.append(f"{where}: item '{iid}' is already defined in "
                            f"{items[iid]['file']}")
            return iid
        items[iid] = {"id": iid, "label": raw["label"], "look_spec": raw.get("look", {}),
                      "quality": raw.get("quality"), "bin": raw.get("bin", "destroy"),
                      "file": where, "game_id": settings.game_id(theme["prefix"], iid)}
        return iid

    def ref_or_define(value, where):
        return define(value, where) if isinstance(value, dict) else value

    # The vessel: clean and dirty plates, and washing as a press step at its station.
    vessel = one("vessel.json")
    for key in ("clean", "dirty"):
        define(vessel[key], "themes/%s/vessel.json" % theme_id)
    steps.append({"type": "press", "station": vessel["wash"]["station"],
                  "input": vessel["dirty"]["id"], "output": vessel["clean"]["id"],
                  "presses": vessel["wash"]["presses"],
                  "file": "themes/%s/vessel.json" % theme_id})

    def read_steps(owner, owner_label, raw_steps, where):
        for n, s in enumerate(raw_steps):
            at = f"{where} step {n + 1}"
            kind = s.get("type")
            if kind == "press":
                steps.append({"type": "press", "station": s["station"], "input": s["input"],
                              "output": ref_or_define(s["output"], at),
                              "presses": s["presses"], "file": at})
            elif kind == "combine":
                steps.append({"type": "combine", "station": s["station"],
                              "inputs": list(s["inputs"]),
                              "output": ref_or_define(s["output"], at), "file": at})
            elif kind == "heat":
                steps.append(_heat(s, owner, owner_label, at))
            else:
                problems.append(f"{at}: unknown step type '{kind}'")

    def _heat(s, owner, owner_label, at):
        ladder = ladders.get(s.get("ladder"))
        if ladder is None:
            problems.append(f"{at}: unknown ladder '{s.get('ladder')}'")
            return {"type": "heat", "station": s["station"], "input": s["input"],
                    "stages": [], "file": at}
        stages = []
        for k, st in enumerate(ladder["stages"]):
            look = dict(s.get("look", {}))
            if "tint" in st:
                look["tint"] = st["tint"]
            look.update(s.get("stage_looks", {}).get(st["id"], {}))
            gives = st["gives"]
            if gives == "input":
                gives = s["input"]
            elif gives == "new":
                gives = define({"id": f"{owner}_{st['id']}",
                                "label": f"{owner_label} ({st['word']})", "look": look}, at)
            seconds = st.get("seconds")
            if seconds is None and k == 0:
                seconds = defaults["heat_seconds"]
            last = k == len(ladder["stages"]) - 1
            stages.append({"id": st["id"], "word": st["word"], "look_spec": look,
                           "seconds": None if last else seconds, "gives": gives})
        return {"type": "heat", "station": s["station"], "ladder": ladder["id"],
                "input": s["input"], "owner": owner, "owner_label": owner_label,
                "stages": stages, "file": at}

    # CRATES: a station file marked per_ingredient is a template, expanded into one station
    # per ingredient that comes from it -- the pumpkin crate, the apple crate... Each gets a
    # "source" step (nothing in, the ingredient out) so everything that reads steps (the
    # kit, the report, checks) sees where raw ingredients come from.
    templates = {sid: st for sid, st in stations.items() if st.get("per_ingredient")}
    for sid in templates:
        del stations[sid]
    for f, d in many("ingredients"):
        iid = define(d["item"], f)
        source = d.get("source")
        items[iid]["source"] = source
        if source:
            t = templates.get(source)
            if t is None:
                problems.append(f"{f}: source '{source}' has no station template")
            else:
                label = d["item"]["label"]
                fill = lambda text: text.replace("{ingredient}", label)
                cid = f"{source}_{iid}"
                stations[cid] = dict(t, id=cid, label=fill(t["label"]), ingredient=iid,
                                     words={k: fill(w) for k, w in t["words"].items()},
                                     file=t["file"])
                steps.append({"type": "source", "station": cid, "output": iid, "file": f})
        read_steps(iid, d["item"]["label"], d.get("steps", []), f)

    # PLATING IS BUILT IN. A dish only lists what it serves; for each, the build makes the
    # plated item (the food's own look, Legendary so it stands out in the hotbar, leaves a
    # dirty plate if binned), the step that plates it at the combine station, and the menu
    # entry. No recipe can forget its plating or get it wrong.
    combine_stations = [sid for sid, st in stations.items() if st["role"] == "combine"]
    clean, dirty = vessel["clean"]["id"], vessel["dirty"]["id"]
    serving = []
    for f, d in many("dishes"):
        for raw in d.get("items", []):
            define(raw, f)
        if "id" not in d:
            continue
        read_steps(d["id"], d["label"], d.get("steps", []), f)
        for e in d.get("serve", []):
            serving.append((f, d, e))
    for f, d, e in serving:
        food = e["item"]
        if food not in items:
            problems.append(f"{f}: serves unknown item '{food}'")
            continue
        plated = define({"id": f"{food}_plated", "label": f"{items[food]['label']}, plated",
                         "look": {"of": food}, "quality": "Legendary",
                         "bin": {"leaves": dirty}}, f)
        station = e.get("plate_at") or (combine_stations[0] if combine_stations else None)
        steps.append({"type": "combine", "station": station, "inputs": [clean, food],
                      "output": plated, "file": f"{f} (plating {food})"})
        menu.append({
            "serves": plated, "label": items[food]["label"], "dish": d["id"], "file": f,
            "price": e.get("price", defaults["price"]),
            "order_patience": e.get("order_patience", defaults["order_patience"]),
            "food_patience": e.get("food_patience", defaults["food_patience"]),
            "eat_seconds": e.get("eat_seconds", defaults["eat_seconds"])})

    # Looks last: an item's look may be "of" another item, defined anywhere.
    resolving = set()

    def resolve(spec, where):
        spec = dict(spec)
        if "of" in spec:
            other = items.get(spec.pop("of"))
            if other is None:
                problems.append(f"{where}: look is 'of' an unknown item")
                return {}
            base = dict(item_look(other))
        elif "base" in spec:
            name = spec.pop("base")
            if name not in looks:
                problems.append(f"{where}: unknown look '{name}'")
                return {}
            base = {k: v for k, v in looks[name].items() if k != "id"}
        else:
            base = {}
        base.update(spec)
        return base

    def item_look(item):
        if "look" in item:
            return item["look"]
        if item["id"] in resolving:
            problems.append(f"{item['file']}: look of '{item['id']}' refers back to itself")
            return {}
        resolving.add(item["id"])
        item["look"] = resolve(item["look_spec"], item["file"])
        resolving.discard(item["id"])
        return item["look"]

    for item in items.values():
        item_look(item)
    for s in steps:
        for st in s.get("stages", []):
            st["look"] = resolve(st["look_spec"], s["file"])

    if problems:
        raise ContentError(problems)
    return {"theme": theme, "vessel": vessel, "stations": stations, "items": items,
            "steps": steps, "menu": menu, "ladders": ladders}
