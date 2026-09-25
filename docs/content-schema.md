# Content schema: themes, layouts, rules, world (agreed 2026-09-24)

A **theme** is everything that makes the restaurant *this* restaurant: what the
stations are called and look like, what is served in what, the ingredients, the
recipes and the menu. The systems (board, stove, counter, sink, bin, guests,
shift) stay as they are: generic machinery that runs on whatever a theme hands
them. Swapping the kitchen for witchery should mean writing a new theme
directory and nothing else. If a theme ever needs a code change, the schema is
wrong.

Themes are JSON. Python (`tools/`) reads a theme, checks it, and turns it into
game assets. Nothing in a theme is code.

## Four kinds of content

Surveying everything the generators build (2026-09-24) turned up four separate
questions, each with its own content. Each gets its own folder of small JSON
files:

| Kind | Answers | Today it lives in |
|---|---|---|
| **Theme** | *What* the restaurant is: stations, items, recipes, menu, guests, words | ingredients.py, dishes.py, plates.py, the station words inside each `sys_*.py`, guest_roles.py |
| **Layout** | *Where*: the room, its zones, the starting stations | hand-built prefabs (`Kitchen_Level_0N`), grid.py, named_volumes.py, gen_testroom.py |
| **Rules** | *How a run plays*: day length, arrivals, offers, prices, recipe cards | shift_rules.py, upgrades.py, the tuning table in dishes.py |
| **World** | *How you get there*: HQ, which restaurants are offered, the plot grid | gen_hq.py, grid.py |

A **restaurant** is one of each: a theme, a layout and a rules set, picked in
HQ. The same layout can be played as a kitchen or as witchery, and the same
theme can be played relaxed or hard.

