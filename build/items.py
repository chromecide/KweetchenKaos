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

  * SERVED DISHES ARE HANDED OVER, not placed: their clicks run serving.py's handshake,
    which a seated guest senses.
"""
import blocks
import pack
import serving


def write_all(model):
    blocks.write_noop()
    stack = model["theme"]["defaults"].get("max_stack", 1)
    served = {e["serves"] for e in model["menu"]}
    for iid, item in model["items"].items():
        gid = item["game_id"]
        quality = item["quality"] or "Common"
        pack.say(f"items.{gid}.name", item["label"])
        names = {"Name": f"server.items.{gid}.name"}
        if item.get("description"):
            pack.say(f"items.{gid}.description", item["description"])
            names["Description"] = f"server.items.{gid}.description"
        pack.write_item(gid, {
            "$Comment": f"{item['label']}. From content/{item['file']}.",
            "TranslationProperties": names,
            "Icon": item["look"]["icon"],
            "Quality": quality,
            "MaxStack": stack,
            "PlayerAnimationsId": "Block",
            # Served dishes are handed to guests (serving.py); everything else does nothing.
            # BOTH buttons, always: an item with no left-click of its own lets the block's
            # through, and a station's left-click is PICK UP (carry.py) -- holding a kit, a
            # left-click on the stove carried it off and the kit was gone.
            "Interactions": (serving.interactions(item) if iid in served
                             else {"Primary": blocks.NOOP, "Secondary": blocks.NOOP}),
            "BlockType": blocks.block_for(item["look"]),
        })
    return len(model["items"])
