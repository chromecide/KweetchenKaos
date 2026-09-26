"""
BLOCKS: the shapes every system builds its blocks from. Infrastructure only -- no content.

    block_for(look)        an item's look as a block: drawn by its model, never solid
    station_block(...)     a pressable cube station with a full top, so what it holds above
                           it stands on something
    display_block(...)     something SITTING ON a station: the item's look, pressable. A
                           separate block from the item's own, so no other system's rule
                           for the item can fire for one sitting on a station
    NOOP                   the do-nothing interaction. A block's Use (F) must run SOMETHING
                           for the press to reach a volume and for its hint to show; the
                           volume does the actual work. Items use it for right-click too.
"""
import carry
import pack
import settings

NOOP = f"{settings.NAMESPACE}_Noop"

STATION_ICON = "Icons/ItemsGenerated/Bench_Cooking.png"


def write_noop():
    pack.write(pack.out("Item", "Interactions", settings.NAMESPACE, f"{NOOP}_Simple.json"),
               {"$Comment": "Does nothing, on purpose: volumes do the work. See build/blocks.py.",
                "Type": "Simple"})
    pack.write(pack.out("Item", "RootInteractions", settings.NAMESPACE, f"{NOOP}.json"),
               {"$Comment": "A press that only exists to reach a volume. See build/blocks.py.",
                "Interactions": [f"{NOOP}_Simple"]})


def block_for(look):
    block = {"Material": "Empty", "DrawType": "Model", "Opacity": "Transparent",
             "CustomModel": look["model"],
             "CustomModelTexture": [{"Texture": look["texture"], "Weight": 1}]}
    if look.get("scale", 1) != 1:
        block["CustomModelScale"] = look["scale"]
    if look.get("tint"):
        block["Tint"] = [look["tint"]]
    return block


def item(game_id, label, icon, block, comment, movable=False):
    """Any block item: its name, icon and block. `movable`: it can be picked up and put
    down elsewhere between days (carry.py)."""
    pack.say(f"items.{game_id}.name", label)
    data = {"$Comment": comment,
            "TranslationProperties": {"Name": f"server.items.{game_id}.name"},
            "Icon": icon, "PlayerAnimationsId": "Block", "BlockType": block,
            "Tags": {"Type": ["Furniture"], "Family": ["Kitchen"]}}
    pack.write_item(game_id, carry.carryable(data) if movable else data)


def hazard_id(model, kind):
    """A hazard's block ("mess", "spill"): made by the hazard system, dropped by whichever
    system causes it (a guest's mess, a sink's spill)."""
    return settings.game_id(model["theme"]["prefix"], kind)


def with_key(text):
    """The player's interact key in a hint, the way the game's own doors say "Press [F] to
    open": the client fills {key} with whatever the player has it bound to. After the first
    standalone "press", or in front when the hint doesn't say press."""
    import re
    keyed, n = re.subn(r"\b([Pp]ress)\b(?![A-Za-z{])", r"\1 [{key}]", text, count=1)
    return keyed if n else f"[{{key}}] {text}"


def hint(game_id, text, keyed=True):
    """A block's hint line; returns the key the block refers to. `keyed`: show the interact
    key (not for things you don't press: a portal you step on, an authoring slot)."""
    key = f"kk.hint.{game_id}"
    pack.say(key, with_key(text) if keyed else text)
    return f"server.{key}"


# THE TRIM: a band round the top of a station's sides, in the look's "trim" colour. It is a
# side mask (TextureSideMask) -- an overlay drawn in its OWN colours times TintUp -- so it is
# one plain white band, the only image the pack ships, coloured per station. The catch, taken
# knowingly: TintUp colours the station's TOP as well (proven in the texture gallery probe).
TRIM_MASK = "BlockTextures/K2_Trim_Band.png"
TRIM_PIXELS = 2                 # of the texture's 32: a hint of an edge, not a stripe


def write_trim_mask():
    pack.write_png(pack.common(TRIM_MASK), 32, 32,
                   lambda x, y: (255, 255, 255, 255) if y < TRIM_PIXELS else (0, 0, 0, 0))


