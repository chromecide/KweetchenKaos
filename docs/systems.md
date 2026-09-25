# How it works: the systems and how they fit together

This is for anyone changing how the game behaves, not just its content. Each
part below says what the player sees, then how it's done. The same thing is
written, in more detail, at the top of every file in `build/`: that's the
reference, and this is the map.

## The big picture

Kweetchen Kaos has **no plugin code**. Everything it does is built from what the
game already understands as data:

- **Items and blocks**: every ingredient, dish, plate and station, and every
  state of a station (a stove with a pie on it, cooking, is a block of its own).
- **Trigger volumes**: invisible boxes with rules. Each rule is conditions plus
  effects, run on an event: a player pressing a block (`BLOCK_USED`), something
  entering or leaving (`ENTER`, `EXIT`), a clock (`TICK`), a message
  (`SIGNAL_RECEIVED`). Effects swap blocks, give items, set **tags** (named
  values a volume keeps, which is how state such as the purse is stored), send
  signals, spawn NPCs, show titles.
- **NPC roles**: the guests. A role is a list of instructions: "if this sensor
  matches, move like this and do these actions". The first match wins.
- **Block growth**: the engine's crop growth, reused as a timer. A pie ageing on
  a stove and a crate restocking are both "growing" into their next block.

The Python in `build/` writes all of that from the content in `content/`:

```
content/ --content.py--> the model --check.py--> the systems --pack.py--> pack/
 (JSON)      reads and       (one resolved      checks it     write blocks,     (the mod)
             resolves        description of     as a whole    items, volumes,
             every file      the theme+rules)                 roles
```

`build.py` runs the whole chain and prints a report. The report is the quickest
way to see what a theme really makes.

## Systems, and the rules that keep them apart

A **system** is the machinery behind one job: a kind of station (the stove, the
counter), or a part of the restaurant (the queue, the shift). Each lives in
`build/systems/`.

Every **station** system has the same shape (`build/systems/__init__.py`):

| Part | What it is |
|---|---|
| `ROLES` | the station roles it runs, e.g. `("press", "wash")` |
| `build(model, station_id, debug)` | writes the station's blocks and its volume's rules; returns the rules' name |
| `free_block(model, station_id)` | the block you place, buy or carry |
| `layout(model, station_id)` | what a layout puts in the station's slot, bottom up (a crate comes with its ingredient on top) |
| `NEEDS_CLOCK`, `TAGS` | optional: the world must run its clock (anything timed); tags its volume must start with |

The theme says which role a station has, so a theme can call its stove a
cauldron, and the heat system runs it all the same.

**The rules**, which keep any one system changeable without breaking the others:

1. A system reads **only the model**. It never imports another system, and
   never assumes what another makes. The counter learns what combines from the
   theme's combine steps, not from the stove.
2. Systems share only **infrastructure** (below). Anything two systems both
   need goes there, or into the model.
3. A system's game ids all start with its station's id, so no two systems ever
   make the same block.
4. Everything notable is written to the **server log** (`volumes.report`).
   Chat is for players.
5. The top of each system's file says, in plain words, what the player does and
   what happens, before any code.
6. A station's free block can be **carried**; anything holding food or a plate
   can't.

Systems **talk only through signals and tags** on named channels
(`build/signals.py`), never by calling each other. A sender and a listener
share an address and the words on it, and nothing else.

## Kitchen systems

### Press: the chopping board and the sink (`press.py`)

Put something on, press it N times, get something else. Raw pumpkin becomes
chopped pumpkin, and a dirty plate becomes a clean one. The theme's press steps
say what goes on, what comes off and how many presses.

The station's **own block carries the count**. It's a ladder of blocks
(free → presses left: 4, 3, 2, 1 → done), and what sits on top is only a
picture. So the blocks are shared by everything the board takes: N ladder
blocks plus one picture per item, not items × presses. The board leaves its
result on top to pick up; the sink hands it straight over.

### Counter: holding and combining (`counter.py`)

