"""
THE PRACTICE SYSTEM: a kitchen to try things in -- guests come and eat, and nothing counts.

    players in the room, fewer than   ->  a guest arrives every few seconds, wanting any
    MAX_GUESTS guests about               dish on the menu (a fair pick)
    press CALL A GUEST                ->  one arrives now
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
            "lock": gid("practice_lock")}


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
    rules = v.Entries()
    entered = {"Type": "ModifyTags", "Event": "ENTER", "Operation": "Set", "TagKey": "entered",
               "TagValue": "1"}   # a TICK rule's first pass only activates it without one
    for event, start in (
            ("TICK", [{"Type": "EntityCountCondition", "Event": "TICK", "EntityType": guests,
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
        # THE FAIR PICK: each menu entry in turn at 1/(entries left); the first that lands
        # sends its guest and stops the pick.
        menu = model["menu"]
        for k, e in enumerate(menu):
            rules.add(base + 1 + k,
                      [going, {"Type": "RandomChanceCondition", "Event": event,
                               "Chance": round(1.0 / (len(menu) - k), 4)}],
                      [signals.to_pool(event, roles[e["serves"]]), put(0)]
                      + ([entered] if event == "TICK" else [])
                      + v.report(f"kk.practice.{event}.{k}",
                                 f"[practice] a guest arrives (wants {e['label']})", debug,
                                 event=event))
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
    return [v.volume("practice", p["effect"], {"practice": "1"}, box=box), lock]
