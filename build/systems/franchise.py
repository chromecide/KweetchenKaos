"""
THE FRANCHISE SYSTEM: items a player banks by reaching day 15, and brings into later runs.

    a run's day 15 ends        ->  franchise items on pads 1-3 (pad 4 still sells): each
                                   player picks ONE, banked on them (once per run)
    in HQ, press a SHELF       ->  one of that item, and your count goes down; press it
                                   holding one, and it goes back (the count goes up); it
                                   says your count after each
    in a restaurant            ->  put a station down; press the open sign holding a token:
                                   start coins (+coins) or a recipe (the dish goes on the
                                   menu -- spent anyway if it's already there)

WHAT CAN BE BANKED: everything the pads sell (stations, plain or upgraded; chairs; mats), start
coins, and a recipe token per dish. A count per item, per player (a stat each: it outlives
the run and a restart; death resets it -- rooms keep players in with barriers).

What the probes taught (the `franchise` and `storeroom` spikes):
  * items are given with ModifyInventory (AddItem is checked before this pack's items load,
    and thrown out); NOTHING after it in a chain runs -- so it comes last, and the count's
    message is an interaction of its own;
  * a take can put the item straight into an empty hand, and the return rule, checked next
    in the same press, saw it: a `took` tag keeps a press to one of the two;
  * a count can't be printed, only checked by threshold: it's told as "N banked", up to "9+".

HOW IT'S JOINED: plain data and interactions. The pads read `offer_rules` for their franchise
cards; the shift spends tokens (`tokens`); the world lays out shelves (`shelf_blocks`) with a
companion volume each (`shelf_volume`), and runs `reset` on a player arriving at a restaurant.
"""
import blocks
import offers
import pack
import settings
import volumes as v

COUNT_TOP = 9                # a count is told exactly up to this, then "9+"
STAT_MAX = 99


def title(key):
    return "_".join(p.capitalize() for p in key.split("_"))


def items(model):
    """[(key, label, item game id, look)] -- everything a player can bank, in order:
    what the pads sell, start coins, then a recipe token per dish."""
    blueprint = model["fixtures"]["looks"]["blueprint"]
    out = []
    for c in offers.catalogue(model):
        look = c["look"] if "model" in c["look"] else blueprint   # a cube station: its blueprint
        out.append((c["key"], c["label"], c["item"], look))
    it = model["items"]
    out.append(("start_coins", "Start coins", it["start_coins"]["game_id"],
                it["start_coins"]["look"]))
    for d, dish in model["dishes"].items():
        tok = it[f"recipe_{d}"]
        out.append((f"recipe_{d}", f"Recipe: {dish['label']}", tok["game_id"], tok["look"]))
    return out


def stat(model, key):
    return settings.game_id(model["theme"]["prefix"], f"franchise_{key}")


def picked_stat(model):
    return settings.game_id(model["theme"]["prefix"], "franchise_picked")


def _root(model, name, interaction):
    rid = settings.game_id(model["theme"]["prefix"], f"franchise_{name}")
    pack.write(pack.out("Item", "RootInteractions", settings.NAMESPACE, f"{rid}.json"),
               {"$Comment": "The franchise. See build/systems/franchise.py.",
                "Interactions": [interaction]})
    return rid


def _say(key, text):
    pack.say(key, text)
    return f"server.{key}"


def _count(model, key, label):
    """Say the count: exactly up to COUNT_TOP, then "N+" -- the highest threshold first."""
    st = stat(model, key)
    chain = {"Type": "SendMessage", "Key": _say(f"kk.franchise.{key}.0", f"{label}: none banked")}
    for k in range(1, COUNT_TOP + 1):
        chain = {"Type": "StatsCondition", "Costs": {st: k}, "ValueType": "Absolute",
                 "LessThan": False,
                 "Next": {"Type": "SendMessage", "Key": _say(
                     f"kk.franchise.{key}.{k}",
                     f"{label}: {k}{'+' if k == COUNT_TOP else ''} banked")},
                 "Failed": chain}
    return chain


