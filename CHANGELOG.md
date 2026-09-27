# Changelog

## Unreleased

- **Much snappier:** the game's big rule sets are split into many small ones; pressing
  and picking things up no longer lags.
- The press count shows on what's on the board or in the sink too, not just the station.
- Tap F with the mop to put it back on its stand (cleaning a mess still takes the hold).
- Burnt food has its own icon (black petals).
- Fixed: taking food off the stove the instant it burnt left the burnt food stuck on
  the stove.

## 0.3.0 (2026-09-27)

- **Messes and spills** (PlateUp's): any guest may leave a mess by its chair as it
  gets up (5%), and the sink spills water now and then (25% a scrub). They slow you
  down, grow from small to large, and spilt water spreads if it's left. Clean them
  with the mop: hold F for a second, once per size.
- **Mop stand:** every room needs one (a new "mop stand" slot) -- it keeps the mop.
- **Messier stations:** the chopping board drops food scraps now and then, and burnt
  food leaves a scorch mark by the stove.
- **Offers are blueprints** (PlateUp's): everything on the pads shows as a blueprint;
  press it to pay and you get the station to put down.
- **No more upgrade kits.** Upgraded stations (dishwashers, fast and safety stoves)
  are bought ready-made. The fast crate is gone with the kits, for now.
- **Mats** (PlateUp's): a mat (10) soaks up messes and gets dirty, then overflows
  when it's filthy; a rubber mat (30) never lets a mess land on it. Every kind of
  mess now spreads if it's left, food as well as water.
- **Card days follow PlateUp:** the start of day 4, then every third day. You must
  choose a card before you can open, and the day's blueprints come once you have
  (they no longer skip that day).
- **Customer cards** (PlateUp's): on a card day, a customer card sits beside the
  recipe card, and you choose one of the two. Six to start: Impatient crowd, Messy
  crowd, Word of mouth, Affordable, Relaxed but busy, Hasty lunch. Each changes the
  guests for the rest of the run: moods, more guests, tips.
- **Guest moods:** a guest may arrive impatient, relaxed or messy (and can be one of
  the first two AND messy), shown on its name tag.
- **Cheap dishwasher** (35): washes by itself, but slower than the dishwasher (60),
  and it drips.
- Recipe spikes: `python3 deploy.py dish:<dish>` lays out one dish's kitchen.

## 0.2.0 (2026-09-26)

- **The Kweebec menu:** ten dishes instead of four pies. New: berry salad, roasted
  corn (both starters), mushroom salad, fruit kebab, mushroom kebab, bread. Three
  need no cooking. New ingredients: lettuce, berries, corn, skewer sticks.
- **Dishwasher:** a sink upgrade (a kit from the pads): a dirty plate goes in and
  comes out clean by itself.
- **More between-day offers:** chairs (each brings its own table), and stations
  already upgraded (a dishwasher, a fast stove, a safety stove) as well as the kits --
  so a kitchen can have a sink AND a dishwasher.
- **PlateUp prices:** dishes pay 4-9 (pies 8, well done 9); stations cost 20, upgrade
  kits 30-45, ready-made upgrades 60, chairs 10 (practice rules: half).
- **Dishes set how many guests they bring** (`guests`): quick dishes more, slow ones
  fewer -- and a starter shifts day 1 the same way.
- **Booking desk** (PlateUp's), in every room: press it during service to call the next
  guest in now, for coins (3 on day 1, 4 on day 2, +1 every two days); with nobody left
  to come, it calls closing time. Every layout needs a booking desk slot.
- Fixed: buying a plate rack gave an item that doesn't exist.
- Fixed: guests could stop coming in. A guest walking out could vanish while standing on
  a queue spot, and that spot then stayed "occupied" for good, so the line never moved
  up. Guests now only vanish once they're off the line.
- Fixed: well-done roasted corn, bread and mushroom kebab couldn't be plated. Every
  cooked dish now serves its well-done version too (one coin more), and the build
  refuses a dish that leaves one out.
- Hints show the interact key, the way the game's doors do.

## 0.1.0 (2026-09-26)

The first release: a full run, from HQ to out of business.

**Restaurants** (HQ portals 1-3, all on the standard rules):

- **Test kitchen**: the first room.
- **KweebecKlub**: a Kweebec club.
- **Alfresco Dining**: up in a tree.

**The game**

- HQ, a floating lobby with a portal per restaurant; a shared run for everyone
  who steps on the same portal, and back to HQ when it's lost.
- The kitchen theme: four pies (pumpkin, apple, meat, mushroom), each cooked
  through unbaked, cooked, well done and burnt.
- Stations: chopping board, counter, stove (plus fast and safety upgrades),
  sink, bin, plate rack, and a crate per ingredient (plus a fast upgrade).
- Guests who queue, sit, order, eat and pay, with patience that shows (amber,
  then red) and ends the run when it runs out.
- Days that grow longer, more guests each day and for each dish on the menu,
  offers to buy between days, and recipe cards that add new dishes.
- Titles for every player: welcome, day start, day over, out of business.
- Rearranging: pick stations up and move them between days.

**For builders**

- The authoring world (`/kk author`): build rooms, HQ and the backdrop by hand
  with slot blocks, save, and deploy. New rooms are picked up and given a portal
  by themselves.

**Needs**: a Hytale server `>=0.6.8 <0.8.0`. The pack is data only: no plugin
code, and no network traffic.
