# Menu: ingredients, processes, dishes

Working table, started 2026-09-24. Every dish is a shipped food item with its own
model; every step is one of the processes already built. Nothing here is built yet.

Processes: **chop** (board, press N), **cook** (stove: raw → cooked → well cooked
→ burnt), **combine** (counter, one thing added at a time), **plate**.

## Raw ingredients (from crates)

All shipped, all have a model. Crate hands one out per press.

| Ingredient | Shipped item | Model |
|---|---|---|
| Lettuce | Plant_Crop_Lettuce_Item | Cabbage (shared with cauliflower) |
| Tomato | Plant_Crop_Tomato_Item | Tomato |
| Carrot | Plant_Crop_Carrot_Item | Carrot |
| Onion | Plant_Crop_Onion_Item | Onion |
| Corn | Plant_Crop_Corn_Item | Corn |
| Pumpkin | Plant_Crop_Pumpkin_Item | Pumpkin |
| Potato | Plant_Crop_Potato_Item | Potato |
| Apple | Plant_Fruit_Apple | Apple |
| Berries | Plant_Fruit_Berries_Red | Wild_Berry |
| Mushroom | Plant_Crop_Mushroom_Cap_* | mushroom caps |
| Raw meat | Food_Wildmeat_Raw (also Beef, Pork, Chicken) | Wildmeat / Beef / Pork / Chicken |
| Raw fish | Food_Fish_Raw | Fish_Piece |
| Egg | Food_Egg | Egg |
| Cheese | Food_Cheese | Cheese |
| Dough | Ingredient_Dough | Dough |
| Stick | Ingredient_Stick | Stick |
| Salt | Ingredient_Salt | Salt |
| Spices | Ingredient_Spices | Spice |

Dough comes straight from a crate for now. Making it (flour + egg) is a candidate
extra step for a harder tier.

## Dishes

The shipped crafting recipe is the guide for ingredients. Quantities are
collapsed to one of each, because each one is a press or a combine.

### Easy: one or two steps

| Dish | Shipped item / model | Chain |
|---|---|---|
| Roasted corn | Food_Vegetable_Cooked / Corn_Roasted | corn → cook |
| Grilled fish | Food_Fish_Grilled / Fish_Piece | raw fish → cook |
| Cooked meat | Food_Wildmeat_Cooked / Wildmeat | raw meat → cook |
| Bread | Food_Bread / Bread | dough → cook |
| Berry salad | Food_Salad_Berry / Salad_Berries | lettuce → chop; + berries → combine |

### Medium: chop, combine and cook, or two chops

| Dish | Shipped item / model | Chain |
|---|---|---|
| Mushroom salad | Food_Salad_Mushroom / Salad_Mushroom | lettuce → chop; mushroom → chop; combine |
| Popcorn | Food_Popcorn / Popcorn | corn + salt → combine → cook |
| Fruit kebab | Food_Kebab_Fruit / Fruit_Skewer | apple → chop; + stick → combine (not cooked) |
| Vegetable kebab | Food_Kebab_Vegetable / Vegetable_Skewer | carrot → chop; tomato → chop; + stick → combine → cook |
| Mushroom kebab | Food_Kebab_Mushroom / Mushroom_Skewer | mushroom → chop; + stick → combine → cook |
| Pumpkin pie | Food_Pie_Pumpkin / Pie | pumpkin → chop; + dough → combine → cook |

### Hard: three or more steps, or two stations feeding one dish

| Dish | Shipped item / model | Chain |
|---|---|---|
| Meat kebab | Food_Kebab_Meat / Meat_Skewer | raw meat → chop; + stick → combine → cook |
| Apple pie | Food_Pie_Apple / Pie | apple → chop; + dough + spices → combine → cook |
| Meat pie | Food_Pie_Meat / Pie | raw meat → chop; + dough + salt → combine → cook |
| Caesar salad | Food_Salad_Caesar / Salad_Caesar | raw meat → cook → chop; lettuce → chop; + cheese → combine |

Cooked and well-cooked are separate orders for anything that goes on the stove,
so the stove dishes double up. The two share one model, so the stage is shown by
tint.

**Pie chain, decided 2026-09-24:** dough (the shipped dough model, half size)
+ filling → unbaked pie → stove. Every pie uses the shipped pie model with its
own filling texture: pumpkin, apple, meat, and mushroom (a shipped texture no
item uses, so a free fourth pie). Texture swaps onto other models came out
scrambled (gallery rows 29–30) and are not used.

| Stage | Look |
|---|---|
| Dough | Dough model, half size |
| Unbaked pie | Pie + filling texture, tinted per pie: apple pink `#f098b8`, meat red `#d06858`, pumpkin and mushroom cool grey `#a8b0c4` |
| Cooked | Pie + filling texture, as shipped |
| Well done | Tinted `#6a4020` |
| Burnt | Tinted `#2e2824` |

