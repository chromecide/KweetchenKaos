"""
SERVING: how a dish in a player's hand reaches a guest. Infrastructure -- the one handshake
the items and the guest system both use, so neither has to know the other.

The mechanism the shipped shears and sheep use: right-clicking (or left-clicking) an NPC
with a served dish runs ContextualUseNPC, which posts the dish's CONTEXT to the NPC; the
guest senses it (InteractionContext) and decides what it means. The dish is ALWAYS taken if
the guest is interactable at all -- it never learns whether the guest wanted it -- which is
why a guest is only interactable while seated, and a wrong dish is a penalty, not a refusal.

ModifyInventory AdjustHeldItemQuantity -1 is how vanilla food is used up (AddItem with a
negative quantity loads but removes nothing). No $Comment inside the interaction map -- it
is a keyed map and an unknown key fails the item.
"""
import settings


def context(item):
    """The label a served dish announces itself by -- one per served item."""
    return f"{settings.NAMESPACE}_Serve_{item['game_id']}"


def interactions(item):
    use = {"Interactions": [
        {"Type": "ContextualUseNPC", "Context": context(item),
         "Effects": {"WorldSoundEventId": "SFX_Player_Pickup_Item"},
         "Next": {"Type": "ModifyInventory", "AdjustHeldItemQuantity": -1}}]}
    return {"Primary": use, "Secondary": use}
