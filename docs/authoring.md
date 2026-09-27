# Authoring: building rooms and putting them in the game

A restaurant is three things: a **layout** (the room), a **theme** (what the
room's stations and fixtures look like), and a **rules** set (how a run plays).
This guide is about layouts, which you build by hand in the game. HQ and the
backdrop around every room are built the same way.

You build with plain **slot blocks** wherever something of the restaurant's
goes: a stove slot, chair slots, queue spots and so on. When the game is built,
each slot becomes the theme's block. A stove slot is a stove in the kitchen
theme, and would be a cauldron in a witchery theme. So you build an ugly room
full of slot blocks, and it's dressed when you deploy.

Set up and deploy once first ([getting-started.md](getting-started.md)).

## The whole process

1. `/kk author floorplan 7`: go to floorplan 7's authoring world.
2. `/kk slots plot`: take the slot blocks.
3. Build the room in the plot, with a **room size** slot (starter, small, medium or large).
4. `/kk save floorplan 7`: save it.
5. `python3 deploy.py`: a new playable room is imported as a layout by itself,
   and its size's HQ portal starts picking it. Built and installed.
6. `/kk hq`, and step on that size's portal (it picks one of its rooms at random
   each run).

**After that, a tweak is just:** `/kk save floorplan 7` in game, then
`python3 deploy.py`. It picks up every world saved since, builds and installs.

**Naming it:** a room picked up by itself is `floorplan_07` / "Floorplan 7"
(shown as players arrive). Change `name` in its `layout.json`, or import it
under an id of your own (below).

Each step is explained below.

## The authoring worlds

Every layout has an **authoring world of its own**, with a single plot, so no
world gets crowded. Each is a flat world with real ground (stone, dirt, grass),
in creative mode, and it **keeps what you build** between visits.

| Command | World | Plot size |
|---|---|---|
| `/kk author border` | the **border**: the backdrop around every room | 64 × 64, with a 32 × 32 hole in the middle |
| `/kk author hq` | **HQ** | 32 × 32 |
| `/kk author practice` | the **practice room** | 32 × 32 |
| `/kk author floorplan 7` | a **restaurant room**: floorplans 1 to 99 | 32 × 32 |

`/kk author` also draws a yellow line of edge blocks one block **outside** the
plot, every time. The line is never saved and never touches what's inside. You
arrive standing just in front of it.

The plot's floor is at **y 32**, the top of the grass. What gets saved:

- **A room plot:** from 3 blocks below the floor to 48 above it (room for a room up a tree). The ground
  under the floor comes with the room. That's what gravel rests on, and it is
  the room's underside in the floating worlds.
- **The border plot:** from 16 below to 48 above, but nothing in the hole. The
  hole is where the room goes.

Build the floor as part of the room: a new plot is just grass.

## Slot blocks

| Command | Gives you |
|---|---|
| `/kk slots plot` | everything a restaurant room uses (the practice room's slots, while it's switched off, only come with `/kk slots`) |
| `/kk slots hq` | the arrival slot, the five portals and the franchise shelves |
| `/kk slots` | all of them |

