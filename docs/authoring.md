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

1. `/kk author`: go to the authoring world.
2. `/kk grid`: mark the plots (first time, or after adding plots).
3. `/kk slots plot`: take the slot blocks.
4. Build the room in a plot.
5. `/kk save`: save the plots.
6. `python3 deploy.py`: a new playable room is imported as a layout by itself,
   added to `content/world/world.json` on the next free HQ portal, built and
   installed.
7. `/kk hq`, and step on its portal.

**After that, a tweak is just:** `/kk save` in game, then `python3 deploy.py`.
It picks up every plot saved since, builds and installs.

**Naming it:** a room picked up by itself is `plot_4` / "Plot 4". Change its
`name` in `world.json` for what players see, or import it under an id of your own
(below) and remove the `plot_4` entry.

Each step is explained below.

## The authoring world

`/kk author` takes you to the authoring world, in creative mode. It is a flat
world with real ground (stone, dirt, grass), and it **keeps what you build**
between visits.

It is laid out as **plots** in a row along x, six chunks (96 blocks) apart, so
no guest can see or walk into the next one:

| Plot | What it's for | Size |
|---|---|---|
| 0 | the **border**: the backdrop around every room | 64 × 64, with a 32 × 32 hole in the middle |
| 1 | **HQ** | 32 × 32 |
| 2–9 | **restaurant layouts** | 32 × 32 each |

**`/kk plot 3`** takes you to plot 3 (standing just in front of it); any plot
number works.

**`/kk grid`** draws a yellow line of edge blocks one block **outside** each
plot. The line is never saved and never touches what's inside, so it is safe to
run any time. `/kk grid 14` marks the first 14 plots, if you want more than the
usual 10.

Each plot's floor is at **y 32**, the top of the grass. What gets saved:

- **A room plot:** from 3 blocks below the floor to 48 above it (room for a room up a tree). The ground
  under the floor comes with the room. That's what gravel rests on, and it is
  the room's underside in the floating worlds.
- **The border plot:** from 16 below to 48 above, but nothing in the hole. The
  hole is where the room goes.

Build the floor as part of the room: a new plot is just grass.

## Slot blocks

| Command | Gives you |
|---|---|
| `/kk slots plot` | everything a restaurant room uses |
| `/kk slots hq` | the arrival slot and portals 1–8 |
| `/kk slots` | all of them |

