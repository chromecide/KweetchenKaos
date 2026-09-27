"""
THE QUEUE SYSTEM: spots guests line up on, the pool they arrive in, and the rules they follow.

    a guest arrives           ->  at the POOL (the pool's volume spawns it when told "arrive")
    the back spot is free     ->  after a short random pause, it walks onto it
    the spot in front is free ->  it moves up ONE spot; nobody ever skips ahead
    at the front, somewhere
    to go (a free chair)      ->  the front is HELD for it and it sets off; the held front
                                  frees once it has sat down
    the queue's patience runs
    out                       ->  "the queue gave up" goes to the shift

Ported from the Kitchen POC, where it took the most iterations of anything; every rule here
is an answer to a bug that was seen (kitchen-poc/docs/systems.md, QueueSystem):

  * OCCUPANCY IS THE SPOT'S JOB. Each spot has its own one-cell volume: the first guest to
    ENTER claims it (an `occ` tag, written instantly), and anyone arriving after -- even in
    the same tick -- is BUMPED (an entity effect it senses on itself: back to the pool). It
    frees when an EXIT finds nobody left. Block reservations were the source of every
    earlier queue bug.
  * GUESTS READ THE BLOCK UNDER THEIR FEET, never a distance.
  * ONE SPOT FORWARD AT A TIME: pool -> 4 -> 3 -> 2 -> 1. With one guest per spot exactly
    one guest is ever heading for any spot, so guests in line never race.
  * THE FRONT IS HELD while its guest walks to a seat -- otherwise the next guest moves up,
    sees the same still-free chair and walks to it too. Only the holder ever sees a held
    spot, and only the holder releases it.
  * ONE PATIENCE CLOCK for the whole queue, on an area volume that covers only where guests
    wait. TICK fires once per guest inside, so it drains faster the longer the line -- free.
    It SHOWS the way a seated guest's patience does: below half, every queued guest pulses
    amber; below a quarter, red -- the whole line together, as it would walk out together.

A queue is a FIXTURE, not a station: its spots and pool are placed by a layout (or the spike
setup), each carrying its own volume. A spot placed by hand gets its volume pasted on by the
queue's world volume.
"""
import blocks
import npc
import pack
import settings
import signals
import volumes as v

FIXTURE = "queue"
LENGTH = 4
POOL_LOITER = 3.0                     # how close to the pool marker counts as "in the pool"
JOIN_PAUSE = (0.05, 1.5)              # the random pause before a pool guest joins
BUMP_SECONDS = 2.0
LEAVE_BEAT = 0.6                      # between asking for the front to be held and stepping off
TICK_SECONDS = 1.0                    # the patience drain: once a second per queued guest
# colour: (bottom tint, top tint, seconds on, every) -- the seated guest's pulses, so a
# worried guest looks the same in the line and at a table.
PULSES = {"amber": ("#d08a20", "#f0b040", 1.5, 3.0), "red": ("#d01810", "#f03020", 0.75, 1.5)}
SPOT_TAG, SIGNAL_KEY, LEAVING, RELEASE = "queuespot", "queue", "leaving", "release"

# Flags and timers a guest carries while it is the queue's -- all prefixed "queue_".
GOING = "queue_going_{}"
PAUSING, PAUSE = "queue_pausing", "queue_pause"
LEAVING_FLAG, BEAT = "queue_leaving", "queue_beat"


def ids(model):
    prefix = model["theme"]["prefix"]
    gid = lambda local: settings.game_id(prefix, local)
    return {"free": lambda i: gid(f"queue_spot_{i}"),
            "taken": lambda i: gid(f"queue_spot_{i}_taken"),
            "held": gid("queue_spot_1_held"),
            "pool": gid("queue_pool"),
            "set_free": lambda i: gid(f"queue_free_{i}"),
            "set_taken": lambda i: gid(f"queue_taken_{i}"),
            "set_taken_any": gid("queue_taken_any"),
            "set_held": gid("queue_held"),
            "set_spot_any": gid("queue_spot_any"),
            "set_pool": gid("queue_pool_marker"),
            "bumped": gid("queue_bumped"),
            "pulse": lambda colour: gid(f"queue_pulse_{colour}"),
            "world_effect": gid("queue_system"),
            "area_effect": gid("queue_area")}


