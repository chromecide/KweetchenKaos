# Kweetchen Kaos

A PlateUp!-style co-op restaurant game for Hytale. Chop, cook, plate and serve
before your guests lose patience, then spend the takings on new stations and
upgrades between days.

It is built entirely from game data: no plugin code. Restaurants come from
**content** (JSON in `content/`), which the build in `build/` turns into a
Hytale asset pack. You build new restaurant rooms by hand, in the game.

## Quick start

1. Install **Python 3.9+** and have a **Hytale server** you can add mods to.
2. Copy `local.cfg.example` to `local.cfg` and set `SERVER` to your server's
   folder (the one holding `mods/`).
3. `python3 deploy.py`: builds the game and installs it on the server (restarting the
   server if it has a `run.sh`; otherwise restart it yourself).
4. Join the server, in **adventure mode**, and type `/kk hq`.
5. Step on a portal to start a run.

Full instructions: **[docs/getting-started.md](docs/getting-started.md)**.

## Docs

| Doc | For |
|---|---|
| [getting-started.md](docs/getting-started.md) | setting up, installing, and how to play |
| [authoring.md](docs/authoring.md) | building restaurant rooms, HQ and the backdrop in game, and putting them in the game |
| [content-schema.md](docs/content-schema.md) | every content file: themes, stations, ingredients, dishes, rules, world |
| [systems.md](docs/systems.md) | how the game works inside: each system, and how they're put together |
| [stations.md](docs/stations.md) | the kitchen theme's station looks, and why |
| [menu.md](docs/menu.md) | the kitchen theme's menu and food looks, and why |

## What's where

```
content/
  themes/kitchen/   the kitchen theme: stations, ingredients, dishes, looks
  layouts/          rooms built in game (hq, test_room, backdrop), and raw saves
  rules/            how a run plays: standard, practice
  world/world.json  HQ and the restaurants its portals lead to
build/              the build: reads content, checks it, writes the pack
  systems/          one system per job (stove, counter, queue, shift...)
docs/               the docs above
deploy.py           build and install
local.cfg.example   where your server is (copy to local.cfg)
pack/               build output (not committed)
```

## Commands

**On your computer:**

| Command | Does |
|---|---|
| `python3 deploy.py` | build the game and install it |
| `python3 deploy.py <spike> [rules]` | build a test world instead (see [systems.md](docs/systems.md#testing-and-debugging)) |
| `python3 build/build.py --check` | check the content and print every dish's chain, crate to plate |
| `python3 build/layouts.py import <plot> <id> "<Name>"` | turn a saved plot into a new layout |
| `python3 build/layouts.py reimport` | import again every layout whose plot has been saved since |

**In game:**

| Command | Does |
|---|---|
| `/kk hq` | go to HQ |
| `/kk author` | go to the authoring world |
| `/kk grid [n]` | mark the authoring plots' edges |
| `/kk slots [hq\|plot]` | take the slot blocks |
| `/kk save [n]` | save the authoring plots |
| `/kk restore [n]` | put plot *n* back as last saved; with no number, restore the kept layouts to a new authoring world |
| `/kk spike`, `/kk kit` | (in a test build) open the test world, take its setup kit |

## Status

Playable end to end: HQ, a test kitchen, the full run (days, guests, offers,
recipe cards, upgrades, losing). One theme (kitchen, with four pies), one
restaurant room, two rules sets. Every item and system loads with nothing
rejected, and each system was tested in game on its own before being put
together.

This started as the second version of the Kitchen POC (`../tools`, `../pack`),
which is untouched and still loads beside it: every game id here starts with
`K2_`, so nothing collides.