| Slot | Becomes | Rules |
|---|---|---|
| **board (press)** | the chopping board | at least one |
| **counter (combine)** | a counter | at least one; where food is assembled and plated, so usually several |
| **stove (heat)** | the stove | at least one |
| **sink (wash)** | the sink | at least one |
| **bin** | the bin | at least one |
| **booking desk** | the booking desk (call the next guest in now) | optional: a room plays without one, and one can be bought |
| **plate rack** | the plate rack, starting with plates | at least one; the only source of plates |
| **chair** | a chair, and **its own table in front of it** | place it facing where you want the table; the cell in front must be free |
| **queue spot 1–4** | the queue | a line: 1 is the front, 4 the back; each needs a clear path to the next |
| **queue pool** | where guests appear | behind spot 4 |
| **offer pad 1–4** | the pads (offers, deliveries, recipe cards) | all four |
| **open sign** | the sign that starts each day | one |
| **arrival** | where players appear | set it in the floor; it becomes the floor around it. Optional: without it, players arrive in front of the room |
| **barrier** | an invisible wall (the game's `Barrier`) | anywhere, in any layout, HQ and the border: a clearly visible block while you build |
| **HQ portal 1–8** | (HQ only) the portal to restaurant 1–8 in `world.json` | set in the floor |

Barriers placed as the game's own `Barrier` block (hard to see) can be turned
into barrier slots with **`/kk barriers`**, once.

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

HQ is plot 1, built the same way with the HQ slots: one **arrival** slot and a
**portal** slot for each restaurant. Portal *n* leads to the restaurant that
`world.json` hangs on portal *n*. Players arrive on the arrival spot, both when
they join and when they come back from a run. To see every portal slot filled while you
line them up, `python3 deploy.py hq` puts a placeholder portal on each empty one.

## The border

Plot 0 is the backdrop pasted around every room and around HQ: trees, rocks,
whatever you like on the 16-block ring around the hole. The hole is left out,
so it doesn't matter what's in it. The border saves 16 blocks below the floor,
so you can shape the underside of a floating island.

## Saving

**`/kk save`** saves every plot (`/kk save 14` for the first 14). It flies
you over each plot as it saves. The saves go into the installed pack, and
`deploy.py` copies them back into `content/layouts/_saves/` before it replaces
the pack. Nothing is lost between deploys.

**Undo:** `/kk restore 2` puts plot 2 back as it was at its last save, throwing
away what you've built since. It exists for every plot that has been saved.

## Importing

`python3 deploy.py` does this for you: a saved plot that is a **playable room**
(every kind of station, chairs, all four queue spots, the pool and the sign) and
not yet a layout is imported as `plot_<n>`. A plot with some slots but not all is
reported as unfinished, with what's missing. To choose the id and name yourself,
import it by hand. A save is raw; importing turns it into a layout the build can
use:

```
python3 build/layouts.py import 2 corner_pass "Corner pass"
```

- `2` is the plot number; `corner_pass` is the layout's id, used in
  `world.json`; `"Corner pass"` is its name.
- It writes `content/layouts/corner_pass/`: `room.prefab.json`, the room, and
  `layout.json`, its name and any zones you drew.
- It lists the slots it found. Check the list: a room with no stove slot, for
  instance, builds with a warning.
- It takes the newest save, even one made since the last deploy.
- Importing again replaces the layout. Import the border (plot 0) and HQ
  (plot 1) the same way; the border is recognised by its plot number.

**After any later `/kk save`, just deploy.** `python3 deploy.py` first imports
again every layout whose plot has a newer save (each layout remembers its plot in
`layout.json`), then builds and installs. `python3 build/layouts.py reimport` does
only the import step, if you want it on its own.

## Putting a room in the game

Every restaurant layout not yet in `content/world/world.json` is **added by
itself** when you deploy: on the next free portal, with the kitchen theme and the
standard rules. After that it's yours to edit: rename it, change its theme,
rules or portal. `world.json` says what HQ offers:

```json
{
  "hq": "hq",
  "ground": "void",
  "weather": "Zone1_Sunny",
  "border": "backdrop",
  "restaurants": [
    { "id": "test_kitchen", "name": "Test kitchen", "theme": "kitchen",
      "layout": "test_room", "rules": "standard", "portal": 1 },
    { "id": "corner_pass", "name": "Corner pass", "theme": "kitchen",
      "layout": "corner_pass", "rules": "standard", "portal": 2 }
  ]
}
```

| Key | Meaning |
|---|---|
| `hq` | the layout HQ is built from |
| `ground` | `"void"` (floating in the sky) or `"flat"` (grass to the horizon), for HQ and every restaurant |
| `weather` | a shipped weather held for good, e.g. `Zone1_Sunny`; leave it out for the world's own |
| `border` | the layout pasted around every room; `"none"` for none |
| `restaurants` | one per portal: `id` (any unique name), `name` (shown in game), `theme`, `layout`, `rules` (`standard`, or `practice` for short, easy days) and `portal` (1–8) |

A restaurant can override `ground`, `weather` and `border` for itself.

Then `python3 deploy.py`, `/kk hq`, and step on the portal.

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

## Starting a fresh authoring world

The authoring world keeps everything. To start again from nothing:

1. Stop the server, and delete `universe/worlds/k2_author` in the server folder.
2. Start it, then `/kk author` (a new world) and `/kk grid`.
3. `/kk restore` pastes the layouts named in `RESTORE` (in `build/layouts.py`:
   the backdrop, HQ and the test room) back into their plots.

## Choosing looks

Station textures, tints and trims are in the theme
(`content/themes/<theme>/stations/`). See [content-schema.md](content-schema.md)
for the format, and [stations.md](stations.md) for what the kitchen uses and why.
The texture and model galleries used to choose them are a separate probe, not
part of this project.
