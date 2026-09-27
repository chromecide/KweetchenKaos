# Content schema: themes, layouts, rules, world

A **theme** is everything that makes the restaurant *this* restaurant: what the
stations are called and look like, what is served in what, the ingredients, the
recipes and the menu. The systems (board, stove, counter, sink, bin, guests,
shift) stay as they are: generic machinery that runs on whatever a theme hands
them. Swapping the kitchen for witchery should mean writing a new theme
directory and nothing else. If a theme ever needs a code change, the schema is
wrong.

Content is JSON, under `content/`. The build (`build/`) reads it, checks it, and
turns it into game assets. Nothing in content is code.

## Four kinds of content

Four separate questions, each with its own folder of small JSON files:

| Kind | Answers | Folder |
|---|---|---|
| **Theme** | *What* the restaurant is: stations, items, recipes, menu, guests, words | `content/themes/<theme>/` |
| **Layout** | *Where*: the room, its slots and zones | `content/layouts/<layout>/` (built by hand: [authoring.md](authoring.md)) |
| **Rules** | *How a run plays*: day length, guests, offers, prices, recipe cards | `content/rules/<rules>/` |
| **World** | *How you get there*: HQ, and which restaurants its portals lead to | `content/world/world.json` |

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
   combine, wash, bin, rack, crate). Today a theme has exactly one station per role, and the
   generator enforces it. Steps already name the station they use, so allowing
   a second press station (board *and* mortar) later is a rule change, not a
   format change.
6. **Tuning has defaults.** Times, patience and prices are set once in
   `theme.json` and overridden only where a dish differs.

## Layout

```
themes/
  kitchen/
    theme.json             identity, prefix, tuning defaults, guest look
    vessel.json            what food is served in, clean and dirty
    stations/              one file per station (upgrades are stations too)
      board.json  stove.json  stove_fast.json  stove_safe.json  counter.json
      sink.json  bin.json  rack.json  crate.json  crate_fast.json
    looks/                 named looks reused by many items (optional)
      pie.json  petal.json
    ladders/               reusable heat-stage ladders
      bake.json
    fixtures.json          the theme's block for each layout slot (chair, queue spot, pad, sign…)
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
  "look": { "sides": "BlockTextures/Metal_Iron.png",
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
(sink), `bin` (bin), `rack` (plate rack), `call` (booking desk), `tool` (mop
stand: `holds` the item it keeps, `on_top` how it shows). Each has one station.

An **upgraded station** (a dishwasher, a fast stove) is its own station file with
`"upgrade_of"` naming the station it improves. It's bought ready-made from the pads;
there are no upgrade kits.

A station may cause a hazard: `"hazard": {"kind": "spill", "chance": 0.25}` is
the chance each press (the sink: each scrub; the board: each chop; the stove: burnt
food taken off; a dishwasher: a clean plate taken out) drops one round it. The
kinds are the fixtures looks marked `"hazard": true` (mess, spill, scraps, scorch);
a look may set `"speeds"` (how much each size slows you) and `"spreads"` (how many
hops a large one spreads). See `docs/systems.md`, Hazards.

A `look` may also say how the station looks while in use: `busy_sides` and
`busy_top` (the stove's top turns copper while something cooks), and `tint` /
`busy_tint` (a colour over the whole block). `top_tint` (a colour) tints the top face only, and
`trim` (a colour) puts a band round the top of the
sides -- one plain white band image the pack ships, coloured by the game's top tint, so the
station's top takes that colour too. Pick textures in the texture
gallery probe (`~/hytale-mods/texture-gallery`, `/tex`): a cube's hint is its path.

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
- A dish that serves one stage of its cooking serves every stage the stove makes
  for it: cooked AND well done (burnt is never served). Leave one out and the
  build stops, naming the missing item.
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

A layout is a room, built by hand in the authoring world with neutral **slot**
blocks, then saved and imported. The whole process is in
[authoring.md](authoring.md). The creator decides *where* things are, and the
build decides what they *are* and *do*: each slot becomes the theme's block for
it.

```
layouts/
  corner_pass/
    layout.json        id, name, the plot it came from, zones drawn
    room.prefab.json   the room as built: floor at y 0, the ground under it below, slots not stations
  _saves/              raw saves (/kk save), kept by deploy.py; import turns one into a layout