**Built as data (2026-09-24), awaiting the kitchen spike:**
- `ingredients.py`: flour, pumpkin, apple, raw meat, mushroom, and their
  prepared forms. Flour is kneaded into dough on the board, 4 presses; the
  others are chopped, 4 presses each.
- `dishes.py`: the four pies. Dough + chopped filling combine on the counter
  into an unbaked pie, and the stove takes the unbaked pie. No system changed.

A tint multiplies the texture, so it can only darken. A plain grey wash made
the unbaked pie look darker than the cooked one, so each unbaked pie is told
apart by colour instead: its filling's colour where that shows on the texture,
and cool grey where it doesn't (pumpkin is already orange). Chosen in gallery
rows 31–34. The stove's raw stage uses the same tint.

**Stage tints, locked 2026-09-24:** well cooked `#6a4020` (gallery row 25)
and burnt `#2e2824`, near-black. Both are in `dishes.py` and `sys_stove.py`.
Cooked is the shipped look, untinted.

The three pies share one model (Pie) but each has its own texture
(`Pie_Textures/Apple`, `Meat`, `Pumpkin`), so they can be told apart.

## Pieces: models for the in-between steps

**Decided 2026-09-24: chopped pieces are petals at scale 0.5.** Most use the
petal's built-in colour textures (`Resources/Plants/Petal_Textures/<Colour>.png`),
with no tinting. Two, cooked meat and onion, are the white petal tinted, as
chosen in the gallery (row 2, #2 and #3). Each piece must be told apart at a
glance.

| Chopped | Petal |
|---|---|
| Lettuce | Green |
| Tomato | Red |
| Carrot | Orange |
| Pumpkin | Yellow |
| Mushroom | White |
| Onion | White, tinted `#f0e6c0` (onion cream) |
| Apple | Pink |
| Raw meat | Blood |
| Cooked meat | White, tinted `#8a4a3a` (meat brown) |

Pink, Blood and Yellow are proposed and haven't been looked at next to the
others yet. Spare for later ingredients: Azure, Black, Blue, Cyan, Purple, Storm.

**Raw ingredients are shown at half their shipped size** wherever they sit on a
station (gallery row "Ingredients at half size").

The candidates below were looked at in the gallery:

The model gallery (`python3 tools/gen_spike.py model-gallery`, tools/probe_models.py)
lays every candidate below out to choose from.

These are what's missing. Every chopped ingredient and every half-combined dish
sitting on a counter needs a look. Candidates, all shipped, all need seeing in
game before choosing:

- **Petals** (Plant_Petals_*): a placeable block, `Resources/Plants/Petal.blockymodel`,
  shipped in 13 colour textures (azure, black, blood, blue, cyan, green, orange,
  pink, purple, red, storm, white, yellow). One model gives many coloured
  "chopped" looks: red for tomato, orange for carrot, green for lettuce, white
  for onion.
- **Mature growth-stage plant blocks**: many shapes, and tinting could stretch
  one to several ingredients.
- **Lime succulent**: reads as torn lettuce if tinted darker.
- **The whole ingredient's own model, tinted**: the fallback. Chopped reads as a
  colour change on the raw model.
- **Unbaked (raw-stage) dishes**: the finished model tinted pale, for example
  an unbaked pie is the Pie model, pale. The stove's raw stage already works
  this way.

Chopped pieces needed by the table above: lettuce, mushroom, apple, carrot,
tomato, pumpkin, raw meat, cooked meat (Caesar salad).

Half-combined states needed: each combine that takes more than two things needs
a look for every partial state. Keeping combines to pairs where possible keeps
this down.

## Plated food: decided 2026-09-24

**A plated dish is drawn as the food alone.** The plate is implied, and it is
only drawn when empty or dirty. Plate + food on a counter gives one block showing
the dish's own shipped model; picking it up clears that block. That is the
pattern the counter, stove and bin already use, so plating needs no new system.

- Dishes that ship with their own vessel (pies, the salad bowls, the popcorn
  bucket) already read as served.
- **Later polish:** our own plate-plus-food models, made in Blockbench as
  original art, one per dish. Only the model path in the dish data changes.
  Candidates are the dishes that look wrong without a plate (grilled fish,
  cooked meat, roasted corn, kebabs, bread).

Rejected, with the reasons, in `docs/systems.md` under "Food on a plate: what
was tried":

- a second block above the plate (it floats a whole block up)
- props (they can't be removed)
- a food NPC (physics, pushing, name tags: too many edge cases)
