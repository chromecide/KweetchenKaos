# Changelog

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