| Slot | Becomes | Rules |
|---|---|---|
| **board (press)** | the chopping board | at least one |
| **counter (combine)** | a counter | at least one; where food is assembled and plated, so usually several |
| **stove (heat)** | the stove | at least one |
| **sink (wash)** | the sink | at least one |
| **bin** | the bin | at least one |
| **booking desk** | the booking desk (call the next guest in now, for coins) | one: every room has one |
| **call a guest** | the practice room's Call a guest block -- and it makes the room a **practice room** (no shift, pads or sign: guests come by themselves, nothing counts) | one, in a practice room |
| **crate - <ingredient>** (one per ingredient) | that ingredient's crate, in a practice room (a real run delivers its crates, so a normal room leaves these out) | one of each the menu needs |
| **franchise shelf** (HQ, one per item) | a shelf in the franchise storeroom: players take their banked items here, and put them back | as many as you like; only the shelves you place appear |
| **mop stand** | the mop stand, with the mop on it (to clean messes and spills) | one: every room has one; without it, messes can't be cleaned |
| **plate rack** | the plate rack, starting with plates | at least one; the only source of plates |
| **chair** | a chair, and **its own table in front of it** | place it facing where you want the table; the cell in front must be free |
| **queue spot 1–4** | the queue | a line: 1 is the front, 4 the back; each needs a clear path to the next |
| **queue pool** | where guests appear | behind spot 4 |
| **offer pad 1–4** | the pads (offers, deliveries, recipe cards) | all four |
| **open sign** | the sign that starts each day | one |
| **arrival** | where players appear | set it in the floor; it becomes the floor around it. Optional: without it, players arrive in front of the room |
| **barrier** | an invisible wall (the game's `Barrier`) | anywhere, in any layout, HQ and the border: a clearly visible block while you build |
| **room size - starter / small / medium / large** | which HQ portal picks this room; gone (air) in game | one in every restaurant room (not the practice room) |
| **HQ portal - practice / starter / small / medium / large** | (HQ only) the portal itself: it looks like the portal pad | place it on the floor, exactly where the portal goes |

Look at any slot to see which it is. Station slots look like the kitchen theme's
stations (a stove slot is an iron stove with its trim); the other slots are tinted
marker blocks.

Every station slot can appear more than once; the build warns if a kind is missing.
Crates are not slots. They are delivered on the pads when a dish goes on the
menu, and players place them.

### Making a room work

- **No doors.** A closed door stops guests from finding their way. Leave
  openings instead.
- **Guests walk**: from the pool, up the queue spots one at a time, to a free
  chair, and back out towards the pool. Every step needs a clear walking path.
- **Keep the queue apart from the dining area.** The queue's patience counts
  every guest standing near the spots and the pool, so a chair there would
  drain it. The build works out the queue's area as the spots and the pool plus
  one block around. To set it exactly, draw a trigger volume with the game's
  volume tool around the queue and name it `queue`; it is saved with the plot.
- **Chairs face their tables.** A chair's table goes in the cell in front of
  it, so four chairs round a 2 × 2 block make a table for four.
- **Stations need space around them** for players to reach, and for things to
  sit on top.
- **Keep the room inside the 32 × 32 plot.** Anything outside the edge line
  isn't saved.

## HQ

HQ has its own world (`/kk author hq`), built the same way with the HQ slots: one **arrival** slot and
five **portal** slots: the practice room, and starter, small, medium and large
rooms (the starter is a tiny room, good for one player). A
size portal starts a run in one of that size's rooms, picked at random each time
a run starts; everyone who steps on it while that run is going joins it. Players arrive on the arrival spot, both when
they join and when they come back from a run. A portal with no rooms yet is left out;
`python3 deploy.py hq` puts a placeholder portal on each empty one.

## The border

The border (`/kk author border`) is the backdrop pasted around every room and around HQ: trees, rocks,
whatever you like on the 16-block ring around the hole. The hole is left out,
so it doesn't matter what's in it. The border saves 16 blocks below the floor,
so you can shape the underside of a floating island.

## Saving

**`/kk save floorplan 7`** saves floorplan 7 (and `/kk save border`,
`/kk save hq`, `/kk save practice`). It takes you into that world first, so it
can only ever save the world it names, wherever you run it from. The saves go
into the installed pack, and `deploy.py` copies them back into
`content/layouts/_saves/` before it replaces the pack. Nothing is lost between
deploys.

**Undo:** `/kk restore floorplan 7` puts it back as it was at its last save,
throwing away what you've built since. It exists for every world that has been
saved (after the next deploy).

## Importing

`python3 deploy.py` does this for you: a saved floorplan (or the practice room)
that is a **playable room** (every kind of station, chairs, all four queue
spots, the pool and the sign) and not yet a layout is imported as
`floorplan_<nn>`. One with some slots but not all is
reported as unfinished, with what's missing. To choose the id and name yourself,
import it by hand. A save is raw; importing turns it into a layout the build can
use:

```
python3 build/layouts.py import floorplan_07 corner_pass "Corner pass"
```

- `floorplan_07` is the world it was saved in (`border`, `hq`, `practice` or
  `floorplan_01` to `floorplan_99`); `corner_pass` is the layout's id, used in
  `world.json`; `"Corner pass"` is its name.
- It writes `content/layouts/corner_pass/`: `room.prefab.json`, the room, and
  `layout.json`, its name and any zones you drew.
- It lists the slots it found. Check the list: a room with no stove slot, for
  instance, builds with a warning.
- It takes the newest save, even one made since the last deploy.
- Importing again replaces the layout. Import the border and HQ the same way;
  the border is recognised by its world.

**After any later `/kk save`, just deploy.** `python3 deploy.py` first imports
again every layout whose world has a newer save (each layout remembers its world
in `layout.json`, as `source`), then builds and installs. `python3 build/layouts.py reimport` does
only the import step, if you want it on its own.

## Putting a room in the game

Nothing to list: every room is **picked up by itself** when you deploy. A room
with a **room size** slot goes into that size's portal; the practice room (a
room with a **call a guest** slot) into the practice portal. The deploy says how
many rooms each portal has, and names any room with no size slot (no portal
picks it).