A counter holds any one thing. Pressing it while holding something that
combines with what's on it makes the combination, in either order. That's how
a pie is assembled (dough plus chopped filling) **and** how food is plated
(clean plate plus cooked pie). Plating is built into every served dish
(`content-schema.md`), so the counter knows nothing about plates.

"Pick up" only matches when what you're holding doesn't combine with what's on
the counter. So a press can never both combine and pick up, and no lock is
needed.

### Heat: the stove (`heat.py`)

Put on something it cooks, and it goes through the theme's **ladder** of stages
by itself (unbaked → cooked → well done → burnt), each its own look. Take it off
at any stage. A part-cooked dish can go back on and carry on.

Every stage is a block that **grows** into the next, after the stage's time. The
world's clock (`clock.py`) runs at a known 2 game seconds per real second, so a
content time of 8 seconds means 8 seconds. Nothing ticks and nothing drifts.

**Upgrades** are the same stove with a different station block that **glows**
(`glow.py`): blue for the fast stove, green for the safety stove. Stage blocks
carry growth modifiers that read the light on them. Blue makes every stage grow
twice as fast. Green all but stops the well-done stage, so food on a safety stove
never burns. Holding a kit and pressing a free, plain stove swaps it for the
upgrade.

### Crate: raw ingredients (`crate.py`)

One crate per ingredient that comes from a crate. Its ingredient sits on top.
Take it, and a tiny one grows back to full size (restocking is growth too). A
fast crate glows, and its restocking grows twice as fast. In a run, crates only
give **while the restaurant is open**: they read the shift's `open` tag, or
players could cook the next day's food in advance.

### Bin (`bin.py`)

Food goes. A plated dish leaves its dirty plate on the bin to pick up. Plates
are never binned, so a restaurant can't run out by accident. Each item's `bin`
setting in the theme says which applies.

### Rack: clean plates (`rack.py`)

Take a plate, put one back. The **count is the block**: one rack block per
count, 0 to 12, so every rack keeps its own count and says it when you look at
it. A plate on top shows it has any. The same block both gives and takes, and
one press was doing both. So the first rule that fires claims a `busy` tag and
the others require it clear: it's the only lock in the kitchen.

## Front of house

### Queue (`queue.py`)

Guests appear at the **pool**, then move up the **spots** one at a time
(pool → 4 → 3 → 2 → 1), never skipping. At the front, with a free chair to go
to, the front spot is **held** for that guest until it sits, so the next guest
can't chase the same chair.

- **Each spot has its own one-block volume.** The first guest to enter claims it
  with a tag; anyone else arriving is bumped back. Guests read the block under
  their own feet, never a distance.
- **One patience clock for the whole queue**, on a volume over where guests
  wait. It drains while guests wait, with amber and red warnings, and sends
  "the queue gave up" to the shift when it runs out.

### Seating (`seating.py`)

Place a chair and its **own table** appears in front of it, whichever way it
faces. Break the chair and its table goes too.

- **Chair states:** free, taken while a guest sits, and dirty once the guest
  leaves a plate. Only free chairs are in the set guests look for, so absence
  is the lock.
- **Sitting:** a guest is moved onto the chair, plays the **Sit** pose, and for
  a moment turns to face the table beside it.
- **Plates:** when the guest gets up, seating places the dirty plate on *that*
  chair's table, because a volume can read a block's rotation and an NPC
  can't. Taking the plate frees the chair.
- **The chair's hitbox is the seat alone**: guests are placed on a block's
  highest hitbox, and the backrest stood them a block up.

### Guest (`guest.py`)

What a seated guest does. The player presses F to take its order, and the dish
shows on its name tag. Each phase has its own **patience** clock, pulsing amber
at half and red at three quarters.

- **The right dish:** it eats, gets up fed (leaving a dirty plate) and reports
  *served* and what it paid.
- **The wrong dish:** it walks out unpaid (*turned away*). That costs money and a
  table, never the run.
- **Patience runs out:** it leaves *angry*, and that ends the run.

