"""
THE SHIFT SYSTEM: the restaurant's day -- open, serve, close, count the takings, deliver.

    the run starts           ->  a STARTER CARD for each dish that can start a run is on the
                                 pads: choose one -- it's on the menu, its crates delivered
    press the SIGN (closed)  ->  the day opens: the clock starts, guests arrive, the service
                                 lock goes on, unbought offers and unchosen cards vanish
    ...the day runs          ->  the day's EXPECTED GUESTS arrive evenly spread over it, each
                                 wanting a dish that is ON THE MENU. How many: the rules'
                                 day_1, +per_day each day, +per_card for each recipe card
                                 chosen -- more dishes, more customers
    CLOSING TIME             ->  no more guests; the day ends when the last one has left
    the day ends             ->  every few days, recipe cards INSTEAD of offers; otherwise
                                 today's offers go out on the pads
    a card is chosen         ->  the dish is on the menu; crates it needs are delivered
    a guest leaves ANGRY, or
    the whole queue gives up ->  OUT OF BUSINESS: a title for everyone, then back to HQ
                                 (the restaurant's world is torn down); in a spike, the
                                 counters reset and play goes on from day 1

It HEARS, on the shift channel: served / angry / turned away, what each guest paid, the
queue's "impatient", and from the pads: short, bought, chose. It TELLS the queue's pool who
arrives and the pads what to show -- all through signals.py. It names no other system.

WHAT IT HOLDS, as tags on its own volume: the purse and the day (the pads read and pay from
them), what is on the menu (has_<dish>), which crates the restaurant owns (own_<crate>, so
none is delivered twice), and its own clocks. Only this volume can PRINT its tags ({money}
in a chat line), which is why the pads ask it to speak.

HOW IT KEEPS TIME, ported from the POC's probes:
  * the clock and the arrivals are WHOLE-VOLUME cooldowns on TICK -- owned by nobody; they
    pause when nobody is inside, by design;
  * every TICK rule also carries an ENTER effect, or its first pass only "activates" it
    and runs nothing (the tick activation gate);
  * a fair pick is a chain: 1/N, 1/(N-1) ... 1, stopped by an instant `picked` tag.
    A pick that lands on a dish not on the menu is thrown away and tried again next tick
    -- so the pick is fair over whatever is on the menu, however many that is.
  * the day ends when a count of guests inside reaches 0 after closing time.
"""
import re

import blocks
import carry
import offers
import settings
import signals
import volumes as v

FIXTURE = "shift"
PACE, OPENED, COUNTED = "pacing", "opened", "counted"   # the shift <-> its pacing volumes
AFTER_CLEAR = 0.5     # PlaceBlock only fills an empty cell, and a clear lands at tick end
TIPS = range(-3, 6)   # the tip levels there are rules for: coins added to (or taken off) each
                      # guest served


def ids(model):
    prefix = model["theme"]["prefix"]
    gid = lambda local: settings.game_id(prefix, local)
    return {"sign": gid("shift_sign"), "sign_open": gid("shift_sign_open"),
            "effect": gid("shift_system"), "lock": gid("shift_service_lock")}


def _t(event, key, value, cmp="Exactly"):
    return {"Type": "TagCondition", "Event": event, "Source": "Self", "TagKey": key,
            "Comparison": cmp, "TagValue": str(value)}


def _set(event, key, value, op="Set"):
    return {"Type": "ModifyTags", "Event": event, "Operation": op, "TagKey": key,
            "TagValue": str(value)}


def _every(seconds):
    """Passes at most once every `seconds` for the WHOLE volume. Last in its rule: it spends
    its window when it passes."""
    return {"Type": "CooldownCondition", "Event": "TICK", "Cooldown": float(seconds),
            "Scope": "WholeVolume"}


# Every TICK rule carries this, so it acts on the tick it first becomes true.
EVERY_TICK = {"Type": "ModifyTags", "Event": "ENTER", "Operation": "Set", "TagKey": "entered",
              "TagValue": "1"}


EXIT = f"{settings.NAMESPACE}_Exit_Instance"
EXIT_AFTER = 4.0        # seconds to read "out of business" before going back to HQ
ANNOUNCE_SECONDS = 3    # how long an announcement runs: every player inside sees it in that time


def write_exit():
    """The interaction that sends a player back where they came from (HQ): the game's
    ExitInstance, which uses the return point set when they walked through the portal."""
    import pack
    pack.write(pack.out("Item", "Interactions", settings.NAMESPACE, f"{EXIT}_Go.json"),
               {"$Comment": "Back to where you came from. See build/systems/shift.py.",
                "Type": "ExitInstance"})
    pack.write(pack.out("Item", "RootInteractions", settings.NAMESPACE, f"{EXIT}.json"),
               {"Interactions": [f"{EXIT}_Go"]})
    return EXIT