def build(model):
    """Every stat and interaction; returns {key: {"earn", "take", "back", "tell"}} root ids
    (and "reset" under None). Also puts the pads' data in the model: model["franchise"] =
    {"cards": [(key, card block, earn root)]} -- the pads read it, never this module."""
    pk = picked_stat(model)
    pack.write(pack.out("Entity", "Stats", settings.NAMESPACE, f"{pk}.json"), {
        "$Comment": "Whether a player has picked their franchise item this run. "
                    "See build/systems/franchise.py.",
        "InitialValue": 0, "Min": 0, "Max": 1})
    roots = {None: {"reset": _root(model, "reset", {
        "Type": "ChangeStat", "StatModifiers": {pk: 0}, "ValueType": "Absolute",
        "Behaviour": "Set"})}}
    for key, label, item, _ in items(model):
        st = stat(model, key)
        pack.write(pack.out("Entity", "Stats", settings.NAMESPACE, f"{st}.json"), {
            "$Comment": f"{label}s banked in a player's franchise. See build/systems/franchise.py.",
            "InitialValue": 0, "Min": 0, "Max": STAT_MAX})
        t = title(key)
        roots[key] = {
            # EARN, once per run: not picked yet? bank it, and mark picked.
            "earn": _root(model, f"earn_{t}", {
                "Type": "StatsCondition", "Costs": {pk: 1}, "ValueType": "Absolute",
                "LessThan": True,
                "Next": {"Type": "Serial", "Interactions": [
                    {"Type": "ChangeStat", "StatModifiers": {st: 1}, "ValueType": "Absolute",
                     "Behaviour": "Add"},
                    {"Type": "ChangeStat", "StatModifiers": {pk: 1}, "ValueType": "Absolute",
                     "Behaviour": "Set"},
                    {"Type": "SendMessage", "Key": _say(f"kk.franchise.{key}.earned",
                                                        f"Banked in your franchise: {label}")}]},
                "Failed": {"Type": "SendMessage", "Key": _say(
                    "kk.franchise.already", "You've already picked your franchise item this run.")}}),
            # TAKE: the count down, then the item -- LAST (nothing after it runs).
            "take": _root(model, f"take_{t}", {
                "Type": "StatsCondition", "Costs": {st: 1}, "ValueType": "Absolute",
                "LessThan": False,
                "Next": {"Type": "Serial", "Interactions": [
                    {"Type": "ChangeStat", "StatModifiers": {st: -1}, "ValueType": "Absolute",
                     "Behaviour": "Add"},
                    {"Type": "ModifyInventory", "ItemToAdd": {"Id": item, "Quantity": 1}}]},
                "Failed": {"Type": "Simple"}}),
            "back": _root(model, f"back_{t}", {
                "Type": "ChangeStat", "StatModifiers": {st: 1}, "ValueType": "Absolute",
                "Behaviour": "Add"}),
            "tell": _root(model, f"tell_{t}", _count(model, key, label)),
        }
    model["franchise"] = {"cards": [(k, card_block(model, k), roots[k]["earn"])
                                    for k, *_ in items(model)],
                          "reset": roots[None]["reset"]}
    card_blocks(model)
    return roots


# ---------------------------------------------------------------- the pads: franchise cards

def card_block(model, key):
    return settings.game_id(model["theme"]["prefix"], f"pad_franchise_{key}")


def card_blocks(model):
    """The franchise cards a pad can show (a purple blueprint, the item's name on hover)."""
    look = dict(model["fixtures"]["looks"]["blueprint"], tint="#9a5ac8")
    for key, label, _, _ in items(model):
        blocks.display_block(card_block(model, key), f"Franchise: {label}", look,
                             f"Franchise: {label} - press to bank it (one per run)",
                             "A franchise card. See build/systems/franchise.py.")
    return [card_block(model, k) for k, *_ in items(model)]


# ---------------------------------------------------------------- the shelves (HQ)

def shelf_id(model, key):
    return settings.game_id(model["theme"]["prefix"], f"franchise_shelf_{key}")


def shelf_blocks(model):
    """Every shelf and what's shown on it: {key: (shelf block, top block)}."""
    look = {"sides": "BlockTextures/Wood_Softwood_Planks_Side.png",
            "top": "BlockTextures/Soil_Snow.png", "sound": "Wood"}
    out = {}
    for key, label, _, item_look in items(model):
        shelf = shelf_id(model, key)
        top = f"{shelf}_Top"
        text = f"{label} - press to take one, or press holding one to put it back"
        blocks.station_block(shelf, f"Franchise shelf: {label}", look, text,
                             "A franchise shelf. See build/systems/franchise.py.", tint="#c08a3a")
        blocks.display_block(top, f"{label} (on the shelf)", item_look, text,
                             "A franchise shelf. See build/systems/franchise.py.")
        out[key] = (shelf, top)
    return out


def shelf_volume(model, key, roots):
    """A shelf's rules, in a volume of its own: its effect's name. TAKE (not holding the
    item) before RETURN (holding it); a take marks the press (`took`) so the return rule
    skips it; the count said after either."""
    shelf = shelf_id(model, key)
    top = f"{shelf}_Top"
    item = next(i for k, _, i, _ in items(model) if k == key)
    r = roots[key]
    run = lambda rid: {"Type": "RunRootInteraction", "Event": "BLOCK_USED", "RootInteraction": rid}
    took = lambda value: {"Type": "TagCondition", "Event": "BLOCK_USED", "Source": "Self",
                          "TagKey": "took", "Comparison": "Exactly", "TagValue": value}
    put = lambda value: {"Type": "ModifyTags", "Event": "BLOCK_USED", "Operation": "Set",
                         "TagKey": "took", "TagValue": value}
    rules = v.Entries()
    for n, where in enumerate(([v.at([shelf])], [v.at([top])])):
        rules.add(1 + n, where + [v.not_holding(item)], [run(r["take"]), run(r["tell"]), put("1")])
        rules.add(3 + n, where + [took("0"), v.holding(item)],
                  [run(r["back"]), run(r["tell"]), v.sound(0.9)])
    rules.add(9, [took("1")], [put("0")])
    name = f"{shelf}_System"
    rules.write(name, f"A franchise shelf ({key}). See build/systems/franchise.py.")
    return name
