"""
THE GUEST SYSTEM: what a guest does once it has a seat -- order, wait, eat, leave.

    sits                      ->  "Ready to order"; a short patience clock starts
    a player presses it (F)   ->  the order is taken: the dish shows on its name tag, and a
                                  fresh, longer clock starts for the food
    served the RIGHT dish     ->  it eats a while, gets up fed (a dirty plate on its table),
                                  and reports "served" and what it paid
    served the WRONG dish     ->  the food is gone (the engine always takes it); it gets up
    (or any dish before           at once, leaving its plate like a guest who ate, and walks
    ordering)                     out UNPAID -- "turned away", which costs money and a table,
                                  never the run
    a clock runs out          ->  it gets up without eating and reports "angry"

IMPATIENCE SHOWS: at half its patience a guest pulses amber, at three quarters red -- a
short tint re-applied on a beat. (Long tints layered up washed the model out and can't be
taken off; short ones expire and leave it clean, so being served just stops the beat.)

Ported from the Kitchen POC (docs/systems.md, GuestSystem). Behaviour only: no blocks, no
volume. It hands the composing guest (build/guests.py) its seated branches and the
interaction branches, and names nothing of seating's -- getting up is whatever `on_fed` and
`on_unfed` the composer hands in.

  * ONLY INTERACTABLE WHILE SEATED: a dish used on any interactable NPC is taken, so a
    queued guest must not be one.
  * EVERY CLOCK IS ITS OWN: a timer keeps the durations it was first started with, so each
    phase has its own patience and warning clocks, and each pulse colour its own beat.
"""
import blocks
import npc
import pack
import serving
import settings
import signals

PULSES = {"amber": ("#d08a20", "#f0b040", 1.5, 3.0), "red": ("#d01810", "#f03020", 0.75, 1.5)}
WARN_FIRST, WARN_LAST = 0.5, 0.75          # fraction of patience GONE at each warning
F = lambda name: f"guest_{name}"


def pulse_id(model, colour):
    return settings.game_id(model["theme"]["prefix"], f"guest_pulse_{colour}")


# MOODS: a guest can arrive with a mood (the queue's spots mark it at random; it reads the
# mark once, into a flag, the first time it stands in line). IMPATIENT: every patience clock runs at this fraction.
IMPATIENT = 0.5
MOOD_FLAG = F("impatient")


def mood_effect(model):
    """The mark a queue spot puts on an arriving guest that is to be impatient. Invisible (a
    tint would wash the model out); it only has to last until the guest reads it."""
    gid = settings.game_id(model["theme"]["prefix"], "guest_mood_impatient")
    pack.write(pack.out("Entity", "Effects", settings.NAMESPACE, f"{gid}.json"), {
        "$Comment": "An arriving guest marked impatient. See build/systems/guest.py.",
        "Duration": 600.0, "OverlapBehavior": "Overwrite"})
    return gid


def read_mood(model):
    """Branches (each Continue) for the moment a guest first stands in line: read the mark
    once, into a flag, and never again."""
    decided, mark = F("mood_read"), mood_effect(model)
    return [npc.branch("First time in line, and marked impatient: remember it.",
                       npc.all_of(npc.no(npc.flag(decided)), npc.has_effect(mark)), None,
                       [npc.set_flag(decided), npc.set_flag(MOOD_FLAG),
                        npc.name_tag("Waiting (impatient)")], cont=True),
            npc.branch("First time in line, not marked: calm, for good.",
                       npc.no(npc.flag(decided)), None, [npc.set_flag(decided)], cont=True)]


def build(model, debug=True):
    """What every guest shares: the pulse effects."""
    for colour, (bottom, top, on, _) in PULSES.items():
        npc.entity_effect(pulse_id(model, colour), on, bottom, top,
                          "A guest's impatience pulse. See build/systems/guest.py.")


def _phase(model, tag, patience, on_out, name_text):
    """One patience phase ("a": waiting to be asked; "b": waiting for food)."""
    started = npc.flag(F(f"{tag}_started"))
    out = [npc.branch(f"Phase {tag}: out of patience.",
                      npc.all_of(started, npc.stopped(F(f"{tag}_patience"))), npc.STILL,
                      list(on_out))]
    for colour, warn, quieter in (("red", "warn2", []), ("amber", "warn1", ["warn2"])):
        every = PULSES[colour][3]
        out.append(npc.branch(
            f"Phase {tag}: {colour} pulse, whenever the beat runs out (amber goes quiet once "
            f"red starts).",
            npc.all_of(started, npc.stopped(F(f"{tag}_{warn}")),
                       *[npc.no(npc.stopped(F(f"{tag}_{o}"))) for o in quieter],
                       npc.stopped(F(f"beat_{colour}"))),
            npc.STILL,
            [{"Type": "ApplyEntityEffect", "EntityEffect": pulse_id(model, colour),
              "UseTarget": False}, *npc.timer(F(f"beat_{colour}"), every)]))
    start = lambda secs, text: [npc.set_flag(F(f"{tag}_started")),
                                npc.once(F(f"{tag}_patience"), secs),
                                npc.once(F(f"{tag}_warn1"), round(secs * WARN_FIRST, 2)),
                                npc.once(F(f"{tag}_warn2"), round(secs * WARN_LAST, 2)),
                                npc.name_tag(text)]
    out += [
        npc.branch(f"Phase {tag}: waiting.", started, npc.STILL),
        npc.branch(f"Phase {tag}: start its clocks, SHORTER - an impatient guest.",
                   npc.flag(MOOD_FLAG), npc.STILL,
                   start(round(patience * IMPATIENT, 2), f"{name_text} (impatient)")),
        npc.branch(f"Phase {tag}: start its clocks (the flag proves they were started).",
                   {"Type": "Any"}, npc.STILL, start(patience, name_text)),
    ]
    return out


