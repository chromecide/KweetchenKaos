"""
CHECKING A THEME as a whole, once content.py has read it. See docs/content-schema.md, "Checks the
generator makes".

Every problem names the file it came from and the id involved, and all problems are
reported together. A theme that fails here builds nothing.
"""
import os
import zipfile

import settings

ROLES = ("press", "heat", "combine", "wash", "bin", "rack", "call", "tool")  # exactly one station each
MANY_ROLES = ("crate",)                                       # one per ingredient
STEP_ROLES = {"press": ("press", "wash"), "combine": ("combine",), "heat": ("heat",),
              "source": ("crate",)}
_shipped = None


def shipped_assets():
    """Every shipped Common/ path -- or None when the game's Assets.zip isn't found (set
    ASSETS in local.cfg): the shipped-path check is then skipped."""
    global _shipped
    if _shipped is None:
        if not settings.ASSETS_ZIP or not os.path.exists(settings.ASSETS_ZIP):
            print("  WARNING: the game's Assets.zip wasn't found (set ASSETS in local.cfg) -- "
                  "shipped model/texture/icon paths are NOT checked")
            _shipped = False
        else:
            with zipfile.ZipFile(settings.ASSETS_ZIP) as z:
                _shipped = {n[len("Common/"):] for n in z.namelist() if n.startswith("Common/")}
    return _shipped or None


def check(model):
    problems = []
    items, stations = model["items"], model["stations"]
    known = lambda iid: iid in items

    # One station per role -- today's rule. Steps already name their station, so lifting
    # this later is a rule change, not a format change.
    base = {sid: s for sid, s in stations.items() if not s.get("upgrade_of")}
    for role in ROLES:
        have = [s["id"] for s in base.values() if s["role"] == role]
        if len(have) != 1:
            problems.append(f"stations/: exactly one '{role}' station is needed, found "
                            f"{have or 'none'}")
    for s in stations.values():
        if s["role"] not in ROLES + MANY_ROLES:
            problems.append(f"{s['file']}: unknown role '{s['role']}'")

    # Upgrades: each names a station of its own role.
    for s in stations.values():
        up = s.get("upgrade_of")
        if up and (up not in stations or stations[up]["role"] != s["role"]):
            problems.append(f"{s['file']}: '{s['id']}' upgrades '{up}', which isn't a "
                            f"{s['role']} station")

    # Rules: offers name real stations and kits; at least one dish starts on the menu.
    rules = model.get("rules")
    if rules:
        kits = {i[:-len("_kit")] for i in items if i.endswith("_kit")}
        for o in rules["offers"]["catalogue"]:
            # Any station can be offered, an upgraded one (a dishwasher) ready-made too.
            if "station" in o and o["station"] not in stations:
                problems.append(f"rules offers.json: unknown station '{o['station']}'")
            if "kit" in o and o["kit"] not in kits:
                problems.append(f"rules offers.json: unknown kit '{o['kit']}'")
            if "fixture" in o and o["fixture"] != "chair":
                problems.append(f"rules offers.json: '{o['fixture']}' can't be offered "
                                f"(the only fixture is chair)")
            for st in rules["stages"]:
                if st["id"] not in o["weights"]:
                    problems.append(f"rules offers.json: '{o.get('station') or o.get('kit') or o.get('fixture')}' "
                                    f"has no weight for stage '{st['id']}'")
    dishes = model.get("dishes", {})
    if dishes and not any(d["unlock"] == "start" for d in dishes.values()):
        problems.append("dishes/: no dish is on the menu from the start")
    for d in dishes.values():
        if d["unlock"] not in ("start", "card"):
            problems.append(f"{d['file']}: unlock must be 'start' or 'card'")

    for step in model["steps"]:
        where, kind = step["file"], step["type"]
        st = stations.get(step["station"])
        if st is None:
            problems.append(f"{where}: unknown station '{step['station']}'")
        elif st["role"] not in STEP_ROLES[kind]:
            problems.append(f"{where}: a {kind} step can't use '{st['id']}' "
                            f"(a {st['role']} station)")
        used = step.get("inputs", []) + ([step["input"]] if "input" in step else [])
        made = [step["output"]] if "output" in step else [s["gives"] for s in step.get("stages", [])]
        for iid in used + made:
            if not known(iid):
                problems.append(f"{where}: unknown item '{iid}'")
        if kind == "combine" and len(step["inputs"]) != 2:
            problems.append(f"{where}: a combine takes exactly two things (for now)")

    # Everything that goes on a counter must be something the counter can show: every
    # combine input and output. (All items have looks, but say which one if not.)
    for iid, item in items.items():
        look = item.get("look", {})
        for field in ("model", "texture", "icon"):
            if not look.get(field):
                problems.append(f"{item['file']}: item '{iid}' has no look {field}")

    # Guests are only ever handed something on a plate.
    clean = model["vessel"]["clean"]["id"]
    plated = {s["output"] for s in model["steps"]
              if s["type"] == "combine" and clean in s["inputs"]}
    for e in model["menu"]:
        if e["serves"] not in plated:
            problems.append(f"{e['file']}: menu entry '{e['label']}' serves "
                            f"'{e['serves']}', which isn't made by plating")

    # Every path a look names must be a shipped asset.
    shipped = shipped_assets()
    unshipped = lambda path: shipped is not None and path not in shipped
    looks = [(i["file"], i["id"], i["look"]) for i in items.values()]
    looks += [(s["file"], f"stage {st['id']}", st["look"])
              for s in model["steps"] for st in s.get("stages", [])]
    for where, what, look in looks:
        for field in ("model", "texture", "icon"):
            path = look.get(field)
            if path and unshipped(path):
                problems.append(f"{where}: {what} {field} is not a shipped asset: {path}")
    fixture_looks = [{"file": "fixtures.json", "look": lk}
                     for lk in model["fixtures"].get("looks", {}).values()]
    for s in list(stations.values()) + fixture_looks:
        for field, path in s.get("look", {}).items():
            if isinstance(path, str) and path.endswith((".png", ".blockymodel")) \
                    and unshipped(path):
                problems.append(f"{s['file']}: look {field} is not a shipped asset: {path}")

    return problems
