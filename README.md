# KwitchenKaos

A Plate Up–style co-op restaurant for Hytale, built entirely from pack data (no
plugin code). Restaurants come from **content**: themes now, and later layouts,
rules and world. All of it is JSON in `content/`, and the build scripts in
`build/` turn it into a game pack. The format is in `docs/content-schema.md`,
and the menu decisions in `docs/menu.md`.

This started as v2 of the Kitchen POC (`../tools`, `../pack`). That project is
untouched and still deploys. KwitchenKaos loads beside it on the same scratch
server: every game id here starts with `K2_`, so nothing collides.

## Use

```
python3 build/build.py --check    read and check the kitchen theme, print the report
python3 build/build.py            ...and write pack/
./deploy.sh [SPIKE]               build with SPIKE in the spike world (default board),
                                  deploy beside the POC, restart, report rejections
```

The report lists every menu entry and the full chain that makes it, crate to
plate. If it reads right, the theme is right.

## Build

| File | Job |
|---|---|
| `settings.py` | paths, the `K2` namespace, how a local id becomes a game id |
| `content.py` | reads a theme folder into one resolved model (looks, ladders, items) |
| `check.py` | checks the model as a whole: references, station roles, plating, shipped asset paths |
| `pack.py` | writes the pack from nothing every build: no stale files, no stale language lines |
| `items.py` | every item: its look, no right-click placing, no eating, one in hand, hotbar quality |
| `blocks.py` | block shapes every system uses: an item's look as a block, stations, things sitting on stations |
| `volumes.py` | the volume rules systems write, plus chat and server-log reporting for debugging |
| `systems/__init__.py` | the one shape every system has, the rules that keep them separate, and which system runs which station role |
| `systems/press.py` | press stations: the chopping board, and later the sink |
| `systems/counter.py` | the counter: holds one thing, combines (assembling and plating) |
| `systems/heat.py` | the stove: cooks through a ladder of stages by itself, and burns |
| `systems/crate.py` | crates: an ingredient on top, restocking after a few seconds |
| `systems/bin.py` | the bin: food goes, plates stay |
| `clock.py` | the world clock that growth (stove, crates) runs on |
| `signals.py` | the channels systems talk on: shift, pool arrivals, reset |
| `npc.py` | NPC behaviour pieces: branches, flags, timers, block-under-feet, roles |
| `serving.py` | the handshake that hands a plated dish to a guest |
| `systems/queue.py` | the queue: spots that decide who arrived first, the pool, the held front, one patience clock |
| `systems/seating.py` | chairs and their own tables, sitting, getting up, the plate left behind |
| `systems/guest.py` | a seated guest: order, patience pulses, eat, or walk out |
| `guests.py` | one guest role per menu entry, composed from the three fragments |
| `spike_front.py` | the service spike's front of house: guest callers and a listener for the shift |
| `spike.py` | the spike world: stations mounted over an empty world, `/kk spike`, `/kk kit`, and a setup block that lays the stations out |
| `build.py` | runs it all and prints the report |

`pack/` is build output and is not committed.

## State (2026-09-24)

- The kitchen theme (`content/themes/kitchen/`) reads and checks, and its 33 items
  build and load in game with nothing rejected.
- **Board: built and spike-tested** (all five ingredients).
- **Counter: built and spike-tested** (put down, pick up, assembling, plating both ways).
- **Batch 1, the whole kitchen: built and spike-tested** (`./deploy.sh kitchen`).
- **Batch 2, front of house: built, awaiting its spike test** (`./deploy.sh service`):
  queue, seating, guests, on top of the kitchen.
- **The other systems are next, rewritten fresh one at a time** (not copied from the POC),
  each reading its station, words and recipes from the model and each re-spiked:
  board, stove, counter, sink, bin, then guests, queue, seating, shift.