### The guest, composed (`guests.py`)

One NPC role per menu entry, because the dish is fixed when the guest spawns.
Each role is **wired together from three systems' parts**: the queue's (arrive,
move up, hold the front), seating's (walk to a chair, sit, get up), and the
guest system's (order, wait, eat). `guests.py` is the one place that knows all
three exist, and the joins are all it decides: a free chair is where to go,
sitting releases the queue's front, and getting up is fed or unfed.

### Serving (`serving.py`)

How a plated dish reaches a guest. The dish's F action offers its "context" to
the NPC in front of you, the way shears work on sheep. The guest senses it and
decides. If there's no guest in front of you, F falls through to the block you're
looking at, so a dish in your hand never stops a counter working.

## The run

### Shift (`shift.py`)

The restaurant's day, and the only volume that holds the run's state as tags:
day, purse, what's on the menu, guests expected, still to come, served.

- **The run starts:** starter recipe cards go on the pads.
- **The sign:** pressing it opens the day. The clock starts, guests start
  arriving, and the **service lock** comes on: stations can't be moved or built
  over during service.
- **Arrivals:** the day's expected guests (`day_1` + `per_day` + `per_card`)
  arrive evenly spread over it. Each wants a fair random pick from the dishes on
  the menu.
- **Closing time:** no more guests. The day ends when the last one has left.
  Every few days recipe cards come instead of offers.
- **Payments:** it hears *served*, *paid*, *turned away*, *angry* and *queue
  gave up*, and adds to the purse or ends the run.
- **Losing:** out of business. In a run from HQ, everyone is sent back to HQ.
- **Titles:** day start, day over and out of business are shown to **every
  player** in the restaurant. A title only reaches the player whose event it is,
  but the volume's clock runs once per player inside. So an event starts a short
  announcement, and each player's clock shows it to them once.

Volume tags can't do arithmetic, so anything worked out is one rule per case. The
expected guests and their pacing are a rule for each day and number of cards.

### Pads (`pads.py`) and offers (`offers.py`)

Four pads out front. Between days they show **offers** (stations and upgrade
kits, weighted by the stage of the run, paid from the purse), **deliveries**
(crates, free) and **recipe cards** (choose one, and its dish goes on the menu).
The pads know no shift: they read the purse through `signals.shift_reads` and
hear place / clear / deliver / card on their own channel. `offers.py` holds the
catalogue, because both the pads and the shift need it and neither may import
the other.

## Putting a restaurant together (`restaurant.py`)

A **restaurant** is a layout's room dressed in a theme. It's built as **one
prefab that carries everything it needs**:

- Every **slot** is swapped for the theme's block: stations, chairs with tables,
  queue spots, the pool, pads, the sign.
- **Every system's volume goes into the prefab** as an entity, positioned
  relative to the room: the stations', the queue's and its patience area, the
  seating's, the shift's and its service lock, the pads'.

Pasted anywhere, the room works. Two things make that possible:

- **A pasted volume's rules are inline.** A volume that names a rules file only
  finds it when the world loads, so one pasted later would do nothing.
- **Signals reach 64 blocks** from the sending volume's position. So every
  volume is placed at the room's centre, and the whole room is in reach.

## The world (`world.py`)

- **HQ** is a layout built by hand, with an arrival slot and portal slots. It's
  one shared world, never torn down.
- **A portal** is a block that sends you into a new world for its restaurant.
  The block remembers the world it opened, so everyone who steps on it while
  the run exists joins the same run. It also sets each player's way back: HQ's
  arrival spot.
- **A restaurant's world** is empty sky (or flat grass: `ground` in
  `world.json`), with its weather held. The first player to arrive triggers a
  volume that pastes the **border** and then the room. The world is removed
  once it's been empty a little while.
- **Titles:** HQ shows every arriving player "Welcome to Kweetchen Kaos".

## Infrastructure (shared by every system)