# THE TURN: a station can stand turned over (look "turn": quarter turns of yaw, pitch and
# roll) -- a face's texture can't be rotated on its own, so the whole block is. It must allow
# any rotation (VariantRotation All) and hold what sits on it whichever face ends up on top.
# Whatever places it sets the turn (turn_index, turn_effect); a block SWAP keeps the block's
# rotation, so a station's states follow it.
ROTATIONS = ("None", "Ninety", "OneEighty", "TwoSeventy")


def turn_index(look):
    """The prefab rotation index of a look's turn (16 x roll + 4 x pitch + yaw), or None."""
    t = look.get("turn")
    return None if not t else 16 * t.get("roll", 0) + 4 * t.get("pitch", 0) + t.get("yaw", 0)


def turned_faces(look, sides, top):
    """The texture entry: `top` on whichever faces END UP top and bottom once the look's turn
    is applied -- so a turned station's "top" is still what you see on top. A quarter roll
    brings East/West up, a quarter pitch North/South (yaw never changes the top)."""
    t = look.get("turn") or {}
    roll, pitch = t.get("roll", 0) % 2, t.get("pitch", 0) % 2
    if roll and pitch:
        raise ValueError("a turn with both a quarter roll and a quarter pitch: say which face "
                         "is on top some other way")
    if roll:
        return {"Weight": 1, "North": sides, "South": sides, "Up": sides, "Down": sides,
                "East": top, "West": top}
    if pitch:
        return {"Weight": 1, "East": sides, "West": sides, "Up": sides, "Down": sides,
                "North": top, "South": top}
    return {"Weight": 1, "Sides": sides, "Up": top, "Down": sides}


def turn_fields(look):
    """The Rotation / Pitch / Roll settings a PlaceBlock or ReplaceBlockType takes."""
    t = look.get("turn") or {}
    return {"Rotation": ROTATIONS[t.get("yaw", 0)], "Pitch": ROTATIONS[t.get("pitch", 0)],
            "Roll": ROTATIONS[t.get("roll", 0)]}


def station_block(game_id, label, look, hint_text, comment, sides=None, tint=None, use=True,
                  light=None, movable=False, top=None, keyed=None, extra=None):
    """`use=False`: a block nothing presses (a queue spot works off ENTER and EXIT only).
    `light`: a glow (glow.light) -- an upgraded station. `sides`/`top`: instead of the
    look's (a busy state's own, e.g. a stove's copper top while cooking)."""
    sides = sides or look["sides"]
    block = {"Material": "Solid", "DrawType": "Cube", "Opacity": "Transparent",
             "Textures": [turned_faces(look, sides, top or look["top"])],
             "BlockSoundSetId": look.get("sound", "Stone"),
             "PhysicalMaterialId": look.get("sound", "Stone"),
             "InteractionHint": hint(game_id, hint_text, use if keyed is None else keyed),
             "Supporting": {"Up": [{"FaceType": "Full"}]}}
    if use:
        block["Interactions"] = {"Use": NOOP}
    if tint:
        block["Tint"] = [tint]
    if light:
        block["Light"] = light
    if look.get("turn"):
        block["VariantRotation"] = "All"
        block["Supporting"] = {face: [{"FaceType": "Full"}]
                               for face in ("Up", "Down", "North", "South", "East", "West")}
    if look.get("top_tint"):
        # The top face only (the sides keep their colour); a trim uses the same tint.
        block["TintUp"] = [look["top_tint"]]
    if look.get("trim"):
        write_trim_mask()
        block["TextureSideMask"] = TRIM_MASK
        block["TintUp"] = [look["trim"]]
    if extra:
        block.update(extra)
    item(game_id, label, look.get("icon", STATION_ICON), block, comment, movable)


def display_block(game_id, label, look, hint_text, comment, extra=None):
    """`extra`: more BlockType settings (a growth config, for things that change by
    themselves)."""
    block = dict(block_for(look), InteractionHint=hint(game_id, hint_text),
                 Interactions={"Use": NOOP},
                 # When what it stands on goes (a crate or a rack picked up), it VANISHES.
                 # The default is to break the ordinary way and drop its own item on the
                 # floor -- "Plate (on the rack)" lying about. (A drop list that drops nothing
                 # isn't allowed: it must drop something.)
                 SupportDropType="Destroy",
                 **(extra or {}))
    item(game_id, label, look["icon"], block, comment)
