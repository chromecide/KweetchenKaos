"""
THE SEATING SYSTEM: chairs, their tables, and the washing up guests leave behind.

    place a chair          ->  its table appears in front of it, whichever way it faces
                               (refused and handed back if that cell already has a table)
    break a chair          ->  its own table goes with it, and nobody else's
    a guest sits           ->  the chair is TAKEN: no other guest can see it
    a guest leaves fed     ->  the chair is DIRTY and a dirty plate sits on its table
    a guest leaves unfed   ->  the chair is clean again
    press that plate       ->  you get the dirty plate; the chair is free again

Ported from the Kitchen POC (kitchen-poc/docs/systems.md, SeatingSystem). What each rule
answers:

  * CHAIRS HAVE A FACING, and the table goes on it. The quarter turns were MEASURED in
    game: Deg0 = +Z, Deg90 = +X, Deg180 = -Z, Deg270 = -X (the first guess had the X pair
    reversed and put half the tables behind their chairs). Enum values are written the
    engine's legacy way, "Deg90" -- never "DEG_90", which is refused.
  * PLATES ARE PLACED BY THIS SYSTEM, not the guest. An NPC can't read a block's rotation;
    a volume can. So a guest only says "I'm leaving, and I'm here", and the plate lands on
    ITS chair's table. A fixed offset in the guest once put a plate on a neighbour's table
    and freed the wrong seat.
  * EVERY CHAIR HAS ITS OWN TABLE, one variant per facing, so breaking a chair removes
    exactly its own table: a table at offset d carrying the variant for facing d can only
    belong to the chair at this cell. Tables are never shared -- a table is where one
    guest's plate goes.
  * THE INTERLOCK IS ABSENCE: a taken or dirty chair is not in the free-chair set, so a
    guest's sensor can't see it at all.
  * A GUEST'S CHAIR IS A REMEMBERED POSITION (StorePosition when it sits), and it asks one
    question afterwards: is the block THERE still a taken chair? A distance guess once let
    a guest leave as if served.
  * GETTING UP IS ONE-WAY. An unfed guest leaves a clean chair while still standing on it;
    the next guest sat there, the first saw "my chair is taken" and sat back down in its
    lap. So getting up sets a leaving flag and never looks at the chair again, and holds
    still a beat so its signal (which finds the chair by the guest's position) lands.

Seating is a FIXTURE: chairs are placed by a layout (or the spike setup) with their tables.
"""
import blocks
import npc
import pack
import settings
import signals
import volumes as v

FIXTURE = "seating"
TABLE_AT = [("Deg0", (0, 1)), ("Deg90", (1, 0)), ("Deg180", (0, -1)), ("Deg270", (-1, 0))]
SIGNAL_TAG = SIGNAL_KEY = "seating"
SAT, FED, STOOD = "sat", "fed", "stood"

SEATED, SETTLE_TIMER, CHAIR_SLOT = "seating_seated", "seating_settle", "seating_chair"
LEAVING, RISE_TIMER = "seating_leaving", "seating_rise"
RISE = 0.6          # after signalling it is getting up, how long the guest stays put
SETTLE = 1.5        # after sitting, before "my chair isn't taken" can mean "I've gone"
REACH_CHAIR = 2.0
FACE_TIMER, FACE = "seating_face", 3.0   # how long a new sitter turns to its table (a half turn takes a while)
# THE POSE: sitting is only an animation (the Status slot); standing up clears it -- BEFORE
# anything else changes the guest, as the queue/role notes warn.
SIT = {"Type": "PlayAnimation", "Slot": "Status", "Animation": "Sit"}
STAND_UP = {"Type": "PlayAnimation", "Slot": "Status"}


def ids(model):
    prefix = model["theme"]["prefix"]
    gid = lambda local: settings.game_id(prefix, local)
    return {"chair": gid("chair"), "taken": gid("chair_taken"), "dirty": gid("chair_dirty"),
            "table": lambda rot: gid(f"table_{rot.lower()}"),
            "plate": gid("table_plate"),
            "set_free": gid("chair_free"), "set_in_use": gid("chair_in_use"),
            "set_tables": gid("chair_tables"),
            "effect": gid("seating_system")}


