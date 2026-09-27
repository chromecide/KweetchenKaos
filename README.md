# Kweetchen Kaos

A PlateUp!-style co-op restaurant game for Hytale. Chop, cook, plate and serve
before your guests lose patience, then spend the takings on new stations and
upgrades between days.

It is built entirely from game data: no plugin code. Restaurants come from
**content** (JSON in `content/`), which the build in `build/` turns into a
Hytale asset pack. You build new restaurant rooms by hand, in the game.

## Install a release (just to play)

1. Download `KweetchenKaos-<version>.zip` from the repo's **Releases**.
2. Unzip it into your Hytale server's `mods/` folder: you get
   `mods/Chromecide_KweetchenKaos/`.
3. Restart the server, join in **adventure mode**, and type `/kk hq`.

What's in each release is in [CHANGELOG.md](CHANGELOG.md).

## Quick start (from the source)

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
  world/world.json  HQ and how its portals play
build/              the build: reads content, checks it, writes the pack
  systems/          one system per job (stove, counter, queue, shift...)
docs/               the docs above
deploy.py           build and install
release.py          package a release (dist/, not committed)
local.cfg.example   where your server is (copy to local.cfg)
pack/               build output (not committed)
```

## Commands

**On your computer:**

| Command | Does |
|---|---|
| `python3 deploy.py` | pick up new layout saves, build the game and install it (all you need after `/kk save`) |
| `python3 deploy.py <spike> [rules]` | build a test world instead (see [systems.md](docs/systems.md#testing-and-debugging)) |
| `python3 build/build.py --check` | check the content and print every dish's chain, crate to plate |
| `python3 build/layouts.py import <world> <id> "<Name>"` | turn a saved authoring world (`floorplan_07`, say) into a new layout |
| `python3 build/layouts.py reimport` | import again every layout whose world has been saved since |
| `python3 release.py` | package a release zip in `dist/` and boot-test it (version in `build/settings.py`) |

**In game:**

| Command | Does |
|---|---|
| `/kk hq` | go to HQ |
| `/kk author <world>` | go to an authoring world: `border`, `hq`, `practice` or `floorplan <n>` (1-99) |
| `/kk slots [hq\|plot]` | take the slot blocks |
| `/kk save <world>` | save that world's plot |
| `/kk restore <world>` | put it back as last saved |
| `/kk spike`, `/kk kit` | (in a test build) open the test world, take its setup kit |

## Status

Playable end to end: HQ, three restaurants, the full run (days, guests, offers,
recipe cards, upgrades, the booking desk, messes and the mop, losing). One theme
(kitchen, ten dishes), two rules sets. Every item and system loads with nothing
rejected, and each system was tested in game on its own before being put
together.

### To do

- **Enter with empty hands.** Nothing stops a player from carrying items into a
  restaurant or the practice room today. They could bring tools to break and rearrange a
  layout, bring food from one run into the next, or carry a practice station out
  into a run. Until this is solved the practice room's stations stay locked in place;
  a recipe picker for it waits on the `practice-picker` branch.
  The plan: HQ is the gate. Every portal out of HQ refuses a player who is carrying
  anything (the game's trigger volumes can check for an empty inventory), and HQ
  gets chests for dumping gear. Franchise items would be **packed** at the shelves
  instead of taken as items, and handed over on arrival in a run. There would be reminders of
  what's packed when you arrive at HQ and when you step on a portal, and a
  "hands must be empty" message when a portal refuses you. It also needs a
  home portal in HQ, back to the server's default world, and an exit from the practice room.
  Unproven: the empty-inventory check, a volume sending a player through a portal (a
  pad can't check inventory itself), and handing over items on arrival.

This started as the second version of the Kitchen POC (`../tools`, `../pack`),
which is untouched and still loads beside it: every game id here starts with
`K2_`, so nothing collides.

## Contributing

Contributions are welcome: see [CONTRIBUTING.md](CONTRIBUTING.md). Every contributor
accepts the short [Contributor License Agreement](CLA.md) once, in their first pull
request.

## Licence

MIT: see [LICENSE](LICENSE). Hytale's own models, textures and prefabs are
referenced by path, never copied into this project.

## AI Use Disclosure

Kweetchen Kaos was made by one person, Chromecide, working with an AI coding agent,
Claude Code. It is worth being plain about what that means.

- The idea, the design decisions, what to build next and what to leave out came from
  a person. So did every test in the game: each system was played on its own in a
  test world before it went into the game, then played again as part of a full run,
  and the ones that did not hold up were reworked. Most of what is in the game is
  there because playing it showed it was needed.
- Nothing is called working because it was written carefully. What counts is seeing
  it work in game; the build also checks the content and reads the server log for
  anything the game refused, and every release is booted from the zip that ships.
- Most of the Python build, the content files and these documents were written by
  the agent under that direction, in a terminal, with the person reading the results
  in the game rather than the code. The restaurant rooms, HQ and the backdrop were
  built by hand, in the game. Hytale's server source and shipped files were read to
  learn how the game works, never copied; the rule is in
  [CONTRIBUTING.md](CONTRIBUTING.md).
- There is no AI in the mod. It is plain game data: no plugin code, and it makes no
  network calls and sends nothing anywhere.
- No generative AI imagery, ever. Everything players see is the game's own art,
  referenced by path, except one image: a thin white band that trims the stations,
  drawn by a script pixel by pixel from numbers. Any art the mod adds will be made by
  people, and contributions containing AI-generated images are rejected; see
  [CONTRIBUTING.md](CONTRIBUTING.md).

If that is not something you want to run on your server, that is a fair choice, and
the whole repository is here to read. Bugs are ours whichever of us typed them;
please report them. Contributions are welcome from people working with or without
such tools, on the same terms.