```

```json
{ "id": "corner_pass", "name": "Corner pass", "from_plot": 2, "zones": {} }
```

- **Slots** are the station roles (`station_press`, `station_heat`,
  `station_combine`, `station_wash`, `station_bin`, `station_rack`) plus the
  fixtures the systems own: `chair` (with its table in front), `queue_1`–`queue_4`,
  `pool`, `pad_1`–`pad_4`, `sign`, and `arrival`. HQ adds `portal_1`–`portal_4`.
  The build warns about any role or pad the room is missing.
- **Zones** are trigger volumes the creator draws and names. Today there is one:
  `queue`, the area where guests wait. Without it, the area is worked out around
  the spots and the pool.
- **A border** (`"kind": "border"`) is a layout from the border plot: a 64 × 64
  backdrop with a 32 × 32 hole, pasted around rooms (`world.json` `border`).

**Decided: no doors.** A closed door stops NPC pathfinding, so no layout has one.
Guests leave by walking off towards the pool and vanishing.

**Decided: everything a theme might dress is a slot**, not only stations. A
theme names the block for each fixture in `fixtures.json`.

A theme may later add a **palette** (`palette.json`) that swaps building
materials when its restaurants are built: `{"Wood_Softwood_Planks": "Wood_Dark_Planks"}`.
Without one, the room keeps what the creator built. (Not built yet.)

## Rules

How a run plays, independent of what it looks like. Built 2026-09-25.

```
rules/
  standard/
    rules.json       day length, stages of a run, expected guests, queue patience
    offers.json      what the pads can offer (stations, plain or upgraded, and chairs) as
                     blueprints, prices, weights,
                     and from which day each pad offers
    cards.json       card days: every N days (recipe and customer cards alike)
    customers.json   the customer card deck (docs/customer-cards.md)
```

```json
{ "id": "standard", "name": "Standard", "day_seconds": 100,
  "day_growth": { "every_days": 3, "seconds": 25 },
  "stages": [ { "id": "early", "from": 1, "to": 3 }, { "id": "mid", "from": 4, "to": 6 },
              { "id": "late", "from": 7, "to": 999 } ],
  "guests": { "day_1": 4, "per_day": 1, "per_card": 2 },
  "queue_patience": 120, "queue_patience_boost": 10, "guest_patience_scale": 1.0,
  "hazards": { "guest_mess_chance": 0.05 } }
```

- **Hazards:** `guest_mess_chance` is the chance (0-1) any guest leaves a mess
  round its chair as it gets up.
- **Milestones** (`"milestones": {"days": [10, 15, ...], "big": 15, "best_from": 5}`): the
  days whose end gets a title of its own (`big`: the big one), and the brackets a
  player's best is kept in (`best_from` before the first).
- **Franchise** (`"franchise": {"start_coins": 20}`): what a start coins token adds to the
  purse. What can be banked is worked out: everything in `offers.json`, start coins, and
  a recipe token per dish.
- **Overtime** (`"overtime": {"guests": 6, "patience": 4, "mess": 4, "mess_chance":
  0.05}`): once every card is taken, each card day squeezes instead, in turn -- one
  more guest a day, every guest a level more hurried (15% less patience a level),
  another `mess_chance` a guest leaves a mess -- each up to its number of levels.

- **Expected guests** each day are `day_1`, plus `per_day` for every day
  after the first, plus what each dish on the menu brings. A dish's `guests`
  (in its dish file) is how many it brings when it's added as a card; without
  one it's `per_card`. The run's first dish shifts day 1 by its difference from
  `per_card`, so a quick salad start brings a guest more and a slow pie start
  one fewer (PlateUp's +15% / -15%). They arrive evenly spread over the day, the first as
  it opens. The shift says how many to expect when it opens, how many are
  still to come and how many were served when the sign is pressed, and the
  served count at the end of the day. Counts are worked out for days 1-30;
  from day 30 on they stop growing.
- Rules name **stations by id**, never blocks, so the same rules
  work for any theme. `offers.json` says "stove, price 14, weights 1/5/10";
  the theme says what a stove is.
- An offer is a **station** (`{"station": "dishwasher", ...}` -- plain, or one already
  upgraded, ready-made) or a **fixture** (`{"fixture": "chair", ...}`: a chair brings
  its own table when it's put down). Every offer shows on its pad as a **blueprint**
  (the recipe card's model, in blue); pressing it pays, and hands over the real
  station to put down. There are no upgrade kits (removed 2026-09-26).
- The theme's `defaults` (times, patience, prices) stay in the theme, because
  they belong to the dishes. The rules can scale them: `guest_patience_scale`
  multiplies every guest's patience (practice: 2.5).

## World

```
world/
  world.json         HQ, the ground and weather, the border, and the restaurants HQ's portals lead to
