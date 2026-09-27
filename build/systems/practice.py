"""
THE PRACTICE SYSTEM: a kitchen to try things in -- guests come and eat, and nothing counts.

    the room's SIGN                   ->  guests on / off: pressed, it turns them on (the
                                          sign shows open), again, off. OFF to start, so a
                                          dish can be picked before anyone comes
    guests on, fewer than MAX_GUESTS  ->  a guest arrives every few seconds, wanting any
    guests about                          dish on the menu (a fair pick)
    press CALL A GUEST                ->  one arrives now
    press a dish's PRACTICE block     ->  from now on every guest wants THAT dish (any of
                                          its versions: cooked or well done)
    press ANY DISH                    ->  back to the whole menu
    always                            ->  the stations stay put: the service lock is on
                                          for good, so nothing can be picked up or broken
                                          -- or carried out of practice into a real run

There's no shift: no days, no purse, no cards, no losing, no records and no franchise picks.
Every guest arrives with the "practice" mood (systems/moods.py): five times the patience,
"(practice)" on its name tag. Its world is thrown away when the last player leaves, so every
visit starts clean.

HOW IT'S JOINED: the pool spawns guests on the arrival channel (signals.to_pool), as the
shift's would; the practice mood is rolled at every guest by the mood system (the chances the
builder hands it: model["mood_chances"]).
"""
import blocks
import carry
import settings
import signals
import volumes as v

MAX_GUESTS = 3        # while fewer than this are about, another arrives...
EVERY = 15.0          # ...this often: seconds


def ids(model):
    prefix = model["theme"]["prefix"]
    gid = lambda local: settings.game_id(prefix, local)
    return {"call": gid("practice_call"), "effect": gid("practice_system"),
            "lock": gid("practice_lock"), "any": gid("practice_any"),
            "sign": gid("practice_sign"), "sign_on": gid("practice_sign_on"),
            "dish": lambda d: gid(f"practice_dish_{d}")}


def dishes(model):
    """[(dish id, label, [its menu entries])], in menu order: what the picker offers."""
    out = {}
    for e in model["menu"]:
        out.setdefault(e["dish"], []).append(e)
    return [(d, model["dishes"][d]["label"], es) for d, es in out.items()]


def picker_blocks(model):
    """THE RECIPE PICKER: a block per dish (the dish itself, plated) and ANY DISH."""
    p = ids(model)
    blocks.station_block(p["any"], "Practice: any dish", {
        "sides": "BlockTextures/Wood_Softwood_Planks_Side.png",
        "top": "BlockTextures/Wood_Softwood_Planks_Side.png", "sound": "Wood"},
        "Press: guests order any dish", "Practice: the whole menu. See build/systems/practice.py.",
        tint="#3c8a5c")
    for d, label, es in dishes(model):
        look = model["items"][es[0]["serves"]]["look"]
        blocks.display_block(p["dish"](d), f"Practice: {label}", look,
                             f"Press: guests order {label} only",
                             "Practice: one dish. See build/systems/practice.py.")


