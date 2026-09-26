# Contributing to Kweetchen Kaos

Thanks for wanting to help. A few things to know before your first pull request.

## The agreement

Kweetchen Kaos is MIT licensed, and it is important that it stays easy to relicense or transfer as a
whole in future. So every contributor accepts the short [Contributor License Agreement](CLA.md) once,
by adding this line to their first pull request:

    I have read the CLA in CLA.md and I agree to its terms.

Pull requests without it can't be merged, however good they are.

## No copied game files or server code

We learn how Hytale works by reading its server source and its shipped assets, and that's fine.
Copying either into this repository is not.

- **Game assets are referenced by path, never copied.** A station's texture, a food's model, a
  prefab: the content names the game's own file (`BlockTextures/Metal_Iron.png`), and the game loads
  it. None of Hytale's models, textures or prefabs are in this repository or in a release.
- **Server code is read, never copied.** The build writes game data the documented way. If something
  can only be done by copying, open an issue and we'll find another way.

## How it's built

Kweetchen Kaos is data only: no plugin code. The Python in `build/` reads the content in `content/`,
checks it, and writes a Hytale asset pack. [docs/systems.md](docs/systems.md) explains how it fits
together; the short version:

- **Content is not code.** A new dish, ingredient, station look or price is a JSON change in
  `content/`, and the build should take it without code changes.
  [docs/content-schema.md](docs/content-schema.md) describes every file.
- **One system per job**, in `build/systems/`, following the contract at the top of
  `build/systems/__init__.py`. The rule that matters most: **a system never imports another
  system.** Systems share only infrastructure (`blocks.py`, `volumes.py`, `signals.py`,
  `settings.py`) and the model. Anything two systems both need goes there.
- **Each system's file starts with what the player does and what happens**, in plain words, before
  any code. Keep that up to date when you change what it does.
- **Instrumented by default.** Every milestone goes to the server log (`volumes.report`). Chat is for
  players.

## Proving it works

This project has no automated tests of the game itself: the only proof something works is seeing it
work in game. So:

- **Every new system is tried on its own first, in a spike** (`python3 deploy.py <spike>`, see
  [docs/systems.md](docs/systems.md#testing-and-debugging)), before it's put into the game. **A spike
  isolates one thing**: it carries only the stations and items its test needs, nothing else, so what it
  proves isn't muddied. A new feature gets its own spike rather than being bolted onto another.
- `python3 build/build.py --check` must pass, and `python3 deploy.py` must end with
  "Kweetchen Kaos: nothing rejected". The game refuses bad data quietly, so that line matters.
- Say in the pull request what you tried in game and what you saw.

## Tests and docs

- New content fields need a paragraph in [docs/content-schema.md](docs/content-schema.md), and a
  check in `build/check.py` if a mistake in them would otherwise fail silently in game.
- A new system or a change to how one behaves needs its section in [docs/systems.md](docs/systems.md).
- A new slot needs its row in [docs/authoring.md](docs/authoring.md).
- Anything a player would notice goes in [CHANGELOG.md](CHANGELOG.md), under "Unreleased".

## Working with AI tools

Most of this project was written by an AI coding agent under a person's direction, and contributions
made the same way are welcome. The terms are the same as for any other contribution: you have read and
understood what you are submitting, you have seen it work in game, the CLA line is in the pull request,
and nothing is copied from the game's files or server code. Say in the pull request if a tool did most
of the typing; it helps the reviewer know where to look.

**Images are the exception.** Generative AI is not used for any image in this mod, and a submission
that contains AI-generated imagery is rejected, whatever the license or the prompt. That covers icons,
textures, screenshots edited with generative tools, and anything else shown to a player or a reader.
Draw it, photograph it, commission it, or leave it out. Procedurally generated textures are fine when
the script that draws them is in the repository, as the stations' trim band is (`write_trim_mask` in
`build/blocks.py`, drawn pixel by pixel from numbers). Today that band is the only image the mod ships;
everything else players see is the game's own art, referenced by path. Art may be given under its own
terms rather than the CLA, and an artist keeps their copyright if that is what was agreed; whatever
was agreed is written down beside the art.

## Reporting bugs

Include what you did and what you expected, the restaurant and day, the server log lines tagged with
the system's name (`[shift]`, `[hazards]`, `[sink]`...), and the Hytale version. A screenshot helps
with anything you can see.

## Before a release

`python3 release.py` builds the release zip and boots it on a plain server before anything is
published: the zip is unpacked and installed exactly as a player would, the server started, and its
log checked. The dev server never sees the packaged files, so a mistake in packaging would otherwise
reach players while every dev run passes. A release is also played through by hand, a full run from
HQ, on that build.

## Branches and tags

- **`main` is the only branch.**
- **Versions** are the mod's own (`VERSION` in `build/settings.py`, semantic). **Tags** `vX.Y.Z` mark
  releases on `main`, and a GitHub release carries the zip and the changelog for that version.
