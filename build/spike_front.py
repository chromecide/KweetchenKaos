"""
SPIKE ONLY: the front of house -- the queue, chairs and guests -- for a service spike or a
full run.

A RUN spike adds the shift (the open sign) and the offer pads: the shift runs the day,
sends guests, delivers the starting crates and puts out offers and recipe cards.

A SERVICE spike has no shift, so it adds two things only it needs:

  * GUEST CALLERS, one per menu entry: press one and a guest who wants that dish arrives at
    the pool. In a restaurant the shift will send arrivals at random; here you choose, which
    is what testing the wrong dish needs.
  * A LISTENER standing in for the shift: what the shift would hear (served, angry, turned
    away, paid, the queue giving up) is printed in chat and the log.

The queue's patience is long here (SPIKE_PATIENCE): it isn't what a service spike tests,
and at the real value it ran out while the line was being set up for a look.
"""
import blocks
import guests
import settings
import signals
import volumes as v
from systems import moods, pads, queue, seating, shift

QUEUE_X, SPOT_Z, POOL_Z = 2, (8, 10, 12, 14), 18   # spot 1 (the front) first
CHAIRS_X, CHAIRS_Z = (12, 14, 16), 4
CALLERS_X, CALLERS_Z = 12, 22
PADS_X, PADS_Z, SIGN_X = 12, 26, 10
QUEUE_AREA = ((-64.0, -8.0, -64.0), (8.0, 40.0, 64.0))
SPIKE_PATIENCE = 600


def caller_id(model, entry):
    return settings.game_id(model["theme"]["prefix"], f"spike_call_{entry['serves']}")


def build(model, ground, debug=True, run=False):
    """Write the front of house; return (volumes, (layout blocks, layout entities))."""
    roles = guests.roles(model)
    # The moods first: the queue rolls them and the guests read them (systems/moods.py).
    moods.build(model)
    built = queue.build(model, roles, debug, patience=SPIKE_PATIENCE)
    seating.build(model, debug)
    guests.build(model, debug)

    layout, entities = [], []
    for i, z in enumerate(SPOT_Z, start=1):
        layout.append({"x": QUEUE_X, "y": ground, "z": z, "name": queue.ids(model)["free"](i)})
        entities.append(queue.spot_entity(QUEUE_X, ground, z))
    layout.append({"x": QUEUE_X, "y": ground, "z": POOL_Z, "name": queue.ids(model)["pool"]})
    entities.append(queue.pool_entity(QUEUE_X, ground, POOL_Z))
    for x in CHAIRS_X:
        for dx, dz, block, turn in seating.layout(model, "Deg0"):
            b = {"x": x + dx, "y": ground, "z": CHAIRS_Z + dz, "name": block}
            if turn is not None:
                b["rotation"] = turn
            layout.append(b)

    base = (queue.volumes(model, QUEUE_AREA, built["patience"]) + seating.volumes(model))
    if run:
        tags = shift.build(model, {e["serves"]: guests.role_id(model, e) for e in model["menu"]},
                           debug)
        pads.build(model, debug)
        layout.append({"x": SIGN_X, "y": ground, "z": PADS_Z, "name": shift.ids(model)["sign"]})
        for k, n in enumerate(pads.numbers(model)):
            layout.append({"x": PADS_X + 2 * k, "y": ground, "z": PADS_Z,
                           "name": pads.ids(model)["pad"](n)})
            entities.append(pads.pad_entity(n, PADS_X + 2 * k, ground, PADS_Z))
        return base + shift.volumes(model, tags) + pads.volumes(model), (layout, entities)

    # Callers and the listener.
    effect = settings.game_id(model["theme"]["prefix"], "spike_front")
    rules = v.Entries()
    look = {"sides": "BlockTextures/Wood_Softwood_Planks_Side.png",
            "top": "BlockTextures/Wood_Softwood_Planks_Side.png", "sound": "Wood"}
    for n, entry in enumerate(model["menu"]):
        cid = caller_id(model, entry)
        blocks.station_block(cid, f"Guest caller - {entry['label']}", look,
                             f"Press to call a guest who wants {entry['label']}",
                             "Spike only: calls a guest. See build/spike_front.py.",
                             tint="#3c8a5c")
        layout.append({"x": CALLERS_X + 2 * n, "y": ground, "z": CALLERS_Z, "name": cid})
        rules.add(10 + n, [v.at([cid])],
                  [signals.to_pool("BLOCK_USED", guests.role_id(model, entry))]
                  + v.report(f"kk.call.{n}", f"[spike] called a guest: {entry['label']}", debug))
    heard = [(signals.GUEST, signals.SERVED, "guest SERVED"),
             (signals.GUEST, signals.ANGRY, "guest ANGRY"),
             (signals.GUEST, signals.TURNED_AWAY, "guest TURNED AWAY (wrong dish: no pay, "
                                                  "not a loss)"),
             (signals.QUEUE, signals.IMPATIENT, "the whole QUEUE gave up")]
    heard += [(signals.PAID, e["serves"], f"PAID {e['price']} for {e['label']}")
              for e in model["menu"]]
    for n, (key, value, text) in enumerate(heard):
        rules.add(100 + n, [signals.heard(key, value)],
                  v.report(f"kk.heard.{n}", f"[shift hears] {text}", True,
                           event="SIGNAL_RECEIVED"))
    rules.write(effect, "Spike only: guest callers and a listener standing in for the shift. "
                        "See build/spike_front.py.")

    volumes = base + [v.volume("spike_front", effect, signals.LISTENER_TAGS)]
    return volumes, (layout, entities)
