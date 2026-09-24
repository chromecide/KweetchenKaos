"""
VOLUME EFFECTS: the conditions and effects systems write, spelled right once.
Infrastructure only -- no content. Each helper carries what was learned the hard way in
the Kitchen POC (kitchen-poc/docs/systems.md has the full record):

  * TIMING. Tags, PlaceBlock, GiveItem and a consumed held item take effect at once.
    ReplaceBlockType lands at the END of the tick. So a chain of presses is safe when each
    press starts from a DIFFERENT block: a press on _Left_3 can only ever be the _Left_3
    rule, even after it has asked for _Left_2.
  * BlockTypeCondition never matches air ("is the cell above empty" can't be asked), which
    is why stations have busy states instead.
  * ItemCondition consumes only after EVERY condition in its entry has passed.
  * The server log: a volume can't log. A throwaway NPC can -- log() spawns one that logs a
    line and vanishes. NPC Log is limited to ONE LINE A SECOND across the whole server.
    The logger has no DisplayNames, so it has no name tag.
  * Chat (say) is for the tester; it never reaches a log file.
"""
import pack
import settings

# A block-sized box a little inside the cell, centred on the event's position (a block
# event's position is the CENTRE of the block).
CELL, HALF = 0.9, 0.45


class Entries:
    """Numbered rules: every condition and effect of rule n carries Entry n."""

    def __init__(self):
        self.conditions, self.effects = [], []

    def add(self, n, conditions, effects):
        self.conditions += [dict(c, Entry=n) for c in conditions]
        self.effects += [dict(e, Entry=n) for e in effects]

    def write(self, name, comment):
        pack.write(pack.out("TriggerVolumes", "Effects", f"{name}.json"),
                   {"$Comment": comment, "Conditions": self.conditions,
                    "Effects": self.effects})


def at(blocks, dy=0.0, event="BLOCK_USED"):
    """The block the event happened at (dy above it) is one of these."""
    c = {"Type": "BlockTypeCondition", "Event": event, "BlockType": list(blocks),
         "PositionSource": "Event"}
    if dy:
        c["PositionOffset"] = {"X": 0.0, "Y": float(dy), "Z": 0.0}
    return c


def holding(item, event="BLOCK_USED"):
    """The presser holds one of these; it is taken once the whole rule passes."""
    return {"Type": "ItemCondition", "Event": event, "Item": item, "Quantity": 1,
            "Consume": True, "Location": "InHand"}


def cell(frm, to, dy=0.0, event="BLOCK_USED"):
    """The block at the event (dy above), if it is one of `frm`, becomes `to` -- at the
    end of the tick."""
    return {"Type": "ReplaceBlockType", "Event": event, "Origin": "Event",
            "FromBlockTypes": list(frm), "ToBlockType": to,
            "Bounds": "Aabb", "X": CELL, "Y": CELL, "Z": CELL,
            "Offset": {"X": -HALF, "Y": dy - HALF, "Z": -HALF}}


def place(block, dy=1.0, event="BLOCK_USED"):
    """Put a block dy above the event, at once."""
    return {"Type": "PlaceBlock", "Event": event, "BlockType": block,
            "Position": {"X": 0.0, "Y": float(dy), "Z": 0.0}, "Origin": "Event",
            "ReplaceMode": "Always"}


def give(item, event="BLOCK_USED"):
    return {"Type": "GiveItem", "Event": event, "Item": item, "Quantity": 1,
            "OverflowBehavior": "DropRemainder"}


def sound(pitch=1.0, volume=1.0, name="SFX_Player_Pickup_Item", event="BLOCK_USED"):
    return {"Type": "PlaySound", "Event": event, "SoundEvent": name, "Volume": volume,
            "Pitch": pitch}


def say(key, text, event="BLOCK_USED"):
    """A chat line to everyone."""
    pack.say(key, text)
    return {"Type": "SendMessage", "Event": event, "Message": f"server.{key}",
            "Recipient": "AllPlayers"}


def log(key, text, event="BLOCK_USED"):
    """A line in the server log, by way of a throwaway NPC (see the top of this file)."""
    role = f"{settings.NAMESPACE}_Log_{key}"
    pack.say(f"npcRoles.{role}.name", "log")
    pack.write(pack.out("NPC", "Roles", settings.NAMESPACE, f"{role}.json"), {
        "$Comment": "Logs one line and vanishes. See build/volumes.py.",
        "Type": "Generic", "StartState": "Idle",
        "NameTranslationKey": f"server.npcRoles.{role}.name",
        "DefaultNPCAttitude": "Ignore", "DefaultPlayerAttitude": "Neutral",
        "Appearance": "Klops", "MaxHealth": 20, "Invulnerable": True,
        "DisableDamageGroups": ["Self"], "KnockbackScale": 0.0,
        "MotionControllerList": [{"Type": "Walk", "MaxWalkSpeed": 4, "Gravity": 10,
                                  "RunThreshold": 0.3, "MaxFallSpeed": 15,
                                  "MaxRotationSpeed": 360, "Acceleration": 10}],
        "Instructions": [{"Instructions": [
            {"Sensor": {"Type": "State", "State": "Idle"},
             "Actions": [{"Type": "Log", "Message": text}, {"Type": "Despawn"}]}]}]})
    return {"Type": "SpawnNpc", "Event": event, "NpcType": role, "Origin": "Entity",
            "Count": 1, "Offset": {"X": 0.0, "Y": 0.0, "Z": 0.0}, "Yaw": 0.0}


def report(key, text, debug, event="BLOCK_USED"):
    """Instrumentation: chat AND server log when debugging, nothing otherwise."""
    return [say(key, text, event), log(key, text, event)] if debug else []


def volume(name, effect, tags, box=64.0):
    """A system mounted over a whole test world."""
    return {"Position": {"X": 0.0, "Y": 0.0, "Z": 0.0},
            "Shape": {"Type": "Box", "Min": {"X": -box, "Y": -8.0, "Z": -box},
                      "Max": {"X": box, "Y": 40.0, "Z": box}},
            "EffectAsset": effect, "TargetTypes": ["Player"], "Enabled": True,
            "KeepLoaded": False, "Tags": dict(tags), "Name": name}
