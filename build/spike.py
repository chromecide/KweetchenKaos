"""
THE SPIKE WORLD: one system (or a few), mounted over an empty world, to test on its own.

    /kk spike    open the spike world (rebuilt fresh every visit)
    /kk kit      hand over what the mounted system needs to be tested

WHICH SPIKE is chosen at build time (`build.py --spike NAME`, or `./deploy.sh NAME`).
Each spike names the systems it mounts and the kit it needs, both read from the theme --
so a spike of the board hands you the board and exactly the things it presses.

What was learned in the POC and is built in here:
  * ADVENTURE MODE. NPCs ignore interactions from a creative player, and every system
    eventually talks to NPCs.
  * THE WORLD IS GONE once the last player leaves (WorldEmpty removal), so every visit
    starts clean. DeleteOnUniverseStart alone only rebuilt it on a server restart.
  * THE KIT IS A SEPARATE COMMAND. Moving between worlds rebuilds the player entity, and
    items handed over around that go to something about to stop existing.
  * ONE ITEM PER LINE in the kit: "give <item> <count>" is read as giving to a player.
  * Don't run /kk spike from inside the spike world: it rebuilds the world you're in and
    has crashed the server. Leave first.
"""
import pack
import settings
import volumes
from systems import press

INSTANCE = f"{settings.NAMESPACE}_Spike"


def _press_spike(station_id):
    """A press station: two of it, and two of everything it takes."""
    def mount(model, debug):
        return [volumes.volume(f"spike_{station_id}", press.build(model, station_id, debug),
                               {"spike": station_id})]

    def kit(model):
        steps = [s for s in model["steps"]
                 if s["type"] == "press" and s["station"] == station_id]
        inputs = list(dict.fromkeys(s["input"] for s in steps))
        return ([(press.ids(model, station_id)["free"], 2)]
                + [(model["items"][i]["game_id"], 2) for i in inputs])
    return {"mount": mount, "kit": kit, "note": f"the {station_id} (a press station)"}


SPIKES = {
    "board": _press_spike("board"),
}


def build(model, name, debug=True):
    spike = SPIKES[name]
    mounted = spike["mount"](model, debug)
    kit = spike["kit"](model)

    world = pack.out("Instances", INSTANCE, "instance.bson")
    pack.write(world, {
        "$Comment": f"KwitchenKaos spike world, mounting {spike['note']}. See build/spike.py.",
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
    pack.say("commands.kk.kit.desc", "Hand over what the spiked system needs")
    pack.write(pack.out("MacroCommands", "KKSpike.json"), {
        "$Comment": f"Open the spike world (mounting {spike['note']}). Not from inside it.",
        "Name": "kk spike", "Description": "server.commands.kk.spike.desc",
        "Commands": [f"instances spawn {INSTANCE}", "wait 4", "gamemode adventure"]})
    pack.write(pack.out("MacroCommands", "KKKit.json"), {
        "$Comment": "What the spiked system needs. One item per line.",
        "Name": "kk kit", "Description": "server.commands.kk.kit.desc",
        "Commands": [f"give {item}" for item, n in kit for _ in range(n)]})
    return spike["note"], kit
