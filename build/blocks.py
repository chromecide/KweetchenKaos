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


def item(game_id, label, icon, block, comment):
    """Any block item: its name, icon and block."""
    pack.say(f"items.{game_id}.name", label)
    pack.write_item(game_id, {
        "$Comment": comment,
        "TranslationProperties": {"Name": f"server.items.{game_id}.name"},
        "Icon": icon, "PlayerAnimationsId": "Block", "BlockType": block,
        "Tags": {"Type": ["Furniture"], "Family": ["Kitchen"]}})


def hint(game_id, text):
    """A block's hint line; returns the key the block refers to."""
    key = f"kk.hint.{game_id}"
    pack.say(key, text)
    return f"server.{key}"


def station_block(game_id, label, look, hint_text, comment, sides=None, tint=None, use=True):
    """`use=False`: a block nothing presses (a queue spot works off ENTER and EXIT only)."""
    sides = sides or look["sides"]
    block = {"Material": "Solid", "DrawType": "Cube", "Opacity": "Transparent",
             "Textures": [{"Weight": 1, "Sides": sides, "Up": look["top"], "Down": sides}],
             "BlockSoundSetId": look.get("sound", "Stone"),
             "PhysicalMaterialId": look.get("sound", "Stone"),
             "InteractionHint": hint(game_id, hint_text),
             "Supporting": {"Up": [{"FaceType": "Full"}]}}
    if use:
        block["Interactions"] = {"Use": NOOP}
    if tint:
        block["Tint"] = [tint]
    item(game_id, label, look.get("icon", STATION_ICON), block, comment)


def display_block(game_id, label, look, hint_text, comment, extra=None):
    """`extra`: more BlockType settings (a growth config, for things that change by
    themselves)."""
    block = dict(block_for(look), InteractionHint=hint(game_id, hint_text),
                 Interactions={"Use": NOOP}, **(extra or {}))
    item(game_id, label, look["icon"], block, comment)