```

```json
{
  "hq": "hq",
  "ground": "void",
  "weather": "Zone1_Sunny",
  "border": "backdrop",
  "restaurants": [
    { "id": "test_kitchen", "name": "Test kitchen", "theme": "kitchen",
      "layout": "test_room", "rules": "standard", "portal": 1 }
  ]
}
```

- `hq`: the layout HQ is built from (its arrival and portal slots matter).
- `ground`: `"void"` (the room floats in the sky) or `"flat"` (grass).
- `weather`: a shipped weather id held for good; leave it out for none.
- `border`: a border layout pasted around every room and HQ; `"none"` for none.
- `restaurants`: each is a theme + a layout + a rules set, hung on an HQ portal
  by number. A restaurant may set its own `ground`, `weather` and `border`.

## Not content

These stay in code, because they are how the machinery works, not what a
restaurant is:

- the systems (`build/systems/`) and their shared infrastructure
  (see [systems.md](systems.md))
- the clock (`clock.py`: how fast game time runs for growth)
- server-log instrumentation
- the test worlds (`spike.py`) and the authoring world (`layouts.py`)

## Deliveries, recipe cards and blueprints (decided 2026-09-24, kits dropped 2026-09-26)

All three arrive on the **offer pads** (a layout slot) between days:

| Day | The pads show |
|---|---|
| Day 0 | a starter card for each starter dish. Choose one: it's on the menu, its crates delivered |
| Card days (the start of day 4, then every 3rd: `rules/cards.json`, PlateUp's rhythm) | a pair of recipe cards FIRST, and one **must** be chosen before the day opens. Choosing one puts the dish on the menu from the next day; any crates it needs that the restaurant doesn't own arrive on the pads, free; then the day's blueprints go out as on other days. (With customer cards, one card of each kind.) |
| Other days | the random offers (`rules/offers.json`): station blueprints |

- A dish says `"unlock": "start"` (a STARTER: offered as a starter card when the
  run begins, and later as a recipe card if not chosen) or `"unlock": "card"` (only
  ever a recipe card). The run begins with every starter's card on the pads; the
  chosen one goes on the menu and its crates are delivered. What it needs is
  worked out from its steps (the report already walks every dish back to its
  crates).
- The run remembers which crates it owns (tags on the run's volume), so a crate
  is never delivered twice. Crates, like plates, can't be binned.
- **Upgrades** come ready-made: a blueprint for a dishwasher, a fast stove, a safety
  stove. The variant is a theme station file with `upgrade_of` (a fast stove glows,
  and a light growth modifier speeds its growth, as `probe_heat` proved; a safety
  stove stops the well-done stage burning). Upgrading a station you already own
  was done with **upgrade kits** until 2026-09-26; they were dropped for PlateUp's
  way, and a **research desk** (a blueprint left on it overnight comes back
  upgraded) is the idea for bringing it back. The fast crate went with the kits:
  crates come one per ingredient, so it can't be offered ready-made.

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
