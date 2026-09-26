# Station looks (kitchen theme)

Chosen by eye in the texture gallery probe (a separate project, not in this repo:
`/tex picks` shows these exact looks) on 2026-09-25. Every texture is a shipped
one, referenced by path; the pack ships one image of its own (the trim band).
The data lives in `content/themes/kitchen/stations/*.json` (`look`).

| Station | Sides | Top | Top while in use | Trim |
|---|---|---|---|---|
| Stove | `Metal_Iron` | `Metal_Iron_Decorative_Top` | `Metal_Copper_Decorative_Top` | `#d0d0d0` grey |
| Fast stove | `Metal_Iron` | `Metal_Iron_Decorative_Top` | `Metal_Copper_Decorative_Top` | `#6080ff` blue (blue glow) |
| Safety stove | `Metal_Iron` | `Metal_Zinc_Decorative_Top` | `Metal_Copper_Decorative_Top` | `#60e080` green (green glow) |
| Chopping board | `Metal_Iron` | `Wood_Softwood_Planks_Top` | same | `#b07850` warm brown |
| Sink | `Metal_Iron` | `Mushroom_Block_Blue_Trunk_Top` (the water) | same | `#d0d0d0` grey (the rim) |
| Dishwasher (sink upgrade) | `Metal_Iron` | `Metal_Iron_Ornate` | same | `#40c0d0` teal; a dirty plate goes in and comes out clean by itself after 4s |
| Bin | `Furniture_Village_Crate` | `Wood_Village_Wall_Black_Full` | same, tinted `#4a4038` with a plate on it | none |
| Plate rack | `Metal_Iron_Ornate`, the block TURNED (roll 90, yaw 90) so the bars lie flat -- a stack of plates | `Metal_Iron` (the stove's plain side) | a plate on top while it holds any | none |
| Counter | `Wood_Softwood_Planks_Side` | `Soil_Snow`, greyed by the trim's tint to read as marble | same | `#aaaaaa` grey (step 6 of 16 on the gallery's snow ramp) |
| Booking desk | `Wood_Softwood_Planks_Side` | `Soil_Snow` (like the counter), with the brown book (`Blocks/Dungeons/Book.blockymodel`, `Book_Brown.png`) at 75% on top | same | `#aaaaaa` grey |
| Mop stand | `Wood_Softwood_Planks_Side` | same, with the mop (the Halloween broomstick model) at 80% on top | same | `#3a78b8` blue |
| Produce crate | `Wood_Village_Wall_RedDark_Full` | same | | none (the fast crate is tinted `#9fb8ff`) |

Every station has been reviewed. The first theme is Hytale Kweebec: softwood and snow-marble suit it.

## The rules behind them

- **Copper means cooking.** Every stove's top turns copper while something is
  on it, whatever its free top is.
- **Iron sides** run through the stoves, sink and board: one line of kitchen units.
- **The trim** is a 2px band round the top of the sides (`look.trim`), kept
  subtle on purpose. It is a side mask: one plain white band, coloured by the
  game's top tint -- which tints the station's TOP too. Taken knowingly: it
  colour-codes the stove upgrades (their tops take the glow's colour) and
  gives the sink its rim.
- **No painted textures.** A band painted with a plank pattern looked great,
  but it starts down the road of custom art; a strip and a tint is enough.
- **A turned station** (`look.turn`, quarter turns of yaw/pitch/roll): a cube
  face's texture can't be rotated, so the whole block is. It allows any rotation
  and holds what sits on it on every face; the room paste sets the turn, block
  swaps keep it, and the rack sets it again whenever one is put down (the client
  picks a rotation from how the player faces). A turned look's `top` is
  what ends up on top: the build puts it on the faces the turn brings up.

## Tried and set aside

- **Transition textures** as a trim: a transition is only a shape, drawn in
  the SPILLING block's own top texture onto a neighbour's top -- never on the
  block itself. Useless for a station's own edge.
- **Shipped models** for the sink (alchemy cauldron) and bin (a scaled-up
  bucket): didn't work out in the gallery; stations stay cubes.
- **Whole-block tints** on the stove upgrades: they tinted the iron too; the
  trim and glow do the job.
- **Fluid_Water** as the sink top: it is greyscale (real water takes the
  environment's tint), so it shows white on a cube.
