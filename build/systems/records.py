"""
THE RECORD SYSTEM: each player's best day at each restaurant, remembered between runs.

    a run passes a milestone  ->  every player in the room has it recorded as their best
    (day 5, 10, 15 ...)           there -- only ever raised, never lowered
    arriving at a restaurant  ->  "Your best at KweebecKlub: day 15+"
    arriving at HQ            ->  the same line for every restaurant

WHERE IT LIVES: a run's world is thrown away and HQ is rebuilt on a restart, so the best is
kept on the PLAYER, as a stat of their own per restaurant (proved in the bestrun probe: it
survives a restart). A volume writes it with RunRootInteraction -> ChangeStat, Behaviour Max:
the higher of the best and the new one, in one step. It can only be read back by threshold
(StatsCondition: "at least N?"), so it's kept -- and shown -- as the last milestone passed:
the rules' "milestones" days, and best_from before the first.

THE CATCH: death resets every stat. Falling into the void is the only way to die here, so
every room and HQ keep players in with barriers.

HOW IT'S JOINED: `recorder` is a companion volume beside the shift (volumes.companion) --
it reads the shift's day, and writes the stat to each player inside, once they're past a
milestone (a per-player beat, so every player gets it). `show` is a root interaction the
world runs on an arriving player.
"""
import pack
import settings
import signals
import volumes as v

BEAT = 5.0            # how often a player in the room is checked: seconds


def brackets(model):
    """The bests there are, lowest first: best_from, then the milestone days."""
    ms = model["rules"].get("milestones", {})
    return sorted({ms.get("best_from", 5), *ms.get("days", [])})


def stat(model, restaurant):
    return settings.game_id(model["theme"]["prefix"], f"best_{restaurant}")


def _root(model, name):
    return settings.game_id(model["theme"]["prefix"], f"records_{name}")


def build(model, restaurant, label):
    """The stat for `restaurant` (its layout id; "spike" in a spike), and the recorder, a
    companion volume. `label`: the restaurant's name, for the lines that show it."""
    st = stat(model, restaurant)
    pack.write(pack.out("Entity", "Stats", settings.NAMESPACE, f"{st}.json"), {
        "$Comment": f"A player's best day at {label}. See build/systems/records.py.",
        "InitialValue": 0, "Min": 0, "Max": 1000})
    rules = v.Entries()
    for k, b in enumerate(brackets(model)):
        root = _root(model, f"{restaurant}_{b}")
        pack.write(pack.out("Item", "RootInteractions", settings.NAMESPACE, f"{root}.json"), {
            "$Comment": f"Record day {b} as a best at {label}. See build/systems/records.py.",
            "Interactions": [{"Type": "ChangeStat", "StatModifiers": {st: b},
                              "ValueType": "Absolute", "Behaviour": "Max"}]})
        # Past day b (the day count is b + 1 once it's done): recorded, for each player
        # inside, on their own beat. Harmless to repeat: Max never lowers it.
        rules.add(1 + k, [signals.shift_reads("TICK", signals.DAY, "AtLeast", b + 1),
                          {"Type": "CooldownCondition", "Event": "TICK", "Cooldown": BEAT,
                           "Scope": "PerPlayer"}],
                  [{"Type": "RunRootInteraction", "Event": "TICK", "RootInteraction": root}])
    name = f"{settings.NAMESPACE}_Records_{restaurant}"
    rules.write(name, f"Remembers each player's best at {label}. See build/systems/records.py.")
    v.companion(name, {"records": restaurant})
    show(model, restaurant, label)


def _chain(model, restaurant, label):
    """The read-back: at least the highest best? say it; else the next ... else none yet."""
    st = stat(model, restaurant)
    none = f"kk.records.{restaurant}.none"
    pack.say(none, f"{label}: no best yet - get past day {brackets(model)[0]}")
    chain = {"Type": "SendMessage", "Key": f"server.{none}"}
    for b in brackets(model):
        key = f"kk.records.{restaurant}.{b}"
        pack.say(key, f"Your best at {label}: day {b}+")
        chain = {"Type": "StatsCondition", "Costs": {st: b}, "ValueType": "Absolute",
                 "LessThan": False, "Next": {"Type": "SendMessage", "Key": f"server.{key}"},
                 "Failed": chain}
    return chain


def show(model, restaurant, label):
    """A root interaction that tells the player their best at `restaurant`; returns its id."""
    root = _root(model, f"show_{restaurant}")
    pack.write(pack.out("Item", "RootInteractions", settings.NAMESPACE, f"{root}.json"), {
        "$Comment": f"Tell a player their best at {label}. See build/systems/records.py.",
        "Interactions": [_chain(model, restaurant, label)]})
    return root


def show_all(model, restaurants):
    """A root interaction that tells the player their best at each of `restaurants`
    ([(layout id, name)]) -- for HQ. Returns its id."""
    root = _root(model, "show_all")
    pack.write(pack.out("Item", "RootInteractions", settings.NAMESPACE, f"{root}.json"), {
        "$Comment": "Tell a player their best at every restaurant. See build/systems/records.py.",
        "Interactions": [{"Type": "Serial",
                          "Interactions": [_chain(model, r, label) for r, label in restaurants]}]})
    return root


def forget(model, restaurant):
    """A root interaction that clears a best (the endgame spike). Returns its id."""
    root = _root(model, f"forget_{restaurant}")
    pack.write(pack.out("Item", "RootInteractions", settings.NAMESPACE, f"{root}.json"), {
        "$Comment": "Spike only: forget a best. See build/systems/records.py.",
        "Interactions": [{"Type": "ChangeStat", "StatModifiers": {stat(model, restaurant): 0},
                          "ValueType": "Absolute", "Behaviour": "Set"}]})
    return root
