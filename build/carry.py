"""
CARRYING: picking a station up and putting it down somewhere else. Infrastructure.

    LEFT-CLICK, empty hands   picks it up      (the block's Primary)
    RIGHT-CLICK, carrying     puts it down     (CarryInteractions.Secondary), facing the
                                               way the player chooses
    F, carrying               says "right-click to put it down" -- F stays "use"

Ported from the POC (probe_carry.py, docs/systems.md, "Rearranging"):
  * With EMPTY hands only left-click and F ask a block anything -- a block's right-click is
    never consulted -- and F is every station's "use", so pick-up is left-click. Holding
    anything, that item's own left-click wins: a station only comes up empty-handed.
  * Put-down is right-click (the place key everywhere else) and never shares a button with
    pick-up: sharing one, a lingering press did both.
  * No Cooldown on either: a cooldown's Id is what shares it, and naming both the same once
    made putting one down block picking the next up.
  * Picking up is a real BREAK and putting down a real PLACE, so whatever a system does on
    those follows the block for free -- a chair's table goes and comes, a crate's top too.
  * DURING SERVICE, A MARK, NOT A RULE: carrying marks the player before it breaks the
    block, so a NoDestroy rule cancelling the break left them holding a DUPLICATE. Instead
    the shift's service lock puts an invisible "in service" effect on every player inside
    it (re-applied every second, fading a moment after service ends), and pick-up opens
    with a check that refuses to start while it's on.

Only a station's FREE block is carryable -- anything holding food or a plate stays put, so
nothing ever travels inside a carried block.
"""
import pack
import settings

NS = settings.NAMESPACE
PICKUP, PLACE, HINT = f"{NS}_Carry_Pickup", f"{NS}_Carry_Place", f"{NS}_Carry_Hint"
IN_SERVICE = f"{NS}_In_Service"
MARK_SECONDS, MARK_EVERY = 1.5, 1.0
_written = []


def in_service_mark():
    """The volume EFFECT marking every player inside as in service while the volume is on.
    TICK with an Interval is per player; no conditions, so it isn't a tick gate."""
    return {"Type": "EntityEffect", "Event": "TICK", "Effect": IN_SERVICE, "Mode": "Apply",
            "Duration": MARK_SECONDS, "Interval": MARK_EVERY}


def _write_once():
    if _written:
        return
    _written.append(True)
    it = lambda name, data: pack.write(pack.out("Item", "Interactions", NS, f"{name}.json"), data)
    root = lambda name, first: pack.write(pack.out("Item", "RootInteractions", NS, f"{name}.json"),
                                          {"$Comment": "No Cooldown -- see build/carry.py.",
                                           "Interactions": [first]})
    title = lambda key: {"Type": "ShowEventTitle", "PrimaryTitle": {"MessageId": f"server.{key}"},
                         "IsMajor": False, "DurationS": 2.0, "FadeInDurationS": 0.2,
                         "FadeOutDurationS": 0.4}
    it(f"{PICKUP}_Take", {"$Comment": "Into your hands. See build/carry.py.", "Type": "CarryBlock"})
    it(f"{PICKUP}_Check", {"$Comment": "Only if NOT in service: failing here, nothing is broken, "
                                       "so nothing can be duplicated. See build/carry.py.",
                           "Type": "EffectCondition", "EntityEffectIds": [IN_SERVICE],
                           "Match": "None", "Next": f"{PICKUP}_Take",
                           "Failed": f"{PICKUP}_Refused"})
    it(f"{PICKUP}_Refused", title("kk.carry.refused"))
    root(PICKUP, f"{PICKUP}_Check")
    it(f"{PLACE}_Put", {"$Comment": "Put it down, facing as you choose.", "Type": "CarryPlaceBlock"})
    root(PLACE, f"{PLACE}_Put")
    it(f"{HINT}_Title", title("kk.carry.hint"))
    pack.write(pack.out("Item", "RootInteractions", NS, f"{HINT}.json"),
               {"Interactions": [f"{HINT}_Title"]})
    pack.write(pack.out("Entity", "Effects", NS, f"{IN_SERVICE}.json"),
               {"$Comment": "Invisible: this player is in service, so nothing can be picked "
                            "up. See build/carry.py.",
                "Duration": MARK_SECONDS, "OverlapBehavior": "Overwrite"})
    pack.say("kk.carry.hint", "Right-click to put it down")
    pack.say("kk.carry.refused", "Can't move things during service")


def carryable(item_data):
    """Make a block item pick-up-able. Mutates and returns the ITEM dict (the item is what
    is carried -- a bare BlockType would carry as nothing)."""
    _write_once()
    item_data["BlockType"].setdefault("Interactions", {})["Primary"] = PICKUP
    item_data["CarryInteractions"] = {"Secondary": PLACE, "Use": HINT}
    item_data["CarryHudInputBindings"] = {"Secondary": "SecondaryItemAction",
                                          "Use": "BlockInteractAction"}
    return item_data
