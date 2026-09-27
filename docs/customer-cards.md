# Customer cards

Status: **built** (2026-09-27); try them in the `cards` spike (`python3 deploy.py cards
practice`), where a card day comes every day.

Customer cards are PlateUp's: every few days you must pick one of two, and it changes
the guests for the rest of the run. Every card carries a downside and an upside.

## When they appear

**PlateUp's rhythm (decided 2026-09-26):** a customer card isn't a step of its own. On
every **card day** -- the start of day 4, then every third day -- the pads show **one
recipe card and one customer card**, and **one of the two must be chosen**: a new dish
or a change to the guests, never both. Until then the open sign refuses, and says why.
Choosing one puts the day's blueprints out, as on any other day. When one kind runs out
(every dish learned, or every customer card taken), both cards are the other kind.


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
  "cards": [
    {
      "id": "impatient_crowd",
      "label": "Impatient crowd",
      "text": "40% chance a guest is impatient. Every guest tips 1 more.",
      "moods": { "impatient": 0.4 },
      "tip": 1
    }
  ]
}
```

When card days come is `cards.json`'s `every_days` (3), shared with the recipe cards.

A card combines any of these effects:

| Effect | Value | What it does |
|---|---|---|
| `moods` | `{mood: chance}` | chance (0-1) a guest has each mood: `impatient`, `relaxed` (patience) or `messy` (tidiness) |
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

## How it's built

- **The shift** runs card days: the countdown, `cardwait` holding the sign, and the picks --
  a recipe card to pad 1 and a customer card to pad 2, or two of one kind when the other
  has run out. Choosing a customer card sets its `card_<id>` tag (never offered again),
  adds its `guests` to the day's extra guests and its `tip` to the tip level, shows its
  name and text to everyone as a title, and lets the day go on (the blueprints).
- **The pads** show a customer card as a gold blueprint (the offers are blue), with its
  text on hover; pressing it tells the shift which was chosen.
- **The queue spots** roll each card's moods, but only once the shift's `card_<id>` tag
  is set -- they read it, as the pads read the purse (`systems/moods.py`, `queue.py`).
- **The guest** reads its moods once, one per track, and acts on them.
- **The build checks** the deck: unique ids, real moods at chances above 0 up to 1, and
  every card's tips added up staying within the tip levels the shift pays (-3 to +5).
