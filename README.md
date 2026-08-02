# Daily Notion entry + quote picker

Creates the day's entry in the Notion `kalender` database and fills the 💭 quote
callout from the [💭 quotes](https://app.notion.com/p/ea30560483dc4c848205ec8c7d9b96a1)
database, without repeating anything featured recently.

## Files

| File | What it is |
| --- | --- |
| `SKILL.md` | The routine prompt. Paste into the cloud routine on claude.ai. |
| `pick_quote.py` | The picker. The routine downloads this at runtime. |

The routine fetches the picker from `main` at run time:

```
https://raw.githubusercontent.com/jesjohannesen/notion-daily-entry/main/pick_quote.py
```

So **changes to `pick_quote.py` take effect on the next run as soon as you
push** — no re-pasting. Only edit and re-paste `SKILL.md` when the *routine
steps* change (the Notion IDs, the SQL, the output format).

The routine verifies the download parses and contains `def select` before
running it, and is instructed to stop rather than improvise a pick if the fetch
fails. Because it tracks `main`, anything you push is what runs tomorrow — treat
a push as a deploy.

## Database schema

Added to `💭 quotes` alongside the existing `Quote` / `Author` / `Category` /
`Date` / `Place`:

| Property | Type | Purpose |
| --- | --- | --- |
| `Source` | Text | Work, essay or letter the line comes from. The reading hook. |
| `Register` | Select | `Aphorism` (short, blunt) or `Profound` (slower, meditative). Drives day-to-day tonal variation. |
| `Last Used` | Date | Stamped by the routine. Drives the cooldown. |
| `Times Used` | Number | Incremented by the routine. Drives the deal-without-replacement tiering. |

Category options were extended with: Science, Mathematics, Art & Literature,
Startups, Discipline, Craft, Risk & Uncertainty.

The 59 pre-existing quotes have no `Register` set. The picker treats a blank
register as a wildcard that always passes, so they stay in rotation. Fill them
in whenever you feel like it — nothing breaks either way.

## How newness is engineered

Corpus is ~300 quotes. Five mechanisms stack:

1. **OS randomness, not model randomness.** Selection uses
   `secrets.SystemRandom`, never seeded from the date. An LLM asked to "pick a
   quote at random" is a badly biased sampler — it gravitates to the same
   memorable handful. The routine is explicitly told never to choose itself.
2. **Deal without replacement.** Among eligible quotes, only those with the
   lowest `Times Used` are in play. You traverse the entire corpus before
   anything repeats — roughly ten months of no repeats at one a day.
3. **Quote cooldown.** Anything used within `max(90, 60% of corpus)` days is
   excluded outright. Currently ~180 days.
4. **Author cooldown (30 days) and category anti-streak (3 days).** Stops
   Nietzsche twice in a fortnight, or three straight days of Economics — the
   things that actually make a feed feel stale, more than literal repeats.
5. **Register alternation.** Two `Aphorism` days in a row forces a `Profound`
   one next, and vice versa. Varies the *texture*, not just the content.

Constraints are applied as a ladder and relaxed from the bottom up if the pool
empties, so the routine degrades gracefully instead of failing. Whatever it
relaxed is reported in the daily summary.

## Tuning

Constants live at the top of `pick_quote.py`:

```python
AUTHOR_COOLDOWN = 30
CATEGORY_COOLDOWN = 3
REGISTER_RUN = 2
```

The quote cooldown is computed from corpus size; override with
`--cooldown-days`. As you add quotes it widens on its own.

## Testing locally

```bash
echo '{"candidates":[{"url":"u1","quote":"q","author":"a","category":"C","register":"Aphorism","last_used":null,"times_used":0}],"recent":[]}' | python3 pick_quote.py --today 2026-08-03
```

To check the spread over a real pool, pull candidates out of Notion with the
query in `SKILL.md` step 3, save as `payload.json`, and run the picker in a loop.

## Notes

- `random()` is blocked by Notion's SQL layer, so the routine pulls the eligible
  pool (~50KB) and randomises client-side. Don't try to move the shuffle into SQL.
- `query_data_sources` is rate-limited on the current Notion plan. Two queries
  per day is well inside it, but don't add a polling loop.
- Attribution: quotes whose wording or origin is contested are labelled
  `(attributed)` in the `Author` field, and `Source` is left blank where a
  specific citation could not be given confidently. Treat blank `Source` as
  "unverified provenance", not "no source exists".