# ---------------------------------------------------------------- what a guest is handed

def release():
    """The ACTION a guest runs once it has arrived where the front sent it (sat down)."""
    return signals.from_npc(SIGNAL_KEY, RELEASE, tag=SPOT_TAG)


def off_the_line(model):
    """A sensor: I'm not standing on any queue spot -- where a guest may despawn. A guest that
    vanishes ON a spot leaves it taken for ever: the engine fires the spot's EXIT while the
    vanishing guest still counts as inside, so "nobody left" never holds, and the whole line
    stalls behind it (seen: a guest walking out despawned on spot 1)."""
    return npc.no(npc.on_block(ids(model)["set_spot_any"]))


def _drop_claims():
    return [npc.set_flag(GOING.format(j), False) for j in range(1, LENGTH + 1)] + \
           [npc.set_flag(PAUSING, False)]


def guest_fragment(model, ready=None, next_state=None, debug=False):
    """Everything a guest does while it belongs to the queue, in priority order. `ready` is
    the guest's sensor for "somewhere to go now" (a free chair); at the front, seeing it
    holds the front, waits a beat, and switches the role to `next_state`."""
    q = ids(model)
    b = lambda *a, **k: npc.branch(*a, debug=debug, **k)
    held = npc.on_block(q["set_held"])
    taken_any = npc.on_block(q["set_taken_any"])
    not_in_line = npc.no(taken_any)
    back = q["set_free"](LENGTH)
    loiter = {"Type": "Seek", "StopDistance": POOL_LOITER, "SlowDownDistance": POOL_LOITER + 1}
    out = [b("Bumped off a spot by the spot itself: someone got there first. FIRST, or a "
             "guest bumped off spot 1 would act as the front.",
             npc.all_of(npc.near(q["set_pool"]), npc.has_effect(q["bumped"])),
             loiter, _drop_claims(), "Bumped - back to the pool")]

    if ready is not None:
        signal_leaving = signals.from_npc(SIGNAL_KEY, LEAVING, tag=SPOT_TAG)
        out += [
            b("The beat is over and the front is held for us: go.",
              npc.all_of(npc.flag(LEAVING_FLAG), npc.stopped(BEAT)), None,
              [npc.set_flag(LEAVING_FLAG, False), {"Type": "State", "State": next_state}],
              "Leaving the queue"),
            b("Waiting out the beat, standing still (once the front turns held we stand on "
              "a spot that isn't 'taken', and the join rule would send us to the back).",
              npc.flag(LEAVING_FLAG), npc.STILL),
            b("Back on the front we hold, and somewhere to go has come up: go again. No "
              "signal: it is already held, for us.",
              npc.all_of(held, ready), npc.STILL,
              [npc.set_flag(LEAVING_FLAG), *npc.timer(BEAT, LEAVE_BEAT)]),
            b("On the front we hold, nowhere to go yet: wait. Only the holder sees it.",
              held, npc.STILL, (), "Holding the front"),
            b("At the front and somewhere to go: ask for the front to be held, then wait a "
              "beat before stepping off (the signal and the block swap land later).",
              npc.all_of(npc.on_block(q["set_taken"](1)), ready), npc.STILL,
              [signal_leaving, *_drop_claims(), npc.set_flag(LEAVING_FLAG),
               *npc.timer(BEAT, LEAVE_BEAT)]),
        ]

    for j in range(1, LENGTH + 1):
        out.append(b(f"Heading for spot {j}, and on it now: in line. First among the move "
                     f"rules, so a race is settled before anything asks if the spot is free.",
                     npc.all_of(npc.flag(GOING.format(j)), npc.on_block(q["set_taken"](j))),
                     npc.STILL, [npc.set_flag(GOING.format(j), False)], f"In line - spot {j}"))
    for j in range(1, LENGTH + 1):
        out.append(b(f"Heading for spot {j}, still free: keep going. The free spot is the "
                     f"FIRST sensor -- And takes its position from it, and Seek goes there.",
                     npc.all_of(npc.near(q["set_free"](j)), npc.flag(GOING.format(j))),
                     dict(npc.WALK), (), f"Heading for spot {j}"))
    for j in range(1, LENGTH + 1):
        out.append(b(f"Was heading for spot {j}, it's taken and we're not on it: somebody "
                     f"got there first. Drop the claim; the pool rule takes us back.",
                     npc.flag(GOING.format(j)), npc.STILL,
                     [npc.set_flag(GOING.format(j), False)], f"Lost spot {j} - back to the pool"))
    for i in range(2, LENGTH + 1):
        out.append(b(f"On spot {i}, and spot {i - 1} in front is free: claim it.",
                     npc.all_of(npc.near(q["set_free"](i - 1)), npc.on_block(q["set_taken"](i))),
                     dict(npc.WALK), [npc.set_flag(GOING.format(i - 1))],
                     f"Moving up to spot {i - 1}"))
    out += [
        b(f"In the pool, pause over, spot {LENGTH} still free: claim it.",
          npc.all_of(npc.near(back), not_in_line, npc.flag(PAUSING), npc.stopped(PAUSE)),
          dict(npc.WALK), [npc.set_flag(GOING.format(LENGTH)), npc.set_flag(PAUSING, False)],
          f"Joining at spot {LENGTH}"),
        b("In the pool, pausing before going for the back of the line.",
          npc.all_of(npc.near(back), not_in_line, npc.flag(PAUSING)), npc.STILL, (),
          "In the pool - about to join"),
        b(f"In the pool and spot {LENGTH} just came free: start a random pause (so pool "
          f"guests don't set off in step). The flag proves the timer was started.",
          npc.all_of(npc.near(back), not_in_line), npc.STILL,
          [npc.set_flag(PAUSING), *npc.timer(PAUSE, *JOIN_PAUSE)], "In the pool - about to join"),
        b("In the pool, the back of the line is taken: loiter round the marker, and forget "
          "any pause, or we'd rush the next opening in step with the others.",
          npc.all_of(npc.near(q["set_pool"]), not_in_line), loiter,
          [npc.set_flag(PAUSING, False)], "In the pool"),
        b("In line with nowhere to move up to.", taken_any, npc.STILL, (), "In line, waiting"),
        b("Nothing applies (no pool in range, most likely) -- say so rather than stand "
          "silently.", {"Type": "Any"}, npc.STILL, (), "Waiting - no queue rule"),
    ]
    return out


