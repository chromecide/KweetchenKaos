"""
SERVING: how a dish in a player's hand reaches a guest. Infrastructure -- the one handshake
the items and the guest system both use, so neither has to know the other.

The mechanism the shipped shears and sheep use: F (or either click) on an NPC
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


def _serve(then=None):
    step = {"Type": "ContextualUseNPC", "Context": None,
            "Effects": {"WorldSoundEventId": "SFX_Player_Pickup_Item"},
            "Next": {"Type": "ModifyInventory", "AdjustHeldItemQuantity": -1}}
    if then:
        step["Failed"] = then
    return step


def interactions(item):
    """Serve with F (like every other step), or either click.

    F, SPIKE: an item's own Use has no shipped example -- F on an NPC is normally the NPC's.
    So F tries the guest first and, when there is no guest to take it, falls back to the
    block's own F (UseBlock) -- the shipped place-block right-click does the same the other
    way round (UseBlock, else place). Without the fallback a dish in hand would make every
    counter, stove and bin deaf to F."""
    serve = lambda then=None: dict(_serve(then), Context=context(item))
    click = {"Interactions": [serve()]}
    return {"Primary": click, "Secondary": click,
            "Use": {"Interactions": [serve({"Type": "UseBlock"})]}}