The rest of this doc covers the theme first, then the other three
([Layouts](#layouts), [Rules](#rules), [World](#world)).

## Principles

1. **Small files, one idea each.** Adding a dish means adding one file; adding
   an ingredient means adding one file. No file grows with the size of the
   menu, so an agent (or a person) edits one small file and cannot break an
   unrelated recipe.
2. **An item is defined where it comes from.** A raw ingredient is defined in
   its ingredient file; a chopped piece in the step that chops it; a baked pie
   in the step that bakes it. Everything else refers to it by id.
3. **Ids are local and plain** (`pumpkin`, `pumpkin_chopped`). The generator
   adds the theme's prefix (`Kitchen_…`) when it makes game ids. A theme never
   writes a game id for its own things.
4. **Every reference is checked.** An unknown id, a duplicate id, a combine
   whose result can't sit on a counter: the generator refuses, naming the file
   and the field.
5. **Fixed roles today, room for more.** A station has a *role* (press, heat,
   combine, wash, bin). Today a theme has exactly one station per role, and the
   generator enforces it. Steps already name the station they use, so allowing
   a second press station (board *and* mortar) later is a rule change, not a
   format change.
6. **Tuning has defaults.** Times, patience and prices are set once in
   `theme.json` and overridden only where a dish differs.

## Layout

```
themes/
  _schema/                 JSON Schema, one per file kind (for editors and agents)
  kitchen/
    theme.json             identity, prefix, tuning defaults, guest look
    vessel.json            what food is served in, clean and dirty
    stations/              one file per station
      board.json  stove.json  counter.json  sink.json  bin.json
    looks/                 named looks reused by many items (optional)
      pie.json  petal.json
    ladders/               reusable heat-stage ladders
      bake.json
    fixtures.json          the theme's block for each layout slot (door, queue spot, seat…)
    ingredients/           one file per ingredient: raw item + how it's prepared
      flour.json  pumpkin.json  apple.json  meat.json  mushroom.json
    dishes/                one file per dish: its steps + what goes on the menu
      _shared.json  pumpkin_pie.json  apple_pie.json  meat_pie.json  mushroom_pie.json
```

## Shared shapes

### Look

How anything is drawn. Every look is a shipped model referenced by path.

| Field | Meaning |
|---|---|
| `model` | model path, e.g. `Items/Consumables/Food/Pie.blockymodel` |
| `texture` | texture path |
| `scale` | model scale, default 1 |
| `tint` | hex colour; multiplies the texture, so it can only darken |
| `icon` | inventory icon path |
| `base` | a named look from `looks/`; every other field overrides it |

`{"base": "pie", "texture": "…/Pumpkin.png", "tint": "#a8b0c4"}` is a
pumpkin-textured pie with the unbaked tint.

### Item

| Field | Meaning |
|---|---|
| `id` | local id, unique in the theme |
| `label` | the name players see |
| `look` | a look |
| `bin` | what a bin does with it: `destroy` (default), `refuse`, or `{"leaves": <item>}` (a plated dish leaves the dirty vessel) |

### Step

Every recipe is a chain of steps. There are three kinds, one per role that
transforms things. Plating and washing are not special: plating is a combine
with the vessel, washing is a press at the wash station.

**press**: put one thing on, press N times, get another.

| Field | Meaning |
|---|---|
| `type` | `"press"` |
| `station` | a press or wash station id |
| `input` | item id |
| `output` | an item (defined here) or an item id |
| `presses` | how many presses |

**combine**: two things on a counter make a third.

| Field | Meaning |
|---|---|
| `type` | `"combine"` |
| `station` | a combine station id |
| `inputs` | two item ids, either order works (a list, so more can be allowed later) |
| `output` | an item (defined here) or an item id |

**heat**: goes on, changes by itself over time, taken off at any stage.

| Field | Meaning |
|---|---|
| `type` | `"heat"` |
| `station` | a heat station id |
| `input` | item id; it is also what you get back at the first stage |
| `stages` | in order, each `{ "id", "look", "seconds", "gives" }`. `gives` is an item (defined here) or an item id, handed over if taken off at that stage. The last stage has no `seconds`: it stays. |
| `resume` | stage ids a taken-off item may go back on at, carrying on (default: every stage except the first and last) |

## File kinds

### `theme.json`

```json
{
  "id": "kitchen",
  "name": "Kitchen",
  "prefix": "Kitchen",
  "defaults": {
    "heat_seconds": 8,
    "order_patience": 30,
    "food_patience": 75,
    "eat_seconds": 6,
    "price": 5
  },
  "guest": { "appearance": "Klops" }
}
```

### `vessel.json`

What a dish is served in. Guests leave it dirty; the wash station cleans it.

```json
{
  "clean": { "id": "plate", "label": "Plate",
             "look": { "model": "Blocks/Miscellaneous/Plate.blockymodel",
                       "texture": "Blocks/Miscellaneous/Plate_Texture.png" },
             "bin": "refuse" },
  "dirty": { "id": "plate_dirty", "label": "Dirty plate",
             "look": { "model": "Blocks/Miscellaneous/Plate.blockymodel",
                       "texture": "Blocks/Miscellaneous/Plate_Texture.png",
                       "tint": "#9a8a70" },
             "bin": "refuse" },
  "wash": { "station": "sink", "presses": 4 }
}
```

### `stations/<id>.json`

A station's role, name, look and words. The role decides which words it needs.

```json
{
  "id": "board",
  "role": "press",
  "label": "Chopping board",
  "look": { "sides": "BlockTextures/Wood_Softwood_Planks_Side.png",
            "top": "BlockTextures/Wood_Softwood_Planks_Top.png",
            "sound": "Wood" },
  "leave_on": true,
  "words": {
    "free": "Chopping board - put something raw on it",
    "busy": "Chopping - {n} press{s} to go",
    "done": "Done - press to pick it up"
  }
}
```

Roles today: `press` (board), `heat` (stove), `combine` (counter), `wash`
(sink), `bin` (bin). Each has one station.

### `looks/<id>.json`

A named look that others extend with `base`.

```json
{ "id": "pie", "model": "Items/Consumables/Food/Pie.blockymodel",
  "icon": "Icons/ItemsGenerated/Food_Pie_Pumpkin.png" }
```

### `ingredients/<id>.json`

A raw ingredient, where it comes from, and the steps that prepare it.

```json
{
  "item": { "id": "pumpkin", "label": "Pumpkin",
            "look": { "model": "Resources/Ingredients/Pumpkin.blockymodel",
                      "texture": "Resources/Ingredients/Pumpkin_default.png",
                      "scale": 0.4,
                      "icon": "Icons/ItemsGenerated/Plant_Crop_Pumpkin.png" } },
  "source": "crate",
  "steps": [
    { "type": "press", "station": "board", "input": "pumpkin", "presses": 4,
      "output": { "id": "pumpkin_chopped", "label": "Chopped pumpkin",
                  "look": { "base": "petal",
                            "texture": "Resources/Plants/Petal_Textures/Yellow.png",
                            "icon": "Icons/ItemsGenerated/Plant_Petals_Yellow.png" } } }
  ]
}
```

An ingredient may have several steps. Later, meat is chopped *and* cooked
whole, as two steps in one file.

### `dishes/<id>.json`

A dish's own steps (from prepared ingredients to cooked) and what it serves.

```json
{
  "id": "pumpkin_pie",
  "label": "Pumpkin pie",
  "steps": [
    { "type": "combine", "station": "counter",
      "inputs": ["dough", "pumpkin_chopped"],
      "output": { "id": "pumpkin_pie_unbaked", "label": "Unbaked pumpkin pie",
                  "look": { "base": "pie", "texture": "…/Pie_Textures/Pumpkin.png",
                            "tint": "#a8b0c4" } } },
    { "type": "heat", "station": "stove", "ladder": "bake",
      "input": "pumpkin_pie_unbaked",
      "look": { "base": "pie", "texture": "…/Pie_Textures/Pumpkin.png" },
      "stage_looks": { "raw": { "tint": "#a8b0c4" } } }
  ],
  "serve": [
    { "item": "pumpkin_pie_cooked" },
    { "item": "pumpkin_pie_well", "price": 6 }
  ]
}
```

`…` marks repetition left out of this doc, not a real value.

**Plating is built in (decided 2026-09-24).** For each `serve` entry the build
makes:
- the plated item `<item>_plated`, labelled "<item>, plated", drawn as the
  food itself, **Legendary** so it stands out in the hotbar, and leaving a
  dirty plate if binned;
- the step that plates it: clean plate + food at the combine station (or
  `plate_at`);
- the menu entry, labelled as the food, with the theme's defaults for price and
  patience unless the entry sets its own (`price`, `order_patience`,
  `food_patience`, `eat_seconds`).

No recipe writes its own plating, so none can forget it or get it wrong. What a
guest can order is exactly the `serve` entries of every dish.

**Burnt** is one item shared by every dish. It is defined once, in
`dishes/_shared.json`, and every heat ladder's last stage refers to it. The
long heat step in the example above is the full form; a dish normally uses a
ladder instead (see "Decided" below).

### Crates (`stations/crate.json`, decided 2026-09-24)

A station file with `"per_ingredient": true` is a **template**. The build makes
one crate per ingredient whose `source` names it (`crate_pumpkin`, `crate_apple`…),
filling `{ingredient}` in its label and words. It also adds a *source* step
(nothing in, the ingredient out), so kits, reports and checks all see where raw
ingredients come from.

A crate shows its ingredient on top. Take it, and the next one appears after
`restock_seconds` (a theme default: 3). Restocking is growth, like the stove:
the top grows from a tiny ingredient to a full one. A new ingredient brings its
own crate with no extra work.

## Checks the generator makes

- Every id is unique across the whole theme.
- Every reference names an item defined somewhere in the theme.
- Every step's `station` exists and has the right role for the step.
- Exactly one station per role (today's rule).
- Every item that can reach a counter has a look, and every combine's inputs
  and output can sit on a counter.
- Every `serve` entry names an item that exists (plating itself is built in,
  so guests are only ever handed something on a plate).
- Every look path exists in the shipped assets.

Every check names the file, the field and the id it failed on.

## Witchery, as a check on the format

Nothing below needs a new field:

| Kitchen | Witchery |
|---|---|
| board (press) | mortar and pestle: *grind* |
| stove (heat) | cauldron: *brew*; stages unbrewed → brewed → potent → spoiled |
| counter (combine) | workbench |
| sink (wash) | rinse tub |
| bin | ash pit |
| plate (vessel) | bottle (shipped potion models) |
| flour → dough | water flask (straight from a crate) |
| pumpkin → chopped | mandrake → powder (a petal, ground) |
| dough + chopped → unbaked pie | flask + powder → unbrewed potion |
| cooked / well done pies | brewed / potent potions |

## Layouts

A layout is a room, built by hand in the authoring world and saved as a prefab
(the existing process: `/kitchen saveprefabs`, then `tools/prefabs_back.py`).
The creator decides *where* things are; the build decides what they *do*.

**Today's problem: layouts name one theme's blocks.** A saved level contains
`Kitchen_Stove`, `Kitchen_Prep` and so on, so it only works with the kitchen.

**The fix: slots.** A layout is built with neutral *slot* blocks, one per role
(a press slot, a heat slot, a combine slot, a seat, a queue spot…). When a
restaurant is built, each slot is swapped for the theme's station of that role.
The swap happens in the same step that already re-anchors saved prefabs, so no
game-side work is needed. The walls and floor can be swapped too, if the theme
has a palette (below).

```
layouts/
  corner_pass/
    layout.json            name, notes, which slots and zones it has
    corner_pass.prefab.json  the room as built (slots, not stations)
```

```json
{
  "id": "corner_pass",
  "name": "Corner pass",
  "notes": "pass opening hard left: a long walk to the far end",
  "zones": ["door", "kitchen", "dining", "queue"],
  "seats": 4
}
```

- **Zones** are the named volumes the creator draws (door, kitchen, dining,
  queue). The build attaches each zone's behaviour, as named_volumes.py does
  today. Zones belong to the systems, not the theme, so they are the same for
  every theme.
- **Slots** use the station roles from the theme schema, plus the fixtures the
  systems own: seat, queue spot, pool, sign, offer pad. The check is that every
  role the rules need has at least one slot.

**Decided 2026-09-25: no doors.** A closed door stops NPC pathfinding, so no
layout has one, hand-built or not. Guests leave by walking off (towards the
pool) and vanishing. There is no door slot, and the door zone is not needed.

**Decided 2026-09-24: slots.** Everything a theme might dress differently is a
slot, not only stations: the door, queue spots, the pool, seats and tables, the
sign, offer pads. A theme names the block for each (`fixtures.json`), so a
witch's hut can use any door and any block to mark the queue. The layout
creator builds with the plain slot blocks and lives with the ugly room until
it's dressed.

A theme may add a **palette** (`palette.json`) that swaps building materials
when its restaurants are built: `{"Wood_Softwood_Planks": "Wood_Dark_Planks"}`.
Without one, the room keeps what the creator built.

## Rules

How a run plays, independent of what it looks like. Built 2026-09-25.

```
rules/
  standard/
    rules.json       day length, stages of a run, arrivals per stage, queue patience
    offers.json      what the pads can offer (stations and upgrade kits), prices, weights,
                     and from which day each pad offers
    cards.json       recipe cards: every N days, how many to choose from
```

```json
{ "id": "standard", "name": "Standard", "day_seconds": 90,
  "stages": [ { "id": "early", "from": 1, "to": 3 }, { "id": "mid", "from": 4, "to": 6 },
              { "id": "late", "from": 7, "to": 999 } ],
  "arrival_every": { "early": 15, "mid": 11, "late": 8 },
  "queue_patience": 60, "queue_patience_boost": 10, "guest_patience_scale": 1.0 }
```

- Rules name **stations and kits by id**, never blocks, so the same rules
  work for any theme. `offers.json` says "stove, price 14, weights 1/5/10";
  the theme says what a stove is.
- **Upgrade kits** are offered as `{"kit": "stove_fast", ...}`. The kit is made
  from the theme's variant station file, which has `upgrade_of`, `glow` and
  `kit`.
- The theme's `defaults` (times, patience, prices) stay in the theme, because
  they belong to the dishes. The rules can scale them: `guest_patience_scale`
  multiplies every guest's patience (practice: 2.5).

## World

```
world/
  world.json         the plot grid, and the restaurants HQ offers
```

```json
{
  "grid": { "layout_chunks": 2, "pitch_chunks": 6 },
  "restaurants": [
    { "id": "kitchen_corner", "theme": "kitchen", "layout": "corner_pass", "rules": "standard" },
    { "id": "witch_corner",   "theme": "witchery", "layout": "corner_pass", "rules": "standard" }
  ]
}
```

Each restaurant becomes a portal key in HQ (gen_hq.py's model: one key per
restaurant, all into the same instance, each arriving at its own plot).

## Not content

These stay in code, because they are how the machinery works, not what a
restaurant is:

- the systems (`sys_*.py`) and their shared helpers (fx, pressladder, carry,
  signals, packio)
- the clock (clock.py: how fast game time runs for growth)
- debug chat and log lines
- spike and probe harnesses

**To retire at integration, not convert:** the old kitchen generators (gen_menu,
gen_volumes, gen_stations, gen_seat, gen_queue, gen_crates, gen_testroom,
gen_author). The new systems replace them. Their saved levels need rebuilding
with slots.

## Deliveries, recipe cards and upgrade kits (decided 2026-09-24)

All three arrive on the **offer pads** (a layout slot) between days:

| Day | The pads show |
|---|---|
| Day 0 | a starter card for each starter dish. Choose one: it's on the menu, its crates delivered |
| Card days (every 3rd, `rules/cards.json`) | a pair of recipe cards, **instead of** the random offer roll. Choosing one puts the dish on the menu from the next day; any crates it needs that the restaurant doesn't own arrive on the pads the next morning, free |
| Other days | the random offers (`rules/offers.json`): stations and upgrade kits |

- A dish says `"unlock": "start"` (a STARTER: offered as a starter card when the
  run begins, and later as a recipe card if not chosen) or `"unlock": "card"` (only
  ever a recipe card). The run begins with every starter's card on the pads; the
  chosen one goes on the menu and its crates are delivered. What it needs is
  worked out from its steps (the report already walks every dish back to its
  crates).
- The run remembers which crates it owns (tags on the run's volume), so a crate
  is never delivered twice. Crates, like plates, can't be binned.
- **Upgrade kits:** bought on a pad, then F on a matching station while holding
  the kit swaps the station for its upgraded variant. The variant is a theme
  station file with `upgrade_of` (a fast crate or a fast stove glows, and a
  light growth modifier speeds its growth, as `probe_heat` proved; a safety
  stove stops the well-done stage burning). The rules decide when kits are
  offered and their price.

## Room to grow

These fit the format later without changing what is already written:

- **More stations per role:** lift the one-per-role rule; steps already name
  their station.
- **Combines of three or more:** `inputs` is already a list.
- **Recipe cards / unlocks:** an `unlock` field on menu entries (`start`, or a
  card id).
- **Upgraded stations:** a station file with `upgrade_of` and its modifiers
  (fast / safety stove).
- **Crates as stations:** `source` on an ingredient already says where it comes
  from.
- **Theme-specific guests:** `guest` in `theme.json` grows (appearance, names).

## Words

Roles and slots have **generic names** in the schema and in the systems (press,
heat, combine, wash, bin; seat, queue spot, door). Only the theme gives them
player-facing names ("Chopping board", "Cauldron").

**Every player-facing string goes through the pack's lang files**, as today
(`packio.write_lang`). A theme's labels and words are written into the lang
file under keys the generator makes, so the wording can be changed later, and
translated, without touching the schema. The generic role names themselves
are also open to renaming later: they are internal ids, and players never see
them.

## Decided 2026-09-24

1. **Shared items** (burnt, and anything else every dish refers to) live in
   `dishes/_shared.json`. `theme.json` stays settings only.
2. **Heat ladders are reusable.** A `ladders/<id>.json` defines a heat
   station's stages once; each dish's heat step names the ladder and fills in
   only what differs (see below).
3. **Theme and rules stay separate.** Pacing, offers and recipe cards are rules,
   so a difficulty mode works with every theme.

### `ladders/<id>.json`

```json
{
  "id": "bake",
  "stages": [
    { "id": "raw",    "word": "unbaked",   "gives": "input" },
    { "id": "cooked", "word": "cooked",    "gives": "new",   "seconds": 8 },
    { "id": "well",   "word": "well done", "gives": "new",   "seconds": 6, "tint": "#6a4020" },
    { "id": "burnt",  "word": "burnt",     "gives": "burnt", "tint": "#2e2824" }
  ]
}
```

- `gives: "input"`: taken off at this stage, you get back what went on.
- `gives: "new"`: the stage makes a new item for this dish, id
  `<dish>_<stage>` and label "<dish label> (<word>)". It is defined here once,
  for every dish that uses the ladder.
- `gives: <item id>`: a shared item (burnt).
- `seconds` is how long the stage lasts before the next; the first stage's
  time comes from `theme.json` defaults unless set.

A dish's heat step then shrinks to:

```json
{ "type": "heat", "station": "stove", "ladder": "bake",
  "input": "pumpkin_pie_unbaked",
  "look": { "base": "pie", "texture": "…/Pie_Textures/Pumpkin.png" },
  "stage_looks": { "raw": { "tint": "#a8b0c4" } } }
```

`look` is the dish's look at every stage, with the ladder's tints on top.
`stage_looks` overrides a single stage (the pie's unbaked colour). The stage
items (`pumpkin_pie_cooked`, `pumpkin_pie_well`) exist by name for plating and
the menu to refer to.
