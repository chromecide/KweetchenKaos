"""
THE SHIFT SYSTEM: the restaurant's day -- open, serve, close, count the takings, deliver.

    the run starts           ->  a STARTER CARD for each dish that can start a run is on the
                                 pads: choose one -- it's on the menu, its crates delivered
    press the SIGN (closed)  ->  the day opens: the clock starts, guests arrive, the service
                                 lock goes on, unbought offers and unchosen cards vanish
    ...the day runs          ->  a guest every few seconds (faster as the run goes on),
                                 wanting a dish that is ON THE MENU
    CLOSING TIME             ->  no more guests; the day ends when the last one has left
    the day ends             ->  every few days, recipe cards INSTEAD of offers; otherwise
                                 today's offers go out on the pads
    a card is chosen         ->  the dish is on the menu; crates it needs are delivered
    a guest leaves ANGRY, or
    the whole queue gives up ->  OUT OF BUSINESS (eventually: back to HQ, the world reaped;
                                 for now the counters reset so a spike can go on)

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
AFTER_CLEAR = 0.5     # PlaceBlock only fills an empty cell, and a clear lands at tick end


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
    assert rules_["cards"]["choices"] in (1, 2), "cards.json: choices must be 1 or 2"
    starters = [d for d, dish in dishes.items() if dish["unlock"] == "start"]
    pads = offers.pad_numbers(model)
    assert starters, "no dish can start a run"
    assert len(starters) <= len(pads), "more starter dishes than offer pads"

    rules = v.Entries()
    num = iter(range(1000, 100000))

    def say(event, key, text):
        """Chat (which can print this volume's tags) -- and the log, without the numbers."""
        out = [v.say(f"kk.shift.{key}", text, event)]
        if debug:
            out.append(v.log(f"kk.shift.{key}", re.sub(r"\{\w+\}", "?", text), event))
        return out

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
    rules.add(10, [v.at([s["sign"]]), _t("BLOCK_USED", "open", 0),
                   _t("BLOCK_USED", "onmenu", 1, "AtLeast")],
              [v.cell([s["sign"]], s["sign_open"]),
               _set("BLOCK_USED", "open", 1), _set("BLOCK_USED", "closing", 0),
               _set("BLOCK_USED", "lost", 0),
               _set("BLOCK_USED", "time_left", rules_["day_seconds"]),
               # The first guest comes the moment the day opens, not a whole beat later: a
               # day that starts with nothing happening looks broken.
               _set("BLOCK_USED", "beat", 1),
               {"Type": "EnableVolume", "Event": "BLOCK_USED", "MatchKey": "servicelock",
                "MatchValue": "1", "Radius": 128.0, "Center": "Volume"},
               signals.to_pads("BLOCK_USED", signals.CLEAR)]
              + say("BLOCK_USED", "opened", "[shift] Day {day} - OPEN. Purse: {money} coins."))
    rules.add(11, [v.at([s["sign_open"]])],
              say("BLOCK_USED", "stillopen", "[shift] Open - {time_left}s to closing time."))
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

    # 30+: the beat, one rule per stage of the run, each at its own pace.
    for k, stage in enumerate(rules_["stages"]):
        rules.add(30 + k, [_t("TICK", "open", 1), _t("TICK", "closing", 0), _t("TICK", "beat", 0),
                           _t("TICK", signals.DAY, stage["from"], "AtLeast"),
                           _t("TICK", signals.DAY, stage["to"], "AtMost"),
                           _every(rules_["arrival_every"][stage["id"]])],
                  [_set("TICK", "beat", 1), EVERY_TICK])

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
                   EVERY_TICK]
                  + (say("TICK", f"arrive.{k}", f"[shift] a guest arrives (wants "
                                                f"{e['label']})") if debug else []))

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
              + say("TICK", "dayover", "[shift] The last guest has gone. Purse: {money} "
                                       "coins. Tomorrow is day {day}."))
    # 51: a card day (and something left to learn) -- cards INSTEAD of offers.
    rules.add(51, [_t("TICK", "dayover", 1), _t("TICK", "cards_in", 0, "AtMost"),
                   _t("TICK", "locked", 1, "AtLeast")],
              [_set("TICK", "cardpick", 1), _set("TICK", "cards_in", every),
               _set("TICK", "dayover", 0), EVERY_TICK]
              + say("TICK", "cards", "[shift] Recipe cards are on the pads - choose one."))
    rules.add(52, [_t("TICK", "dayover", 1)],
              [signals.to_pads("TICK", signals.PLACE, delay=AFTER_CLEAR),
               _set("TICK", "dayover", 0), EVERY_TICK]
              + say("TICK", "offers", "[shift] Today's offers are on the pads."))

    # 60+: the cards -- the first (A) to pad 1, the second (B, different) to pad 2. Each is
    # the fair pick over every dish, accepted only if it isn't on the menu (and B not A).
    dlist = list(dishes)
    fair_pick(300, _t("TICK", "cardpick", 1), dlist)
    for k, d in enumerate(dlist):
        rules.add(400 + k, [_t("TICK", "cardpick", 1), _t("TICK", "choice", k + 1),
                            _t("TICK", f"has_{d}", 0)],
                  [signals.to_pad("TICK", pads[0], signals.CARD, d, delay=AFTER_CLEAR),
                   _set("TICK", f"offered_{d}", 1),
                   # One card only: done. Two: go on to pick the second.
                   _set("TICK", "cardpick", 2 if rules_["cards"]["choices"] == 2 else 0),
                   EVERY_TICK])
    rules.add(450, [_t("TICK", "cardpick", 2), _t("TICK", "locked", 1, "AtMost")],
              [_set("TICK", "cardpick", 0), EVERY_TICK]
              + [_set("TICK", f"offered_{d}", 0) for d in dlist])
    if rules_["cards"]["choices"] == 2:
        fair_pick(500, _t("TICK", "cardpick", 2), dlist)
        for k, d in enumerate(dlist):
            rules.add(600 + k, [_t("TICK", "cardpick", 2), _t("TICK", "choice", k + 1),
                                _t("TICK", f"has_{d}", 0), _t("TICK", f"offered_{d}", 0)],
                      [signals.to_pad("TICK", pads[1], signals.CARD, d, delay=AFTER_CLEAR),
                       _set("TICK", "cardpick", 0), EVERY_TICK]
                      + [_set("TICK", f"offered_{x}", 0) for x in dlist])
    # 699: a pick is spent, taken or not -- after every rule that reads it.
    rules.add(699, [_t("TICK", "picked", 1)],
              [_set("TICK", "picked", 0), _set("TICK", "choice", 0), EVERY_TICK])

    # 700+: a card was chosen: the dish is on the menu, the other card goes, and any crate
    # it needs that the restaurant doesn't own is delivered.
    for d, dish in dishes.items():
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
                            f"[shift] A {stations[c]['label'].lower()} is delivered."))

    # PAYMENTS. A wrong dish pays nothing, and isn't a loss.
    for e in menu:
        rules.add(next(num), [signals.heard(signals.PAID, e["serves"])],
                  [_set("SIGNAL_RECEIVED", signals.MONEY, e["price"], op="Increment")]
                  + say("SIGNAL_RECEIVED", f"paid.{e['serves']}",
                        f"[shift] +{e['price']} coins ({e['label']}) - purse: {{money}}"))
    rules.add(next(num), [signals.heard(signals.GUEST, signals.TURNED_AWAY)],
              say("SIGNAL_RECEIVED", "turnedaway",
                  "[shift] A guest got the wrong dish and left without paying."))

    # OUT OF BUSINESS: an angry guest, or the queue giving up. The message FIRST (it prints
    # the tags as they are); the guests go LAST, half a second later -- the signals above are
    # queued with the reporting guest as their actor, and dropped if it has gone.
    lose = (say("SIGNAL_RECEIVED", "lost", "[shift] OUT OF BUSINESS on day {day}, with "
                                           "{money} coins. (Later: back to HQ, the world "
                                           "reaped.)")
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
               # Until HQ exists: start again from day 1 so a spike can play on.
               _set("SIGNAL_RECEIVED", signals.DAY, 1), _set("SIGNAL_RECEIVED", signals.MONEY, 0),
               _set("SIGNAL_RECEIVED", "cards_in", every)])
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
                      f"{{money}} left."
                      + ("" if c["cube"] else " Hold it and press a free station it fits "
                                              "to upgrade it.")))

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
            "lost": "0", "started": "0", "dayover": "0", "cardpick": "0",
            "cards_in": str(every), "locked": str(locked), "onmenu": "0"}
    tags.update({f"has_{d}": "0" for d in dishes})
    tags.update({f"offered_{d}": "0" for d in dishes})
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
