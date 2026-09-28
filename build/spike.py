"""
THE SPIKE WORLD: stations (and, for a service spike, the front of house) mounted over an
empty world, to test on their own.

    /kk spike    open the spike world (rebuilt fresh every visit)
    /kk kit      hand over the SETUP block and what the mounted stations take
    SETUP block  place it anywhere and press it once: everything is laid out at fixed
                 places (see the map below), so nobody sets a spike up by hand

A SPIKE ISOLATES ONE THING, carrying only the stations and items that thing needs (SPIKES
below says what each proves). Only `service` and `run` carry the whole kitchen: they are the
game. Anything extra in a spike is noise in what it proves.

A RECIPE SPIKE, `dish:<id>` (e.g. python3 deploy.py dish:roasted_corn), is a service spike
for one dish: the stations that dish's chain needs and no others (worked out from its
steps, crates included), a bin if it cooks, plates in the kit, and guest callers for that
dish's orders only (cooked and well done, say). One recipe, start to plate to paid.

A SPIKE IS A LIST OF STATIONS AND HOW MANY OF EACH, plus "front": True for the queue,
chairs and guests, and what /kk kit hands over (SPIKES below). Each station is mounted by whichever system runs its role
(systems/__init__.py) -- the way a layout will mount it later, so a spike tests exactly what
ships. Chosen at build time: `build.py --spike NAME`, or `python3 deploy.py NAME`.

THE KIT IS WORKED OUT FROM THE THEME: the setup block, and everything the stations take
that none of them make (two of raw ingredients and plates, one of the rest).

THE MAP (spawn is 8, 2, 8):

        x:  2              12 ...
    z  4                   chairs, tables at z 5        (front)
       8   queue spot 1
      10   spot 2
      12   spot 3          stations and crates in a row
      14   spot 4
      18   pool
      22                   guest callers, one per menu entry   (front)

The queue's patience area covers x <= 8 only: a seated guest inside it would drain the
line's patience.

What was learned in the POC and is built in here:
  * ADVENTURE MODE. NPCs ignore interactions from a creative player.
  * THE WORLD IS GONE once the last player leaves, so every visit starts clean.
  * THE KIT IS A SEPARATE COMMAND: moving between worlds rebuilds the player entity, and
    items handed over around that are lost. ONE ITEM PER LINE ("give x 2" means a player).
  * Don't run /kk spike from inside the spike world: it has crashed the server.
"""
import blocks
import clock
import npc
import pack
import restaurant
import settings
import signals
import spike_front
import systems
import volumes as v

INSTANCE = f"{settings.NAMESPACE}_Spike"
# THE WHOLE KITCHEN, for the two spikes that ARE the game (service, run).
KITCHEN = {"crates": 1, "board": 2, "counter": 3, "stove": 2, "bin": 1, "sink": 1,
           "rack": 1, "mop_stand": 1}