def return_fragment(model, queue_state, debug=False):
    """For a guest that left the front and lost where it was going: walk back to the front
    it still holds and be the queue's again. It NEVER releases the front -- a guest wrongly
    here once un-held it mid-walk and the whole line emptied into the room. Ends with no
    catch-all: the composing guest decides what happens if there is no held front."""
    q = ids(model)
    return [npc.branch("Back on the front we hold: the queue's again.",
                       npc.on_block(q["set_held"]), None,
                       [{"Type": "State", "State": queue_state}], "Holding the front", debug),
            npc.branch("Walking back to the front we hold.", npc.near(q["set_held"]),
                       dict(npc.WALK), (), "Going back to my place", debug)]


# ---------------------------------------------------------------- the volumes a spot carries

def _spot_rules(q, boost_by, debug, moods=()):
    """The one-cell volume on every spot, INLINE: a pasted volume keeps an EMPTY effect
    list if it names an effect asset (resolved once, at world start, over volumes that
    already exist), so its rules have to travel with it."""
    rules = v.Entries()
    rep = lambda key, text, event: v.report(f"kk.queue.{key}", f"[queue] {text}", debug,
                                            event=event, to_log=False)
    occ = lambda event, value: {"Type": "TagCondition", "Event": event, "Source": "Self",
                                "TagKey": "occ", "Comparison": "Exactly", "TagValue": value}
    here = lambda event, blocks_: {"Type": "BlockTypeCondition", "Event": event,
                                   "BlockType": list(blocks_), "PositionSource": "VolumeOrigin"}
    swap = lambda event, frm, to: {"Type": "ReplaceBlockType", "Event": event,
                                   "FromBlockTypes": list(frm), "ToBlockType": to}
    empty = {"Type": "EntityCountCondition", "Event": "EXIT", "Comparison": "AtMost", "Count": 0}
    for i in range(1, LENGTH + 1):
        rules.add(i, [here("ENTER", [q["free"](i)]), occ("ENTER", "0")],
                  [swap("ENTER", [q["free"](i)], q["taken"](i))]
                  + rep(f"enter.{i}", f"spot {i}: someone arrived", "ENTER"))
        rules.add(50 + i, [here("EXIT", [q["taken"](i)]), empty],
                  [swap("EXIT", [q["taken"](i)], q["free"](i))]
                  + rep(f"exit.{i}", f"spot {i}: free again", "EXIT"))
    # 5 BEFORE 6: someone already here -> bump; the first arrival claims (tags are instant).
    rules.add(5, [{"Type": "TagCondition", "Event": "ENTER", "Source": "Self", "TagKey": "occ",
                   "Comparison": "AtLeast", "TagValue": "1"}],
              [{"Type": "EntityEffect", "Event": "ENTER", "Effect": q["bumped"],
                "Mode": "Apply", "Duration": BUMP_SECONDS}]
              + rep("bumped", "a second guest arrived - bumped back", "ENTER"))
    rules.add(6, [occ("ENTER", "0")],
              [{"Type": "ModifyTags", "Event": "ENTER", "Operation": "Set", "TagKey": "occ",
                "TagValue": "1"}])
    rules.add(55, [empty], [{"Type": "ModifyTags", "Event": "EXIT", "Operation": "Set",
                             "TagKey": "occ", "TagValue": "0"}])
    # THE HANDOFF: the front guest asks for the front to be held, and releases it on sitting.
    boost = {"Type": "ModifyTags", "Event": "SIGNAL_RECEIVED", "MatchKey": "queuearea",
             "MatchValue": "1", "Radius": 64.0, "Center": "Volume", "Operation": "Increment",
             "TagKey": "qpatience", "TagValue": str(boost_by)}
    rules.add(60, [signals.heard(SIGNAL_KEY, LEAVING), here("SIGNAL_RECEIVED", [q["taken"](1)])],
              [swap("SIGNAL_RECEIVED", [q["taken"](1)], q["held"]), boost]
              + rep("held", "front held - someone is walking to a seat", "SIGNAL_RECEIVED"))
    rules.add(61, [signals.heard(SIGNAL_KEY, RELEASE), here("SIGNAL_RECEIVED", [q["held"]])],
              [swap("SIGNAL_RECEIVED", [q["held"]], q["free"](1))]
              + rep("released", "front released - next in line moves up", "SIGNAL_RECEIVED"))
    # MOODS (model["moods"]["arrival"], from systems/moods.py): [(mark, chance, [marks it
    # takes off])] -- a guest stepping onto a spot is marked at that chance. Only its FIRST
    # spot counts: the guest reads its marks once, the first time it stands in line. The
    # queue only marks; what a mood is, and means, is the mood system's business. A roll
    # that lands takes off the other moods on its track: last roll wins, within a track.
    # A card's roll only once the card is chosen: its tag on the shift (read from here, as
    # the pads read the purse). Numbered 200+: clear of the spot's own rules.
    for k, (effect, chance, others, gate) in enumerate(moods):
        rules.add(200 + k, ([signals.shift_reads("ENTER", gate, "AtLeast", 1)] if gate else [])
                  + [{"Type": "RandomChanceCondition", "Event": "ENTER",
                      "Chance": float(chance)}],
                  [{"Type": "EntityEffect", "Event": "ENTER", "Effect": other,
                    "Mode": "Remove"} for other in others]
                  + [{"Type": "EntityEffect", "Event": "ENTER", "Effect": effect,
                      "Mode": "Apply"}]
                  + rep(f"mood.{k}", f"a guest stepped on, marked {effect}", "ENTER"))
    # RESET: guests were removed wholesale; free every spot and its claim.
    rules.add(65, [signals.heard(signals.RESET, signals.RESET)],
              [swap("SIGNAL_RECEIVED", [q["taken"](i)], q["free"](i)) for i in range(1, LENGTH + 1)]
              + [swap("SIGNAL_RECEIVED", [q["held"]], q["free"](1)),
                 {"Type": "ModifyTags", "Event": "SIGNAL_RECEIVED", "Operation": "Set",
                  "TagKey": "occ", "TagValue": "0"}])
    # The spot's volume goes when its block does (DeleteVolume with no tag: this volume).
    rules.add(99, [{"Type": "BlockTypeCondition", "Event": "BLOCK_BROKEN",
                    "BlockType": [q["free"](i) for i in range(1, LENGTH + 1)]
                    + [q["taken"](i) for i in range(1, LENGTH + 1)] + [q["held"]],
                    "PositionSource": "Event"}],
              [{"Type": "DeleteVolume", "Event": "BLOCK_BROKEN"}])
    return rules