# ---------------------------------------------------------------- what a guest is handed

def chair_free(model):
    """A sensor: somewhere to sit exists, anywhere in the room."""
    return npc.near(ids(model)["set_free"])


def _get_up(value):
    return [signals.from_npc(SIGNAL_KEY, value, tag=SIGNAL_TAG),
            npc.set_flag(LEAVING), *npc.timer(RISE_TIMER, RISE), STAND_UP]


def left_fed():
    """Actions: get up after eating -- dirty chair, dirty plate on its own table."""
    return _get_up(FED)


def left_unfed():
    """Actions: get up without eating -- the chair is clean again."""
    return _get_up(STOOD)


def _beside(block_set, dx, dz):
    """A sensor: the block beside me (dx, dz), at seat height, is in this set -- its position
    (that point) is what a Watch then looks at."""
    return {"Type": "BlockType", "BlockSet": block_set,
            "Sensor": {"Type": "AdjustPosition", "Offset": [float(dx), -0.3, float(dz)],
                       "Sensor": {"Type": "Self", "Filters": []}}}


def guest_fragment(model, on_sat=(), while_seated=(), on_unseated=(), on_lost=(), debug=False):
    """From setting off for a chair to getting up from it.

    on_sat        actions the moment it sits (the queue's release(), in a restaurant)
    while_seated  branches while it sits on its chair: the guest's own seated behaviour,
                  which gets up by running left_fed() or left_unfed()
    on_unseated   branches once it has got up (or its chair went): leaving
    on_lost       branches if no free chair is left on the way
    """
    s = ids(model)
    seated, leaving = npc.flag(SEATED), npc.flag(LEAVING)
    after = ({"Instructions": list(on_unseated)} if on_unseated else {"BodyMotion": npc.STILL})
    mine = {"Type": "BlockType", "BlockSet": s["set_in_use"],
            "Sensor": {"Type": "ReadPosition", "Slot": CHAIR_SLOT, "Range": 8}}
    return [
        dict(npc.branch("Got up, and the signal has had time to land: leave. FIRST, so a "
                        "leaving guest never looks at its old chair again.",
                        npc.all_of(leaving, npc.stopped(RISE_TIMER))), **after),
        npc.branch("Just got up: stay on the chair until the signal has found it.",
                   leaving, npc.STILL),
        # FACING THE TABLE, for a moment after sitting -- and BEFORE the seated branches: the
        # chair turns taken almost at once, so a branch after them never ran. A chair's own
        # table is the block right BESIDE it, on its front; nothing else beside a chair is a
        # table (a neighbour's is diagonal). So: is there a table in the block beside me, this
        # way? -- one branch per side -- and face that point (MatchLook + Watch, the Feran
        # civilian's pattern). Not a distance: a Block sensor measures to a block's corner,
        # so a table on a chair's -x/-z side read 1.5 away and was never found.
        *[dict(npc.branch(f"Just sat down, my table is {side}: turn to face it.",
                          npc.all_of(_beside(s["set_tables"], dx, dz), seated,
                                     {"Type": "Timer", "Name": FACE_TIMER, "State": "Running"}),
                          {"Type": "MatchLook"}), HeadMotion={"Type": "Watch"},
               Tag=f"FACE_TABLE_{side.upper()}")
          for side, dx, dz in (("east", 1, 0), ("west", -1, 0), ("south", 0, 1), ("north", 0, -1))],
        npc.branch("Sitting, and the chair we remembered is still taken: the guest's own "
                   "seated behaviour.", npc.all_of(seated, mine),
                   instructions=list(while_seated) or None,
                   motion=None if while_seated else npc.STILL),
        dict(npc.branch("Sitting, settled, and our chair isn't taken any more: we got up, "
                        "or it went.", npc.all_of(seated, npc.stopped(SETTLE_TIMER))), **after),
        npc.branch("Just sat down; the chair hasn't turned taken yet.", seated, npc.STILL),
        npc.branch("At a free chair: sit, claim it, remember where it is. The chair sensor "
                   "comes FIRST: the teleport and StorePosition use its position.",
                   npc.all_of(npc.near(s["set_free"], REACH_CHAIR), npc.no(seated)),
                   {"Type": "Teleport", "OffsetRange": [0.0, 0.0], "MaxYOffset": 1.5,
                    "Orientation": "Unchanged"},
                   [signals.from_npc(SIGNAL_KEY, SAT, tag=SIGNAL_TAG),
                    {"Type": "StorePosition", "Slot": CHAIR_SLOT}, npc.set_flag(SEATED), SIT,
                    *npc.timer(FACE_TIMER, FACE),
                    *npc.timer(SETTLE_TIMER, SETTLE), *on_sat], "Seated", debug),
        npc.branch("Walking to the nearest free chair.", chair_free(model),
                   {"Type": "Seek", "StopDistance": 1.0, "SlowDownDistance": 3}, (),
                   "Heading to a chair", debug),
        *on_lost,
    ]


