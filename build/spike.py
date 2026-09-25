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
import settings
import spike_front
import systems
import volumes as v

INSTANCE = f"{settings.NAMESPACE}_Spike"
KITCHEN = {"crates": 1, "board": 2, "counter": 3, "stove": 2, "bin": 1, "sink": 1}
SPIKES = {
    "board": {"stations": {"board": 2}},
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
    # WORLD position: the layout lands in the same place wherever the block was pressed.
    rules.add(2, [v.at([SETUP]), once("0")],
              [{"Type": "PastePrefab", "Event": "BLOCK_USED", "Prefab": f"{SETUP}_Layout",
                "Origin": "VolumeOrigin", "Position": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                "ShowParticles": False},
               {"Type": "ModifyTags", "Event": "BLOCK_USED", "Operation": "Set",
                "TagKey": "done", "TagValue": "1"}]
              + v.report("kk.setup.done", f"[setup] laid out: {what}, the crates"
                         + (", the queue, chairs and guest callers" if front else ""), debug))
    rules.write(SETUP_EFFECT, "Spike only: the setup block. See build/spike.py.")
    return v.volume("spike_setup", SETUP_EFFECT, {"done": "0"})


def build(model, name, debug=True):
    spike = SPIKES[name]
    stations = stations_of(model, name)
    mounted = [v.volume(f"spike_{st}", systems.for_station(model, st).build(model, st, debug),
                        {"spike": st}) for st in stations]
    front = None
    if spike.get("front"):
        front_volumes, front_layout = spike_front.build(model, GROUND, debug,
                                                        run=spike.get("run", False))
        mounted += front_volumes
        front = front_layout
    mounted.append(setup(model, stations, front, debug))
    # A run needs only plates: the run delivers the crates, which make everything else.
    given = ([(SETUP, 1), (model["items"][model["vessel"]["clean"]["id"]]["game_id"], 2)]
             if spike.get("run") else kit(model, stations))
    note = " + ".join(model["stations"][st]["label"].lower() for st in stations)
    if front:
        note += " + the front of house"
    needs_clock = any(getattr(systems.for_station(model, st), "NEEDS_CLOCK", False)
                      for st in stations)

    pack.write(pack.out("Instances", INSTANCE, "instance.bson"), {
        "$Comment": f"KwitchenKaos spike world, mounting: {note}. See build/spike.py.",
        "Version": 2,
        "WorldGen": {"Type": "Flat",
                     "Layers": [{"From": 0, "To": 1, "BlockType": "Soil_Grass"}]},
        "SpawnProvider": {"Id": "Global",
                          "SpawnPoint": {"X": 8.0, "Y": 2.0, "Z": 8.0,
                                         "Pitch": 0.0, "Yaw": 0.0, "Roll": 0.0}},
        "GameMode": "Adventure",
        "GameTime": "0001-01-01T12:00:00Z",
        "IsGameTimePaused": True,
        # A timed station (stove, crates) needs the clock running.
        **(clock.WORLD_TIME if needs_clock or spike.get("run") else {}),
        "IsSpawningNPC": False, "IsSpawnMarkersEnabled": False,
        "IsBlockSpawnersEnabled": False,
        "DeleteOnRemove": True, "DeleteOnUniverseStart": True,
        "Plugin": {"Instance": {
            "InstanceKey": INSTANCE.lower(),
            "RemovalConditions": [{"Type": "WorldEmpty", "TimeoutSeconds": 10.0}]}}})
    pack.write(pack.out("Instances", INSTANCE, "resources", "TriggerVolumeData.json"),
               {"Volumes": {f"5b1ce000-0000-4000-8000-{i:012d}": vol
                            for i, vol in enumerate(mounted, start=1)}})

    pack.say("commands.kk.spike.desc", "Open the KwitchenKaos spike world")
    pack.say("commands.kk.kit.desc", "Hand over what the spiked stations need")
    pack.write(pack.out("MacroCommands", "KKSpike.json"), {
        "$Comment": f"Open the spike world (mounting: {note}). Not from inside it.",
        "Name": "kk spike", "Description": "server.commands.kk.spike.desc",
        "Commands": [f"instances spawn {INSTANCE}", "wait 4", "gamemode adventure"]})
    pack.write(pack.out("MacroCommands", "KKKit.json"), {
        "$Comment": "What the spiked stations need. One item per line.",
        "Name": "kk kit", "Description": "server.commands.kk.kit.desc",
        "Commands": [f"give {item}" for item, n in given for _ in range(n)]})
    return note, given
