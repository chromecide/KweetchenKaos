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
  * ItemCondition consumes only after EVERY condition in its entry has passed, and then at
    once -- a later rule for the same press sees the hand already emptied.
  * RULES RUN IN NUMBER ORDER. The volume sorts its entry numbers and walks them upwards
    (TriggerVolumeTickingSystem.collectEntries), so a rule that must see the hand before
    another empties it gets the lower number.
  * The server log: a volume can't log. A throwaway NPC can -- log() spawns one that logs a
    line and vanishes. NPC Log is limited to ONE LINE A SECOND across the whole server.
    The logger must stay out of the way: a full-size Klops spawned on the player made the
    board nearly unusable. So its body is a speck (the salt model at a tenth size, with a
    tiny hitbox), and it has no DisplayNames, so no name tag. It spawns AT the player's
    feet: spawned two blocks below, it fell out of the bottom of the flat spike world and
    was removed before it could log anything.
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


# THE EIGHT CELLS ROUND A POINT, at its own height: where a mess or a spill can land.
AROUND = [(-1, -1), (0, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (0, 1), (1, 1)]


def drop_around(rules, first, key, sizes, gate, event, origin="Event", dy=0.0, large=(),
                on_large=None):
    """Rules first..first+49: one of the eight cells round the origin ("Event": the block
    the event was at; "Entity": whoever caused it), dy up, picked AT RANDOM, gets a hazard:

        empty            ->  a new one, the smallest (sizes[0])
        one of `sizes`   ->  it GROWS a size
        one of `large`   ->  with `on_large`: that is placed over it -- a SPREADING large one,
                             whose placing sets off a drop round IT (hazards.py); without,
                             it's full, like:
        anything else    ->  (a table, a chair, another kind) full: the pick goes on to
                             another cell; if every cell is full, nothing
    `gate`: the conditions that start it. `key` names its tags (unique per volume).

    Why it's built this way: a condition can't ask "is this cell empty?" (BlockTypeCondition
    fails on an empty cell), but it CAN ask "is it a small mess?", and PlaceBlock OnlyAir only
    fills an empty cell, whose block is there AT ONCE. So each cell in turn is picked at a
    chance of 1/(cells left) -- the fair pick -- and then: grow it if it's a hazard that can
    grow; else try to place; and if the smallest is now there, it landed. Growing is
    checked BEFORE placing, so a small one already there grows rather than counts as placed."""
    going, tried = f"{key}_drop", f"{key}_tried"
    tag = lambda k, val: {"Type": "TagCondition", "Event": event, "Source": "Self",
                          "TagKey": k, "Comparison": "Exactly", "TagValue": str(val)}
    put = lambda k, val: {"Type": "ModifyTags", "Event": event, "Operation": "Set",
                          "TagKey": k, "TagValue": str(val)}
    rules.add(first, list(gate), [put(going, 1), put(tried, 0)])
    for k, (dx, dz) in enumerate(AROUND):
        at_cell = {"X": float(dx), "Y": float(dy), "Z": float(dz)}
        is_ = lambda *blocks_: {"Type": "BlockTypeCondition", "Event": event,
                                "BlockType": list(blocks_), "PositionSource": origin,
                                "PositionOffset": at_cell}
        # GROW BY PLACING the next size over it: PlaceBlock rounds the point to a cell exactly
        # as the condition that found it does. (ReplaceBlockType only takes blocks whose
        # CENTRE is in its box: a tenth-of-a-block box offset from the point held none -- above
        # a block's centre for a press, anywhere for an entity's feet -- and nothing grew.)
        grow = lambda frm, to: {"Type": "PlaceBlock", "Event": event, "BlockType": to,
                                "Position": at_cell, "Origin": origin, "ReplaceMode": "Always"}
        n = first + 1 + 6 * k
        rules.add(n, [tag(going, 1), {"Type": "RandomChanceCondition", "Event": event,
                                      "Chance": 1.0 / (len(AROUND) - k)}], [put(tried, k + 1)])
        if on_large:
            rules.add(n + len(sizes) + 2, [tag(going, 1), tag(tried, k + 1), is_(*large)],
                      [grow(None, on_large), put(going, 0)])
        for j in range(len(sizes) - 1, 0, -1):          # the larger first: one grows once
            rules.add(n + len(sizes) - j, [tag(going, 1), tag(tried, k + 1), is_(sizes[j - 1])],
                      [grow(sizes[j - 1], sizes[j]), put(going, 0)])
        rules.add(n + len(sizes), [tag(going, 1), tag(tried, k + 1)],
                  [{"Type": "PlaceBlock", "Event": event, "BlockType": sizes[0],
                    "Position": at_cell, "Origin": origin, "ReplaceMode": "OnlyAir"}])
        rules.add(n + len(sizes) + 1, [tag(going, 1), tag(tried, k + 1), is_(sizes[0])],
                  [put(going, 0)])
    rules.add(first + 1 + 6 * len(AROUND), [tag(going, 1)], [put(going, 0)])


def holding(item, event="BLOCK_USED"):
    """The presser holds one of these; it is taken once the whole rule passes."""
    return {"Type": "ItemCondition", "Event": event, "Item": item, "Quantity": 1,
            "Consume": True, "Location": "InHand"}


def has(item, event="BLOCK_USED"):
    """The presser holds one of these; nothing is taken."""
    return {"Type": "ItemCondition", "Event": event, "Item": item, "Quantity": 1,
            "Consume": False, "Location": "InHand"}


def not_holding(item, event="BLOCK_USED"):
    """The presser does NOT have this in hand (a count of at most zero). Nothing is taken."""
    return {"Type": "ItemCondition", "Event": event, "Item": item, "Quantity": 0,
            "Comparison": "AtMost", "Consume": False, "Location": "InHand"}


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


def title(key, text, sub_key=None, sub_text=None, event="BLOCK_USED", seconds=4.0):
    """The big centre banner. It reaches only the player who set the event off, so it goes
    on player events (a block used), never on a tick or a signal. It can print tags too."""
    pack.say(key, text)
    effect = {"Type": "ShowEventTitle", "Event": event, "PrimaryTitle": f"server.{key}",
              "IsMajor": True, "Duration": seconds}
    if sub_key:
        pack.say(sub_key, sub_text)
        effect["SecondaryTitle"] = f"server.{sub_key}"
    return effect


LOGGER_MODEL = f"{settings.NAMESPACE}_Logger"


def _write_logger_model():
    pack.write(pack.out("Models", settings.NAMESPACE, f"{LOGGER_MODEL}.json"), {
        "$Comment": "The logger's body: a speck, so it is never in the way. See build/volumes.py.",
        # An entity model must come from Characters/, NPC/, Items/ or VFX/ -- the petal
        # (Resources/) was refused. Salt is already tiny.
        "Model": "Items/Ingredients/Salt.blockymodel",
        "Texture": "Items/Ingredients/Salt_Texture.png",
        "HitBox": {"Min": {"X": -0.05, "Y": 0.0, "Z": -0.05},
                   "Max": {"X": 0.05, "Y": 0.1, "Z": 0.05}},
        "MinScale": 0.1, "MaxScale": 0.1})


def log(key, text, event="BLOCK_USED"):
    """A line in the server log, by way of a throwaway NPC (see the top of this file)."""
    _write_logger_model()
    role = f"{settings.NAMESPACE}_Log_{key}"
    pack.say(f"npcRoles.{role}.name", "log")
    pack.write(pack.out("NPC", "Roles", settings.NAMESPACE, f"{role}.json"), {
        "$Comment": "Logs one line and vanishes. See build/volumes.py.",
        "Type": "Generic", "StartState": "Idle",
        "NameTranslationKey": f"server.npcRoles.{role}.name",
        "DefaultNPCAttitude": "Ignore", "DefaultPlayerAttitude": "Neutral",
        "Appearance": LOGGER_MODEL, "MaxHealth": 20, "Invulnerable": True,
        "DisableDamageGroups": ["Self"], "KnockbackScale": 0.0,
        "MotionControllerList": [{"Type": "Walk", "MaxWalkSpeed": 4, "Gravity": 10,
                                  "RunThreshold": 0.3, "MaxFallSpeed": 15,
                                  "MaxRotationSpeed": 360, "Acceleration": 10}],
        "Instructions": [{"Instructions": [
            {"Sensor": {"Type": "State", "State": "Idle"},
             "Actions": [{"Type": "Log", "Message": text}, {"Type": "Despawn"}]}]}]})
    return {"Type": "SpawnNpc", "Event": event, "NpcType": role, "Origin": "Entity",
            "Count": 1, "Offset": {"X": 0.0, "Y": 0.0, "Z": 0.0}, "Yaw": 0.0}


def report(key, text, debug, event="BLOCK_USED", to_log=True):
    """Instrumentation: the server log when debugging, nothing otherwise. NEVER chat -- chat
    is for players (say); a station's every move in chat was debug noise.

    to_log=False drops a line: the log takes ONE line a second, so frequent events (every
    press) would crowd out the milestones that matter; log the milestones."""
    if not debug or not to_log:
        return []
    return [log(key, text, event)]


# A spike world mounts its systems over this box, round the origin. A RESTAURANT mounts
# them over its own room instead (restaurant.room_box): signals reach 64 blocks from a
# volume's POSITION, so a volume must sit on what it serves (see volume()).
WORLD_BOX = ((-64.0, -8.0, -64.0), (64.0, 40.0, 64.0))


def volume(name, effect, tags, targets=("Player",), box=WORLD_BOX):
    """A system mounted in a box ((min x, y, z), (max x, y, z)) -- by default the whole
    test world."""
    # POSITION IS THE BOX'S CENTRE, and the shape is drawn round it. A signal's reach (and
    # a tag read from another volume) is measured from the volume's POSITION -- with every
    # position at the origin and the box drawn out at the room, a pool 70 blocks from the
    # origin never heard "arrive", while pads at 62 did.
    (x0, y0, z0), (x1, y1, z1) = box
    cx, cy, cz = (x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2
    return {"Position": {"X": cx, "Y": cy, "Z": cz},
            "Shape": {"Type": "Box",
                      "Min": {"X": x0 - cx, "Y": y0 - cy, "Z": z0 - cz},
                      "Max": {"X": x1 - cx, "Y": y1 - cy, "Z": z1 - cz}},
            "EffectAsset": effect, "TargetTypes": list(targets), "Enabled": True,
            "KeepLoaded": False, "Tags": dict(tags), "Name": name}
