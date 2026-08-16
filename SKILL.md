---
name: daily-notion-entry
description: Create today's Notion daily entry in the "kalender" database and fill the daily quote callout with a randomly selected, non-repeating quote from the 💭 quotes database.
---

You are creating Jesper's daily entry in Notion and choosing the day's quote.
Work through the steps in order. Do not skip the picker script — the whole point
is that the selection is genuinely random and does not repeat recent quotes.

## Fixed IDs

- Quotes data source: `collection://397b4c07-2387-43cf-91f2-30d4a66d42c9`
- Daily-entry data source (`kalender`): `collection://a5979e60-916d-4018-a1ab-bcfb7245c177`
- Daily-entry page template: `2f3856f366e080e9ac62eedefcb6c5b7`
- Picker script: `https://raw.githubusercontent.com/jesjohannesen/notion-daily-entry/main/pick_quote.py`

## 1. Today's date

Use the local date in Europe/Oslo. Call it `TODAY` (format `YYYY-MM-DD`) and use
it consistently everywhere below.

## 2. Find or create today's entry page

Query the `kalender` data source for a page whose `Dato` is `TODAY`:

```sql
SELECT url FROM "collection://a5979e60-916d-4018-a1ab-bcfb7245c177"
WHERE "date:Dato:start" = 'TODAY'
```

(The title property is called `Test` in this database — a leftover name. Match
on `Dato`, never on the title: `Dato` is the authoritative date field, and the
title is display text that can be edited by hand without breaking anything.)

If a page exists, use it. If not, create one with `notion-create-pages`:

- parent: `{"type": "data_source_id", "data_source_id": "a5979e60-916d-4018-a1ab-bcfb7245c177"}`
- `template_id`: `2f3856f366e080e9ac62eedefcb6c5b7` (do **not** also pass `content` — the template supplies it)
- `icon`: `♟️`
- properties:
  - `"Test"`: **static text**, formatted exactly like the existing entries —
    `@August 3, 2026` (an `@`, then full month name, day without leading zero,
    year). Do **not** write a `<mention-date>` here.

    Why not a mention: a real date mention renders under the workspace's display
    setting, which is relative — the title shows `@Today`, then `@Yesterday`, and
    only later settles into the full date. The chip's display format cannot be set
    over the API (Notion-flavored Markdown accepts only `start`, `end`, `startTime`,
    `endTime` and `timeZone` on `<mention-date>`; `format` / `date-format` /
    `relative` are silently discarded on write), and turning off "Relative" requires
    clicking each chip in the UI. Static text is stable and reads the same on every
    day. The real date lives in `Dato`, which is what sorting and the step-2 lookup
    use, so nothing is lost by the title being plain text.

    Sanity check: static text reads back as itself over SQL; a date mention reads
    back as `null`. If a `SELECT "Test"` comes back `null`, that entry has a mention
    and needs converting.
  - `"date:Dato:start"`: `TODAY`
  - `"date:Dato:is_datetime"`: `0` — pass it as the JSON number `0`, not the string
    `"0"`. Quoted, `notion-create-pages` rejects the whole call with a 400.

Leave the habit checkboxes alone — Jesper ticks those himself.

## 3. Pull the recent log and the candidate pool

Two queries against the quotes data source. Substitute `TODAY` into both.

**Recent (what has been featured lately):**

```sql
SELECT "Quote" AS quote, "Author" AS author, "Category" AS category,
       "Register" AS register, "date:Last Used:start" AS date
FROM "collection://397b4c07-2387-43cf-91f2-30d4a66d42c9"
WHERE "date:Last Used:start" IS NOT NULL
  AND julianday('TODAY') - julianday("date:Last Used:start") <= 45
ORDER BY "date:Last Used:start" DESC
```

**Candidates (everything off cooldown):**

```sql
SELECT url, "Quote" AS quote, "Author" AS author, "Source" AS source,
       "Category" AS category, "Register" AS register,
       "date:Last Used:start" AS last_used, COALESCE("Times Used",0) AS times_used
FROM "collection://397b4c07-2387-43cf-91f2-30d4a66d42c9"
WHERE "date:Last Used:start" IS NULL
   OR julianday('TODAY') - julianday("date:Last Used:start") > 120
ORDER BY COALESCE("Times Used", 0) ASC
LIMIT 100
```

The `ORDER BY` is load-bearing, not cosmetic. `query_data_sources` returns at
most 100 rows in SQL mode and gives no cursor to page past them, so on a corpus
of ~300 the pool is always truncated. This is expected, not an error — and note
that the explicit `LIMIT 100` makes the response report `has_more: false`, so
that flag is not a truncation signal here. Sorting by `Times Used` ascending
guarantees the truncation
throws away rows the picker could never have chosen anyway: it only ever deals
from the lowest-`Times Used` tier, so those rows must be the ones inside the
window. Without the sort, the cut is arbitrary and can discard the entire
eligible tier. Traversal still holds — each pick lifts one row out of the tier,
letting a row from position 101 slide in — so every quote gets its turn before
anything repeats.

