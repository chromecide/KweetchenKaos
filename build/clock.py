"""
THE CLOCK: how fast game time runs, for everything timed by the engine's own growth (a pie
ageing on a stove, a crate restocking).

Growth counts GAME seconds on the world clock, so any world with a timed station has to
run its clock. It runs a day of 12 real hours -- the sky barely moves in a session, and the
rate is steady and known:

    86,400 game seconds / 43,200 real seconds = 2 game seconds per real second

Measured in the POC (2026-09-24): an 8 second stage took about 8 seconds. The 60/40 day and
night split matches the engine's own, which keeps the rate the same by day and by night.
Growth rounds to whole game seconds, so times resolve to half a real second.

Content writes REAL seconds; this converts. Tuning a stage is changing one number that
means what it says.
"""
DAY_REAL_SECONDS = 43200
_DAYTIME = int(DAY_REAL_SECONDS * 0.6)
GAME_PER_REAL = 86400 / DAY_REAL_SECONDS

# What a world with timed stations puts in its instance config.
WORLD_TIME = {"IsGameTimePaused": False,
              "DaytimeDurationSeconds": _DAYTIME,
              "NighttimeDurationSeconds": DAY_REAL_SECONDS - _DAYTIME}


def game_seconds(real):
    return round(real * GAME_PER_REAL)


def growth(stage_blocks, durations, final_sound="SFX_Crops_Grow_Stage_Complete"):
    """A growth config that walks a block through `stage_blocks`, each lasting its REAL
    seconds (None: stays). Every stage's block carries the SAME config -- a stage swaps the
    block for the next type, and growth carries on reading the stages from whatever block
    it finds. The last stage's sound must be one-shot: a looping sound fails validation
    and takes every stage block with it."""
    stages = []
    for block, seconds in zip(stage_blocks, durations):
        s = {"Type": "BlockType", "Block": block}
        if seconds is not None:
            g = game_seconds(seconds)
            s["Duration"] = {"Min": g, "Max": g}
        stages.append(s)
    if final_sound:
        stages[-1]["SoundEventId"] = final_sound
    return {"Farming": {"Stages": {"Default": stages}, "StartingStageSet": "Default"},
            # What makes the engine track a block's growth at all.
            "BlockEntity": {"Components": {"FarmingBlock": {}}}}
