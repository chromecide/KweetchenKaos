"""
THE SPIKE WORLD: a few stations, mounted over an empty world, to test on their own.

    /kk spike    open the spike world (rebuilt fresh every visit)
    /kk kit      hand over the SETUP block and what the mounted stations take
    SETUP block  place it anywhere and press it once: the stations are laid out in a row
                 in front of spawn, so nobody has to set a spike up by hand

A SPIKE IS JUST A LIST OF STATIONS AND HOW MANY OF EACH (SPIKES below). Each is mounted by whichever system runs
its role (systems/__init__.py) -- the same way a layout will mount it later, so a spike
tests exactly what ships. Chosen at build time: `build.py --spike NAME`, `./deploy.sh NAME`.

THE KIT IS WORKED OUT FROM THE THEME: the setup block, and everything the stations take
that none of them make (two of raw ingredients and plates, one of the rest).
A board + counter spike hands over raw ingredients (the board makes the dough and pieces),
plates, and cooked pies (the stove isn't mounted, so those can't be made here) --
everything needed to try every combine.

What was learned in the POC and is built in here:
  * ADVENTURE MODE. NPCs ignore interactions from a creative player, and every system
    eventually talks to NPCs.
  * THE WORLD IS GONE once the last player leaves (WorldEmpty removal), so every visit
    starts clean.
  * THE KIT IS A SEPARATE COMMAND. Moving between worlds rebuilds the player entity, and
    items handed over around that go to something about to stop existing.
  * ONE ITEM PER LINE in the kit: "give <item> <count>" is read as giving to a player.
  * Don't run /kk spike from inside the spike world: it rebuilds the world you're in and
    has crashed the server. Leave first.
"""
import blocks
import pack
import settings
import systems
import volumes as v

INSTANCE = f"{settings.NAMESPACE}_Spike"

# name -> {station: how many the setup block lays out}
SPIKES = {
    "board": {"board": 2},
    "counter": {"counter": 3, "board": 2},
}

SETUP = f"{settings.NAMESPACE}_Spike_Setup"
SETUP_EFFECT = f"{SETUP}_System"
GROUND = 1              # the flat spike world's surface: blocks stand at y 1
ROW_Z, ROW_X, GAP = 12, 4, 2   # spawn is (8, 2, 8); the row runs along x, in front of it


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
    # Items stack one to a slot, so keep it lean: two of anything used up in quantity
    # (raw ingredients, plates), one of the rest.
    plate = model["vessel"]["clean"]["id"]
    many = lambda i: model["items"][i].get("source") or i == plate
    return ([(SETUP, 1)]
            + [(model["items"][i]["game_id"], 2 if many(i) else 1) for i in needed])


def setup(model, stations, debug):
    """The setup block, the layout it pastes, and the rule that pastes it once. Returns
    the setup volume."""
    free = lambda st: systems.for_station(model, st).free_block(model, st)
    row = [free(st) for st, count in stations.items() for _ in range(count)]
    pack.write(pack.out("Prefabs", f"{SETUP}_Layout.prefab.json"), {
        "$Comment": "The spike world's stations, in a row in front of spawn. See build/spike.py.",
        "version": 8, "blockIdVersion": 11, "anchorX": 0, "anchorY": 0, "anchorZ": 0,
        "blocks": [{"x": ROW_X + GAP * k, "y": GROUND, "z": ROW_Z, "name": block}
                   for k, block in enumerate(row)],
        "entities": []})
    blocks.station_block(SETUP, "Spike setup", {
        "sides": "BlockTextures/Wood_Softwood_Planks_Side.png",
        "top": "BlockTextures/Wood_Softwood_Planks_Side.png", "sound": "Wood"},
        "Press to lay out the stations (once)",
        "Spike only: press to lay out the stations. See build/spike.py.", tint="#e0c020")

    once = lambda value: {"Type": "TagCondition", "Event": "BLOCK_USED", "Source": "Self",
                          "TagKey": "done", "Comparison": "Exactly", "TagValue": value}
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
              + v.report("kk.setup.done", "[setup] stations laid out: " + ", ".join(
                  f"{n}x {model['stations'][st]['label'].lower()}" for st, n in stations.items()),
                         debug))
    rules.write(SETUP_EFFECT, "Spike only: the setup block. See build/spike.py.")
    return v.volume("spike_setup", SETUP_EFFECT, {"done": "0"})


def build(model, name, debug=True):
    stations = SPIKES[name]
    mounted = [v.volume(f"spike_{st}", systems.for_station(model, st).build(model, st, debug),
                        {"spike": st}) for st in stations]
    mounted.append(setup(model, stations, debug))
    given = kit(model, stations)
    note = " + ".join(model["stations"][st]["label"].lower() for st in stations)

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
