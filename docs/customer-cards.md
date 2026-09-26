# Customer cards (planned)

Status: **designed, not built.** The per-guest roll it depends on is proven (the
`impatient` spike, `python3 deploy.py impatient`), and so is the messy guest (the
`hazards` spike): a messy guest always leaves a mess round its chair as it gets up.

Customer cards are PlateUp's: every few days you must pick one of two, and it changes
the guests for the rest of the run. Every card carries a downside and an upside.

## When they appear

**PlateUp's rhythm (decided 2026-09-26):** a customer card isn't a step of its own. On
every **card day** -- the start of day 4, then every third day -- the pads show **one
recipe card and one customer card**, and **one of the two must be chosen**: a new dish
or a change to the guests, never both. Until then the open sign refuses, and says why.
Choosing one puts the day's blueprints out, as on any other day. When one kind runs out
(every dish learned, or every customer card taken), both cards are the other kind.

This is built for recipe cards already (both cards are recipes until customer cards
exist); customer cards take pad 2.

- **No repeats:** a card that has been chosen is not offered again in the same run.

## How a card changes guests: per-guest rolls

A card doesn't change every guest. It gives each guest a **chance** of a mood, rolled
once, when the guest first steps into the line.

- **Moods are on separate tracks**, rolled independently, so one guest can have one mood
  from each: **patience** (impatient or relaxed) and **tidiness** (messy). An impatient
  guest can be messy too.
- **Last roll wins, within a track.** Each chosen card adds a roll, in the order the
  cards are listed in `customers.json`. A roll that lands replaces the guest's mood on
  that track only: picking Relaxed after Impatient can turn an impatient guest relaxed,
  but a messy card never undoes an impatient one.
- The mood shows on the guest's name tag, e.g. "Ready to order (impatient, messy)".
- **Impatient:** every patience clock is ⅔ as long. **Relaxed:** 1.5 times as long.
  **Messy:** always leaves a mess round its chair as it gets up (any guest has the rules'
  small chance, 5%, anyway).

Why a guest only rolls once: the roll was first made in the pool, and a guest that
wandered in and out of it while the line was full rolled again each time. Rolling on
the first queue spot, the moment the guest reads its mood, gives exactly one roll.

## The card file: `content/rules/<rules>/customers.json`

```json
{
  "every_days": 5,
  "choices": 2,
  "cards": [
    {
      "id": "impatient",
      "label": "Impatient crowd",
      "text": "40% chance a guest is impatient. Every guest tips 1 more.",
      "mood": ["impatient", 0.4],
      "tip": 1
    }
  ]
}
```

A card combines any of these effects:

| Effect | Value | What it does |
|---|---|---|
| `mood` | `[mood, chance]` | chance (0-1) a guest has the mood: `impatient`, `relaxed` (patience) or `messy` (tidiness) |
| `guests` | whole number | extra guests every day |
| `tip` | whole number | extra coins for every guest served; negative is a price cut |

Word card text as **"X% chance a guest is Y"**, not "X% of guests".

## The first deck

| Card | Downside | Upside |
|---|---|---|
| Impatient crowd | 40% chance a guest is impatient | +1 coin per guest served |
| Messy crowd | 30% chance a guest is messy | +1 coin per guest served |
| Word of mouth | +3 guests a day | more guests, more money |
| Affordable | −1 coin per dish | +2 guests a day |
| Relaxed, but busy | +2 guests a day | 40% chance a guest is relaxed |
| Hasty lunch | 25% chance a guest is impatient, +1 guest a day | +2 coins per guest served |

## How it will be built

- **The shift** already runs card days (the countdown, `cardwait` holding the sign, the
  blueprints once a card is chosen). A customer card is the second card on those days,
  and choosing it applies its effects instead of adding a dish.
- **The pads** show a customer card as a blueprint in its own colour (the offers are
  blue), with the card's text on hover. Pressing it sends "chose" to the shift.
- **The queue spots** keep a count per card and roll each chosen card's mood when a
  guest steps on (`systems/queue.py`). The shift tells them when a card is chosen, and
  a new run clears the counts.
- **The guest** reads its moods once, one per track, and acts on them: its patience
  clocks, and a mess as it gets up (`systems/guest.py`, `build/guests.py`).

## What has to be built first

| Piece | State |
|---|---|
| Impatient mood | built (the probe runs clocks at ½; the cards use ⅔) |
| Messy mood | built |
| Separate tracks | to build: a mark per track, read once each |
| Relaxed mood | to build: a mark, and longer clocks |
| `guests` effect | the shift's extra-guests count, already there |
| `tip` effect | built: the shift's tip level (`tips` spike) |
| Card days (every 3rd from day 4, must pick, the sign held, then the blueprints) | built, for recipe cards |
| The customer card on pad 2 | to build |