# A SPIKE ISOLATES ONE THING: it carries the stations and items that thing needs, and
# nothing else -- so what it proves is that thing, built the way the game will build it.
# Only `service` and `run` carry the whole kitchen, because the whole game is what they test.
#   stations  {station id: how many}; "crates" is one of every crate
#   give      items handed over by /kk kit (item ids); without it, what the stations take
#             that none of them make (spike.kit)
#   front     the queue, chairs and guests (guest callers, or the shift in a run)
#   moods     {mood: chance} a guest arrives with (systems/moods.py)
#   hazards   the hazard system mounted (systems/hazards.py); a station's hazard only
#             drops where it is
SPIKES = {
    # Chopping (pumpkin) and kneading (flour into dough): the board's two kinds of press.
    "board": {"stations": {"board": 1}, "give": ["pumpkin", "flour"]},
    # Cooking through every stage to burnt, on two ladders side by side: a pie (put together
    # first) and corn (straight on). Each dish's own times belong to its dish:<id> spike.
    "stove": {"stations": {"stove": 2}, "give": ["pumpkin_pie_unbaked", "corn"]},
    # The plate rack on its own, with a sink to wash a dirty plate to put back.
    "rack": {"stations": {"rack": 2, "sink": 1}},
    # Combining (dough + chopped pumpkin into an unbaked pie) and plating (a plate + a
    # cooked dish): the counter's two jobs.
    "counter": {"stations": {"counter": 2},
                "give": ["dough", "pumpkin_chopped", "plate", "roasted_corn_cooked"]},
    # MOODS on their two tracks (systems/moods.py). Only the front of house, and hazards so a
    # messy guest's mess shows: impatient 40% then relaxed 40% on the patience track (last
    # roll wins: ~40% relaxed, ~24% impatient), messy 50% on its own track. Moods show on
    # the name tag; an impatient guest walks out angry in ⅔ the time, a relaxed one 1.5x.
    "moods": {"stations": {}, "front": True, "hazards": True,
              "moods": {"impatient": 0.4, "relaxed": 0.4, "messy": 0.5}},
    # PROBE: every hazard and its source. A messy guest (every one here) leaves a mess round
    # its chair; the sink spills, the board drops scraps, burnt food off the stove scorches;
    # a dispenser drops a mess round you; the mop is on its stand. One raw thing to chop,
    # one thing to burn, a dirty plate to scrub.
    "hazards": {"stations": {"sink": 1, "board": 1, "stove": 1, "mop_stand": 1},
                "front": True, "moods": {"messy": 1.0}, "hazards": True, "dispenser": True,
                "give": ["plate_dirty", "pumpkin", "corn"]},
    # MATS: a mat soaks up what lands on it (clean, dirty, filthy -- then full) and the mop
    # cleans it; a rubber mat is always full. The dispenser drops messes round you (stand
    # among the mats), the sink spills round itself (put mats by it); the mop is on its stand.
    "mats": {"stations": {"sink": 1, "mop_stand": 1}, "hazards": True, "dispenser": True,
             "give": ["plate_dirty", "plate_dirty"], "mats": {"mat": 6, "mat_rubber": 3}},
    # TIPS: the shift pays the tip level on top of every dish served. A small run (the
    # shift, the pads, the guests), a stove and a bin as well as a board and counters so
    # any starter -- and any dish a card day offers -- can be made, and a TIP DIAL (two
    # blocks: up, down) standing in for the customer cards that will move the level.
    "tips": {"stations": {"crates": 0, "board": 1, "counter": 2, "stove": 1, "bin": 1,
                          "rack": 1}, "front": True, "run": True, "tip_dial": True},
    # CUSTOMER CARDS: a small run whose card day comes EVERY day (card_every), so each day
    # ends with a recipe card beside a customer card. A kitchen that can make any dish, and
    # hazards and a mop stand for a messy crowd. Watch: the opening title's guest count,
    # the purse (tips), and the name tags (moods).
    "cards": {"stations": {"crates": 0, "board": 1, "counter": 2, "stove": 1, "bin": 1,
                           "rack": 1, "sink": 1, "mop_stand": 1}, "front": True, "run": True,
              "hazards": True, "card_every": 1},
    # THE ENDGAME, without playing it: a run that starts on day 9 with every card taken and
    # a card day every day, and three blocks -- END THE DAY (the day ends at once: its title,
    # a milestone's, overtime's squeeze, the blueprints), SHOW MY BEST and FORGET MY BEST
    # (systems/records.py). Six presses pass the day 10 and 15 milestones and all three
    # squeezes. The kitchen is there to try a squeeze on real guests between presses.
    "endgame": {"stations": {"crates": 0, "board": 1, "counter": 2, "stove": 1, "bin": 1,
                             "rack": 1, "sink": 1, "mop_stand": 1}, "front": True, "run": True,
                "hazards": True, "card_every": 1, "start_day": 9, "cards_done": True,
                "endgame_blocks": True,
                # A handful of guests a day, not day 9's crowd.
                "guests": {"day_1": 2, "per_day": 0, "per_card": 1}},
    # THE FRANCHISE (systems/franchise.py): a run from day 14 with every card taken and the
    # END THE DAY block -- two presses end day 15, and pads 1-3 show franchise cards (bank
    # one; a second pick says you already have) -- a SHELF for every item (take one, put it
    # back), and a small kitchen to put a station down in, or spend a token on the sign.
    "franchise": {"stations": {"crates": 0, "board": 1, "counter": 2, "stove": 1, "bin": 1,
                               "rack": 1, "sink": 1}, "front": True, "run": True,
                  "card_every": 1, "start_day": 14, "cards_done": True, "endgame_blocks": True,
                  "shelves": True, "guests": {"day_1": 2, "per_day": 0, "per_card": 1}},
    # PROBE: can a run remember the best day on the player, and can it be read back? Four
    # blocks, nothing else (see _best_run).
    "bestrun": {"stations": {}, "best_probe": True, "give": []},
    # PROBE: food as carried blocks, one thing at a time, F only (see _carry_food). Its own
    # blocks and two guests; the kit is popcorn, to see the hotbar go out of play.
    "carry": {"stations": {}, "carry_probe": True, "give": []},
    # THE PRACTICE KITCHEN (systems/practice.py): the whole kitchen and the front of house,
    # guests arriving by themselves (and a CALL A GUEST block), every one in the practice
    # mood (five times the patience), the stations locked in place, hazards and the mop.
    # No shift: nothing counts.
    "practice": {"stations": KITCHEN, "front": True, "practice": True, "hazards": True,
                 "moods": {"practice": 1.0}},
    # THE GAME, service only: the kitchen, the queue, chairs and guests, called by hand.
    "service": {"stations": KITCHEN, "front": True, "hazards": True},
    # THE GAME, a full RUN: the shift runs the days. Crates at 0: mounted (so delivered ones
    # work) but not laid out -- the run delivers them on day 1, and more with recipe cards.
    "run": {"stations": dict(KITCHEN, crates=0), "front": True, "run": True, "hazards": True},
}
HAZARD_DISPENSER = (8, 4)     # x, z: between the queue and the chairs
TIP_DIAL = (6, 4)             # x, z: the tip dial's UP block; DOWN beside it (x - 2)
SETUP = f"{settings.NAMESPACE}_Spike_Setup"
SETUP_EFFECT = f"{SETUP}_System"
GROUND = 1              # the flat spike world's surface: blocks stand at y 1
ROW_Z, ROW_X, GAP = 12, 12, 2


# A recipe spike's stations beyond its chain: two stoves (one to watch through well done
# while the other cooks), two counters (assemble on one, plate on the other); a bin if it
# cooks (for what burns). Plates come in the kit: no rack, no sink.
DISH_COUNTS = {"stove": 2, "counter": 2}
DISH_PLATES = 4


TIP_DIAL_EFFECT = f"{settings.NAMESPACE}_Spike_Tip_Dial"
ENDGAME_EFFECT = f"{settings.NAMESPACE}_Spike_Endgame"
ENDGAME_ROW = (4, 4)          # x, z of the first of its three blocks, 2 apart in x


def _endgame_blocks(model):
    """Spike only: END THE DAY -- the day counts as done whatever state it's in: the guests
    go (and the queue and chairs are reset, as when a run is lost), no more arrive, and the
    shift's open and closing are set, so its day end runs on the next tick (a milestone's
    on a milestone day, overtime's squeeze on a card day). SHOW MY BEST and FORGET MY BEST
    (the spike's record: systems/records.py). Returns layout blocks."""
    import guests as guest_roles
    from systems import records
    look = {"sides": "BlockTextures/Wood_Softwood_Planks_Side.png",
            "top": "BlockTextures/Wood_Softwood_Planks_Side.png", "sound": "Wood"}
    blocks_ = [("end", "End the day", "#d04040",
                [{"Type": "RemoveEntities", "Event": "BLOCK_USED", "IncludeNpcs": True,
                  "IncludePlayers": False, "IgnoreInvulnerability": True,
                  "Roles": guest_roles.roles(model)},
                 signals.reset_everything("BLOCK_USED"),
                 signals.shift_changes("BLOCK_USED", "to_arrive", "Set", 0),
                 signals.shift_changes("BLOCK_USED", "beat", "Set", 0),
                 signals.shift_changes("BLOCK_USED", "open", "Set", 1),
                 signals.shift_changes("BLOCK_USED", "closing", "Set", 1)]),
               ("show", "Show my best", "#3c6a8a",
                [{"Type": "RunRootInteraction", "Event": "BLOCK_USED",
                  "RootInteraction": records.show(model, "spike", "the spike")}]),
               ("forget", "Forget my best", "#806040",
                [{"Type": "RunRootInteraction", "Event": "BLOCK_USED",
                  "RootInteraction": records.forget(model, "spike")}])]
    if model.get("franchise"):
        # A run in a restaurant clears a player's franchise pick as they arrive; a spike has
        # no arrival, so this does it.
        blocks_.append(("reset", "Reset my franchise pick", "#9a5ac8",
                        [{"Type": "RunRootInteraction", "Event": "BLOCK_USED",
                          "RootInteraction": model["franchise"]["reset"]}]))
    rules = v.Entries()
    out = []
    for n, (key, text, tint, effects) in enumerate(blocks_):
        gid = f"{settings.NAMESPACE}_Spike_Endgame_{key.capitalize()}"
        blocks.station_block(gid, text, look, f"Press to {text[0].lower() + text[1:]}",
                             "Spike only: the endgame spike. See build/spike.py.", tint=tint)
        rules.add(10 + n, [v.at([gid])], effects + [v.sound(1.2)])
        out.append({"x": ENDGAME_ROW[0] + 2 * n, "y": GROUND, "z": ENDGAME_ROW[1], "name": gid})
    rules.write(ENDGAME_EFFECT, "Spike only: the endgame spike's blocks. See build/spike.py.")
    return out


