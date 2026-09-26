"""
THE BOOKING SYSTEM: the desk every restaurant has, with a book on it -- call the next guest in
now (PlateUp's booking desk).

    press the desk (or the book), during
    service, with guests still to come     ->  the next guest arrives now instead of at the
                                               day's pace, and the call PAYS a few coins
                                               (the station's "pay": 3 on day 1, 4 on day 2,
                                               then one more every two days)
    press it with nobody left to come      ->  closing time now: the day ends once the last
                                               guests leave
    press it outside service               ->  it says so

It doesn't add guests: it brings the day's expected ones in sooner -- more pressure, for
money. The shift does the calling and the paying (it holds the day's count and the purse):
the desk only asks, on the shift channel (signals.CALL). No cooldown: each call uses up one of
the day's expected guests, so the day itself is the limit.

Every layout has a booking desk slot. The book on top is a picture: it goes with the desk when
it's carried.
"""
import blocks
import settings
import signals
import volumes as v

ROLES = ("call",)


def ids(model, station_id):
    prefix = model["theme"]["prefix"]
    gid = lambda local: settings.game_id(prefix, local)
    return {"free": gid(station_id), "top": gid(f"{station_id}_top"),
            "effect": gid(f"{station_id}_system")}


def free_block(model, station_id):
    return ids(model, station_id)["free"]


def layout(model, station_id):
    return [(0, ids(model, station_id)["free"]), (1, ids(model, station_id)["top"])]


def build(model, station_id, debug=True):
    st = model["stations"][station_id]
    b = ids(model, station_id)
    label, look, words = st["label"], st["look"], st["words"]
    note = f"{label}. See build/systems/booking.py."
    blocks.station_block(b["free"], label, look, words["free"], note, movable=True)
    blocks.display_block(b["top"], f"{st['on_top'].get('label', 'Book')} (on the {label.lower()})",
                         st["on_top"], words["free"], note)

    rules = v.Entries()
    rep = lambda key, text: v.report(f"kk.{station_id}.{key}", f"[{station_id}] {text}", debug)
    open_now = signals.shift_reads("BLOCK_USED", "open", "Exactly", 1)
    closed = signals.shift_reads("BLOCK_USED", "open", "Exactly", 0)
    for dy, where in ((0.0, [v.at([b["free"]])]), (-1.0, [v.at([b["top"]]), v.at([b["free"]], dy=-1)])):
        # CALL: ask the shift for the next guest (it pays, or calls closing time).
        rules.add(100 + int(-dy), where + [open_now],
                  [signals.from_volume("BLOCK_USED", signals.CALL, "next"),
                   v.sound(1.3)] + rep("call", "called the next guest"))
        rules.add(110 + int(-dy), where + [closed],
                  [v.say(f"kk.{station_id}.closed", words["closed"])])
    # CARRIED: put down, the book goes back on top; picked up, it goes with it.
    rules.add(200, [v.at([b["free"]], event="BLOCK_PLACED")],
              [v.place(b["top"], event="BLOCK_PLACED")])
    rules.add(201, [v.at([b["free"]], event="BLOCK_BROKEN")],
              [v.cell([b["top"]], "Empty", dy=1, event="BLOCK_BROKEN")])
    rules.write(b["effect"], f"The {label.lower()}: call the next guest now. "
                             f"See build/systems/booking.py.")
    return b["effect"]
