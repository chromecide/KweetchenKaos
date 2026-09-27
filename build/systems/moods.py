"""
THE MOOD SYSTEM: what kind of guest this is -- impatient, relaxed, messy -- rolled as it arrives.

    a guest steps into the line  ->  for each mood in play, a roll at its chance: a roll that
                                     lands marks the guest with it
    it stands in line            ->  it reads its marks, ONCE, and they're its moods for good
    its moods then               ->  impatient: every patience clock ⅔ as long; relaxed: 1.5
                                     times as long; messy: a mess round its chair as it gets up
                                     -- each shown on its name tag, e.g. "(impatient, messy)"

Moods sit on TRACKS, rolled independently, so a guest has at most one mood per track and can
have one from each: PATIENCE (impatient or relaxed) and TIDINESS (messy). Last roll wins
WITHIN a track: a roll that lands takes off the other moods on its track only -- relaxed can
replace impatient, but nothing a messy roll does touches patience.

Which moods are in play, and at what chance: a spike's "moods" (always), and each CUSTOMER
CARD's (rules customers.json: rolled only once that card is chosen -- the shift's
"card_<id>" tag). Rolls go in that order, the cards in their file's order. A mood not in
play is never rolled, but every guest can still carry it.

HOW IT'S JOINED, without any system importing another: `build` writes the marks and puts
plain DATA in the model (model["moods"]) --

    arrival   [(mark, chance, [marks it takes off], gate)]: what a queue spot rolls
              (queue.py); `gate`, if any, is (a tag of the shift's, the level it must
              reach first) -- a customer card's ("card_<id>", 1), set when it's chosen, or
              overtime's ("ot_patience", level)
    flags     {mood: flag}: what a guest carries once it has read its marks
    combos    every mix of moods, most specific first, with its patience factor and the
              words for its name tag (systems/guest.py uses them for its clocks)

-- and the guest composer (build/guests.py) puts `read_branches` into a guest.

Why the roll is on the first queue spot, and read once: rolled in the pool at first, a
guest wandering in and out of it while the line was full rolled again each time. A mark is
invisible (a tint would wash the model out) and only has to last until it's read.
"""
import itertools

import npc
import pack
import settings

# mood: (track, patience factor, the word on its name tag -- None: not shown)
MOODS = {"impatient": ("patience", 2 / 3, "impatient"),
         "relaxed": ("patience", 1.5, "relaxed"),
         "messy": ("tidiness", 1.0, "messy")}
# PRESSURE: overtime's patience squeeze (systems/shift.py). Every guest arrives HURRIED once
# the shift's `ot_patience` reaches a level -- each level 15% less patience -- on its own
# track, so it stacks with impatient or relaxed. Not shown: everyone has it.
PRESSURE_LEVELS = 6               # the most there can be; the rules' overtime.patience says how many
for _k in range(1, PRESSURE_LEVELS + 1):
    MOODS[f"hurried_{_k}"] = ("pressure", round(0.85 ** _k, 3), None)
TRACKS = ("patience", "tidiness", "pressure")
MARK_SECONDS = 600.0


def mark(model, mood):
    return settings.game_id(model["theme"]["prefix"], f"guest_mood_{mood}")


def flag(mood):
    return f"mood_{mood}"


def card_tag(card_id):
    """The shift's tag that says a customer card has been chosen (systems/shift.py)."""
    return f"card_{card_id}"


def _read(track):
    return f"mood_read_{track}"


def build(model):
    """Write every mood's mark, and put the moods' data in the model (see the top of this
    file). The moods in play and their chances: model["mood_chances"] ({mood: chance})."""
    for mood in MOODS:
        pack.write(pack.out("Entity", "Effects", settings.NAMESPACE, f"{mark(model, mood)}.json"), {
            "$Comment": f"An arriving guest marked {mood}. See build/systems/moods.py.",
            "Duration": MARK_SECONDS, "OverlapBehavior": "Overwrite"})
    chances = model.get("mood_chances", {})
    for mood in chances:
        if mood not in MOODS:
            raise SystemExit(f"no mood '{mood}' (moods: {', '.join(MOODS)})")
    others = lambda m: [mark(model, o) for o in MOODS if o != m and MOODS[o][0] == MOODS[m][0]]
    arrival = [(mark(model, m), c, others(m), None) for m, c in chances.items()]
    for card in model.get("rules", {}).get("customers", {}).get("cards", []):
        arrival += [(mark(model, m), c, others(m), (card_tag(card["id"]), 1))
                    for m, c in card.get("moods", {}).items()]
    # Overtime's pressure, a level at a time: the highest level reached rolls last and wins.
    levels = model.get("rules", {}).get("overtime", {}).get("patience", 0)
    assert levels <= PRESSURE_LEVELS, f"overtime patience: at most {PRESSURE_LEVELS} levels"
    arrival += [(mark(model, f"hurried_{k}"), 1.0, others(f"hurried_{k}"), ("ot_patience", k))
                for k in range(1, levels + 1)]
    per_track = [[None] + [m for m in MOODS if MOODS[m][0] == t] for t in TRACKS]
    combos = []
    for mix in itertools.product(*per_track):
        moods = [m for m in mix if m]
        if not moods:
            continue
        factor = 1.0
        for m in moods:
            factor *= MOODS[m][1]
        combos.append({"flags": [flag(m) for m in moods], "patience": factor,
                       "words": ", ".join(MOODS[m][2] for m in moods if MOODS[m][2])})
    combos.sort(key=lambda c: -len(c["flags"]))
    model["moods"] = {"arrival": arrival, "flags": {m: flag(m) for m in MOODS},
                      "combos": combos}


def read_branches(model):
    """Branches (each Continue) for a guest standing in line: read its marks, once per
    track, into flags; then, once, show its moods on its name tag."""
    out = []
    for track in TRACKS:
        done = npc.flag(_read(track))
        for mood in [m for m in MOODS if MOODS[m][0] == track]:
            out.append(npc.branch(f"First time in line, marked {mood}: remember it.",
                                  npc.all_of(npc.no(done), npc.has_effect(mark(model, mood))),
                                  None, [npc.set_flag(flag(mood))], cont=True))
        out.append(npc.branch(f"First time in line: its {track} is read, for good.",
                              npc.no(done), None, [npc.set_flag(_read(track))], cont=True))
    shown = npc.flag("mood_shown")
    for combo in model["moods"]["combos"]:
        if not combo["words"]:
            continue                      # nothing to show (the pressure track alone)
        out.append(npc.branch(f"Show its moods: {combo['words']}.",
                              npc.all_of(npc.no(shown), *[npc.flag(f) for f in combo["flags"]]),
                              None, [npc.set_flag("mood_shown"),
                                     npc.name_tag(f"Waiting ({combo['words']})")], cont=True))
    out.append(npc.branch("No moods to show.", npc.no(shown), None,
                          [npc.set_flag("mood_shown")], cont=True))
    return out