SHELF_ROW = (4, 18)           # x, z of the franchise spike's first shelf: 2 apart in x, rows 3 apart


def _shelves(model):
    """The franchise spike: a SHELF for every item a player can bank (systems/franchise.py),
    in rows, each with its volume. Returns (layout blocks, volumes)."""
    from systems import franchise
    roots = franchise.build(model)
    shelves = franchise.shelf_blocks(model)
    out, vols = [], []
    for n, (key, (shelf, top)) in enumerate(shelves.items()):
        x, z = SHELF_ROW[0] + 2 * (n % 12), SHELF_ROW[1] + 3 * (n // 12)
        out += [{"x": x, "y": GROUND, "z": z, "name": shelf},
                {"x": x, "y": GROUND + 1, "z": z, "name": top}]
        vols.append(v.volume(f"shelf_{key}", franchise.shelf_volume(model, key, roots),
                             {"took": "0"}))
    return out, vols


BEST_EFFECT = f"{settings.NAMESPACE}_Spike_Best"
BEST_STAT = f"{settings.NAMESPACE}_Best_Probe"
BEST_ROW = (4, 4)             # x, z of the first of the probe's four blocks, 2 apart in x


def _best_run(model, debug):
    """PROBE: can a restaurant remember the best day on the PLAYER (a stat outlives the
    run's world and a restart), and can HQ read it back? Four blocks: record day 7 and day
    3 (ChangeStat with Behaviour Max: best = the higher of the two -- 3 must not lower 7),
    show it (StatsCondition: at least 5? -- a threshold check, as HQ would use), and reset
    it. `/entity stats get K2_Best_Probe` prints the number itself. Returns layout blocks."""
    pack.write(pack.out("Entity", "Stats", settings.NAMESPACE, f"{BEST_STAT}.json"), {
        "$Comment": "Probe: the best day reached, remembered on the player. See build/spike.py.",
        "InitialValue": 0, "Min": 0, "Max": 1000})
    say = lambda key, text: (pack.say(key, text), f"server.{key}")[1]
    roots = {
        "set7": {"Type": "ChangeStat", "StatModifiers": {BEST_STAT: 7}, "ValueType": "Absolute",
                 "Behaviour": "Max"},
        "set3": {"Type": "ChangeStat", "StatModifiers": {BEST_STAT: 3}, "ValueType": "Absolute",
                 "Behaviour": "Max"},
        "show": {"Type": "StatsCondition", "Costs": {BEST_STAT: 5}, "ValueType": "Absolute",
                 "LessThan": False,
                 "Next": {"Type": "Serial", "Interactions": [
                     {"Type": "SendMessage", "Key": say("kk.probe.best.ge5", "Best day: at least 5")},
                     {"Type": "ShowEventTitle", "PrimaryTitle": {"MessageId": say("kk.probe.best.t.ge5", "Best: day 5+")}, "IsMajor": True}]},
                 "Failed": {"Type": "Serial", "Interactions": [
                     {"Type": "SendMessage", "Key": say("kk.probe.best.lt5", "Best day: under 5")},
                     {"Type": "ShowEventTitle", "PrimaryTitle": {"MessageId": say("kk.probe.best.t.lt5", "Best: under day 5")}, "IsMajor": True}]}},
        "reset": {"Type": "ChangeStat", "StatModifiers": {BEST_STAT: 0}, "ValueType": "Absolute",
                  "Behaviour": "Set"},
    }
    look = {"sides": "BlockTextures/Wood_Softwood_Planks_Side.png",
            "top": "BlockTextures/Wood_Softwood_Planks_Side.png", "sound": "Wood"}
    labels = {"set7": ("Record day 7", "#3c8a5c"), "set3": ("Record day 3", "#8a8a3c"),
              "show": ("Show the best day", "#3c6a8a"), "reset": ("Forget the best day", "#a04030")}
    rules = v.Entries()
    out = []
    for n, (key, root) in enumerate(roots.items()):
        rid = f"{settings.NAMESPACE}_Probe_Best_{key.capitalize()}"
        pack.write(pack.out("Item", "RootInteractions", settings.NAMESPACE, f"{rid}.json"),
                   {"$Comment": "Probe: see build/spike.py (_best_run).", "Interactions": [root]})
        gid = f"{settings.NAMESPACE}_Spike_Best_{key.capitalize()}"
        text, tint = labels[key]
        blocks.station_block(gid, text, look, f"Press to {text[0].lower() + text[1:]}",
                             "Spike only: the best-run probe. See build/spike.py.", tint=tint)
        rules.add(10 + n, [v.at([gid])],
                  [{"Type": "RunRootInteraction", "Event": "BLOCK_USED", "RootInteraction": rid},
                   v.sound(1.2)])
        out.append({"x": BEST_ROW[0] + 2 * n, "y": GROUND, "z": BEST_ROW[1], "name": gid})
    rules.write(BEST_EFFECT, "Spike only: the best-run probe. See build/spike.py.")
    return out


CARRY_EFFECT = f"{settings.NAMESPACE}_Spike_Carry"
CARRY_PAD_EFFECT = f"{settings.NAMESPACE}_Spike_Carry_Pad"
CARRY_ROW = 12                # z of the probe's row of blocks
CARRY_GUEST_DZ = 3            # a guest stands this far past its caller (+z)


def _carry_food(model, debug):
    """PROBE: food as CARRIED BLOCKS, so a player holds one thing at a time -- with F as the
    only key. Returns layout blocks; writes its own volume (CARRY_EFFECT) and a small one
    round guest B (CARRY_PAD_EFFECT).

    Food is a block. F on it with empty hands runs the block's own Use: CarryBlock. While
    carrying, EVERY interaction comes from the carried item's CarryInteractions (the hotbar
    is out of play), and its Use is: hand it to a guest (ContextualUseNPC), else pass the
    press to the block looked at (UseBlock), whose volume checks what is carried
    (ItemCondition Location Carried) and takes it (Consume). No right-click put-down.

    The row, left to right (x), at z CARRY_ROW:
      4   CRATE   corn on top. F on the corn picks it up; a new one comes 1.5 s later.
      6   COUNTER F carrying food: it goes on top. F on it again: back in hand. Movable
                  (left-click) between shifts, like the game's: left-click on the FOOD on
                  it should do nothing, and on the counter pick the counter up.
      8   STOVE   F carrying raw corn: in; 3 s later roasted corn sits on top. F: take it.
      12  CALLER A  a guest 3 blocks behind it
      16  CALLER B  a guest 3 blocks behind it, standing in a PAD volume
    Serving, two ways, one per food (the consume is the unknown):
      roasted corn: hand over, then ModifyInventory -1 (how KK serves a held dish today)
      raw corn:     hand over, then UseEntity -- a real entity use, which the pad around
                    guest B hears, and takes the carried corn (so: raw to B empties, raw to
                    A is the control and should NOT)
    Also watched: F on food while already carrying (the pick-up fails -- does its volume
    still hear the press? decides combining on a counter), Q while carrying, and the
    popcorn in the kit (right-click eats it -- not while carrying?)."""
    ns = settings.NAMESPACE
    gid = lambda local: f"{ns}_Probe_Carry_{local}"
    comment = "Probe only: carried food. See build/spike.py (_carry_food)."
    say = lambda key, text: (pack.say(key, text), f"server.{key}")[1]
    root = lambda rid, first: pack.write(pack.out("Item", "RootInteractions", ns, f"{rid}.json"),
                                         {"$Comment": comment, "Interactions": [first]})

    # --- the food: a block you pick up with F, carried with its own F
    pick = gid("Pick")
    root(pick, {"Type": "CarryBlock"})
    guest_roles = {"a": gid("Guest_A"), "b": gid("Guest_B")}
    ctx = {"raw": gid("Serve_Raw"), "cooked": gid("Serve_Cooked")}
    then = {"raw": {"Type": "UseEntity"},
            "cooked": {"Type": "ModifyInventory", "AdjustHeldItemQuantity": -1}}
    food = {"raw": (gid("Corn"), "Corn (probe)", {
                "model": "Resources/Ingredients/Corn.blockymodel",
                "texture": "Resources/Ingredients/Corn_Texture.png", "scale": 0.75,
                "icon": "Icons/ItemsGenerated/Plant_Crop_Corn.png"}),
            "cooked": (gid("Corn_Roasted"), "Roasted corn (probe)", {
                "model": "Items/Consumables/Food/Corn_Roasted.blockymodel",
                "texture": "Resources/Ingredients/Corn_Texture.png",
                "icon": "Icons/ItemsGenerated/Food_Roasted_Corn.png"})}
    for kind, (fid, label, look) in food.items():
        use = f"{fid}_Carried_Use"
        root(use, {"Type": "ContextualUseNPC", "Context": ctx[kind],
                   "Effects": {"WorldSoundEventId": "SFX_Player_Pickup_Item"},
                   "Next": then[kind], "Failed": {"Type": "UseBlock"}})
        block = dict(blocks.block_for(look),
                     InteractionHint=blocks.hint(fid, f"Press to pick up the {label.lower()}"),
                     Interactions={"Use": pick, "Primary": blocks.NOOP},
                     SupportDropType="Destroy")
        pack.say(f"items.{fid}.name", label)
        pack.write_item(fid, {
            "$Comment": comment, "TranslationProperties": {"Name": f"server.items.{fid}.name"},
            "Icon": look["icon"], "PlayerAnimationsId": "Block", "BlockType": block,
            "CarryInteractions": {"Use": use},
            "CarryHudInputBindings": {"Use": "BlockInteractAction"},
            "Tags": {"Type": ["Furniture"], "Family": ["Kitchen"]}})
    raw, cooked = food["raw"][0], food["cooked"][0]

    # --- the stations: plain blocks with a state each
    wood = {"sides": "BlockTextures/Wood_Softwood_Planks_Side.png",
            "top": "BlockTextures/Wood_Softwood_Planks_Side.png", "sound": "Wood"}
    st = {k: gid(k) for k in ("Crate", "Counter", "Counter_Full", "Stove", "Stove_Cooking",
                              "Stove_Done", "Caller_A", "Caller_B")}
    blocks.station_block(st["Crate"], "Corn crate (probe)", wood, "Take the corn on top",
                         comment, tint="#c0a040", keyed=False)
    blocks.station_block(st["Counter"], "Counter (probe)", wood,
                         "Press carrying food to put it here", comment, tint="#8a8a8a",
                         movable=True)
    blocks.station_block(st["Counter_Full"], "Counter, food on it (probe)", wood,
                         "Something is on it", comment, tint="#6a6a6a", movable=True)
    blocks.station_block(st["Stove"], "Stove (probe)", wood, "Press carrying raw corn to cook it",
                         comment, tint="#404040")
    blocks.station_block(st["Stove_Cooking"], "Stove, cooking (probe)", wood, "Cooking...",
                         comment, tint="#c05020")
    blocks.station_block(st["Stove_Done"], "Stove, done (probe)", wood, "Take the roasted corn",
                         comment, tint="#40a040")
    for g in ("A", "B"):
        blocks.station_block(st[f"Caller_{g}"], f"Call guest {g} (probe)", wood,
                             f"Press to call guest {g}", comment, tint="#3c6a8a")

    # --- the guests: stand still, always take a dish, and say what they got
    for g, role_id in guest_roles.items():
        hint_key = say(f"kk.probe.carry.guest.{g}", "Give the corn")
        got = lambda what: [{"Type": "Log", "Message": f"[carry] guest {g.upper()} got: {what}"},
                            npc.name_tag(f"Guest {g.upper()}: got {what}")]
        # SetInteractable is only valid in the INTERACTION instructions, not the behaviour.
        npc.role(role_id, f"Guest {g.upper()} (probe)", "Idle", {"Idle": [
            npc.branch("Stand still.", {"Type": "Any"}, npc.STILL)]},
            interactions=[
                npc.branch("Always interactable, with a prompt.", {"Type": "Any"}, None,
                           [{"Type": "SetInteractable", "Interactable": True,
                             "ShowPrompt": True, "Hint": hint_key}], cont=True),
                npc.branch("Handed raw corn.", {"Type": "InteractionContext", "Context": ctx["raw"]},
                           None, got("RAW corn")),
                npc.branch("Handed roasted corn.",
                           {"Type": "InteractionContext", "Context": ctx["cooked"]},
                           None, got("ROASTED corn")),
                npc.branch("Pressed.", {"Type": "HasInteracted"}, None, got("a press"))],
            display=f"Guest {g.upper()}", comment=comment)

    # --- the rules
    chat = lambda key, text, event: v.say(f"kk.probe.carry.{key}", f"[carry] {text}", event)
    rep = lambda key, text, event: [chat(key, text, event)] + v.report(
        f"kk.probe.carry.{key}", f"[carry] {text}", debug, event, to_log=True)
    under = lambda what, event: {"Type": "BlockTypeCondition", "Event": event, "BlockType": [what],
                                 "PositionSource": "Event",
                                 "PositionOffset": {"X": 0.0, "Y": -1.0, "Z": 0.0}}
    put = lambda block, dy, event, delay=None: dict(
        {"Type": "PlaceBlock", "Event": event, "BlockType": block, "Origin": "Event",
         "Position": {"X": 0.0, "Y": float(dy), "Z": 0.0}, "ReplaceMode": "Always"},
        **({"Delay": delay} if delay else {}))
    carrying = lambda fid, event="BLOCK_USED": {"Type": "ItemCondition", "Event": event,
                                                "Item": fid, "Location": "Carried",
                                                "Consume": True}
    carrying_check = lambda fid: {"Type": "ItemCondition", "Event": "BLOCK_USED", "Item": fid,
                                  "Location": "Carried"}
    rules = v.Entries()
    b = "BLOCK_BROKEN"
    # THE CRATE: the corn on it taken (a carry is a real break) -> a new one, a moment later.
    rules.add(10, [v.at([raw], event=b), under(st["Crate"], b)],
              [dict(put(raw, 0, b, 1.5), ReplaceMode="OnlyAir")]
              + rep("crate.take", "picked up corn from the crate (a new one in 1.5 s)", b))
    # THE COUNTER: F carrying food -> the counter takes it and shows it on top.
    for n, (kind, fid) in enumerate((("raw", raw), ("cooked", cooked))):
        rules.add(20 + n, [v.at([st["Counter"]]), carrying(fid)],
                  [put(st["Counter_Full"], 0, "BLOCK_USED"), put(fid, 1, "BLOCK_USED"),
                   v.sound(1.0)]
                  + rep(f"counter.put.{kind}", f"counter took the {kind} corn: on top now",
                        "BLOCK_USED"))
    rules.add(22, [v.at([raw, cooked], event=b), under(st["Counter_Full"], b)],
              [put(st["Counter"], -1, b)] + rep("counter.take", "picked food up off the counter", b))
    # THE STOVE: raw corn in -> 3 s -> roasted corn on top; taken -> empty again.
    rules.add(30, [v.at([st["Stove"]]), carrying(raw)],
              [put(st["Stove_Cooking"], 0, "BLOCK_USED"), v.sound(0.8),
               put(st["Stove_Done"], 0, "BLOCK_USED", 3.0), put(cooked, 1, "BLOCK_USED", 3.0)]
              + rep("stove.in", "stove took the raw corn: roasted in 3 s", "BLOCK_USED"))
    rules.add(31, [v.at([cooked], event=b), under(st["Stove_Done"], b)],
              [put(st["Stove"], -1, b)] + rep("stove.take", "picked the roasted corn off the stove", b))
    # F ON FOOD WHILE CARRYING: the pick-up fails (already carrying). Is the press heard?
    for n, (kind, fid) in enumerate((("raw", raw), ("cooked", cooked))):
        rules.add(40 + n, [v.at([raw, cooked]), carrying_check(fid)],
                  rep(f"combine.{kind}", f"heard F on food while carrying {kind} corn "
                                         "(combining would work)", "BLOCK_USED"))
    # THE CALLERS: a guest behind each, one at a time.
    for n, g in enumerate(("a", "b")):
        role_id = guest_roles[g]
        rules.add(50 + n, [v.at([st[f"Caller_{g.upper()}"]]),
                           {"Type": "EntityCountCondition", "Event": "BLOCK_USED",
                            "Comparison": "AtMost", "Count": 0, "EntityType": [role_id]}],
                  [{"Type": "SpawnNpc", "Event": "BLOCK_USED", "NpcType": role_id,
                    "Origin": "Event", "Count": 1, "Yaw": 180.0,
                    "Offset": {"X": 0.0, "Y": -0.5, "Z": float(CARRY_GUEST_DZ)}}]
                  + rep(f"call.{g}", f"guest {g.upper()} called", "BLOCK_USED"))
    rules.write(CARRY_EFFECT, comment)
    # THE PAD round guest B: a real entity use while carrying -> it takes the carried corn.
    pad = v.Entries()
    for n, (kind, fid) in enumerate((("raw", raw), ("cooked", cooked))):
        pad.add(1 + n, [carrying(fid)],
                rep(f"pad.{kind}", f"guest B's pad took the carried {kind} corn "
                                   "(UseEntity path)", "BLOCK_USED"))
    pad.write(CARRY_PAD_EFFECT, comment)

    y = GROUND
    return [{"x": 4, "y": y, "z": CARRY_ROW, "name": st["Crate"]},
            {"x": 4, "y": y + 1, "z": CARRY_ROW, "name": raw},
            {"x": 6, "y": y, "z": CARRY_ROW, "name": st["Counter"]},
            {"x": 8, "y": y, "z": CARRY_ROW, "name": st["Stove"]},
            {"x": 12, "y": y, "z": CARRY_ROW, "name": st["Caller_A"]},
            {"x": 16, "y": y, "z": CARRY_ROW, "name": st["Caller_B"]}]


def _carry_pad_box():
    """Round guest B: its caller at x 16, it stands CARRY_GUEST_DZ further on."""
    z = CARRY_ROW + CARRY_GUEST_DZ
    return ((15.0, 0.0, z - 1.0), (18.0, 5.0, z + 2.0))


def _tip_dial(model, debug):
    """Spike only: two blocks that move the shift's tip level up or down, as a customer card
    will. Returns their layout blocks."""
    look = {"sides": "BlockTextures/Wood_Softwood_Planks_Side.png",
            "top": "BlockTextures/Wood_Softwood_Planks_Side.png", "sound": "Wood"}
    rules = v.Entries()
    out = []
    for n, (direction, label, tint, dx) in enumerate(
            ((signals.UP, "up", "#3c8a5c", 0), (signals.DOWN, "down", "#a04030", -2))):
        gid = f"{settings.NAMESPACE}_Spike_Tip_{label.capitalize()}"
        blocks.station_block(gid, f"Tip dial - {label}",
                             look, f"Press to move every guest's tip {label} a coin",
                             "Spike only: moves the shift's tip level. See build/spike.py.",
                             tint=tint)
        rules.add(10 + n, [v.at([gid])],
                  [signals.from_volume("BLOCK_USED", signals.TIP, direction), v.sound(1.2)])
        out.append({"x": TIP_DIAL[0] + dx, "y": GROUND, "z": TIP_DIAL[1], "name": gid})
    rules.write(TIP_DIAL_EFFECT, "Spike only: the tip dial. See build/spike.py.")
    return out


def dish_stations(model, dish_id):
    """Every station a dish's chain passes through, found by walking back from what its
    guests order (the plated items) to the crates; and a bin if it cooks. In the kitchen's
    order: crates, then the rest."""
    wanted = {e["serves"] for e in model["menu"] if e["dish"] == dish_id}
    plate = model["vessel"]["clean"]["id"]
    used, grew = set(), True
    while grew:
        grew = False
        for s in model["steps"]:
            made = ([s["output"]] if "output" in s
                    else [x["gives"] for x in s.get("stages", []) if x["gives"] != s["input"]])
            if plate in made or not wanted & set(made) or id(s) in used:
                continue
            used.add(id(s))
            wanted.update(s.get("inputs", []) + ([s["input"]] if "input" in s else []))
            grew = True
    chain = {s["station"] for s in model["steps"] if id(s) in used}
    crates = sorted(st for st in chain if model["stations"][st]["role"] == "crate")
    if any(model["stations"][st]["role"] == "heat" for st in chain):
        chain.add("bin")
    rest = [st for st in KITCHEN if st in chain]
    return {**{st: 1 for st in crates}, **{st: DISH_COUNTS.get(st, 1) for st in rest}}


def stations_of(model, name):
    """A spike's stations; "crates" means one of every crate the theme has."""
    out = {}
    for st, count in SPIKES[name]["stations"].items():
        if st == "crates":
            out.update({sid: count for sid, s in model["stations"].items()
                        if s["role"] == "crate" and not s.get("upgrade_of")})
        else:
            out[st] = count
    return out


def kit(model, stations):
    steps = [s for s in model["steps"] if s["station"] in stations]
    made = set()
    for s in steps:
        # A stove "gives back" what went on (taken off before cooking): that isn't making it.
        made.update([s["output"]] if "output" in s
                    else [x["gives"] for x in s["stages"] if x["gives"] != s["input"]])
    needed = []
    for s in steps:
        for iid in s.get("inputs", []) + ([s["input"]] if "input" in s else []):
            if iid not in made and iid not in needed:
                needed.append(iid)
    # The restaurant's plates: the sink makes clean ones from dirty, but a restaurant
    # starts with a stack, so a spike that plates always gets some.
    plate = model["vessel"]["clean"]["id"]
    if any(plate in s.get("inputs", []) for s in steps) and plate not in needed:
        needed.append(plate)
    # Items stack one to a slot: two of anything used up in quantity, one of the rest.
    many = lambda i: model["items"][i].get("source") or i == plate
    return ([(SETUP, 1)]
            + [(model["items"][i]["game_id"], 2 if many(i) else 1) for i in needed])


def setup(model, stations, front, debug):
    """The setup block, the layout it pastes, and the rule that pastes it once. Returns
    the setup volume."""
    row = [(systems.for_station(model, st).layout(model, st),
            blocks.turn_index(model["stations"][st]["look"]))
           for st, count in stations.items() for _ in range(count)]
    layout = [dict({"x": ROW_X + GAP * k, "y": GROUND + dy, "z": ROW_Z, "name": block},
                   **({"rotation": turn} if turn is not None and dy == 0 else {}))
              for k, (column, turn) in enumerate(row) for dy, block in column]
    entities = []
    if front:
        more, entities = front
        layout += more
    pack.write(pack.out("Prefabs", f"{SETUP}_Layout.prefab.json"), {
        "$Comment": "The spike world's layout. See build/spike.py for the map.",
        "version": 8, "blockIdVersion": 11, "anchorX": 0, "anchorY": 0, "anchorZ": 0,
        "blocks": layout, "entities": entities})
    blocks.station_block(SETUP, "Spike setup", {
        "sides": "BlockTextures/Wood_Softwood_Planks_Side.png",
        "top": "BlockTextures/Wood_Softwood_Planks_Side.png", "sound": "Wood"},
        "Press to lay everything out (once)",
        "Spike only: press to lay everything out. See build/spike.py.", tint="#e0c020")

    once = lambda value: {"Type": "TagCondition", "Event": "BLOCK_USED", "Source": "Self",
                          "TagKey": "done", "Comparison": "Exactly", "TagValue": value}
    what = ", ".join(f"{n}x {model['stations'][st]['label'].lower()}"
                     for st, n in stations.items() if model["stations"][st]["role"] != "crate")
    rules = v.Entries()
    rules.add(1, [v.at([SETUP]), once("1")],
              [v.say("kk.setup.again", "[setup] already laid out - leave and /kk spike again "
                                       "for a fresh world")])
    # WORLD position (WorldAbsolute: Position IS the spot): the layout lands in the same
    # place wherever the block was pressed, and wherever the setup volume sits.
    rules.add(2, [v.at([SETUP]), once("0")],
              [{"Type": "PastePrefab", "Event": "BLOCK_USED", "Prefab": f"{SETUP}_Layout",
                "Origin": "WorldAbsolute", "Position": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                "ShowParticles": False},
               {"Type": "ModifyTags", "Event": "BLOCK_USED", "Operation": "Set",
                "TagKey": "done", "TagValue": "1"}]
              + v.report("kk.setup.done", f"[setup] laid out: {what}, the crates"
                         + (", the queue, chairs and guest callers" if front else ""), debug))
    rules.write(SETUP_EFFECT, "Spike only: the setup block. See build/spike.py.")
    return v.volume("spike_setup", SETUP_EFFECT, {"done": "0"})


def _world(note, needs_clock, mounted, given, spawn=(8.0, 2.0, 8.0)):
    """The spike instance, its volumes, and /kk spike and /kk kit."""
    pack.write(pack.out("Instances", INSTANCE, "instance.bson"), {
        "$Comment": f"Kweetchen Kaos spike world, mounting: {note}. See build/spike.py.",
        "Version": 2,
        "WorldGen": {"Type": "Flat",
                     "Layers": [{"From": 0, "To": 1, "BlockType": "Soil_Grass"}]},
        "SpawnProvider": {"Id": "Global",
                          "SpawnPoint": {"X": spawn[0], "Y": spawn[1], "Z": spawn[2],
                                         "Pitch": 0.0, "Yaw": 0.0, "Roll": 0.0}},
        "GameMode": "Adventure",
        "GameTime": "0001-01-01T12:00:00Z",
        "IsGameTimePaused": True,
        # A timed station (stove, crates) needs the clock running.
        **(clock.WORLD_TIME if needs_clock else {}),
        "IsSpawningNPC": False, "IsSpawnMarkersEnabled": False,
        "IsBlockSpawnersEnabled": False,
        "DeleteOnRemove": True, "DeleteOnUniverseStart": True,
        "Plugin": {"Instance": {
            "InstanceKey": INSTANCE.lower(),
            "RemovalConditions": [{"Type": "WorldEmpty", "TimeoutSeconds": 10.0}]}}})
    pack.write(pack.out("Instances", INSTANCE, "resources", "TriggerVolumeData.json"),
               {"Volumes": {f"5b1ce000-0000-4000-8000-{i:012d}": vol
                            for i, vol in enumerate(mounted, start=1)}})
    pack.say("commands.kk.spike.desc", "Open the Kweetchen Kaos spike world")
    pack.say("commands.kk.kit.desc", "Hand over what the spiked stations need")
    pack.write(pack.out("MacroCommands", "KKSpike.json"), {
        "$Comment": f"Open the spike world (mounting: {note}). Not from inside it.",
        "Name": "kk spike", "Description": "server.commands.kk.spike.desc",
        "Commands": [f"instances spawn {INSTANCE}", "wait 4", "gamemode adventure"]})
    pack.write(pack.out("MacroCommands", "KKKit.json"), {
        "$Comment": "What the spiked stations need. One item per line.",
        "Name": "kk kit", "Description": "server.commands.kk.kit.desc",
        "Commands": [f"give {item}" for item, n in given for _ in range(n)]})


def build_room(model, layout_id, debug=True):
    """A RESTAURANT spike: a layout's room, dressed in the theme, carrying its own systems
    (restaurant.py). Place the setup block anywhere and press it: the room is pasted with
    its corner one block past the setup block (+x, +z), its floor at the ground the block
    stands on. The world itself holds nothing but the setup block's volume."""
    room, problems, info = restaurant.build(model, layout_id, debug=debug,
                                            patience=spike_front.SPIKE_PATIENCE)
    for p in problems:
        print(f"  LAYOUT: {p}")
    pack.write(pack.out("Prefabs", f"{SETUP}_Layout.prefab.json"),
               dict(room, **{"$Comment": f"The room '{info['name']}', dressed, carrying its "
                                         f"systems. See build/restaurant.py."}))
    blocks.station_block(SETUP, "Spike setup", {
        "sides": "BlockTextures/Wood_Softwood_Planks_Side.png",
        "top": "BlockTextures/Wood_Softwood_Planks_Side.png", "sound": "Wood"},
        "Press to build the room here (once)", "Spike only. See build/spike.py.",
        tint="#e0c020")
    once = lambda value: {"Type": "TagCondition", "Event": "BLOCK_USED", "Source": "Self",
                          "TagKey": "done", "Comparison": "Exactly", "TagValue": value}
    rules = v.Entries()
    rules.add(1, [v.at([SETUP]), once("1")],
              [v.say("kk.setup.again", "[setup] already built - leave and /kk spike again")])
    # AT THE BLOCK: a block event's position is its centre, and the paste floors it, so
    # (1, -1, 1) puts the room's corner one block over and its floor at ground level.
    rules.add(2, [v.at([SETUP]), once("0")],
              [{"Type": "PastePrefab", "Event": "BLOCK_USED", "Prefab": f"{SETUP}_Layout",
                "Origin": "Event", "Position": {"X": 1.0, "Y": -1.0, "Z": 1.0},
                "ShowParticles": False},
               {"Type": "ModifyTags", "Event": "BLOCK_USED", "Operation": "Set",
                "TagKey": "done", "TagValue": "1"}]
              + v.report("kk.setup.room", f"[setup] built the room: {info['name']}", debug))
    rules.write(SETUP_EFFECT, "Spike only: the setup block. See build/spike.py.")
    given = [(SETUP, 1), (model["items"][model["vessel"]["clean"]["id"]]["game_id"], 2)]
    note = f"the room {info['name']}"
    _world(note, True, [v.volume("spike_setup", SETUP_EFFECT, {"done": "0"})], given)
    return note, given



# THE PICK SPIKE: a random room each time the world is made (world._paste_on_arrival with
# choices -- what the HQ's size portals will use). Three marker rooms, a colour each, a
# pillar in a different corner and an arrival spot of their own. Nothing else: no stations.
PICK_ROOMS = [("red", "#d03030", (1, 1), (7, 7)), ("green", "#30b040", (7, 1), (1, 7)),
              ("blue", "#3050e0", (4, 7), (4, 1))]     # colour, tint, pillar x z, arrival x z
PICK_SIZE, PICK_PILLAR = 9, 6


def build_pick(debug=True):
    import world
    choices = []
    for colour, tint, (px, pz), (ax, az) in PICK_ROOMS:
        block = f"{settings.NAMESPACE}_Spike_Pick_{colour.capitalize()}"
        blocks.station_block(block, f"Room {colour}", {
            "sides": "BlockTextures/Wood_Softwood_Planks_Side.png",
            "top": "BlockTextures/Wood_Softwood_Planks_Side.png", "sound": "Wood"},
            f"The {colour} room", "Spike only: a pick marker. See build/spike.py.",
            tint=tint, use=False)
        cells = [{"x": x, "y": 0, "z": z, "name": block}
                 for x in range(PICK_SIZE) for z in range(PICK_SIZE)]
        cells += [{"x": px, "y": y, "z": pz, "name": block} for y in range(1, PICK_PILLAR + 1)]
        prefab = f"{settings.NAMESPACE}_Spike_Pick_Room_{colour.capitalize()}"
        pack.write(pack.out("Prefabs", f"{prefab}.prefab.json"), {
            "$Comment": f"Spike only: the {colour} pick room. See build/spike.py.",
            "version": 8, "blockIdVersion": 11, "anchorX": 0, "anchorY": 0, "anchorZ": 0,
            "blocks": cells, "fluids": [], "entities": []})
        spawn = (world.AT[0] + ax + 0.5, world.AT[1] + world.STAND, world.AT[2] + az + 0.5)
        choices.append({"prefab": prefab, "spawn": spawn, "label": f"the {colour} room",
                        "welcome": (f"The {colour.upper()} room",
                                    "Leave, /kk spike again: a new pick each world")})
    arrive = world._paste_on_arrival(f"{settings.NAMESPACE}_Spike_Pick", None, None,
                                     choices=choices, debug=debug)
    note = "a random room: " + ", ".join(c for c, *_ in PICK_ROOMS)
    _world(note, False, [arrive], [])
    return note, []


def build(model, name, debug=True):
    if name == "pick":
        return build_pick(debug)
    if name.startswith("room:"):
        return build_room(model, name[len("room:"):], debug)
    if name.startswith("dish:"):
        dish = name[len("dish:"):]
        if dish not in model["dishes"]:
            raise SystemExit(f"no dish '{dish}'; the dishes are: "
                             + ", ".join(sorted(model["dishes"])))
        spike = {"front": True}
        stations = dish_stations(model, dish)
        # Guests (and their callers) for this dish's orders only. Items are already
        # written, so narrowing the menu here touches the front of house alone.
        model["menu"] = [e for e in model["menu"] if e["dish"] == dish]
    else:
        spike = SPIKES[name]
        stations = stations_of(model, name)
    # HAZARDS where the spike says (the game's spikes, and the hazards probe). Before the
    # stations: a station that causes one (a sink's spill) needs to know.
    model["hazards"] = spike.get("hazards", False)
    v.take_companions()           # nothing left over from another build
    mounted = []
    for st in stations:
        mounted.append(v.volume(f"spike_{st}", systems.for_station(model, st).build(model, st, debug),
                                systems.tags_for(model, st, {"spike": st})))
        # Its companion volumes (volumes.companion): its hazard drops, each in its own.
        mounted += [v.volume(f"spike_{st}_{n}", eff, tags)
                    for n, (eff, tags) in enumerate(v.take_companions())]
    front = None
    model["in_run"] = spike.get("run", False)
    model["start_day"] = spike.get("start_day", 1)
    model["cards_done"] = spike.get("cards_done", False)
    if spike.get("guests"):
        model["rules"]["guests"] = dict(model["rules"]["guests"], **spike["guests"])
    if spike.get("card_every"):
        model["rules"]["cards"] = dict(model["rules"]["cards"], every_days=spike["card_every"])
    # The moods in play (systems/moods.py, built with the front of house).
    model["mood_chances"] = spike.get("moods", {})
    if spike.get("front"):
        front_volumes, front_layout = spike_front.build(model, GROUND, debug,
                                                        run=spike.get("run", False),
                                                        practice=spike.get("practice", False))
        mounted += front_volumes
        front = front_layout
    if spike.get("hazards"):
        from systems import hazards
        hazards.build(model, debug, dispenser=spike.get("dispenser", False))
        mounted += hazards.volumes(model)
        mounted += [v.volume(f"hazards_{n}", eff, tags)
                    for n, (eff, tags) in enumerate(v.take_companions())]
    extra = []
    if spike.get("tip_dial"):
        extra += _tip_dial(model, debug)
        mounted.append(v.volume("spike_tip_dial", TIP_DIAL_EFFECT, {"spike": "tipdial"}))
    if spike.get("endgame_blocks"):
        extra += _endgame_blocks(model)
        mounted.append(v.volume("spike_endgame", ENDGAME_EFFECT, {"spike": "endgame"}))
    if spike.get("shelves"):
        shelf_blocks, shelf_vols = _shelves(model)
        extra += shelf_blocks
        mounted += shelf_vols
    if spike.get("best_probe"):
        extra += _best_run(model, debug)
        mounted.append(v.volume("spike_best", BEST_EFFECT, {"spike": "best"}))
    if spike.get("carry_probe"):
        extra += _carry_food(model, debug)
        mounted.append(v.volume("spike_carry", CARRY_EFFECT, {"spike": "carry"}))
        mounted.append(v.volume("spike_carry_pad", CARRY_PAD_EFFECT, {"spike": "carrypad"},
                                box=_carry_pad_box()))
    if spike.get("dispenser"):
        extra.append({"x": HAZARD_DISPENSER[0], "y": GROUND, "z": HAZARD_DISPENSER[1],
                      "name": hazards.ids(model)["dispenser"]})
    if extra:
        front = (front[0] + extra, front[1]) if front else (extra, [])
    mounted.append(setup(model, stations, front, debug))
    items = model["items"]
    plate = items[model["vessel"]["clean"]["id"]]["game_id"]
    if spike.get("run"):
        # A run needs only plates: it delivers the crates, which make everything else.
        given = [(SETUP, 1), (plate, 2)]
    elif name.startswith("dish:"):
        # Its crates make everything else.
        given = [(SETUP, 1), (plate, DISH_PLATES)]
    elif "give" in spike:
        given = [(SETUP, 1)] + [(items[i]["game_id"], 1) for i in spike["give"]]
    else:
        given = kit(model, stations)
    if spike.get("carry_probe"):
        given += [("Food_Popcorn", 3)]
    if spike.get("mats"):
        mats = blocks.mat_ids(model)
        ids_ = {"mat": mats["levels"][0], "mat_rubber": mats["rubber"]}
        given += [(ids_[k], n) for k, n in spike["mats"].items()]
    note = " + ".join(model["stations"][st]["label"].lower() for st in stations)
    if spike.get("front"):
        note += " + the front of house"
    needs_clock = any(getattr(systems.for_station(model, st), "NEEDS_CLOCK", False)
                      for st in stations) or spike.get("run", False)
    _world(note, needs_clock, mounted, given)
    return note, given