One knock-on: the picker derives its default cooldown from the number of
candidates it was handed, so it sits at the 90-day floor instead of widening
with the corpus. That is inert here — the SQL above already excludes anything
used within 120 days, which is the stricter of the two.

Both queries count against a monthly `query_data_sources` quota. Run each of
them exactly once. If either returns a usage-limit error, stop and report it —
do not retry in a loop and do not fall back to picking a quote yourself.

## 4. Fetch and run the picker

Never choose the quote yourself. Models are badly biased samplers and drift
toward the same memorable handful — the whole design exists to prevent that.

Download the picker and check it arrived intact:

```bash
curl -fsSL -o /tmp/pick_quote.py \
  https://raw.githubusercontent.com/jesjohannesen/notion-daily-entry/main/pick_quote.py
grep -q "def select" /tmp/pick_quote.py && python3 -c "import ast;ast.parse(open('/tmp/pick_quote.py').read())" \
  && echo "picker ok"
```

If the download or the check fails, stop and report it. Do not improvise a
selection.

Write the payload to `/tmp/payload.json` as
`{"candidates": [...], "recent": [...]}` using the rows from step 3 verbatim,
then run:

```bash
python3 /tmp/pick_quote.py --today TODAY --payload /tmp/payload.json
```

Use whatever the script returns. If it reports relaxed constraints, that is
fine — just mention it in the summary.

## 5. Stamp the chosen quote

Update the chosen quote's page (`pick.url`) with `notion-update-page`,
`command: update_properties`:

- `"date:Last Used:start"`: `TODAY`
- `"date:Last Used:is_datetime"`: `0`
- `"Times Used"`: `pick.times_used + 1`

This is what makes tomorrow's run avoid today's quote. Do not skip it.

## 6. Write the quote into the daily entry

The template leaves an empty callout in the `daily quote` section:

```
<callout icon="💭" color="brown_bg">
	“”
</callout>
```

Use `notion-update-page` with `command: update_content` to replace the empty
`“”` with the quote. The quote itself is **bold**, including its curly quotation
marks; the attribution that follows is not. Format:

```
**“<quote>”** — <Author>
```

If the quote has a `Source`, append it in italics on the same line, outside the
bold:

```
**“<quote>”** — <Author>, *<Source>*
```

Then, on the next line **inside the same callout**, add a short context note in
gray. The finished cell looks like this:

```
<callout icon="💭" color="brown_bg">
	**“<quote>”** — <Author>, *<Source>*
	<span color="gray"><context></span>
</callout>
```

The context is one or two sentences, 40 words at the outside, so that it stays
smaller than the quote it sits under. Write it yourself, as there is no database
field for it. Aim it at *why the line means what it means*, so who the author
was, what situation or argument produced the line, what the phrase is actually
claiming. For Braudel's "Events are dust":

```
Braudel drafted the book from memory in a German POW camp. He argued that
history runs at three speeds, and that the fastest of them, the daily churn of
events, is mere foam over the slow tides that actually move the world.
```

### Language

Jesper's preferences. They matter most for the context note, but apply to
anything this routine writes.

- **No em-dash constructions.** Where a dash wants to go, use a comma, a full
  stop, or brackets. Two short sentences beat one sentence hinged on a dash.
- **No colon constructs.** Do not set up a phrase and then deliver the payoff
  after a colon. Say the thing in a sentence.

The dash in the attribution line stays, since that is a citation separator and
not prose.

Two failure modes to avoid. Do not restate the quote in flatter words, and if a
note would only paraphrase, give the origin instead. Do not invent provenance
either. Where `Author` carries `(attributed)` or `Source` is blank, the origin
is genuinely unverified (see the README note on attribution), so either say the
attribution is disputed or write about the idea rather than the anecdote. A
plain, slightly dry note is fine. A confidently wrong one is not.

If the search-and-replace fails because the placeholder is missing or already
filled, fetch the page, find the 💭 callout under `daily quote`, and replace its
text content instead. Never append a second callout, and never overwrite a
quote Jesper has already written there by hand — if the callout already holds a
non-empty quote, leave it and say so in the summary.

## 7. Summary

Report back briefly:

- the daily entry page URL (and whether you created it or it already existed)
- the quote, author and source
- one line of picker diagnostics: pool size, tier size, and any relaxed constraints

Keep it short. No preamble.