def fragment(model, entry, on_fed=(), on_unfed=()):
    """(seated branches, interaction branches) for a guest who wants menu `entry`."""
    items = model["items"]
    wanted = items[entry["serves"]]
    menu_id = entry["serves"]
    leave_angry = [npc.set_flag(F("gone")), *on_unfed,
                   signals.from_npc(signals.GUEST, signals.ANGRY),
                   npc.name_tag("Leaving - angry")]
    leave_refused = [npc.set_flag(F("gone")), *on_fed,
                     signals.from_npc(signals.GUEST, signals.TURNED_AWAY),
                     npc.name_tag("Leaving - wrong dish")]
    leave_happy = [npc.set_flag(F("gone")), *on_fed,
                   signals.from_npc(signals.GUEST, signals.SERVED),
                   signals.from_npc(signals.PAID, menu_id),
                   npc.name_tag("Leaving - happy")]

    seated = [
        npc.branch("Got up: whoever composed the guest takes it from here.",
                   npc.flag(F("gone")), npc.STILL),
        npc.branch("Finished eating: get up fed, and report.",
                   npc.all_of(npc.flag(F("served")), npc.stopped(F("eat"))), npc.STILL,
                   leave_happy),
        npc.branch("Eating. No clock runs, so no pulse.", npc.flag(F("served")), npc.STILL),
        npc.branch("Handed the right dish after ordering it: eat. (The interaction tree can "
                   "only raise a flag; this is where it's acted on.)",
                   npc.all_of(npc.flag(F("got_right")), npc.flag(F("ordered"))), npc.STILL,
                   [npc.set_flag(F("got_right"), False), npc.set_flag(F("served")),
                    npc.once(F("eat"), entry["eat_seconds"]), npc.name_tag("Eating")]),
        npc.branch("Handed a dish it didn't order, or any dish before ordering: the food is "
                   "gone either way; leave the plate and walk out unpaid.",
                   npc.any_of(npc.flag(F("got_wrong")), npc.flag(F("got_right"))), npc.STILL,
                   [npc.set_flag(F("got_wrong"), False), npc.set_flag(F("got_right"), False),
                    *leave_refused]),
        npc.branch("Order taken: wait for the food, on a fresh clock.", npc.flag(F("ordered")),
                   instructions=_phase(model, "b", entry["food_patience"], leave_angry,
                                       entry["label"])),
        npc.branch("Sat down, not asked yet: wait to be asked.", {"Type": "Any"},
                   instructions=[
                       npc.branch("Now interactable (see the note on queued guests).",
                                  npc.no(npc.flag(F("active"))), None,
                                  [npc.set_flag(F("active"))], cont=True),
                       *_phase(model, "a", entry["order_patience"], leave_angry,
                               "Ready to order")]),
    ]

    others = [serving.context(items[e["serves"]]) for e in model["menu"]
              if e["serves"] != menu_id]
    order_hint = "kk.guest.order"
    pack.say(order_hint, blocks.with_key(model["fixtures"]["words"]["order"]))
    interactions = [
        npc.branch("Not seated yet, or already gone: not interactable.",
                   npc.any_of(npc.no(npc.flag(F("active"))), npc.flag(F("gone"))), None,
                   [{"Type": "SetInteractable", "Interactable": False}]),
        npc.branch("Before the order: offer the prompt.", npc.no(npc.flag(F("ordered"))), None,
                   [{"Type": "SetInteractable", "Interactable": True, "ShowPrompt": True,
                     "Hint": f"server.{order_hint}"}], cont=True),
        npc.branch("After the order: still interactable, so it can be served; no prompt.",
                   npc.flag(F("ordered")), None,
                   [{"Type": "SetInteractable", "Interactable": True, "ShowPrompt": False}],
                   cont=True),
        # DISHES BEFORE THE PRESS: a dish used on a guest may also count as a press.
        npc.branch("Handed the dish it wants.",
                   {"Type": "InteractionContext", "Context": serving.context(wanted)}, None,
                   [npc.set_flag(F("got_right"))]),
        *[npc.branch("Handed some other dish.", {"Type": "InteractionContext", "Context": c},
                     None, [npc.set_flag(F("got_wrong"))]) for c in others],
        npc.branch("Pressed: the order is taken.",
                   npc.all_of({"Type": "HasInteracted"}, npc.no(npc.flag(F("ordered")))), None,
                   [npc.set_flag(F("ordered"))]),
    ]
    return seated, interactions
