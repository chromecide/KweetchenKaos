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
            made = gives == "new"
            if gives == "input":
                gives = s["input"]
            elif gives == "new":
                gives = define({"id": f"{owner}_{st['id']}",
                                "label": f"{owner_label} ({st['word']})", "look": look}, at)
            # How long this stage lasts before the next: the dish's own time for it
            # ("stage_seconds" on its heat step), else the ladder's, else the theme default
            # (first stage only).
            seconds = s.get("stage_seconds", {}).get(st["id"], st.get("seconds"))
            if seconds is None and k == 0:
                seconds = defaults["heat_seconds"]
            last = k == len(ladder["stages"]) - 1
            stages.append({"id": st["id"], "word": st["word"], "look_spec": look,
                           "seconds": None if last else seconds, "gives": gives,
                           # The stage a safety stove holds (it all but stops growing).
                           "safety": st.get("safety", False),
                           # A food of its own (cooked, well done): servable. Not the raw
                           # input or the shared burnt.
                           "made": made})
        return {"type": "heat", "station": s["station"], "ladder": ladder["id"],
                "input": s["input"], "owner": owner, "owner_label": owner_label,
                "stages": stages, "file": at}

    # CRATES: a station file marked per_ingredient is a template, expanded into one station
    # per ingredient that comes from it -- the pumpkin crate, the apple crate... Each gets a
    # "source" step (nothing in, the ingredient out) so everything that reads steps (the
    # kit, the report, checks) sees where raw ingredients come from.
    fixtures = one("fixtures.json")
    templates = {sid: st for sid, st in stations.items() if st.get("per_ingredient")}
    for sid in templates:
        del stations[sid]
    # UPGRADE KITS: any station (or template) with a "kit" is an upgraded variant of the
    # station it names in upgrade_of. The kit is an item -- apply it to a free station of
    # that kind and the station becomes the variant. One kit per variant file, so one
    # "fast crate kit" upgrades any crate.
    for sid, st in list(stations.items()) + list(templates.items()):
        if "kit" in st:
            base = stations.get(st["upgrade_of"]) or templates.get(st["upgrade_of"])
            what = (base["label"].replace("{ingredient} ", "") if base else "station").lower()
            kid = define({"id": f"{sid}_kit", "label": st["kit"]["label"],
                          "look": fixtures["looks"]["kit"], "quality": "Rare",
                          "bin": "refuse"}, st["file"])
            items[kid]["description"] = st["kit"].get(
                "description", f"An upgrade: hold it and press a free {what} (F).")
            st["kit_item"] = kid
    # THE MOP: what cleans up a mess (systems/hazards.py). Never binned.
    define({"id": "mop", "label": "Mop", "look": fixtures["looks"]["mop"], "bin": "refuse"},
           f"themes/{theme_id}/fixtures.json")
    items["mop"]["description"] = "Hold it and press a mess (F) to clean it up."
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
                # ...and each upgrade of the template, for this ingredient.
                for vid, vt in templates.items():
                    if vt.get("upgrade_of") == source:
                        stations[f"{vid}_{iid}"] = dict(
                            vt, id=f"{vid}_{iid}", label=fill(vt["label"]), ingredient=iid,
                            upgrade_of=cid, words={k: fill(w) for k, w in vt["words"].items()},
                            file=vt["file"])
        read_steps(iid, d["item"]["label"], d.get("steps", []), f)

    # PLATING IS BUILT IN. A dish only lists what it serves; for each, the build makes the
    # plated item (the food's own look, Legendary so it stands out in the hotbar, leaves a
    # dirty plate if binned), the step that plates it at the combine station, and the menu
    # entry. No recipe can forget its plating or get it wrong.
    combine_stations = [sid for sid, st in stations.items()
                        if st["role"] == "combine" and not st.get("upgrade_of")]
    dishes = {}
    clean, dirty = vessel["clean"]["id"], vessel["dirty"]["id"]
    serving = []
    for f, d in many("dishes"):
        for raw in d.get("items", []):
            define(raw, f)
        if "id" not in d:
            continue
        dishes[d["id"]] = {"id": d["id"], "label": d["label"], "file": f,
                           "unlock": d.get("unlock", "start"),
                           # Guests it brings when it goes on the menu (None: the rules'
                           # per_card, or nothing for the run's first dish).
                           "guests": d.get("guests"),
                           "serves": [e["item"] for e in d.get("serve", [])]}
        read_steps(d["id"], d["label"], d.get("steps", []), f)
        for e in d.get("serve", []):
            serving.append((f, d, e))
    # EVERY WAY A DISH CAN COME OFF THE STOVE IS SERVABLE: a dish that serves one stage of
    # its heat step (cooked) serves them all (well done too) -- a well done corn that
    # couldn't be plated was the bug this catches.
    for f, d in many("dishes"):
        served = {e["item"] for e in d.get("serve", [])}
        for s in steps:
            if s["type"] != "heat" or s.get("owner") != d.get("id"):
                continue
            made = [st["gives"] for st in s["stages"] if st.get("made")]
            if served & set(made):
                for food in made:
                    if food not in served:
                        problems.append(f"{f}: serves {' and '.join(sorted(served & set(made)))} "
                                        f"but not '{food}' - add it to serve (a stage that "
                                        f"comes off the stove must be plateable)")
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

    # WHAT EACH DISH NEEDS: the crates its chain starts from, walked back through the
    # steps -- so a recipe card knows which crates to deliver, with nobody listing them.
    made_by = {}
    for s in steps:
        outs = [s["output"]] if "output" in s else [st["gives"] for st in s["stages"]
                                                   if st["gives"] != s["input"]]
        for o in outs:
            made_by.setdefault(o, s)

    def crates_for(iid, seen):
        if iid in seen:
            return []
        seen.add(iid)
        s = made_by.get(iid)
        if s is None:
            return []
        if s["type"] == "source":
            return [s["station"]]
        ins = s.get("inputs", []) + ([s["input"]] if "input" in s else [])
        return [c for i in ins for c in crates_for(i, seen)]
    for d in dishes.values():
        seen, needs = set(), []
        for food in d["serves"]:
            for c in crates_for(food, seen):
                if c not in needs:
                    needs.append(c)
        d["needs"] = needs

    if problems:
        raise ContentError(problems)
    return {"theme": theme, "vessel": vessel, "stations": stations, "items": items,
            "steps": steps, "menu": menu, "ladders": ladders, "fixtures": fixtures,
            "dishes": dishes}


def load_rules(rules_id):
    """A rules set: rules.json, offers.json, cards.json, as one dict."""
    root = os.path.join(settings.CONTENT, "rules", rules_id)
    out = _read(os.path.join(root, "rules.json"))
    out["offers"] = _read(os.path.join(root, "offers.json"))
    out["cards"] = _read(os.path.join(root, "cards.json"))
    return out


def load(theme_id, rules_id="standard"):
    """A restaurant's content: the theme, with the rules it runs under."""
    model = load_theme(theme_id)
    model["rules"] = load_rules(rules_id)
    # The rules may scale how patient guests are (the theme sets the dish's own patience;
    # a practice run doubles it, a hard mode could shorten it).
    scale = model["rules"].get("guest_patience_scale", 1.0)
    for e in model["menu"]:
        e["order_patience"] = round(e["order_patience"] * scale, 1)
        e["food_patience"] = round(e["food_patience"] * scale, 1)
    return model
