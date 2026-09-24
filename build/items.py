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
  * QUALITY COLOURS THE HOTBAR SLOT. An item may set its own: plated dishes are Legendary
    (made so by content.py when it builds plating in), a dirty plate is Junk; everything
    else is Common.

Serving (a guest taking a dish) is added by the guest system when it exists; nothing here
knows about guests yet.
"""
import blocks
import pack


def write_all(model):
    blocks.write_noop()
    stack = model["theme"]["defaults"].get("max_stack", 1)
    for iid, item in model["items"].items():
        gid = item["game_id"]
        quality = item["quality"] or "Common"
        pack.say(f"items.{gid}.name", item["label"])
        pack.write_item(gid, {
            "$Comment": f"{item['label']}. From content/{item['file']}.",
            "TranslationProperties": {"Name": f"server.items.{gid}.name"},
            "Icon": item["look"]["icon"],
            "Quality": quality,
            "MaxStack": stack,
            "PlayerAnimationsId": "Block",
            "Interactions": {"Secondary": blocks.NOOP},
            "BlockType": blocks.block_for(item["look"]),
        })
    return len(model["items"])
