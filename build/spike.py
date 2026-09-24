"""
THE SPIKE WORLD: a few stations, mounted over an empty world, to test on their own.

    /kk spike    open the spike world (rebuilt fresh every visit)
    /kk kit      hand over what the mounted stations need to be tested

A SPIKE IS JUST A LIST OF STATIONS (SPIKES below). Each is mounted by whichever system runs
its role (systems/__init__.py) -- the same way a layout will mount it later, so a spike
tests exactly what ships. Chosen at build time: `build.py --spike NAME`, `./deploy.sh NAME`.

THE KIT IS WORKED OUT FROM THE THEME: two of each mounted station, and everything those
stations take that none of them make (two of raw ingredients and plates, one of the rest).
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
import pack
import settings
import systems
import volumes

INSTANCE = f"{settings.NAMESPACE}_Spike"

SPIKES = {
    "board": ["board"],
    "counter": ["counter", "board"],
}


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
    return ([(systems.for_station(model, st).free_block(model, st), 2) for st in stations]
            + [(model["items"][i]["game_id"], 2 if many(i) else 1) for i in needed])


def build(model, name, debug=True):
    stations = SPIKES[name]
    mounted = [volumes.volume(f"spike_{st}", systems.for_station(model, st).build(model, st, debug),
                              {"spike": st}) for st in stations]
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
