"""
THE HAZARD SYSTEM: things that go wrong on the floor, and what clears them (PlateUp's messes).

    a messy guest gets up    ->  a MESS on the floor, in an empty cell round its chair
    a sink spills (its
    station's "spills"
    chance, each scrub)      ->  a SPILL (water) in an empty cell round the sink -- dropped
                                 by the press system, which runs the sink
    a drop picks a cell      ->  small grows to medium, medium to large; a LARGE one (of a
    that already has one         kind that spreads: the spill) spreads -- a drop round IT,
                                 and on, up to its look's "spreads" hops away
    walk through either      ->  you're slowed (the spider web's numbers: 65% speed, weak jumps)
    hold F with a mop (1s)   ->  it's cleaned up (the mop's own hold: items.py)
    press it without one     ->  it says so

A PROBE for now (the `hazards` spike): whether a walk-through floor block slows a player,
whether a flat one can be aimed at and pressed, and what guests do about one in their way.

  * THE MESS IS A WALK-THROUGH BLOCK ON THE FLOOR, whatever the floor is: the shipped petals
    (flat, lying on the ground), tinted brown, with the web's MovementSettings. The web
    slows whoever is INSIDE it -- so the mess slows the feet standing in its cell.
  * ROUND ITS SOURCE, NOT AT ITS FEET: a seated guest's feet are in its chair, so a mess
    "where it stands" had nowhere to go. It lands in a random EMPTY cell of the eight round
    the chair (volumes.drop_around) -- never over a table, a chair or a station.
  * THE MOP is a theme item (content.py, from fixtures.json's look); the rule checks it's in
    hand and never takes it.

Guests learn they're messy from a mood (systems/guest.py): the queue marks them at random,
and the composer (build/guests.py) asks for a mess on the HAZARD channel as they walk off.
"""
import blocks
import settings
import signals
import volumes as v

FIXTURE = "hazards"
# SIZES, smallest first: (name, model scale, walking speed, jump). The medium is the spider
# web's numbers (Deco_SpiderWeb); the others either side of it. Scales far apart: at 0.7
# and 1.0, a small one read as full size.
SIZES = [("small", 0.5, 0.8, 0.7), ("medium", 0.85, 0.65, 0.5), ("large", 1.25, 0.5, 0.35)]


def slow(speed, jump):
    return {"HorizontalSpeedMultiplier": speed, "JumpForceMultiplier": jump,
            "TerminalVelocityModifier": 0.5, "Drag": 0.45}


def ids(model):
    prefix = model["theme"]["prefix"]
    gid = lambda local: settings.game_id(prefix, local)
    return {"mess": blocks.hazard_ids(model, "mess"), "spill": blocks.hazard_ids(model, "spill"),
            "mop": model["items"]["mop"]["game_id"],
            "dispenser": gid("spike_mess_dispenser"), "effect": gid("hazards_system")}