| File | What it gives the systems |
|---|---|
| `settings.py` | paths (`local.cfg`), the `K2` namespace, and the one rule that turns a content id into a game id |
| `content.py` | reads a theme and rules into the model |
| `check.py` | checks the model as a whole: references, roles, plating, that every shipped path exists |
| `pack.py` | writes the pack from nothing every build, plus the language file |
| `items.py` | every item: its look, one in hand, no eating, no placing, its F and click actions |
| `blocks.py` | block shapes: stations (textures, trim, turn), things sitting on stations |
| `volumes.py` | the rule pieces (at, holding, cell, place, give, say, title), server-log reporting, volume boxes |
| `signals.py` | the channels: shift, pool (arrive), reset, pads; reading and changing the shift's tags |
| `npc.py` | NPC pieces: branches, flags, timers, block sets, roles (with an optional decision trace) |
| `carry.py` | picking stations up and putting them down, refused during service |
| `glow.py` | the glow of upgraded stations and the growth modifiers that listen for it |
| `clock.py` | the world clock that growth runs on |
| `serving.py` | the dish-to-guest handshake |
| `offers.py` | what the pads can carry |
| `layouts.py` | slot blocks, the authoring world and its commands, importing saves |
| `spike.py`, `spike_front.py` | the test worlds |
| `build.py` | runs it all |

## A day, end to end

1. The player **presses the sign**. The shift sets `open`, sets how many guests
   to expect, starts the clock, turns on the service lock, clears the pads, and
   starts the day-start title.
2. On the day's beat the shift picks a dish and **signals the pool**: "arrive:
   the guest who wants pumpkin pie". The pool's volume spawns that guest.
3. The guest **queues** (queue system), then walks to a **free chair** and sits
   (seating). Its chair turns taken, and the queue's front is released.
4. The player **takes its order** (F). The guest's food patience starts.
5. The player cooks: crate → board → counter (assemble) → stove → counter
   (plate, with a plate from the rack). Each station's volume handles its own
   presses.
6. The player **serves** it (F). The guest eats, gets up, and **signals the
   shift**: served, paid pumpkin pie. The shift adds the price to the purse. The
   guest also signals seating, which puts a dirty plate on its table.
7. The plate goes to the **sink**, then back to the **rack**.
8. At **closing time** no more guests are sent. When none are left, the day ends:
   the day-over title, then offers or recipe cards on the pads.
9. Any **angry** guest, or the queue giving up, signals the shift, which ends the
   run and, in a run from HQ, sends everyone home.

## Testing and debugging

- **`./deploy.sh <spike>`** builds a test world instead of the game, then
  `/kk spike` and `/kk kit` in game. Spikes (`build/spike.py`): `board`,
  `stove`, `rack`, `counter`, `kitchen` (every station), `service` (front of
  house), `run` (the whole run), `room:<layout>` (one restaurant). Add a
  rules name, e.g. `./deploy.sh run practice`, for short days.
- **The deploy's rejection check** lists any asset the game refused, any rule it
  dropped, and any block a room names that doesn't exist.
- **The server log** has a line for every milestone: each station's presses,
  arrivals, payments and seating, each tagged with its system. The game allows
  about one such line a second, so very frequent events are left out.
- **A guest's decision trace:** set `TRACE = True` in `build/guests.py`, deploy,
  play, then search the server log. Every instruction every guest tries is
  logged, as matched or failed, with the rule's tag. It's very noisy: switch it
  off afterwards.
- **Play in adventure mode.** Guests ignore creative players.

## Adding things

- **A dish, an ingredient, a look, a price:** content only
  ([content-schema.md](content-schema.md)); no code.
- **A new room:** authoring only ([authoring.md](authoring.md)).
- **A new theme:** a new folder under `content/themes/`, the same shape as
  `kitchen/`. Its stations need roles the systems know.
- **A new kind of station:** a new system in `build/systems/` with the contract
  above, added to `_BY_ROLE` in `systems/__init__.py`, its role added to `ROLES`
  in `check.py`, and a slot for its role in `layouts.SLOTS`.
