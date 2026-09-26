"""
THE HAZARD SYSTEM: things that go wrong on the floor, and what clears them (PlateUp's messes).

    any guest gets up        ->  at the rules' guest_mess_chance (small), a MESS on the floor,
                                 in an empty cell round its chair; a MESSY guest always
    a sink spills (its
    station's "spills"
    chance, each scrub)      ->  a SPILL (water) in an empty cell round the sink -- dropped
                                 by the press system, which runs the sink
    a drop picks a cell      ->  small grows to medium, medium to large; a LARGE one spreads
    that already has one         -- a drop round IT, and on, up to its look's "spreads" hops
                                 away (every kind: food mess, water, scraps, scorch)
    walk through either      ->  you're slowed (the spider web's numbers: 65% speed, weak jumps)
    one lands on a MAT       ->  the mat soaks it up and gets dirtier (clean, dirty, filthy);
                                 on a FILTHY one, the mat overflows -- spreads, as a large
                                 hazard does; a RUBBER mat is full: it lands elsewhere
    hold F with a mop (1s)   ->  it's cleaned up (the mop's own hold: items.py)
    press it without one     ->  it says so

Mounted in every restaurant and spike (a sink spills only where it is). The `hazards` spike
makes every guest messy and adds a dispenser that drops a mess by hand. The mop lives on a
mop stand (systems/tools.py).

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
    return {**{k: blocks.hazard_ids(model, k) for k in blocks.hazard_kinds(model)},
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
    for kind in blocks.hazard_kinds(model):
        look = fx["looks"][kind]
        name = kind.capitalize()
        # A kind may slow less (or more) than the default, size by size: its look's "speeds".
        speeds = look.get("speeds") or [sz[2] for sz in SIZES]
        spreading = blocks.hazard_spreading(model, kind)
        for j, gid in enumerate(h[kind]):
            shrink[gid] = h[kind][j - 1] if j else "Empty"
        for gid in spreading:
            shrink[gid] = h[kind][-2]
        # The spreading large ones look and act exactly like the large one.
        for gid, (size, scale, _, jump), speed in [
                (g, sz, sp) for g, sz, sp in zip(h[kind], SIZES, speeds)] + [
                (g, SIZES[-1], speeds[-1]) for g in spreading]:
            blocks.item(gid, f"{name} ({size})", look["icon"],
                        dict(blocks.block_for(dict(look, scale=scale)), HitboxType="Plant_Seed",
                             RandomRotation="YawStep1", BlockSoundSetId="Seeds",
                             PhysicalMaterialId="Foliage", MovementSettings=slow(speed, jump),
                             # The words say "hold [{key}]" themselves.
                             InteractionHint=blocks.hint(gid, words[kind], keyed=False),
                             Interactions={"Use": blocks.NOOP}), note)
        hazards += h[kind] + spreading

    # MATS: a hazard lands on neither -- the mat soaks it up and goes a level dirtier (a
    # tint), a filthy mat or a rubber one is just full. Only a clean mat (or a rubber one)
    # can be picked up and moved. A mop hold cleans a mat a level.
    mats = blocks.mat_ids(model)
    mat_look, rubber_look = fx["looks"]["mat"], fx["looks"]["mat_rubber"]
    tints = [None] + mat_look["dirt"]
    for j, (gid, tint) in enumerate(zip(mats["levels"], tints)):
        blocks.item(gid, mat_look["label"] if not j else f"{mat_look['label']} ({'dirty' if j == 1 else 'filthy'})",
                    mat_look["icon"],
                    dict(blocks.block_for(dict(mat_look, tint=tint)), HitboxType="Block_Flat",
                         BlockSoundSetId="Cloth", PhysicalMaterialId="Cloth",
                         InteractionHint=blocks.hint(gid, words["mat_dirty" if j else "mat"],
                                                     keyed=False),
                         Interactions={"Use": blocks.NOOP}), note, movable=not j)
        if j:
            shrink[gid] = mats["levels"][j - 1]
    blocks.item(mats["rubber"], rubber_look["label"], rubber_look["icon"],
                dict(blocks.block_for(rubber_look), HitboxType="Block_Flat",
                     BlockSoundSetId="Cloth", PhysicalMaterialId="Cloth",
                     InteractionHint=blocks.hint(mats["rubber"], words["mat_rubber"], keyed=False),
                     Interactions={"Use": blocks.NOOP}), note, movable=True)
    # OVERFLOWING: a filthy mat something landed on, put down again (one per kind per hop):
    # looks, mops and stays put exactly like a filthy mat.
    overflowing = [g for kind in mats["overflow"] for g in mats["overflow"][kind]]
    for gid in overflowing:
        blocks.item(gid, f"{mat_look['label']} (filthy)", mat_look["icon"],
                    dict(blocks.block_for(dict(mat_look, tint=tints[-1])), HitboxType="Block_Flat",
                         BlockSoundSetId="Cloth", PhysicalMaterialId="Cloth",
                         InteractionHint=blocks.hint(gid, words["mat_dirty"], keyed=False),
                         Interactions={"Use": blocks.NOOP}), note)
        shrink[gid] = mats["levels"][-2]
    dirty_mats = mats["levels"][1:] + overflowing

    rules = v.Entries()
    rep = lambda key, text, event="BLOCK_USED": v.report(f"kk.hazards.{key}",
                                                         f"[hazards] {text}", debug, event=event)
    # 1+: MOPPED -- one size smaller each hold; the smallest goes.
    for n, (block, to) in enumerate(shrink.items()):
        rules.add(1 + n, [v.at([block]), v.has(h["mop"])],
                  [v.cell([block], to), v.sound(1.2)] + rep(f"mopped.{n}", f"mopped a {block}"))
    rules.add(90, [v.at(hazards + dirty_mats), v.not_holding(h["mop"])],
              [v.say("kk.hazards.needmop", words["mop_needed"])])
    # 10+: a messy guest got up -- a mess round its chair (the guest is still on it).
    heard = [signals.heard(signals.HAZARD_KEY, signals.MESS)]
    rules.add(999, heard, rep("mess", "a guest left a mess", "SIGNAL_RECEIVED"))
    mess = blocks.hazard_drop(model, "mess")
    # Each drop_around takes up to v.DROP_RULES numbers: they start 100 apart.
    v.drop_around(rules, 1000, "mess", mess["sizes"], heard, "SIGNAL_RECEIVED", origin="Entity",
                  large=mess["large"], on_large=mess["on_large"], absorb=mess["absorb"],
                  overflow=mess["overflow"])
    # 150+: ANY guest got up -- a mess round its chair at the rules' chance.
    chance = model["rules"].get("hazards", {}).get("guest_mess_chance", 0)
    if chance:
        got_up = [signals.heard(signals.HAZARD_KEY, signals.GOT_UP),
                  {"Type": "RandomChanceCondition", "Event": "SIGNAL_RECEIVED",
                   "Chance": float(chance)}]
        v.drop_around(rules, 1100, "gotup", mess["sizes"], got_up, "SIGNAL_RECEIVED",
                      origin="Entity", large=mess["large"], on_large=mess["on_large"],
                      absorb=mess["absorb"], overflow=mess["overflow"])
    # 1300+: SPREADING -- a large hazard, or a full mat, that something lands on. It's put
    # down again as that kind's hop-1 block (a spreading large one, or an overflowing mat);
    # placing it is a BLOCK_PLACED at ITS cell, answered here with a drop round it, which
    # can land on another large one or full mat and put the next hop over that. The last
    # hop's drop finds them full, so a spread goes at most `spreads` hops from where it
    # began. Hazards and mats spread as one: food mess and water alike.
    first = 1300
    for kind in blocks.hazard_kinds(model):
        spreading = blocks.hazard_spreading(model, kind)
        for hop, block in enumerate(spreading):
            at_hop = [block, mats["overflow"][kind][hop]]
            d = blocks.hazard_drop(model, kind, hop + 1)
            rules.add(first - 1, [v.at(at_hop, event="BLOCK_PLACED")],
                      rep(f"spread.{kind}.{hop}", f"a {kind} spread (hop {hop + 1})",
                          "BLOCK_PLACED"))
            v.drop_around(rules, first, f"{kind}spread{hop}", d["sizes"],
                          [v.at(at_hop, event="BLOCK_PLACED")], "BLOCK_PLACED",
                          large=d["large"], on_large=d["on_large"], absorb=d["absorb"],
                          overflow=d["overflow"])
            first += 100
    # RESET: a new run starts with a clean floor.
    rules.add(95, [signals.heard(signals.RESET, signals.RESET)],
              [{"Type": "ReplaceBlockType", "Event": "SIGNAL_RECEIVED",
                "FromBlockTypes": hazards, "ToBlockType": "Empty"},
               {"Type": "ReplaceBlockType", "Event": "SIGNAL_RECEIVED",
                "FromBlockTypes": dirty_mats, "ToBlockType": mats["levels"][0]}])
    if dispenser:
        blocks.station_block(h["dispenser"], "Mess dispenser", {
            "sides": "BlockTextures/Wood_Softwood_Planks_Side.png",
            "top": "BlockTextures/Wood_Softwood_Planks_Side.png", "sound": "Wood"},
            "Press to drop a mess where you stand", "Spike only. See build/systems/hazards.py.",
            tint="#6b4a2a")
        # Round the presser, the way a guest's mess lands round its chair.
        rules.add(1199, [v.at([h["dispenser"]])], rep("dropped", "a mess dropped by hand"))
        v.drop_around(rules, 1200, "hand", mess["sizes"], [v.at([h["dispenser"]])], "BLOCK_USED",
                      origin="Entity", large=mess["large"], on_large=mess["on_large"],
                      absorb=mess["absorb"], overflow=mess["overflow"])
    rules.write(h["effect"], "Hazards: messes and the mop. See build/systems/hazards.py.")
    return h["effect"]


def volumes(model, box=v.WORLD_BOX):
    return [v.volume("hazards", ids(model)["effect"],
                     {signals.HAZARD_KEY: "system", **signals.RESET_TAGS}, box=box)]
