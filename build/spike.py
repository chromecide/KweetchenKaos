"""
THE SPIKE WORLD: stations (and, for a service spike, the front of house) mounted over an
empty world, to test on their own.

    /kk spike    open the spike world (rebuilt fresh every visit)
    /kk kit      hand over the SETUP block and what the mounted stations take
    SETUP block  place it anywhere and press it once: everything is laid out at fixed
                 places (see the map below), so nobody sets a spike up by hand

A SPIKE IS A LIST OF STATIONS AND HOW MANY OF EACH, plus "front": True for the queue,
chairs and guests (SPIKES below). Each station is mounted by whichever system runs its role
(systems/__init__.py) -- the way a layout will mount it later, so a spike tests exactly what
ships. Chosen at build time: `build.py --spike NAME`, or `./deploy.sh NAME`.

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
import spike_front
import systems
import volumes as v

INSTANCE = f"{settings.NAMESPACE}_Spike"
KITCHEN = {"crates": 1, "board": 2, "counter": 3, "stove": 2, "bin": 1, "sink": 1,
           "rack": 1}
SPIKES = {
    "board": {"stations": {"board": 2}},
    # The plate rack on its own, with a sink to wash a dirty plate to put back.
    "rack": {"stations": {"rack": 2, "sink": 1}},
    "counter": {"stations": {"counter": 3, "board": 2}},
    "kitchen": {"stations": KITCHEN},
    # A full service: the kitchen, the queue, chairs and guests, called by hand.
    "service": {"stations": KITCHEN, "front": True},
    # A full RUN: the shift runs the days. The crates aren't laid out -- the run delivers
    # them on day 1, and more with recipe cards.
    # Crates at 0: mounted (so delivered ones work) but not laid out.
    "run": {"stations": dict(KITCHEN, crates=0), "front": True, "run": True},
}
SETUP = f"{settings.NAMESPACE}_Spike_Setup"
SETUP_EFFECT = f"{SETUP}_System"
GROUND = 1              # the flat spike world's surface: blocks stand at y 1
ROW_Z, ROW_X, GAP = 12, 12, 2


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
        made.update([s["output"]] if "output" in s else [x["gives"] for x in s["stages"]])
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
    row = [systems.for_station(model, st).layout(model, st)
           for st, count in stations.items() for _ in range(count)]
    layout = [{"x": ROW_X + GAP * k, "y": GROUND + dy, "z": ROW_Z, "name": block}
              for k, column in enumerate(row) for dy, block in column]
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
    kits = [(it["game_id"], 1) for i, it in model["items"].items() if i.endswith("_kit")]
    given = [(SETUP, 1), (model["items"][model["vessel"]["clean"]["id"]]["game_id"], 2)] + kits
    note = f"the room {info['name']}"
    _world(note, True, [v.volume("spike_setup", SETUP_EFFECT, {"done": "0"})], given)
    return note, given



def build(model, name, debug=True):
    if name.startswith("room:"):
        return build_room(model, name[len("room:"):], debug)
    spike = SPIKES[name]
    stations = stations_of(model, name)
    mounted = [v.volume(f"spike_{st}", systems.for_station(model, st).build(model, st, debug),
                        systems.tags_for(model, st, {"spike": st})) for st in stations]
    front = None
    if spike.get("front"):
        front_volumes, front_layout = spike_front.build(model, GROUND, debug,
                                                        run=spike.get("run", False))
        mounted += front_volumes
        front = front_layout
    mounted.append(setup(model, stations, front, debug))
    # A run needs only plates: the run delivers the crates, which make everything else.
    # ...plus one of every upgrade kit, so upgrades can be tried without earning them.
    kits = [(it["game_id"], 1) for i, it in model["items"].items() if i.endswith("_kit")]
    given = ([(SETUP, 1), (model["items"][model["vessel"]["clean"]["id"]]["game_id"], 2)]
             + kits if spike.get("run") else kit(model, stations))
    note = " + ".join(model["stations"][st]["label"].lower() for st in stations)
    if front:
        note += " + the front of house"
    needs_clock = any(getattr(systems.for_station(model, st), "NEEDS_CLOCK", False)
                      for st in stations) or spike.get("run", False)
    _world(note, needs_clock, mounted, given)
    return note, given