def _pool_rules(q, guests, debug):
    rules = v.Entries()
    for n, role in enumerate(guests):
        rules.add(10 + n, [signals.heard(signals.ARRIVE, role)],
                  # The volume sits on the block's CORNER: the top middle is (0.5, 1, 0.5).
                  [{"Type": "SpawnNpc", "Event": "SIGNAL_RECEIVED", "NpcType": role,
                    "Origin": "VolumeOrigin", "Count": 1,
                    "Offset": {"X": 0.5, "Y": 1.0, "Z": 0.5}, "Yaw": 0.0}]
                  + v.report("kk.queue.arrived", "[queue] a guest arrived", debug,
                             event="SIGNAL_RECEIVED", to_log=False))
    rules.add(99, [{"Type": "BlockTypeCondition", "Event": "BLOCK_BROKEN",
                    "BlockType": [q["pool"]], "PositionSource": "Event"}],
              [{"Type": "DeleteVolume", "Event": "BLOCK_BROKEN"}])
    return rules


def _entity(name, rules, box_height, tags, targets):
    """A volume as a prefab entity: pasted with its block, landing on the block's corner."""
    return {"Components": {
        "TriggerVolume": {"Shape": {"Type": "Box", "Min": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                                    "Max": {"X": 1.0, "Y": box_height, "Z": 1.0}},
                          "Conditions": rules.conditions, "Effects": rules.effects,
                          "Enabled": True, "TargetTypes": targets, "Tags": tags,
                          "Name": name, "PrefabIndex": 0},
        "Transform": {"Position": {"X": 0.0, "Y": 0.0, "Z": 0.0},
                      "Rotation": {"Pitch": 0.0, "Yaw": 0.0, "Roll": 0.0}}}}