def build(model, roles, debug=True):
    """The arrivals and the call block (one volume), and the lock's effect. `roles`: {menu
    entry serves-id: guest role}. Returns {"effect", "lock"}."""
    p = ids(model)
    look = {"sides": "BlockTextures/Wood_Softwood_Planks_Side.png",
            "top": "BlockTextures/Wood_Softwood_Planks_Side.png", "sound": "Wood"}
    blocks.station_block(p["call"], "Call a guest", look, "Press to call a practice guest now",
                         "Practice: calls a guest. See build/systems/practice.py.",
                         tint="#3c8a5c")
    guests = list(roles.values())
    picker_blocks(model)
    # THE SIGN: guests on and off, drawn as the theme's open sign (closed: off, open: on).
    sign = model["fixtures"]["looks"]["sign"]
    note = "Practice: guests on and off. See build/systems/practice.py."
    blocks.station_block(p["sign"], "Practice sign (guests off)", sign,
                         "Press: guests start coming", note, tint=sign.get("closed_tint"))
    blocks.station_block(p["sign_on"], "Practice sign (guests on)", sign,
                         "Press: guests stop coming", note, tint=sign.get("open_tint"))
    on = {"Type": "TagCondition", "Event": "TICK", "Source": "Self", "TagKey": "open",
          "Comparison": "Exactly", "TagValue": "1"}
    focus = lambda event, value: {"Type": "TagCondition", "Event": event, "Source": "Self",
                                  "TagKey": "focus", "Comparison": "Exactly",
                                  "TagValue": str(value)}
    rules = v.Entries()
    entered = {"Type": "ModifyTags", "Event": "ENTER", "Operation": "Set", "TagKey": "entered",
               "TagValue": "1"}   # a TICK rule's first pass only activates it without one
    for event, start in (
            ("TICK", [on,
                      {"Type": "EntityCountCondition", "Event": "TICK", "EntityType": guests,
                       "Comparison": "AtMost", "Count": MAX_GUESTS - 1},
                      {"Type": "CooldownCondition", "Event": "TICK", "Cooldown": EVERY,
                       "Scope": "WholeVolume"}]),
            ("BLOCK_USED", [v.at([p["call"]])])):
        base = 100 if event == "TICK" else 300
        put = lambda val: {"Type": "ModifyTags", "Event": event, "Operation": "Set",
                           "TagKey": "going", "TagValue": str(val)}
        going = {"Type": "TagCondition", "Event": event, "Source": "Self", "TagKey": "going",
                 "Comparison": "Exactly", "TagValue": "1"}
        rules.add(base, start, [put(1)] + ([entered] if event == "TICK" else []))
        # THE FAIR PICK: each entry in turn at 1/(entries left); the first that lands sends
        # its guest and stops the pick. Among the whole menu (focus 0), or the picked dish's
        # entries (focus n: the picker's dish n).
        groups = [(0, model["menu"])] + [(n, es) for n, (_, _, es) in
                                         enumerate(dishes(model), start=1)]
        rule = base + 1
        for f, menu in groups:
            for k, e in enumerate(menu):
                left = len(menu) - k
                rules.add(rule,
                          [going, focus(event, f)]
                          + ([{"Type": "RandomChanceCondition", "Event": event,
                               "Chance": round(1.0 / left, 4)}] if left > 1 else []),
                          [signals.to_pool(event, roles[e["serves"]]), put(0)]
                          + ([entered] if event == "TICK" else [])
                          + v.report(f"kk.practice.{event}.{rule}",
                                     f"[practice] a guest arrives (wants {e['label']})", debug,
                                     event=event))
                rule += 1
    # THE SIGN: which block was pressed says which way it goes (the swap lands at the end of
    # the tick, so only one of the two matches a press).
    open_ = lambda value: {"Type": "ModifyTags", "Event": "BLOCK_USED", "Operation": "Set",
                           "TagKey": "open", "TagValue": str(value)}
    rules.add(490, [v.at([p["sign"]])],
              [v.cell([p["sign"]], p["sign_on"]), open_(1),
               v.say("kk.practice.on", "Practice: guests are coming"), v.sound(0.9)])
    rules.add(491, [v.at([p["sign_on"]])],
              [v.cell([p["sign_on"]], p["sign"]), open_(0),
               v.say("kk.practice.off", "Practice: no more guests (the ones here stay)"),
               v.sound(0.9)])
    # THE PICKER: which dish guests want from now on (said to everyone: it's the room's).
    set_focus = lambda value: {"Type": "ModifyTags", "Event": "BLOCK_USED", "Operation": "Set",
                               "TagKey": "focus", "TagValue": str(value)}
    rules.add(500, [v.at([p["any"]])],
              [set_focus(0), v.say("kk.practice.any", "Practice: guests order any dish"),
               v.sound(0.9)])
    for n, (d, label, _) in enumerate(dishes(model), start=1):
        rules.add(500 + n, [v.at([p["dish"](d)])],
                  [set_focus(n), v.say(f"kk.practice.dish.{d}",
                                       f"Practice: guests order {label} only"), v.sound(0.9)])
    rules.write(p["effect"], "Practice: guests arrive by themselves. "
                             "See build/systems/practice.py.")
    lock = v.Entries()
    lock.add(1, [], [carry.in_service_mark()])
    lock.write(p["lock"], "Practice: the service lock, on for good. See build/systems/practice.py.")
    return p


def volumes(model, box=v.WORLD_BOX):
    """The arrivals' volume, and the lock (on for good: its rules stop building and
    breaking, and its effect marks every player in service, so nothing can be picked up)."""
    p = ids(model)
    lock = v.volume("practice_lock", p["lock"], {"servicelock": "1"}, box=box)
    lock.update({"Enabled": True, "Rules": [{"Type": "NoBuild"}, {"Type": "NoDestroy"}],
                 "RulesActive": True})
    return [v.volume("practice", p["effect"], {"practice": "1", "focus": "0", "open": "0"},
                     box=box), lock]