`content/world/world.json` says how HQ and its portals play:

```json
{
  "hq": "hq",
  "ground": "void",
  "weather": "Zone1_Sunny",
  "border": "backdrop",
  "portals": {
    "practice": { "name": "Practice", "theme": "kitchen", "rules": "standard" },
    "starter":  { "name": "Starter",  "theme": "kitchen", "rules": "standard" },
    "small":    { "name": "Small",    "theme": "kitchen", "rules": "standard" },
    "medium":   { "name": "Medium",   "theme": "kitchen", "rules": "standard" },
    "large":    { "name": "Large",    "theme": "kitchen", "rules": "standard" }
  }
}
```

| Key | Meaning |
|---|---|
| `hq` | the layout HQ is built from |
| `ground` | `"void"` (floating in the sky) or `"flat"` (grass to the horizon), for HQ and every restaurant |
| `weather` | a shipped weather held for good, e.g. `Zone1_Sunny`; leave it out for the world's own |
| `border` | the layout pasted around every room; `"none"` for none |
| `portals` | the five portals: `name` (shown in game), `theme` and `rules` (`standard`, or `practice` for short, easy days) |

A portal can override `ground`, `weather` and `border` for itself, and
`"enabled": false` switches it off (no portal in HQ). The practice portal is off
for now. Each player's
best is kept per portal ("Your best at Medium: day 15+").

A room built before size slots can be given one in its `layout.json` instead:
`"size": "medium"`. `"enabled": false` in a room's `layout.json` takes it out of
the rotation but keeps it (the three first rooms are out, for now).

## Testing a room on its own

To try a layout without going through HQ:

```
python3 deploy.py room:corner_pass practice
```

Then, in game: `/kk spike` (the test world, rebuilt fresh each visit), then
`/kk kit` (a setup block and some ingredients and plates). Place the setup block
and press it: the room is laid out beside it with everything working, under the
`practice` rules, which have short days and patient guests. Other test worlds,
of single stations or the whole kitchen, are listed in `build/spike.py`.

## Starting an authoring world again

Each world keeps everything. To start one again from nothing, stop the server,
delete its folder in the server's `universe/worlds/` (`k2_author_floorplan_07`,
say), start it, and `/kk author floorplan 7`.

## Choosing looks

Station textures, tints and trims are in the theme
(`content/themes/<theme>/stations/`). See [content-schema.md](content-schema.md)
for the format, and [stations.md](stations.md) for what the kitchen uses and why.
The texture and model galleries used to choose them are a separate probe, not
part of this project.
