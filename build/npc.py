"""
NPC BEHAVIOUR: the pieces guest behaviour is written from, spelled right once.
Infrastructure only -- no content. What was learned the hard way (kitchen-poc/docs):

  * A ROLE IS A LIST OF BRANCHES tried in order; the first whose sensor passes runs. Order
    is priority, so the rule that must win goes first.
  * And TAKES ITS POSITION FROM ITS FIRST SENSOR, and a Seek or Teleport goes there. Put
    the thing to walk to first.
  * TIMERS: TimerStart only ever starts a timer ONCE per NPC; TimerRestart does nothing
    until one was started. timer() does both, so a timer works the second time too. A
    timer keeps the durations it was FIRST started with, so a clock with a different length
    needs its own name. An unstarted timer also reads Stopped -- pair a timer with a flag
    that proves it was started.
  * STANDING ON A BLOCK is read under the feet (on_block), never by distance: every
    distance guess was wrong somewhere.
  * A role whose StartState is never sensed is rejected outright.
"""
import pack
import settings


def flag(name, on=True):
    return {"Type": "Flag", "Name": name, "Set": on}


def set_flag(name, on=True):
    return {"Type": "SetFlag", "Name": name, "SetTo": on}


def stopped(timer_name):
    return {"Type": "Timer", "Name": timer_name, "State": "Stopped"}


def timer(name, lo, hi=None):
    """Start -- or restart -- a timer (see the top of this file)."""
    hi = lo if hi is None else hi
    return [{"Type": "TimerStart", "Name": name, "StartValueRange": [lo, hi],
             "RestartValueRange": [lo, hi], "Repeating": False},
            {"Type": "TimerRestart", "Name": name}]


def once(name, seconds):
    """A timer started exactly once in the NPC's life."""
    return {"Type": "TimerStart", "Name": name, "StartValueRange": [seconds, seconds],
            "RestartValueRange": [seconds, seconds], "Repeating": False}


def all_of(*sensors):
    return {"Type": "And", "Sensors": list(sensors)}


def any_of(*sensors):
    return {"Type": "Or", "Sensors": list(sensors)}


def no(sensor):
    return {"Type": "Not", "Sensor": sensor}


def near(block_set, rng=60):
    """A block of this set within range -- also where a Seek will walk."""
    return {"Type": "Block", "Range": rng, "Blocks": block_set}


def on_block(block_set):
    """THE BLOCK UNDER MY FEET is in this set. Half a block below the feet is inside the
    block stood on, whatever fraction the feet are at."""
    return {"Type": "BlockType", "BlockSet": block_set,
            "Sensor": {"Type": "AdjustPosition", "Offset": [0.0, -0.5, 0.0],
                       "Sensor": {"Type": "Self", "Filters": []}}}


def has_effect(effect_id):
    """An entity effect is on me (a volume can put one on an NPC to tell it something)."""
    return {"Type": "Self", "Filters": [{"Type": "EntityEffect", "EffectId": effect_id}]}


def name_tag(text):
    return {"Type": "DisplayName", "DisplayName": text}


WALK = {"Type": "Seek", "StopDistance": 0.4, "SlowDownDistance": 2}
STILL = {"Type": "Nothing"}


# STEP TAGS: a branch's `tag` shown as the NPC's name while it runs -- "Heading to a chair",
# "Spot 3" -- for chasing a behaviour bug. Off: players see only what a guest says on
# purpose (Waiting, Ready to order, the dish, Eating, Leaving).
SHOW_STEPS = False


def branch(note, sensor, motion=None, actions=(), tag=None, debug=False, instructions=None,
           cont=False):
    """One rule. `tag` is a name-tag line shown while it runs (with debug and SHOW_STEPS)."""
    b = {"$Comment": note, "Sensor": sensor}
    if cont:
        b["Continue"] = True
    if instructions is not None:
        b["Instructions"] = list(instructions)
    elif motion:
        b["BodyMotion"] = motion
    acts = list(actions) + ([name_tag(tag)] if tag and debug and SHOW_STEPS else [])
    if acts:
        b["Actions"] = acts
    return b


def role(game_id, label, start_state, states, interactions=None, appearance="Klops",
         display=None, comment="", trace=False):
    """Write an NPC role: `states` is {state: [branches]}. The standard kitchen body:
    unkillable, unshovable, walking at guest pace, ignoring other NPCs."""
    pack.say(f"npcRoles.{game_id}.name", label)
    r = {"$Comment": comment,
         "Type": "Generic", "StartState": start_state,
         "NameTranslationKey": f"server.npcRoles.{game_id}.name",
         "DefaultNPCAttitude": "Ignore", "DefaultPlayerAttitude": "Neutral",
         "Appearance": appearance, "MaxHealth": 20, "Invulnerable": True,
         "DisableDamageGroups": ["Self"], "KnockbackScale": 0.0,
         "MotionControllerList": [{"Type": "Walk", "MaxWalkSpeed": 4, "Gravity": 10,
                                   "RunThreshold": 0.3, "MaxFallSpeed": 15,
                                   "MaxRotationSpeed": 360, "Acceleration": 10}],
         "Instructions": [{"Instructions": [
             {"Sensor": {"Type": "State", "State": s}, "Instructions": b}
             for s, b in states.items()]}]}
    if display:
        r["DisplayNames"] = [display]
    if trace:
        # The engine's own decision log: every instruction matched or failed, by its Tag.
        r["Debug"] = "TraceSuccess,TraceFail"
    if interactions is not None:
        r["InteractionInstruction"] = {"Instructions": list(interactions)}
    pack.write(pack.out("NPC", "Roles", settings.NAMESPACE, f"{game_id}.json"), r)


def block_set(name, blocks, comment):
    pack.write(pack.out("Item", "Block", "Sets", f"{name}.json"),
               {"$Comment": comment, "IncludeBlockTypes": list(blocks)})
    return name


def entity_effect(name, seconds, bottom, top, comment):
    """A short tint an NPC wears -- how a volume tells an NPC something, or how a guest
    shows impatience."""
    pack.write(pack.out("Entity", "Effects", settings.NAMESPACE, f"{name}.json"), {
        "$Comment": comment, "Duration": seconds, "OverlapBehavior": "Overwrite",
        "ApplicationEffects": {"EntityBottomTint": bottom, "EntityTopTint": top}})
    return name
