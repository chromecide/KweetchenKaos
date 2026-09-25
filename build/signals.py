"""
THE CHANNELS systems talk on. Infrastructure: names and the effect/action shapes, nothing
else. A sender and a listener share an address and the words below -- never each other.

    shift    what the run needs to hear: a guest served / angry / turned away, what it paid,
             the whole queue walking out. Whatever carries the shift tag hears it (the
             ShiftSystem later; the spike's listener now).
    pool     "arrive: <guest role>" -- the queue's pool spawns that guest. The queue says
             WHERE a guest appears; the sender says WHEN and WHO.
    reset    guests were removed wholesale (a run lost): every system holding guest state
             (taken chairs, occupied spots) frees it.

A volume sends with an EFFECT (SendSignal); an NPC with an ACTION (SignalTaggedVolumes).
Signals are QUEUED: they land a tick or so later, and are dropped if the sending NPC is gone
by then -- so an NPC that signals and then despawns must wait a beat first.
"""
SHIFT_KEY, SHIFT_VALUE = "shift", "system"
LISTENER_TAGS = {SHIFT_KEY: SHIFT_VALUE}

GUEST, SERVED, ANGRY, TURNED_AWAY = "guest", "served", "angry", "turned_away"
PAID = "paid"                       # value: the menu entry it paid for
QUEUE, IMPATIENT = "queue", "impatient"

POOL_KEY, POOL_VALUE, ARRIVE = "queuepool", "1", "arrive"

RESET_KEY, RESET_VALUE, RESET = "guestreset", "1", "reset"
RESET_TAGS = {RESET_KEY: RESET_VALUE}


def from_npc(key, value, tag=SHIFT_KEY):
    """The ACTION an NPC runs to send on a channel (by default, to the shift)."""
    return {"Type": "SignalTaggedVolumes", "MatchTag": tag, "Radius": 64.0,
            "SignalKey": key, "SignalValue": value}


def from_volume(event, key, value, match=(SHIFT_KEY, SHIFT_VALUE), radius=64.0):
    """The EFFECT a volume runs to send on a channel (by default, to the shift)."""
    return {"Type": "SendSignal", "Event": event, "MatchKey": match[0],
            "MatchValue": match[1], "Radius": radius, "Center": "Volume",
            "SignalKeys": [key], "SignalValues": [value]}


def to_pool(event, role):
    """The EFFECT that makes a guest of `role` appear at the queue's pool."""
    return from_volume(event, ARRIVE, role, match=(POOL_KEY, POOL_VALUE))


def reset_everything(event):
    return from_volume(event, RESET, RESET, match=(RESET_KEY, RESET_VALUE), radius=128.0)


def heard(key, value):
    """The CONDITION a volume's rule uses to answer a signal."""
    return {"Type": "TagCondition", "Event": "SIGNAL_RECEIVED", "Source": "Event",
            "TagKey": key, "TagValue": value}
