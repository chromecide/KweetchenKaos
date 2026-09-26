"""
THE HAZARD SYSTEM: things that go wrong on the floor, and what clears them (PlateUp's messes).

    a messy guest gets up    ->  a MESS on the floor, in an empty cell round its chair
    a sink spills (its
    station's "spills"
    chance, each scrub)      ->  a SPILL (water) in an empty cell round the sink -- dropped
                                 by the press system, which runs the sink
    walk through either      ->  you're slowed (the spider web's numbers: 65% speed, weak jumps)
    press it with a mop      ->  it's cleaned up
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
# The spider web's (Deco_SpiderWeb): slow, and hard to jump out of.
SLOW = {"HorizontalSpeedMultiplier": 0.65, "TerminalVelocityModifier": 0.5,
        "JumpForceMultiplier": 0.5, "Drag": 0.45}


def ids(model):
    prefix = model["theme"]["prefix"]
    gid = lambda local: settings.game_id(prefix, local)
    return {"mess": blocks.hazard_id(model, "mess"), "spill": blocks.hazard_id(model, "spill"),
            "mop": model["items"]["mop"]["game_id"],
            "dispenser": gid("spike_mess_dispenser"), "effect": gid("hazards_system")}


def build(model, debug=True, dispenser=False):
    """The mess block and the rules. `dispenser`: a spike-only block that drops a mess
    where the presser stands, to test without waiting on guests."""
    h = ids(model)
    fx = model["fixtures"]
    look, words = fx["looks"]["mess"], fx["words"]
    note = "A mess. See build/systems/hazards.py."
    for kind, name in (("mess", "Mess"), ("spill", "Spill")):
        look = fx["looks"][kind]
        blocks.item(h[kind], name, look["icon"],
                    dict(blocks.block_for(look), HitboxType="Plant_Seed",
                         RandomRotation="YawStep1", BlockSoundSetId="Seeds",
                         PhysicalMaterialId="Foliage", MovementSettings=SLOW,
                         InteractionHint=blocks.hint(h[kind], words[kind]),
                         Interactions={"Use": blocks.NOOP}), note)
    hazards = [h["mess"], h["spill"]]

    rules = v.Entries()
    rep = lambda key, text, event="BLOCK_USED": v.report(f"kk.hazards.{key}",
                                                         f"[hazards] {text}", debug, event=event)
    rules.add(1, [v.at(hazards), v.has(h["mop"])],
              [v.cell(hazards, "Empty"), v.sound(1.4)] + rep("mopped", "mopped up"))
    rules.add(2, [v.at(hazards), v.not_holding(h["mop"])],
              [v.say("kk.hazards.needmop", words["mop_needed"])])
    # 10+: a messy guest got up -- a mess round its chair (the guest is still on it).
    heard = [signals.heard(signals.HAZARD_KEY, signals.MESS)]
    rules.add(9, heard, rep("mess", "a guest left a mess", "SIGNAL_RECEIVED"))
    v.drop_around(rules, 10, "mess", h["mess"], heard, "SIGNAL_RECEIVED", origin="Entity")
    # RESET: a new run starts with a clean floor.
    rules.add(50, [signals.heard(signals.RESET, signals.RESET)],
              [{"Type": "ReplaceBlockType", "Event": "SIGNAL_RECEIVED",
                "FromBlockTypes": hazards, "ToBlockType": "Empty"}])
    if dispenser:
        blocks.station_block(h["dispenser"], "Mess dispenser", {
            "sides": "BlockTextures/Wood_Softwood_Planks_Side.png",
            "top": "BlockTextures/Wood_Softwood_Planks_Side.png", "sound": "Wood"},
            "Press to drop a mess where you stand", "Spike only. See build/systems/hazards.py.",
            tint="#6b4a2a")
        # Round the presser, the way a guest's mess lands round its chair.
        rules.add(29, [v.at([h["dispenser"]])], rep("dropped", "a mess dropped by hand"))
        v.drop_around(rules, 30, "hand", h["mess"], [v.at([h["dispenser"]])], "BLOCK_USED",
                      origin="Entity")
    rules.write(h["effect"], "Hazards: messes and the mop. See build/systems/hazards.py.")
    return h["effect"]


def volumes(model, box=v.WORLD_BOX):
    return [v.volume("hazards", ids(model)["effect"],
                     {signals.HAZARD_KEY: "system", **signals.RESET_TAGS}, box=box)]