# ---------------------------------------------------------------- blocks and the volume

# THE SEAT HEIGHT. A seated guest is moved onto its chair, and the engine stands it on the
# chair's HIGHEST hitbox (translateToAccessiblePosition: "highest y value wins") -- the shipped
# Chair_Small has a backrest box up to 1.0, which stood the guest a whole block up. So the
# chair stands on a hitbox of our own: Chair_Small's SEAT alone (SEAT_HEIGHT high), and the
# guest sits at seat height. Aiming keeps the whole chair (the interaction
# hitbox), so picking it up still works on the backrest.
SEAT_HITBOX = f"{settings.NAMESPACE}_Chair_Seat"
# Higher than the seat itself (0.5): the Sit pose drops the body below the feet, so at 0.5 a
# guest sank into the chair. Tuned by eye in game.
SEAT_HEIGHT = 0.8


def _write_seat_hitbox():
    pack.write(pack.out("Item", "Block", "Hitboxes", settings.NAMESPACE, f"{SEAT_HITBOX}.json"),
               {"Boxes": [{"Min": {"X": 0.1, "Y": 0.0, "Z": 0.05},
                           "Max": {"X": 0.9, "Y": SEAT_HEIGHT, "Z": 0.9}}]})


def _chair_block(game_id, label, look, tint=None, movable=False):
    _write_seat_hitbox()
    block = {"CustomModel": look["model"],
             "CustomModelTexture": [{"Texture": look["texture"], "Weight": 1}],
             "DrawType": "Model", "Material": "Solid", "Opacity": "Transparent",
             "HitboxType": SEAT_HITBOX, "InteractionHitboxType": "Chair_Small",
             "BlockSoundSetId": look.get("sound", "Wood"),
             "PhysicalMaterialId": look.get("sound", "Wood"),
             "Support": {"Down": [{"FaceType": "Full"}]},
             # A FACING, so "in front of it" means something.
             "VariantRotation": "NESW"}
    if tint:
        block["Tint"] = [tint]
    blocks.item(game_id, label, look["icon"], block, "A chair. See build/systems/seating.py.",
                movable)


def layout(model, rotation="Deg0"):
    """A chair and its table, for a layout: [(dx, dz, block, rotation index)]."""
    s = ids(model)
    rot = dict(TABLE_AT)[rotation]
    turn = [r for r, _ in TABLE_AT].index(rotation)
    return [(0, 0, s["chair"], turn), (rot[0], rot[1], s["table"](rotation), None)]