def build(model, roles, debug=True, exit_on_lose=False):
    """`roles`: {menu entry serves-id: guest role} -- who can arrive. `exit_on_lose`: a
    real run (from HQ) sends everyone back to HQ when it's lost; a spike just starts again."""
    s, rules_, looks, words = ids(model), model["rules"], model["fixtures"]["looks"], \
        model["fixtures"]["words"]
    menu, dishes, stations = model["menu"], model["dishes"], model["stations"]
    note = "The shift. See build/systems/shift.py."
    sign = looks["sign"]
    blocks.station_block(s["sign"], "Open sign (closed)", sign, words["sign_closed"], note,
                         tint=sign.get("closed_tint"))
    blocks.station_block(s["sign_open"], "Open sign (open)", sign, words["sign_open"], note,
                         tint=sign.get("open_tint"))
    guests = list(roles.values())
    every = rules_["cards"]["every_days"]
    customers = rules_.get("customers", {}).get("cards", [])
    assert rules_["cards"]["choices"] in (1, 2), "cards.json: choices must be 1 or 2"
    starters = [d for d, dish in dishes.items() if dish["unlock"] == "start"]
    pads = offers.pad_numbers(model)
    assert starters, "no dish can start a run"
    assert len(starters) <= len(pads), "more starter dishes than offer pads"

    rules = v.Entries()
    num = iter(range(1000, 100000))

    def say(event, key, text):
        """Chat for the players (which can print this volume's tags; the "[shift]" tag is
        the log's only) -- and the log, without the numbers."""
        out = [v.say(f"kk.shift.{key}", text.replace("[shift] ", "", 1), event)]
        if debug:
            out.append(v.log(f"kk.shift.{key}", re.sub(r"\{\w+\}", "?", text), event))
        return out

    def logged(event, key, text):
        """The log line alone (the words go on screen as a title instead)."""
        return [v.log(f"kk.shift.{key}", re.sub(r"\{\w+\}", "?", text), event)] if debug else []

    # ANNOUNCEMENTS: a title for EVERY player in the restaurant. A title only reaches the
    # player an event belongs to, but TICK runs once per player inside -- so an event just
    # starts an announcement (a countdown tag), and each player's tick shows it to them once
    # (a PER-PLAYER cooldown, longer than the countdown) until it runs out.
    announcements = {}

    def announce(event, key, title, sub):
        announcements[key] = (title, sub)
        return [_set(event, f"t_{key}", ANNOUNCE_SECONDS)]

    def deliver(event, crate, pad, delay=None):
        return [signals.to_pad(event, pad, signals.DELIVER, crate, delay),
                _set(event, f"own_{crate}", 1)]

    # 1: THE RUN STARTS once there are pads: a starter card on a pad for each dish that can
    # start a run. Choosing one is an ordinary card choice (below): on the menu, crates
    # delivered. The others can still come round later as recipe cards.
    pad_here = {"Type": "TagCondition", "Event": "TICK", "Source": "Radius",
                "MatchKey": signals.PADS_KEY, "MatchValue": signals.PADS_VALUE, "Radius": 64.0,
                "Center": "Volume", "TagKey": signals.PADS_KEY, "Comparison": "Exactly",
                "TagValue": signals.PADS_VALUE}
    rules.add(1, [_t("TICK", "started", 0), pad_here],
              [_set("TICK", "started", 1), EVERY_TICK]
              + [signals.to_pad("TICK", pads[j], signals.CARD, d) for j, d in enumerate(starters)]
              + say("TICK", "started", "[shift] Choose your starting recipe on the pads, set up "
                                       "the kitchen, then open the sign."))

    # 10: open the day. 11: already open. 12: nothing delivered yet.
    # 9: a card is waiting to be chosen -- no opening until it is.
    rules.add(9, [v.at([s["sign"]]), _t("BLOCK_USED", "cardwait", 1)],
              say("BLOCK_USED", "cardwait", "[shift] Choose a card on the pads first."))
    rules.add(10, [v.at([s["sign"]]), _t("BLOCK_USED", "open", 0),
                   _t("BLOCK_USED", "onmenu", 1, "AtLeast"), _t("BLOCK_USED", "cardwait", 0)],
              [v.cell([s["sign"]], s["sign_open"]),
               _set("BLOCK_USED", "open", 1), _set("BLOCK_USED", "closing", 0),
               _set("BLOCK_USED", "lost", 0),
               _set("BLOCK_USED", "time_left", rules_["day_seconds"]),
               # No beat set here: the day's beat rule (6000+) fires the moment the day opens --
               # its cooldown was last spent the day before -- so the first guest still comes at
               # once. Setting one here as well brought TWO guests at opening.
               {"Type": "EnableVolume", "Event": "BLOCK_USED", "MatchKey": "servicelock",
                "MatchValue": "1", "Radius": 128.0, "Center": "Volume"},
               signals.to_pads("BLOCK_USED", signals.CLEAR),
               _set("BLOCK_USED", "served", 0),
               # THE DAY'S GUESTS: the pacing volume for today sets how many, then says so
               # (PACE "counted", below) -- a signal, since rule order between volumes isn't
               # guaranteed. Sent after this rule's tags (open) are set.
               signals.from_volume("BLOCK_USED", PACE, OPENED, match=(PACE, "1"))]
              )
    # 13+: THE DAY GROWS (rules day_growth): every few days it's longer -- more room for the
    # same kind of rush, as PlateUp does. Rule 10 has just set `open` (tags are instant) and
    # the sign block itself only turns at the end of the tick, so these see "just opened".
    growth = rules_.get("day_growth") or {}
    if growth.get("seconds"):
        every_n = growth["every_days"]
        for k in range(1, 15):
            first, last = 1 + every_n * k, every_n * (k + 1)
            rules.add(13 + k, [v.at([s["sign"]]), _t("BLOCK_USED", "open", 1),
                               _t("BLOCK_USED", signals.DAY, first, "AtLeast")]
                      + ([_t("BLOCK_USED", signals.DAY, last, "AtMost")] if k < 14 else []),
                      [_set("BLOCK_USED", "time_left",
                            rules_["day_seconds"] + growth["seconds"] * k)])
    rules.add(11, [v.at([s["sign_open"]])],
              say("BLOCK_USED", "stillopen", "[shift] Open - {time_left}s to closing time; "
                                             "{to_arrive} guests still to come, {served} served."))
    rules.add(12, [v.at([s["sign"]]), _t("BLOCK_USED", "onmenu", 0)],
              say("BLOCK_USED", "nomenu", "[shift] Nothing on the menu yet - choose a "
                                          "starting recipe on the pads."))

    # 20, 21: the clock.
    rules.add(20, [_t("TICK", "open", 1), _t("TICK", "closing", 0), _every(1.0)],
              [_set("TICK", "time_left", -1, op="Increment"), EVERY_TICK])
    rules.add(21, [_t("TICK", "open", 1), _t("TICK", "closing", 0),
                   _t("TICK", "time_left", 0, "AtMost")],
              [_set("TICK", "closing", 1), EVERY_TICK]
              + say("TICK", "closing", "[shift] Closing time - no more guests today."))

    # EXPECTED GUESTS AND THEIR PACE, for every day and number of EXTRA guests the menu brings
    # (tags can't do arithmetic, so each combination is its own rule). 5000+: at opening -- rule 10 has just
    # set `open` -- the count is set; 6000+: the beat spreads them over the day, the first
    # arriving the moment it opens (its cooldown is long spent by then).
    g, growth = rules_["guests"], rules_.get("day_growth") or {}
    last_day = 30

    def extra_guests(dish):
        """(if it's the run's first dish, if it's added later): the guests a dish brings when it
        goes on the menu. A dish's own "guests" says how many it brings as a later dish (a
        quick salad more, a slow pie fewer, as PlateUp does); without one, the rules'
        per_card. As the FIRST dish it shifts day 1 by its difference from per_card -- a salad
        start brings a guest more than a plain one, a pie start one fewer."""
        own = dish.get("guests")
        return (0 if own is None else own - g["per_card"], g["per_card"] if own is None else own)

    # Every total the menu can reach: the first dish's, plus any of the rest's -- plus every
    # customer card's guests.
    gains = [extra_guests(dh) for dh in dishes.values()]
    lo = min(f for f, _ in gains) + sum(min(0, l) for _, l in gains)
    hi = (max(f for f, _ in gains) + sum(max(0, l) for _, l in gains)
          + sum(c.get("guests", 0) for c in customers))

    def expected(day, extra):
        return max(1, g["day_1"] + g["per_day"] * (day - 1) + extra)

    def day_length(day):
        steps = (day - 1) // growth["every_days"] if growth.get("seconds") else 0
        return rules_["day_seconds"] + growth.get("seconds", 0) * steps

    # THE PACING VOLUMES (volumes.companion): one per day, each holding only that day's
    # rules, for the extra-guest totals the day can reach (a card day adds at most
    # `max_gain`). A volume's cost grows with the square of its rules; these tables were
    # most of the shift's, so they're split off. They read the shift's tags and set its
    # `to_arrive`, `expected` and `beat` from outside (signals.shift_reads/shift_changes).
    #   opening (the shift's PACE "opened")  ->  today's guests set, then PACE "counted"
    #   while open                           ->  a BEAT every day_length / guests seconds;
    #                                            the first the moment it opens (its
    #                                            cooldown is long spent by then)
    max_first = max(f for f, _ in gains)
    max_gain = max([l for _, l in gains] + [c.get("guests", 0) for c in customers] + [0])
    for day in range(1, last_day + 1):
        at_day = lambda ev: signals.shift_reads(ev, signals.DAY,
                                                "AtLeast" if day == last_day else "Exactly", day)
        cards_by = (day - 1) // every
        top = hi if day == last_day else min(hi, max_first + cards_by * max_gain)
        pr = v.Entries()
        for extra in range(lo, top + 1):
            n = expected(day, extra)
            k = extra - lo
            pr.add(100 + k, [signals.heard(PACE, OPENED), at_day("SIGNAL_RECEIVED"),
                             signals.shift_reads("SIGNAL_RECEIVED", "extra", "Exactly", extra)],
                   [signals.shift_changes("SIGNAL_RECEIVED", "to_arrive", "Set", n),
                    signals.shift_changes("SIGNAL_RECEIVED", "expected", "Set", n),
                    signals.from_volume("SIGNAL_RECEIVED", PACE, COUNTED)])
            gap = round(day_length(day) / n, 1)
            pr.add(1000 + k, [signals.shift_reads("TICK", "open", "Exactly", 1),
                              signals.shift_reads("TICK", "closing", "Exactly", 0),
                              signals.shift_reads("TICK", "beat", "Exactly", 0),
                              signals.shift_reads("TICK", "to_arrive", "AtLeast", 1),
                              at_day("TICK"),
                              signals.shift_reads("TICK", "extra", "Exactly", extra),
                              _every(gap)],
                   [signals.shift_changes("TICK", "beat", "Set", 1), EVERY_TICK])
        name = f"{s['effect']}_Pacing_{day}"
        pr.write(name, f"The shift's day {day}{'+' if day == last_day else ''}: how many guests, "
                       f"and their pace. See build/systems/shift.py.")
        v.companion(name, {PACE: "1"})
    rules.add(59999, [signals.heard(PACE, COUNTED)],
              say("SIGNAL_RECEIVED", "opened", "[shift] Day {day} - OPEN. Expecting {expected} "
                                               "guests. Purse: {money} coins.")
              + announce("SIGNAL_RECEIVED", "open", "Day {day}", "Expecting {expected} guests"))

    def fair_pick(base, gate, options):
        """The fair chain over `options` while `gate` holds: sets choice = k + 1."""
        for k, _ in enumerate(options):
            rules.add(base + k, [gate, _t("TICK", "picked", 0),
                                 {"Type": "RandomChanceCondition", "Event": "TICK",
                                  "Chance": round(1.0 / (len(options) - k), 4)}],
                      [_set("TICK", "picked", 1), _set("TICK", "choice", k + 1), EVERY_TICK])

    # 100+: who arrives -- any menu entry, then 200+: accepted only if its dish is on the
    # menu; otherwise the beat stands and the pick is tried again next tick.
    fair_pick(100, _t("TICK", "beat", 1), menu)
    for k, e in enumerate(menu):
        rules.add(200 + k, [_t("TICK", "beat", 1), _t("TICK", "choice", k + 1),
                            _t("TICK", f"has_{e['dish']}", 1)],
                  [signals.to_pool("TICK", roles[e["serves"]]), _set("TICK", "beat", 0),
                   _set("TICK", "to_arrive", -1, op="Increment"), EVERY_TICK]
                  + logged("TICK", f"arrive.{k}", f"[shift] a guest arrives (wants "
                                                   f"{e['label']})"))

    # 50-52: the day ends (after closing time, the last guest gone).
    rules.add(50, [_t("TICK", "open", 1), _t("TICK", "closing", 1),
                   {"Type": "EntityCountCondition", "Event": "TICK", "EntityType": guests,
                    "Comparison": "AtMost", "Count": 0}],
              [_set("TICK", "open", 0), _set("TICK", "closing", 0),
               _set("TICK", signals.DAY, 1, op="Increment"),
               _set("TICK", "cards_in", -1, op="Increment"), _set("TICK", "dayover", 1),
               {"Type": "ReplaceBlockType", "Event": "TICK",
                "FromBlockTypes": [s["sign_open"]], "ToBlockType": s["sign"]},
               {"Type": "DisableVolume", "Event": "TICK", "MatchKey": "servicelock",
                "MatchValue": "1", "Radius": 128.0, "Center": "Volume"},
               signals.to_pads("TICK", signals.CLEAR), EVERY_TICK]
              + announce("TICK", "dayover", "Day over",
                         "{served} of {expected} served - {money} coins")
              + logged("TICK", "dayover", "[shift] The last guest has gone - {served} of "
                                          "{expected} served. Purse: {money} coins."))
    # 51, 52: a CARD DAY (PlateUp's rhythm: the start of day 4, then every third day). Two
    # cards, and one MUST be chosen (`cardwait` holds the sign); choosing one puts the day's
    # blueprints out (1000+). Pad 1 a RECIPE card, pad 2 a CUSTOMER card -- or, when one
    # kind has run out (every dish learned, every customer card taken), two of the other.
    # No card day when both have.
    card_day = lambda first: ([_set("TICK", "cardpick", first), _set("TICK", "cards_in", every),
                               _set("TICK", "cardwait", 1), _set("TICK", "dayover", 0),
                               EVERY_TICK]
                              + say("TICK", "cards", "[shift] Card day - choose a card on the "
                                                     "pads. The blueprints come once you have."))
    rules.add(51, [_t("TICK", "dayover", 1), _t("TICK", "cards_in", 0, "AtMost"),
                   _t("TICK", "locked", 1, "AtLeast")], card_day(1))
    rules.add(52, [_t("TICK", "dayover", 1), _t("TICK", "cards_in", 0, "AtMost"),
                   _t("TICK", "locked", 0, "AtMost"), _t("TICK", "ccards_left", 1, "AtLeast")],
              card_day(3))
    rules.add(53, [_t("TICK", "dayover", 1)],
              [signals.to_pads("TICK", signals.PLACE, delay=AFTER_CLEAR),
               _set("TICK", "dayover", 0), EVERY_TICK]
              + say("TICK", "offers", "[shift] Today's offers are on the pads."))

    # THE PICKS, as a chain of `cardpick` states. Each is the fair pick over its kind,
    # accepted only if it's still to be had (and not the card on the other pad).
    #   1: a recipe card to pad 1 -> 2
    #   2: to pad 2 a customer card if there's one (-> 4), else a second recipe card (or none)
    #   3: a customer card to pad 1 (the dishes have run out) -> 4
    #   4: a customer card to pad 2 (if one is left beside pad 1's) -> done
    dlist, clist = list(dishes), [c["id"] for c in customers]
    assert len(dlist) <= 20 and len(clist) <= 40, "too many cards for the pick's rule numbers"
    no_offered = lambda: [_set("TICK", f"offered_{d}", 0) for d in dlist]
    no_offeredc = lambda: [_set("TICK", f"offeredc_{c}", 0) for c in clist]
    fair_pick(300, _t("TICK", "cardpick", 1), dlist)
    for k, d in enumerate(dlist):
        rules.add(400 + k, [_t("TICK", "cardpick", 1), _t("TICK", "choice", k + 1),
                            _t("TICK", f"has_{d}", 0)],
                  [signals.to_pad("TICK", pads[0], signals.CARD, d, delay=AFTER_CLEAR),
                   _set("TICK", f"offered_{d}", 1), _set("TICK", "cardpick", 2), EVERY_TICK])
    rules.add(440, [_t("TICK", "cardpick", 2), _t("TICK", "ccards_left", 1, "AtLeast")],
              [_set("TICK", "cardpick", 4), EVERY_TICK] + no_offered())
    if rules_["cards"]["choices"] == 1:
        rules.add(445, [_t("TICK", "cardpick", 2)],
                  [_set("TICK", "cardpick", 0), EVERY_TICK] + no_offered())
    rules.add(450, [_t("TICK", "cardpick", 2), _t("TICK", "locked", 1, "AtMost")],
              [_set("TICK", "cardpick", 0), EVERY_TICK] + no_offered())
    fair_pick(500, _t("TICK", "cardpick", 2), dlist)
    for k, d in enumerate(dlist):
        rules.add(600 + k, [_t("TICK", "cardpick", 2), _t("TICK", "choice", k + 1),
                            _t("TICK", f"has_{d}", 0), _t("TICK", f"offered_{d}", 0)],
                  [signals.to_pad("TICK", pads[1], signals.CARD, d, delay=AFTER_CLEAR),
                   _set("TICK", "cardpick", 0), EVERY_TICK] + no_offered())
    if clist:
        fair_pick(320, _t("TICK", "cardpick", 3), clist)
        for k, c in enumerate(clist):
            rules.add(360 + k, [_t("TICK", "cardpick", 3), _t("TICK", "choice", k + 1),
                                _t("TICK", f"card_{c}", 0)],
                      [signals.to_pad("TICK", pads[0], signals.CUSTOMER, c, delay=AFTER_CLEAR),
                       _set("TICK", f"offeredc_{c}", 1), _set("TICK", "cpad1", 1),
                       _set("TICK", "cardpick", 4), EVERY_TICK])
        rules.add(455, [_t("TICK", "cardpick", 4), _t("TICK", "cpad1", 1),
                        _t("TICK", "ccards_left", 1, "AtMost")],
                  [_set("TICK", "cardpick", 0), _set("TICK", "cpad1", 0), EVERY_TICK]
                  + no_offeredc())
        fair_pick(540, _t("TICK", "cardpick", 4), clist)
        for k, c in enumerate(clist):
            rules.add(640 + k, [_t("TICK", "cardpick", 4), _t("TICK", "choice", k + 1),
                                _t("TICK", f"card_{c}", 0), _t("TICK", f"offeredc_{c}", 0)],
                      [signals.to_pad("TICK", pads[1], signals.CUSTOMER, c, delay=AFTER_CLEAR),
                       _set("TICK", "cardpick", 0), _set("TICK", "cpad1", 0), EVERY_TICK]
                      + no_offeredc())
    # 699: a pick is spent, taken or not -- after every rule that reads it.
    rules.add(699, [_t("TICK", "picked", 1)],
              [_set("TICK", "picked", 0), _set("TICK", "choice", 0), EVERY_TICK])

    # 700+: a card was chosen: the dish is on the menu, the other card goes, and any crate
    # it needs that the restaurant doesn't own is delivered.
    for d, dish in dishes.items():
        # THE GUESTS IT BRINGS (extra_guests below): the run's first dish or a later one.
        # FIRST, before the menu count below goes up.
        first, later = extra_guests(dish)
        for gate, add in ((0, first), (1, later)):
            if add:
                rules.add(next(num), [signals.heard(signals.CHOSE, d),
                                      _t("SIGNAL_RECEIVED", "onmenu", gate,
                                         "Exactly" if gate == 0 else "AtLeast")],
                          [_set("SIGNAL_RECEIVED", "extra", add, op="Increment")])
        # On a card day, choosing lets the day go on: the blueprints, once the pads are clear
        # and any crates delivered (they skip a pad holding one). Not for the starter.
        rules.add(next(num), [signals.heard(signals.CHOSE, d), _t("SIGNAL_RECEIVED", "cardwait", 1)],
                  [_set("SIGNAL_RECEIVED", "cardwait", 0),
                   signals.to_pads("SIGNAL_RECEIVED", signals.PLACE, delay=3 * AFTER_CLEAR)]
                  + say("SIGNAL_RECEIVED", "offers.after", "[shift] Today's offers are on the pads."))
        rules.add(next(num), [signals.heard(signals.CHOSE, d)],
                  [_set("SIGNAL_RECEIVED", f"has_{d}", 1),
                   _set("SIGNAL_RECEIVED", "locked", -1, op="Increment"),
                   _set("SIGNAL_RECEIVED", "onmenu", 1, op="Increment"),
                   signals.to_pads("SIGNAL_RECEIVED", signals.CLEAR)]
                  + say("SIGNAL_RECEIVED", f"chose.{d}",
                        f"[shift] {dish['label']} is on the menu from the next day."))
        for j, c in enumerate(dish["needs"]):
            rules.add(next(num), [signals.heard(signals.CHOSE, d),
                                  _t("SIGNAL_RECEIVED", f"own_{c}", 0)],
                      deliver("SIGNAL_RECEIVED", c, pads[j % len(pads)], delay=AFTER_CLEAR)
                      + say("SIGNAL_RECEIVED", f"deliver.{d}.{c}",
                            f"[shift] {'An' if stations[c]['label'][0].lower() in 'aeiou' else 'A'} "
                            f"{stations[c]['label'].lower()} is delivered."))

    # A CUSTOMER CARD was chosen: it's in play for the rest of the run (its tag, which the
    # queue's mood rolls read), its guests and tip are added, the other card goes -- and on a
    # card day the day goes on (the blueprints). Never offered again: card_<id> is 1.
    for c in customers:
        cid = c["id"]
        rules.add(next(num), [signals.heard(signals.CHOSE_CUSTOMER, cid),
                              _t("SIGNAL_RECEIVED", "cardwait", 1)],
                  [_set("SIGNAL_RECEIVED", "cardwait", 0),
                   signals.to_pads("SIGNAL_RECEIVED", signals.PLACE, delay=3 * AFTER_CLEAR)]
                  + say("SIGNAL_RECEIVED", "offers.aftercustomer",
                        "[shift] Today's offers are on the pads."))
        rules.add(next(num), [signals.heard(signals.CHOSE_CUSTOMER, cid)],
                  [_set("SIGNAL_RECEIVED", f"card_{cid}", 1),
                   _set("SIGNAL_RECEIVED", "ccards_left", -1, op="Increment"),
                   signals.to_pads("SIGNAL_RECEIVED", signals.CLEAR)]
                  + ([_set("SIGNAL_RECEIVED", "extra", c["guests"], op="Increment")]
                     if c.get("guests") else [])
                  + ([_set("SIGNAL_RECEIVED", "tip", c["tip"], op="Increment")]
                     if c.get("tip") else [])
                  + announce("SIGNAL_RECEIVED", f"cust_{cid}", c["label"], c["text"])
                  + logged("SIGNAL_RECEIVED", f"cust.{cid}", f"[shift] customer card: {c['label']}"))

    # PAYMENTS. A wrong dish pays nothing, and isn't a loss.
    for e in menu:
        rules.add(next(num), [signals.heard(signals.PAID, e["serves"])],
                  [_set("SIGNAL_RECEIVED", signals.MONEY, e["price"], op="Increment")]
                  + logged("SIGNAL_RECEIVED", f"paid.{e['serves']}",
                           f"[shift] +{e['price']} coins ({e['label']}) - purse: {{money}}"))
    # A BOOKING DESK CALLED (booking.py). Guests still to come: the next one comes now (the
    # day's beat fires, so it counts against the day's expected guests) and the call PAYS, by
    # the day (the desk's "pay"). Nobody left: closing time now. CLOSING FIRST, while
    # to_arrive still says nobody's left -- the call's beat only lands on the next tick.
    desk = next((st for st in model["stations"].values() if st["role"] == "call"), None)
    if desk:
        rules.add(next(num), [signals.heard(signals.CALL, "next"), _t("SIGNAL_RECEIVED", "open", 1),
                              _t("SIGNAL_RECEIVED", "closing", 0),
                              _t("SIGNAL_RECEIVED", "to_arrive", 0, "AtMost")],
                  [_set("SIGNAL_RECEIVED", "time_left", 0)]
                  + say("SIGNAL_RECEIVED", "call_close", "[shift] Nobody else is booked in - "
                                                         "closing early."))
        pay = desk.get("pay", {"day_1": 3, "day_2": 4, "then_every_days": 2})

        def call_pays(day):
            return pay["day_1"] if day == 1 else pay["day_2"] + (day - 2) // pay["then_every_days"]

        for day in range(1, last_day + 1):
            rules.add(next(num), [signals.heard(signals.CALL, "next"),
                                  _t("SIGNAL_RECEIVED", "open", 1), _t("SIGNAL_RECEIVED", "closing", 0),
                                  _t("SIGNAL_RECEIVED", "to_arrive", 1, "AtLeast"),
                                  _t("SIGNAL_RECEIVED", signals.DAY, day,
                                     "AtLeast" if day == last_day else "Exactly")],
                      [_set("SIGNAL_RECEIVED", "beat", 1),
                       _set("SIGNAL_RECEIVED", signals.MONEY, call_pays(day), op="Increment")]
                      + logged("SIGNAL_RECEIVED", f"call.{day}",
                               f"[shift] a guest called in (+{call_pays(day)} coins)"))
    rules.add(next(num), [signals.heard(signals.GUEST, signals.SERVED)],
              [_set("SIGNAL_RECEIVED", "served", 1, op="Increment")])
    # TIPS: every guest served pays the tip level on top of its dish (negative: less). The
    # level is the shift's `tip`; a customer card moves it (later), the tips spike's dial now.
    for k in TIPS:
        if k:
            rules.add(next(num), [signals.heard(signals.GUEST, signals.SERVED),
                                  _t("SIGNAL_RECEIVED", "tip", k)],
                      [_set("SIGNAL_RECEIVED", signals.MONEY, k, op="Increment")]
                      + logged("SIGNAL_RECEIVED", f"tip.{k}",
                               f"[shift] tip {k:+d} - purse: {{money}}"))
    for direction, step, edge in ((signals.UP, 1, TIPS[-1]), (signals.DOWN, -1, TIPS[0])):
        rules.add(next(num), [signals.heard(signals.TIP, direction),
                              _t("SIGNAL_RECEIVED", "tip", edge, "Exactly")],
                  say("SIGNAL_RECEIVED", f"tip.edge.{direction}",
                      "[shift] Tips can't go any " + ("higher." if step > 0 else "lower.")))
        rules.add(next(num), [signals.heard(signals.TIP, direction),
                              _t("SIGNAL_RECEIVED", "tip", edge, "NotEquals")],
                  [_set("SIGNAL_RECEIVED", "tip", step, op="Increment")]
                  + say("SIGNAL_RECEIVED", f"tip.{direction}",
                        "[shift] Every guest served now tips {tip} coins."))
    rules.add(next(num), [signals.heard(signals.GUEST, signals.TURNED_AWAY)],
              say("SIGNAL_RECEIVED", "turnedaway",
                  "[shift] A guest got the wrong dish and left without paying."))

    # OUT OF BUSINESS: an angry guest, or the queue giving up. The message FIRST (it prints
    # the tags as they are); the guests go LAST, half a second later -- the signals above are
    # queued with the reporting guest as their actor, and dropped if it has gone.
    # A real run (exit_on_lose) keeps the day and purse for the title and goes back to HQ;
    # a spike starts again from day 1 so it can play on.
    lose = (announce("SIGNAL_RECEIVED", "lost", "OUT OF BUSINESS",
                     "Day {day} - {money} coins" if exit_on_lose else "Starting again from day 1")
            + logged("SIGNAL_RECEIVED", "lost", "[shift] OUT OF BUSINESS on day {day}, with "
                                                "{money} coins.")
            + [_set("SIGNAL_RECEIVED", "lost", 1), _set("SIGNAL_RECEIVED", "open", 0),
               _set("SIGNAL_RECEIVED", "closing", 0), _set("SIGNAL_RECEIVED", "time_left", 0),
               {"Type": "ReplaceBlockType", "Event": "SIGNAL_RECEIVED",
                "FromBlockTypes": [s["sign_open"]], "ToBlockType": s["sign"]},
               {"Type": "DisableVolume", "Event": "SIGNAL_RECEIVED", "MatchKey": "servicelock",
                "MatchValue": "1", "Radius": 128.0, "Center": "Volume"},
               signals.reset_everything("SIGNAL_RECEIVED"),
               signals.to_pads("SIGNAL_RECEIVED", signals.CLEAR),
               {"Type": "RemoveEntities", "Event": "SIGNAL_RECEIVED", "IncludeNpcs": True,
                "IncludePlayers": False, "IgnoreInvulnerability": True, "Roles": guests,
                "Delay": 0.5},
               _set("SIGNAL_RECEIVED", "cards_in", every), _set("SIGNAL_RECEIVED", "cardwait", 0)]
            + ([] if exit_on_lose else [_set("SIGNAL_RECEIVED", signals.DAY, 1),
                                        _set("SIGNAL_RECEIVED", signals.MONEY, 0),
                                        _set("SIGNAL_RECEIVED", "tip", 0)]))
    rules.add(900, [signals.heard(signals.GUEST, signals.ANGRY),
                    _t("SIGNAL_RECEIVED", "lost", 0)], lose)
    rules.add(901, [signals.heard(signals.QUEUE, signals.IMPATIENT),
                    _t("SIGNAL_RECEIVED", "lost", 0)], lose)
    if exit_on_lose:
        # 902: lost -- every player inside goes back to HQ a few seconds later (TICK runs per
        # player; the effect's Interval keeps it to one try each). The empty world is reaped.
        write_exit()
        rules.add(902, [_t("TICK", "lost", 1)],
                  [{"Type": "RunRootInteraction", "Event": "TICK", "RootInteraction": EXIT,
                    "Delay": EXIT_AFTER, "Interval": EXIT_AFTER + 2}, EVERY_TICK])

    # The pads ask it to speak: only it can print the purse.
    for c in offers.catalogue(model):
        rules.add(next(num), [signals.heard(signals.SHORT, c["key"])],
                  say("SIGNAL_RECEIVED", f"short.{c['key']}",
                      f"[shift] Not enough for the {c['label'].lower()} ({c['price']} coins) "
                      f"- the purse has {{money}}."))
        rules.add(next(num), [signals.heard(signals.BOUGHT, c["key"])],
                  say("SIGNAL_RECEIVED", f"bought.{c['key']}",
                      f"[shift] Bought the {c['label'].lower()} for {c['price']} - "
                      f"{{money}} left. Put it down where you want it."))

    # 9000+: THE ANNOUNCEMENTS (see announce): every player's tick shows a running one to
    # them once; a whole-volume beat counts it down.
    for k, (key, (title, sub)) in enumerate(sorted(announcements.items())):
        tag = f"t_{key}"
        rules.add(9000 + 2 * k,
                  [_t("TICK", tag, 1, "AtLeast"),
                   {"Type": "CooldownCondition", "Event": "TICK",
                    "Cooldown": float(ANNOUNCE_SECONDS + 4), "Scope": "PerPlayer"}],
                  [v.title(f"kk.shift.title.{key}", title, f"kk.shift.title.{key}.sub", sub,
                           event="TICK"), EVERY_TICK])
        rules.add(9001 + 2 * k, [_t("TICK", tag, 1, "AtLeast"), _every(1.0)],
                  [_set("TICK", tag, -1, op="Increment"), EVERY_TICK])

    rules.write(s["effect"], "The shift: the day, arrivals, the purse, the menu, deliveries. "
                             "See build/systems/shift.py.")
    # The service lock: its Rules stop building and breaking, and its one effect marks
    # every player inside as in service, so nothing can be picked up (carry.py).
    lock = v.Entries()
    lock.add(1, [], [carry.in_service_mark()])
    lock.write(s["lock"], "The service lock. See build/systems/shift.py.")
    locked = len(dishes)          # nothing is on the menu until a starter is chosen
    tags = {**signals.LISTENER_TAGS, signals.MONEY: "0", signals.DAY: "1", "open": "0",
            "closing": "0", "time_left": "0", "beat": "0", "picked": "0", "choice": "0",
            "lost": "0", "started": "0", "dayover": "0", "cardpick": "0", "cardwait": "0",
            "tip": "0", "ccards_left": str(len(customers)), "cpad1": "0",
            "cards_in": str(every), "locked": str(locked), "onmenu": "0",
            "to_arrive": "0", "expected": "0", "served": "0", "extra": "0",
            **{f"t_{k}": "0" for k in announcements}}
    tags.update({f"has_{d}": "0" for d in dishes})
    tags.update({f"offered_{d}": "0" for d in dishes})
    tags.update({f"card_{c['id']}": "0" for c in customers})
    tags.update({f"offeredc_{c['id']}": "0" for c in customers})
    tags.update({f"own_{c}": "0" for c in offers.crates(model)})
    return tags


def volumes(model, tags, box=v.WORLD_BOX):
    """The shift's volume, and the SERVICE LOCK over the restaurant -- off until the day
    opens: no building and no breaking during service."""
    s = ids(model)
    lock = v.volume("shift_service_lock", s["lock"], {"servicelock": "1"}, box=box)
    lock.update({"Enabled": False, "Rules": [{"Type": "NoBuild"}, {"Type": "NoDestroy"}],
                 "RulesActive": True})
    return [v.volume("shift", s["effect"], tags, box=box), lock]
