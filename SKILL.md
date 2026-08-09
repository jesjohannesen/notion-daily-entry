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

(The title property is called `Test` in this database — a leftover name. It
reads back as `null` over SQL, so match on `Dato` only, never on the title.)

If a page exists, use it. If not, create one with `notion-create-pages`:

- parent: `{"type": "data_source_id", "data_source_id": "a5979e60-916d-4018-a1ab-bcfb7245c177"}`
- `template_id`: `2f3856f366e080e9ac62eedefcb6c5b7` (do **not** also pass `content` — the template supplies it)
- `icon`: `♟️`
- properties:
  - `"Test"`: the title, formatted exactly like the existing entries — `@August 3, 2026` (an `@`, then full month name, day without leading zero, year)
  - `"date:Dato:start"`: `TODAY`
  - `"date:Dato:is_datetime"`: `0`

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
```

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
`“”` with the quote. The quote itself is bold — including the quotation marks —
and the attribution is not. Format:

```
**“<quote>”** — <Author>
```

If the quote has a `Source`, append it in italics on the same line:

```
**“<quote>”** — <Author>, *<Source>*
```

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
