"""
THE GUEST, COMPOSED: one NPC role per menu entry, built from three systems' fragments.

WIRING, not a system: the one place that knows the queue, seating and the guest system all
exist, and joins them. Every rule a guest follows still belongs to a system:

    Queue state  ->  queue.guest_fragment     pool, one-spot moves, bumps, holding the front
    Seat state   ->  seating.guest_fragment   walk to a chair, sit, get up
                     while seated: guest.fragment   order, wait, eat or walk out

and the joins are all that is decided here:

    somewhere to go       a free chair                  (seating.chair_free)
    on sitting            release the queue's front     (queue.release)
    getting up            seating.left_fed / left_unfed (handed to the guest system)
    after getting up      walk off, then go -- see _leaving
    chair lost en route   back to the held front         (queue.return_fragment)

ONE ROLE PER MENU ENTRY and no role changes ever: the dish is fixed at spawn (an NPC can't
pick at random and check a plate against it later), and changing role drops queued signals.

LEAVING: walk off towards the pool for a few seconds and vanish (layouts have no doors -- a
closed door blocks NPC pathfinding). A different exit replaces _leaving() and nothing else.
"""
import npc
import settings
import signals
from systems import guest, queue, seating

WALK_OFF = 4.0


# The engine's decision log on every guest (npc.role trace): ON only while chasing a
# behaviour bug -- it logs every instruction of every guest, every tick.
TRACE = False


def role_id(model, entry):
    return settings.game_id(model["theme"]["prefix"], f"guest_{entry['serves']}")


def roles(model):
    return [role_id(model, e) for e in model["menu"]]


def _leaving(model):
    going = npc.flag("guests_going")
    return [
        npc.branch("Messy, and just got up (still on its chair): ask for a mess round the "
                   "chair, once (hazards.py puts it down).",
                   npc.all_of(npc.flag(guest.mood_flag("messy")),
                              npc.no(npc.flag("guests_messed"))),
                   None, [signals.from_npc(signals.HAZARD_KEY, signals.MESS,
                                           tag=signals.HAZARD_KEY),
                          npc.set_flag("guests_messed")], cont=True),
        npc.branch("Walked off long enough, and not on a queue spot: go (stands in for "
                   "leaving by the door). Never ON a spot -- see queue.off_the_line.",
                   npc.all_of(going, npc.stopped("guests_walk"), queue.off_the_line(model)),
                   None, [{"Type": "Despawn"}]),
        npc.branch("Walked off long enough, but standing on a queue spot: keep going, right "
                   "to the pool, to get off the line.",
                   npc.all_of(npc.near(queue.ids(model)["set_pool"]), going,
                              npc.stopped("guests_walk")),
                   {"Type": "Seek", "StopDistance": 0.5, "SlowDownDistance": 1.5}),
        npc.branch("Walking off towards the pool: away from the tables.",
                   npc.all_of(npc.near(queue.ids(model)["set_pool"]), going),
                   {"Type": "Seek", "StopDistance": 3.0, "SlowDownDistance": 4.0}),
        npc.branch("Walking off.", going, npc.STILL),
        npc.branch("Just got up: start walking off.", {"Type": "Any"}, npc.STILL,
                   [npc.set_flag("guests_going"), *npc.timer("guests_walk", WALK_OFF)]),
    ]


def build(model, debug=True):
    """Write every guest role for the model's menu."""
    guest.build(model, debug)
    for entry in model["menu"]:
        seated, interactions = guest.fragment(model, entry, on_fed=seating.left_fed(),
                                              on_unfed=seating.left_unfed())
        # Read a mood the pool marked it with, once: the first time it stands in line.
        mood = [dict(b, Sensor=npc.all_of(npc.on_block(queue.ids(model)["set_taken_any"]),
                                          b["Sensor"])) for b in guest.read_mood(model)]
        queue_state = mood + queue.guest_fragment(model, ready=seating.chair_free(model),
                                                  next_state="Seat", debug=debug)
        seat_state = seating.guest_fragment(
            model, on_sat=[queue.release()], while_seated=seated,
            on_unseated=_leaving(model),
            on_lost=queue.return_fragment(model, "Queue", debug) + [
                npc.branch("No chair and no held front to go back to: just go.",
                           {"Type": "Any"}, None, [{"Type": "Despawn"}])],
            debug=debug)
        npc.role(role_id(model, entry), f"Guest - wants {entry['label']}", "Queue",
                 {"Queue": queue_state, "Seat": seat_state}, interactions,
                 appearance=model["theme"]["guest"]["appearance"], display="Waiting",
                 comment=f"A guest who wants {entry['label']}, composed from the queue's, "
                         f"seating's and the guest system's fragments. See build/guests.py.",
                 trace=TRACE)
