# Getting started

From a fresh checkout to playing a shift. No coding needed: everything here is
running a Python script and editing a settings file. To build your own rooms, carry
on to [authoring.md](authoring.md) afterwards.

## What you need

- **A Hytale server** you can put mods on: a folder with `mods/` in it, which you
  can start and stop. The pack is data only (no plugin code), so any server that
  loads asset-pack mods will do.
- **Python 3.9 or newer** (`python3 --version`; on Windows it may be `py` or
  `python`). No extra packages: every script, the build and the deploy, only
  uses what comes with Python, on macOS, Linux or Windows.
- **The Hytale game**, to play. Its `Assets.zip` is also used to check that
  everything the content names really ships with the game. The build finds it
  in the launcher's usual place, or you can tell it where it is. Without it the
  build still works, with that check skipped.

## One-time setup

1. Copy `local.cfg.example` to `local.cfg` (it is yours; it is never committed).
2. Set `SERVER` to your server's folder, the one that holds `mods/`:

   ```
   SERVER=~/hytale-server
   ```

3. Only if the build warns that it can't find `Assets.zip`, set `ASSETS` to its
   path too.

`KK_SERVER` and `KK_ASSETS` in the environment work instead of the file.

## Build and install

```
python3 deploy.py
```

This picks up any layout saves made since the last run (see
[authoring.md](authoring.md)), builds the whole game from `content/` into
`pack/`, then installs it as `mods/Chromecide_KweetchenKaos` in your server folder.

- **If your server folder has a `run.sh`** (a script that starts the server;
  macOS and Linux), `deploy.py` stops the server, installs, starts it again, and
  then reads the server log for anything the game refused. `Kweetchen Kaos: nothing rejected`
  is what you want to see. Anything else lists the file and the reason.
- **Otherwise** it installs and tells you to restart the server yourself.

Run it again after any change to `content/`. Each build starts from nothing, so
nothing stale is left behind. It also rescues your layout saves before it
replaces the installed pack (see [authoring.md](authoring.md)).

To only check the content, without building or installing:

```
python3 build/build.py --check
```

It prints every dish's full chain, from crate to plate, and any problems it
finds, naming the file each came from.

### Installing by hand

```
python3 build/build.py
```

Then copy the `pack/` folder into your server's `mods/` folder, name it
`Chromecide_KweetchenKaos`, and restart the server.

## Playing

Join the server and type **`/kk hq`**. You arrive at HQ: a lobby with a portal
for each room size (starter, small, medium, large) and one to the practice room. Step on a portal and you, and anyone who steps on after
you, are taken into that restaurant together. Each restaurant is a fresh world
of its own, floating in the sky, and it is thrown away when everyone has left.

Play in **adventure mode**. Guests ignore players in creative.

### The controls

| Key | What it does |
|---|---|
| **F** | Everything a station does: put down, pick up, chop, wash, cook, take a plate. Also takes a guest's order, and **serves** a plated dish to a guest. |
| **Left-click, empty hands** | Picks a station up to move it (only between days). |
| **Right-click, carrying** | Puts it down, facing the way you choose. |

Look at anything to see what it is and what it wants. Every station and guest
says so.

### A run

1. **Choose your first recipe.** Starter recipe cards are on the pads out front.
   Press one: that dish is on the menu, and its ingredient crates are
   delivered to the pads. Take them.
2. **Set up the kitchen.** Place the crates, and move stations around if you
   like. This is the time to do it, because nothing can be moved during
   service.
3. **Open.** Press the **sign**. A title says the day and how many guests to
   expect. Guests arrive through the day, queue, and sit down when a chair is
   free.
4. **Take orders.** Press **F** on a seated guest to take its order. What it
   wants shows above its head.
5. **Cook.** Take ingredients from the crates. Chop them on the board, combine
   them on a counter (dough plus a chopped filling makes an unbaked pie), and
   put that on the stove. It cooks by itself, through cooked, well done, and
   burnt. Take it off in time.
6. **Plate and serve.** Take a clean plate from the rack. Put the plate and the
   food together on a counter, and serve the plated dish to the guest with **F**.
7. **Clear up.** A fed guest leaves a dirty plate on its table. Take it and wash
   it at the sink (press it a few times), then put it back on the rack. Food
   nobody wants goes in the bin.
8. **End of day.** At closing time no more guests come, and the day ends when
   the last one leaves. A title shows how many you served and your purse.
   Blueprints appear on the pads: press one to buy that station (plain, or already
   upgraded, like a dishwasher or a fast stove) and put it down. At the start of
   day 4, and every third day after, it's a **card day**: two recipe cards come
   first, and you must choose one (a new dish, which brings more guests) before
   you can open. The blueprints come once you have.
9. **Upgraded stations.** The fast stove glows blue and cooks faster, the safety
   stove glows green and never burns food, and the dishwashers wash by themselves.
10. **Losing.** If a guest leaves angry, because its order or its food took too
    long, or the whole queue gives up, you are **out of business**. Everyone
    goes back to HQ, and the next person through the portal starts a new run.

Anything you need to know that isn't a title is in chat: offers, deliveries,
"not enough coins", a crate that's closed until the day opens, and so on.

## Where to go next

- [authoring.md](authoring.md): build your own restaurant rooms, HQ, and the
  backdrop, and put them in the game.
- [content-schema.md](content-schema.md): every content file: themes, dishes,
  stations, rules, world.
- [systems.md](systems.md): how the game works inside, system by system.
- [stations.md](stations.md) and [menu.md](menu.md): the looks chosen for the
  kitchen theme, and why.
