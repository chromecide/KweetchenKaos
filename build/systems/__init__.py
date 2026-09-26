"""
THE SYSTEMS, and the one shape every system has.

A system is the machinery behind one ROLE of station (press, combine, heat...). The theme
says what stations exist and what they do; a system turns one station into blocks and a
volume effect. The same code runs in a spike world today and in a real layout later, so
integration is mounting, never rewiring.

THE CONTRACT -- every system module:

    ROLES               the station roles it serves, e.g. ("press", "wash")
    build(model, station_id, debug) -> str
                        writes the station's blocks and its volume effect; returns the
                        effect's name, for whoever mounts it (spike world, layout)
    free_block(model, station_id) -> str
                        the game id of the station as you place it (for kits, layouts)
    layout(model, station_id) -> [(dy, block)]
                        what a layout places for this station, bottom up: usually just the
                        station, but a crate comes with its ingredient on top
    NEEDS_CLOCK         (optional) True if the world must run its clock (anything timed by
                        growth: the stove, crates)
    TAGS                (optional) tags the station's volume must carry (a lock, say): a rule
                        can't read a tag that was never set

THE RULES that keep systems maintainable:

  1. A system reads ONLY the model (build/content.py). It never imports another system, and
     never assumes what another system makes -- if the counter needs to know what combines,
     it reads the theme's combine steps, not the stove's code.
  2. Systems share only infrastructure: blocks.py (block shapes), volumes.py (rules and
     reporting), settings.py (ids). Anything two systems both need goes there, or into the
     model, never into one of them.
  3. A system's game ids all start with its station's id (K2_Kitchen_Counter_...), so no two
     systems can make the same block.
  4. Instrumented by default: every milestone goes to the SERVER LOG (volumes.report; the
     log takes one line a second, so frequent events are left out). Chat is for players.
  5. The top of each system file says what the player does and what happens, in plain
     words, before any code.
  6. A station's FREE block is movable (blocks.station_block movable=True, carry.py):
     picked up and put down between days. Anything holding food or a plate is not.
"""
from systems import bin, booking, counter, crate, heat, press, rack

_BY_ROLE = {}
for _module in (press, counter, heat, crate, bin, rack, booking):
    for _role in _module.ROLES:
        _BY_ROLE[_role] = _module


def tags_for(model, station_id, extra):
    """The tags a station's volume carries: whatever it mounts with, plus its system's own."""
    return dict(extra, **getattr(for_station(model, station_id), "TAGS", {}))


def for_station(model, station_id):
    """The system that runs this station."""
    role = model["stations"][station_id]["role"]
    if role not in _BY_ROLE:
        raise KeyError(f"no system is written yet for '{role}' stations ({station_id})")
    return _BY_ROLE[role]
