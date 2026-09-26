# Customer cards (planned)

Status: **designed, not built.** The per-guest roll it depends on is proven (the
`impatient` spike, `python3 deploy.py impatient`). Messes and other hazards are being
probed first; their cards join this deck once that system exists.

Customer cards are PlateUp's: every few days you must pick one of two, and it changes
the guests for the rest of the run. Every card carries a downside and an upside.

## When they appear

- Every **5 days**: before day 5, 10, 15 and so on.
- The day ends as usual. Then two customer cards are on pads 1 and 2, and nothing
  else. **One must be chosen**: until then the open sign refuses, and says why.
- Once one is chosen, both vanish and the day goes on as it does today: recipe cards
  on a recipe-card day (day 15 is both), offers otherwise.
- A card that has been chosen is not offered again in the same run.

## How a card changes guests: per-guest rolls

A card doesn't change every guest. It gives each guest a **chance** of a mood, rolled
once, when the guest first steps into the line.

- **Last roll wins.** Each chosen card adds a roll, in the order the cards are listed
  in `customers.json`. A roll that lands replaces any mood the guest already had, so a
  guest has at most one mood.
- The mood shows on the guest's name tag, e.g. "Ready to order (impatient)".
- **Impatient:** every patience clock is ⅔ as long. **Relaxed:** 1.5 times as long.

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
| `mood` | `[mood, chance]` | chance (0-1) a guest has the mood: `impatient` or `relaxed` |
| `guests` | whole number | extra guests every day |
| `tip` | whole number | extra coins for every guest served; negative is a price cut |

Word card text as **"X% chance a guest is Y"**, not "X% of guests".

## The first deck

| Card | Downside | Upside |
|---|---|---|
| Impatient crowd | 40% chance a guest is impatient | +1 coin per guest served |
| Word of mouth | +3 guests a day | more guests, more money |
| Affordable | −1 coin per dish | +2 guests a day |
| Relaxed, but busy | +2 guests a day | 40% chance a guest is relaxed |
| Hasty lunch | 25% chance a guest is impatient, +1 guest a day | +2 coins per guest served |

## How it will be built

- **The shift** counts down to customer-card days, as it does for recipe cards. On one,
  it holds the normal end of day (recipe cards or offers) until a customer card is
  chosen, then lets it run.
- **The pads** show a customer card as a tinted book (the booking desk's), with the
  card's text on hover. Pressing it sends "chose" to the shift.
- **The queue spots** keep a count per card and roll each chosen card's mood when a
  guest steps on (`systems/queue.py`). The shift tells them when a card is chosen, and
  a new run clears the counts.
- **The guest** reads its mood once and runs its patience clocks to match
  (`systems/guest.py`).
