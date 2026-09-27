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

REACH: a signal (and a tag read from another volume) reaches volumes within 64 blocks of
the sending volume's POSITION. That is a room's reach, so every system is mounted over the
room it serves with its position at the room's centre (restaurant.room_box,
volumes.volume).
"""
SHIFT_KEY, SHIFT_VALUE = "shift", "system"
LISTENER_TAGS = {SHIFT_KEY: SHIFT_VALUE}

GUEST, SERVED, ANGRY, TURNED_AWAY = "guest", "served", "angry", "turned_away"
PAID = "paid"                       # value: the menu entry it paid for
QUEUE, IMPATIENT = "queue", "impatient"

POOL_KEY, POOL_VALUE, ARRIVE = "queuepool", "1", "arrive"

RESET_KEY, RESET_VALUE, RESET = "guestreset", "1", "reset"
RESET_TAGS = {RESET_KEY: RESET_VALUE}


# THE SHIFT'S STATE, which other volumes read and pay from: the purse and the day are tags
# on the shift's volume. A pad reads them (TagCondition, Source Radius) and changes them
# (ModifyTags by tag) -- instant, so two presses in a tick can't overspend.
MONEY, DAY = "money", "day"
_SHIFT = {"MatchKey": SHIFT_KEY, "MatchValue": SHIFT_VALUE, "Radius": 64.0, "Center": "Volume"}

# THE PADS: the shift tells every pad to PLACE today's offers or CLEAR them; tells ONE pad
# (by its number) to take a DELIVERY (a crate) or show a CARD (a dish). A pad tells the
# shift a buyer was SHORT or BOUGHT something (only the shift can print the purse), and
# which card was CHOSEN.
PADS_KEY, PADS_VALUE, PAD_KEY = "offerpad", "1", "pad"
OFFERS, PLACE, CLEAR = "offers", "place", "clear"
DELIVER, CARD = "deliver", "card"
SHORT, BOUGHT, CHOSE = "short", "bought", "chose"
# A CUSTOMER card on a pad (value: its id), and the one CHOSEN (to the shift).
CUSTOMER, CHOSE_CUSTOMER = "customer", "chosecustomer"
# A booking desk asks the shift for the next guest now (booking.py).
CALL = "call"
# TIPS: the shift's tip level (extra coins per guest served) goes UP or DOWN -- a customer
# card, later; the tips spike's dial today.
TIP, UP, DOWN = "tip", "up", "down"
# HAZARDS (hazards.py): every guest says it GOT UP (a small chance of a mess round its
# chair); a messy guest asks for a MESS (always).
HAZARD_KEY, MESS, GOT_UP = "hazard", "mess", "gotup"


def shift_reads(event, key, comparison, value):
    """A condition on the shift's tag `key`, read from another volume."""
    return dict(_SHIFT, Type="TagCondition", Event=event, Source="Radius", TagKey=key,
                Comparison=comparison, TagValue=str(value))


def shift_changes(event, key, operation, value):
    """An effect changing the shift's tag `key`, from another volume. Instant."""
    return dict(_SHIFT, Type="ModifyTags", Event=event, Operation=operation, TagKey=key,
                TagValue=str(value))


def to_pads(event, value, delay=None):
    e = from_volume(event, OFFERS, value, match=(PADS_KEY, PADS_VALUE))
    return dict(e, Delay=delay) if delay else e


def to_pad(event, n, key, value, delay=None):
    e = from_volume(event, key, value, match=(PAD_KEY, str(n)))
    return dict(e, Delay=delay) if delay else e


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