_built = {}


def build(model, guests, debug=True, patience=None):
    """Write the queue's blocks, sets, effects and the volumes its spots and pool carry.
    `guests`: every role that counts as a customer (spawned at the pool, counted by the
    patience clock). `patience`: the queue's patience in seconds (the spike sets it long)."""
    q = ids(model)
    fx_ = model["fixtures"]
    looks, words = fx_["looks"], fx_["words"]
    spot, pool = looks["queue_spot"], looks["pool"]
    rules = model["rules"]
    patience = patience or rules["queue_patience"]
    boost_by = rules["queue_patience_boost"]
    note = "Queue. See build/systems/queue.py."

    def spot_block(key, label, tint, hint_text):
        blocks.station_block(key, label, spot, hint_text, note, tint=tint, use=False)

    for i in range(1, LENGTH + 1):
        where = "front of the line" if i == 1 else f"position {i}"
        spot_block(q["free"](i), f"Queue spot {i}", spot["shades"][i - 1],
                   words["queue_spot"].format(where=where))
        spot_block(q["taken"](i), f"Queue spot {i} (occupied)", spot["taken_tint"],
                   words["queue_spot"].format(where=f"{where} (occupied)"))
        npc.block_set(q["set_free"](i), [q["free"](i)],
                      f"Queue spot {i} while FREE: what a guest walks to.")
        npc.block_set(q["set_taken"](i), [q["taken"](i)],
                      f"Queue spot {i} while taken: which spot a guest is standing on.")
    spot_block(q["held"], "Queue spot 1 (held)", spot["held_tint"],
               words["queue_spot"].format(where="front of the line (someone is on the way "
                                                "to a seat)"))
    npc.block_set(q["set_held"], [q["held"]], "The held front: ONLY its holder looks for it.")
    npc.block_set(q["set_taken_any"], [q["taken"](i) for i in range(1, LENGTH + 1)],
                  "Any occupied spot: negated, it means 'not in the queue yet'.")
    blocks.station_block(q["pool"], "Queue pool", pool, words["pool"], note,
                         tint=pool.get("tint"), use=False)
    npc.block_set(q["set_spot_any"], [q["free"](i) for i in range(1, LENGTH + 1)]
                  + [q["taken"](i) for i in range(1, LENGTH + 1)] + [q["held"]],
                  "Any queue spot, whatever its state: where a guest must never vanish.")
    npc.block_set(q["set_pool"], [q["pool"]], "Where guests arrive and wait.")
    npc.entity_effect(q["bumped"], BUMP_SECONDS, "#d03020", "#f07050",
                      "Put on a guest by a spot that already had someone: back to the pool.")
    for colour, (bottom, top, on, _) in PULSES.items():
        npc.entity_effect(q["pulse"](colour), on, bottom, top,
                          "The queue's impatience, on every queued guest. See build/systems/queue.py.")

    moods = model["moods"]["arrival"]
    spot_rules = _spot_rules(q, boost_by, debug, moods)
    pool_rules = _pool_rules(q, guests, debug)
    _built["spot"] = _entity("queue_spot", spot_rules, 3.0,
                             {SPOT_TAG: "1", "occ": "0", **signals.RESET_TAGS}, ["Player", "Npc"])
    _built["pool"] = _entity("queue_pool", pool_rules, 2.0,
                             {signals.POOL_KEY: signals.POOL_VALUE}, ["Player"])
    for key in ("spot", "pool"):
        pack.write(pack.out("Prefabs", f"{q['world_effect']}_{key.capitalize()}.prefab.json"), {
            "$Comment": f"A queue {key}'s own volume. See build/systems/queue.py.",
            "version": 8, "blockIdVersion": 11, "anchorX": 0, "anchorY": 0, "anchorZ": 0,
            "blocks": [], "entities": [_built[key]]})

    # THE WORLD VOLUME: a spot or pool placed by hand gets its volume pasted on.
    world = v.Entries()
    for i in range(1, LENGTH + 1):
        world.add(10 + i, [v.at([q["free"](i)], event="BLOCK_PLACED")],
                  [{"Type": "PastePrefab", "Event": "BLOCK_PLACED",
                    "Prefab": f"{q['world_effect']}_Spot", "Origin": "Event",
                    "ShowParticles": False}])
    world.add(20, [v.at([q["pool"]], event="BLOCK_PLACED")],
              [{"Type": "PastePrefab", "Event": "BLOCK_PLACED",
                "Prefab": f"{q['world_effect']}_Pool", "Origin": "Event", "ShowParticles": False}])
    world.write(q["world_effect"], "The queue: gives spots and pools placed by hand their "
                                   "volumes. See build/systems/queue.py.")

    # THE AREA VOLUME: the queue's one patience clock (NPCs only).
    area = v.Entries()
    # Drain: no condition -- TICK fires once per guest inside, which IS the scaling. The
    # EFFECT's Interval is the throttle (kept per entity); a volume Cooldown only gates
    # entering, and once inside it drained every server tick.
    area.add(10, [], [{"Type": "ModifyTags", "Event": "TICK", "Interval": TICK_SECONDS,
                       "Operation": "Increment", "TagKey": "qpatience", "TagValue": "-1"}])
    # Out of patience: tell the shift, reset in the same rule so it fires once. The ENTER
    # effect stops an all-TICK rule being a "gate" that skips its first tick.
    area.add(20, [{"Type": "TagCondition", "Event": "TICK", "Source": "Self",
                   "TagKey": "qpatience", "Comparison": "AtMost", "TagValue": "0"}],
             [signals.from_volume("TICK", signals.QUEUE, signals.IMPATIENT),
              {"Type": "ModifyTags", "Event": "ENTER", "Operation": "Set",
               "TagKey": "entered", "TagValue": "1"},
              {"Type": "ModifyTags", "Event": "TICK", "Operation": "Set",
               "TagKey": "qpatience", "TagValue": str(patience)}]
             + v.report("kk.queue.impatient", "[queue] out of patience - the queue gave up",
                        debug, event="TICK"))
    # 40, 41: IT SHOWS. Below half, amber on every queued guest; below a quarter, red. TICK
    # runs per guest and the effect's Interval is per guest, so each pulses on its own beat.
    # The ENTER effect keeps an all-TICK rule from skipping its first tick.
    tag = lambda cmp, value: {"Type": "TagCondition", "Event": "TICK", "Source": "Self",
                              "TagKey": "qpatience", "Comparison": cmp, "TagValue": str(value)}
    half, quarter = patience // 2, patience // 4
    for n, (colour, lo, hi) in enumerate((("amber", quarter + 1, half), ("red", 1, quarter))):
        bottom, top, on, every = PULSES[colour]
        area.add(40 + n, [tag("AtMost", hi), tag("AtLeast", lo)],
                 [{"Type": "EntityEffect", "Event": "TICK", "Effect": q["pulse"](colour),
                   "Mode": "Apply", "Duration": on, "Interval": every},
                  {"Type": "ModifyTags", "Event": "ENTER", "Operation": "Set",
                   "TagKey": "entered", "TagValue": "1"}])
    # The last guest left: patience back to full (on EXIT -- TICK can't fire when empty).
    area.add(30, [{"Type": "EntityCountCondition", "Event": "EXIT", "EntityType": list(guests),
                   "Comparison": "AtMost", "Count": 1}],
             [{"Type": "ModifyTags", "Event": "EXIT", "Operation": "Set",
               "TagKey": "qpatience", "TagValue": str(patience)}])
    area.write(q["area_effect"], "The queue's patience: one clock for the whole line. "
                                 "See build/systems/queue.py.")
    return {"patience": patience}


def spot_entity(x, y, z):
    """A spot's volume, for a layout to paste with the spot at (x, y, z)."""
    return _placed(_built["spot"], x, y, z)


def pool_entity(x, y, z):
    return _placed(_built["pool"], x, y, z)


def _placed(entity, x, y, z):
    import copy
    e = copy.deepcopy(entity)
    e["Components"]["Transform"]["Position"] = {"X": float(x), "Y": float(y), "Z": float(z)}
    return e


def volumes(model, area_box, patience, box=v.WORLD_BOX):
    """The queue mounted: the world volume (hand-placed spots get their volumes) over
    everything, and the patience area over `area_box` ((min xyz, max xyz): only where
    guests wait -- a seated guest inside it would drain the line's patience)."""
    q = ids(model)
    (x0, y0, z0), (x1, y1, z1) = area_box
    return [v.volume("queue", q["world_effect"], {"queue": "system"}, box=box),
            v.volume("queue_area", q["area_effect"],
                     {"queuearea": "1", "qpatience": str(patience)}, targets=["Npc"],
                     box=((x0, y0, z0), (x1, y1, z1)))]
