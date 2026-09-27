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
    # PROBE: can a run remember the best day on the player, and can it be read back? Four
    # blocks, nothing else (see _best_run).
    "bestrun": {"stations": {}, "best_probe": True, "give": []},
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



def build(model, name, debug=True):
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
                                                        run=spike.get("run", False))
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
    if spike.get("best_probe"):
        extra += _best_run(model, debug)
        mounted.append(v.volume("spike_best", BEST_EFFECT, {"spike": "best"}))
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