def build(model, debug=True, dispenser=False):
    """The mess block and the rules. `dispenser`: a spike-only block that drops a mess
    where the presser stands, to test without waiting on guests."""
    h = ids(model)
    fx = model["fixtures"]
    look, words = fx["looks"]["mess"], fx["words"]
    note = "A mess. See build/systems/hazards.py."
    hazards, shrink = [], {}             # every hazard block; what one mop hold makes it
    for kind, name in (("mess", "Mess"), ("spill", "Spill")):
        look = fx["looks"][kind]
        spreading = blocks.hazard_spreading(model, kind)
        for j, gid in enumerate(h[kind]):
            shrink[gid] = h[kind][j - 1] if j else "Empty"
        for gid in spreading:
            shrink[gid] = h[kind][-2]
        # The spreading large ones look and act exactly like the large one.
        for gid, (size, scale, speed, jump) in list(zip(h[kind], SIZES)) + [
                (g, SIZES[-1]) for g in spreading]:
            blocks.item(gid, f"{name} ({size})", look["icon"],
                        dict(blocks.block_for(dict(look, scale=scale)), HitboxType="Plant_Seed",
                             RandomRotation="YawStep1", BlockSoundSetId="Seeds",
                             PhysicalMaterialId="Foliage", MovementSettings=slow(speed, jump),
                             # The words say "hold [{key}]" themselves.
                             InteractionHint=blocks.hint(gid, words[kind], keyed=False),
                             Interactions={"Use": blocks.NOOP}), note)
        hazards += h[kind] + spreading

    rules = v.Entries()
    rep = lambda key, text, event="BLOCK_USED": v.report(f"kk.hazards.{key}",
                                                         f"[hazards] {text}", debug, event=event)
    # 1+: MOPPED -- one size smaller each hold; the smallest goes.
    for n, (block, to) in enumerate(shrink.items()):
        rules.add(1 + n, [v.at([block]), v.has(h["mop"])],
                  [v.cell([block], to), v.sound(1.2)] + rep(f"mopped.{n}", f"mopped a {block}"))
    rules.add(90, [v.at(hazards), v.not_holding(h["mop"])],
              [v.say("kk.hazards.needmop", words["mop_needed"])])
    # 10+: a messy guest got up -- a mess round its chair (the guest is still on it).
    heard = [signals.heard(signals.HAZARD_KEY, signals.MESS)]
    rules.add(99, heard, rep("mess", "a guest left a mess", "SIGNAL_RECEIVED"))
    mess = blocks.hazard_drop(model, "mess")
    v.drop_around(rules, 100, "mess", mess["sizes"], heard, "SIGNAL_RECEIVED", origin="Entity",
                  large=mess["large"], on_large=mess["on_large"])
    # 300+: SPREADING. A drop that lands on a large one puts a spreading one over it (hop 1);
    # placing it is a BLOCK_PLACED at ITS cell, answered here with a drop round it -- which
    # can land on another large one and put the next hop over that. The last hop's drop
    # finds large ones full, so a spread goes at most `spreads` hops from where it began.
    first = 300
    for kind in ("mess", "spill"):
        spreading = blocks.hazard_spreading(model, kind)
        for hop, block in enumerate(spreading):
            nxt = spreading[hop + 1] if hop + 1 < len(spreading) else None
            rules.add(first - 1, [v.at([block], event="BLOCK_PLACED")],
                      rep(f"spread.{kind}.{hop}", f"a {kind} spread (hop {hop + 1})",
                          "BLOCK_PLACED"))
            v.drop_around(rules, first, f"{kind}spread{hop}", h[kind],
                          [v.at([block], event="BLOCK_PLACED")], "BLOCK_PLACED",
                          large=[h[kind][-1]] + spreading, on_large=nxt)
            first += 100
    # RESET: a new run starts with a clean floor.
    rules.add(95, [signals.heard(signals.RESET, signals.RESET)],
              [{"Type": "ReplaceBlockType", "Event": "SIGNAL_RECEIVED",
                "FromBlockTypes": hazards, "ToBlockType": "Empty"}])
    if dispenser:
        blocks.station_block(h["dispenser"], "Mess dispenser", {
            "sides": "BlockTextures/Wood_Softwood_Planks_Side.png",
            "top": "BlockTextures/Wood_Softwood_Planks_Side.png", "sound": "Wood"},
            "Press to drop a mess where you stand", "Spike only. See build/systems/hazards.py.",
            tint="#6b4a2a")
        # Round the presser, the way a guest's mess lands round its chair.
        rules.add(199, [v.at([h["dispenser"]])], rep("dropped", "a mess dropped by hand"))
        v.drop_around(rules, 200, "hand", mess["sizes"], [v.at([h["dispenser"]])], "BLOCK_USED",
                      origin="Entity", large=mess["large"], on_large=mess["on_large"])
    rules.write(h["effect"], "Hazards: messes and the mop. See build/systems/hazards.py.")
    return h["effect"]


def volumes(model, box=v.WORLD_BOX):
    return [v.volume("hazards", ids(model)["effect"],
                     {signals.HAZARD_KEY: "system", **signals.RESET_TAGS}, box=box)]
