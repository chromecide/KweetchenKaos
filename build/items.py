"""
THE ITEMS: every item a theme defines, written as a game item.

What every item is, whatever the theme:

  * DRAWN BY ITS LOOK. A shipped model, texture, scale and tint, by path. The item's block
    form is how it shows in the hand; stations never place the item's own block -- each
    system makes its own display blocks from the same look.
  * NEVER PUT DOWN BY HAND. An item with a block form can be right-clicked into the world
    anywhere, and in adventure nothing gets it back (v1 lost plates that way). Right-click
    runs a no-op. Things only go down through the stations that handle them.
  * NOT FOOD TO THE GAME. v1 parented food on the shipped Template_Food, which brings the
    game's own eating with it. v2 items have no parent: nothing in a kitchen is eaten by
    the player.
  * ONE AT A TIME. MaxStack is the theme's default (1: Plate Up's one-thing-in-hand).
  * QUALITY COLOURS THE HOTBAR SLOT. Served dishes are Legendary so they stand out; an
    item may set its own (a dirty plate is Junk); everything else is Common.

Serving (a guest taking a dish) is added by the guest system when it exists; nothing here
knows about guests yet.
"""
import pack
import settings

NOOP = f"{settings.NAMESPACE}_Noop"


def write_noop():
    """The do-nothing right-click every item gets."""
    pack.write(pack.out("Item", "Interactions", settings.NAMESPACE, f"{NOOP}_Simple.json"),
               {"$Comment": "Does nothing, on purpose. See build/items.py.",
                "Type": "Simple"})
    pack.write(pack.out("Item", "RootInteractions", settings.NAMESPACE, f"{NOOP}.json"),
               {"$Comment": "Right-click on any kitchen item: nothing. See build/items.py.",
                "Interactions": [f"{NOOP}_Simple"]})


def block_for(look):
    """A look as a block: drawn by its model, never solid. Systems use this for their
    display blocks too, so an item looks the same in the hand and on a station."""
    block = {"Material": "Empty", "DrawType": "Model", "Opacity": "Transparent",
             "CustomModel": look["model"],
             "CustomModelTexture": [{"Texture": look["texture"], "Weight": 1}]}
    if look.get("scale", 1) != 1:
        block["CustomModelScale"] = look["scale"]
    if look.get("tint"):
        block["Tint"] = [look["tint"]]
    return block


def write_all(model):
    write_noop()
    served = {e["serves"] for e in model["menu"]}
    stack = model["theme"]["defaults"].get("max_stack", 1)
    for iid, item in model["items"].items():
        gid = item["game_id"]
        quality = item["quality"] or ("Legendary" if iid in served else "Common")
        pack.say(f"items.{gid}.name", item["label"])
        pack.write_item(gid, {
            "$Comment": f"{item['label']}. From content/{item['file']}.",
            "TranslationProperties": {"Name": f"server.items.{gid}.name"},
            "Icon": item["look"]["icon"],
            "Quality": quality,
            "MaxStack": stack,
            "PlayerAnimationsId": "Block",
            "Interactions": {"Secondary": NOOP},
            "BlockType": block_for(item["look"]),
        })
    return len(model["items"])