def build(model, debug=True):
    s = ids(model)
    looks, words = model["fixtures"]["looks"], model["fixtures"]["words"]
    chair, table = looks["chair"], looks["table"]
    dirty_plate = model["items"][model["vessel"]["dirty"]["id"]]
    note = "Seating. See build/systems/seating.py."

    # Only a CLEAN chair moves; one with a guest on it or a plate to clear stays put. Its
    # table follows by itself: picking up is a break (the table goes), putting down a place.
    _chair_block(s["chair"], "Chair", chair, movable=True)
    # Taken is tinted only while debugging: whether the chair really turned taken is the
    # question a spike asks.
    _chair_block(s["taken"], "Chair (taken)", chair, "#7fb3e6" if debug else None)
    _chair_block(s["dirty"], "Chair (needs clearing)", chair, "#8a8a8a")
    tables = [s["table"](rot) for rot, _ in TABLE_AT]
    for rot, _ in TABLE_AT:
        # A plain cube: its top is flush with the cell, so a plate on it stands on it.
        blocks.station_block(s["table"](rot), "Table", table, "Table", note, use=False)
    blocks.display_block(s["plate"], f"{dirty_plate['label']} (on the table)",
                         dirty_plate["look"], words["clear_plate"], note)
    npc.block_set(s["set_free"], [s["chair"]],
                  "Chairs a guest may sit on: clean ones only. Absence is the interlock.")
    npc.block_set(s["set_in_use"], [s["taken"]],
                  "Taken chairs: how a seated guest checks its own chair is still its own.")
    npc.block_set(s["set_tables"], [s["table"](rot) for rot, _ in TABLE_AT],
                  "Every chair's table: what a guest who has just sat down turns to face.")

    rules = v.Entries()
    rep = lambda key, text, event: v.report(f"kk.seating.{key}", f"[seating] {text}", debug,
                                            event=event)
    refused = lambda value: {"Type": "TagCondition", "Event": "BLOCK_PLACED", "Source": "Self",
                             "TagKey": "refused", "Comparison": "Exactly", "TagValue": value}
    placed_chair = lambda rot: dict(v.at([s["chair"]], event="BLOCK_PLACED"), RotationY=rot)

    # 10+: REFUSE a chair whose table would land on an existing table -- before placing
    # (PlaceBlock is instant, so placing first would find its own new table), with a tag
    # the place rule checks (so a refused chair doesn't also overwrite the neighbour's).
    for i, (rot, (dx, dz)) in enumerate(TABLE_AT):
        other_table = dict(v.at(tables, event="BLOCK_PLACED"),
                           PositionOffset={"X": float(dx), "Y": 0.0, "Z": float(dz)})
        rules.add(10 + i, [placed_chair(rot), other_table, refused("0")],
                  [v.cell([s["chair"]], "Empty", event="BLOCK_PLACED"),
                   v.give(s["chair"], event="BLOCK_PLACED"),
                   {"Type": "ModifyTags", "Event": "BLOCK_PLACED", "Operation": "Set",
                    "TagKey": "refused", "TagValue": "1"},
                   v.say("kk.seating.refused", "That chair needs its own table - move it over.",
                         event="BLOCK_PLACED")])
    for i, (rot, (dx, dz)) in enumerate(TABLE_AT):
        rules.add(14 + i, [placed_chair(rot), refused("0")],
                  [{"Type": "PlaceBlock", "Event": "BLOCK_PLACED", "BlockType": s["table"](rot),
                    "Position": {"X": float(dx), "Y": 0.0, "Z": float(dz)}, "Origin": "Event",
                    "ReplaceMode": "Always"}]
                  + rep(f"placed.{rot.lower()}", f"chair placed facing {rot}", "BLOCK_PLACED"))
    rules.add(18, [v.at([s["chair"], s["taken"], s["dirty"]], event="BLOCK_PLACED")],
              [{"Type": "ModifyTags", "Event": "BLOCK_PLACED", "Operation": "Set",
                "TagKey": "refused", "TagValue": "0"}])

    # 20+: a chair came up -- take its own table (see the top of this file).
    for i, (rot, (dx, dz)) in enumerate(TABLE_AT):
        rules.add(20 + i, [v.at([s["chair"], s["taken"], s["dirty"]], event="BLOCK_BROKEN")],
                  [dict(v.cell([s["table"](rot)], "Empty", event="BLOCK_BROKEN"),
                        Offset={"X": dx - v.HALF, "Y": -v.HALF, "Z": dz - v.HALF})])

    # 40+: clear the washing up. The plate is on the table; its chair is one block down and
    # one step back along the way it faces -- checked with that chair's rotation.
    for i, (rot, (dx, dz)) in enumerate(TABLE_AT):
        back = {"X": float(-dx), "Y": -1.0, "Z": float(-dz)}
        rules.add(40 + i, [v.at([s["plate"]]),
                           dict(v.at([s["dirty"]]), PositionOffset=back, RotationY=rot)],
                  [v.give(dirty_plate["game_id"]), v.cell([s["plate"]], "Empty"),
                   dict(v.cell([s["dirty"]], s["chair"]),
                        Offset={"X": -dx - v.HALF, "Y": -1 - v.HALF, "Z": -dz - v.HALF}),
                   v.sound(0.9)] + rep("cleared", "table cleared - chair free", "BLOCK_USED"))

    def under_guest(frm, to):
        """The chair under the guest who signalled: a seated guest's feet are in the
        chair's cell or the one above it, so a two-block column reaching down."""
        return {"Type": "ReplaceBlockType", "Event": "SIGNAL_RECEIVED", "Origin": "Entity",
                "FromBlockTypes": [frm], "ToBlockType": to, "Bounds": "Aabb",
                "X": v.CELL, "Y": 2.0, "Z": v.CELL,
                "Offset": {"X": -v.HALF, "Y": -2.0, "Z": -v.HALF}}

    # 60: a guest sat down. No refusal needed: the queue only ever sends one guest at a time.
    rules.add(60, [signals.heard(SIGNAL_KEY, SAT)], [under_guest(s["chair"], s["taken"])]
              + rep("sat", "a guest sat down", "SIGNAL_RECEIVED"))
    rules.add(61, [signals.heard(SIGNAL_KEY, STOOD)], [under_guest(s["taken"], s["chair"])]
              + rep("stood", "a guest left without eating", "SIGNAL_RECEIVED"))
    # 62+: left fed: dirty chair, plate on THIS chair's table -- its facing read at the
    # guest's position, at each of the two heights a seated guest's feet can be.
    for i, (rot, (dx, dz)) in enumerate(TABLE_AT):
        for k, dy in enumerate((0.0, -1.0)):
            rules.add(62 + 2 * i + k, [
                signals.heard(SIGNAL_KEY, FED),
                {"Type": "BlockTypeCondition", "Event": "SIGNAL_RECEIVED",
                 "BlockType": [s["taken"]], "PositionSource": "Entity",
                 "PositionOffset": {"X": 0.0, "Y": dy, "Z": 0.0}, "RotationY": rot}],
                [under_guest(s["taken"], s["dirty"]),
                 {"Type": "PlaceBlock", "Event": "SIGNAL_RECEIVED", "BlockType": s["plate"],
                  "Position": {"X": float(dx), "Y": dy + 1.0, "Z": float(dz)},
                  "Origin": "Entity", "ReplaceMode": "Always"}]
                + rep("fed", "a guest left fed - plate on its table", "SIGNAL_RECEIVED"))
    # 70: reset -- guests removed wholesale; a chair still taken has nobody on it.
    rules.add(70, [signals.heard(signals.RESET, signals.RESET)],
              [{"Type": "ReplaceBlockType", "Event": "SIGNAL_RECEIVED",
                "FromBlockTypes": [s["taken"]], "ToBlockType": s["chair"]}])

    rules.write(s["effect"], "Seating: chairs, tables, plates left behind. "
                             "See build/systems/seating.py.")
    return s["effect"]


def volumes(model, box=v.WORLD_BOX):
    return [v.volume("seating", ids(model)["effect"],
                     {"seating": "system", "refused": "0", **signals.RESET_TAGS}, box=box)]
