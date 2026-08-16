#!/usr/bin/env python3
"""Pick the day's quote from the Notion 💭 quotes corpus.

Reads a JSON payload on stdin:

    {
      "candidates": [
        {"url": "...", "quote": "...", "author": "...", "source": "...",
         "category": "...", "register": "Aphorism"|"Profound"|null,
         "last_used": "2026-05-01"|null, "times_used": 0}
      ],
      "recent": [
        {"date": "2026-08-01", "quote": "...", "author": "...",
         "category": "...", "register": "..."}
      ]
    }

`recent` is the log of what was already featured, newest first or in any order —
it is sorted here. Writes the chosen row, the day's page icon, and diagnostics
as JSON to stdout.

Randomness is drawn from secrets.SystemRandom (the OS CSPRNG), never seeded
from the date, so consecutive days are statistically independent.

Usage:
    python3 pick_quote.py --today 2026-08-03 < payload.json
"""

import argparse
import json
import secrets
import sys
from datetime import date

RNG = secrets.SystemRandom()

# Cooldowns, in days. Tuned for a corpus of ~300; see README.
AUTHOR_COOLDOWN = 30
CATEGORY_COOLDOWN = 3
REGISTER_RUN = 2  # force a switch after this many identical registers in a row

# Page icons for the daily entry, drawn per day. Kept in the same muted register
# as the original chess pawn, small objects rather than loud symbols. The draw is
# independent of the quote and of the previous day, so consecutive repeats happen
# about once every len(ICONS) days; widen the pool if that grates.
ICONS = [
    "♟️", "🕯️", "🧭", "🗝️", "🪶", "🫖", "🕰️", "🪴", "🐚", "🧶",
    "🌾", "🍂", "🪵", "🧊", "🪞", "🌙", "⛰️", "🗺️", "☕", "🥾",
    "🎐", "🪟", "🧱", "🍃", "🌗", "🪺", "🧺", "🪔", "📎", "🔭",
]


def parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def days_since(value, today):
    parsed = parse_date(value)
    return None if parsed is None else (today - parsed).days


def recent_within(recent, today, field, window):
    """Values of `field` used within `window` days of today."""
    out = set()
    for entry in recent:
        age = days_since(entry.get("date"), today)
        if age is not None and age <= window and entry.get(field):
            out.add(entry[field])
    return out


def register_to_avoid(recent):
    """If the last REGISTER_RUN picks shared a register, avoid it today."""
    ordered = sorted(
        (e for e in recent if parse_date(e.get("date"))),
        key=lambda e: parse_date(e["date"]),
        reverse=True,
    )
    run = [e.get("register") for e in ordered[:REGISTER_RUN]]
    if len(run) == REGISTER_RUN and run[0] and all(r == run[0] for r in run):
        return run[0]
    return None


def build_constraints(recent, today, cooldown_days):
    """Ordered list of (name, predicate). Later entries are relaxed first."""
    seen_quotes = {e["quote"] for e in recent if e.get("quote")}
    stale_authors = recent_within(recent, today, "author", AUTHOR_COOLDOWN)
    stale_categories = recent_within(recent, today, "category", CATEGORY_COOLDOWN)
    avoid_register = register_to_avoid(recent)

    def not_repeated(c):
        return c["quote"] not in seen_quotes

    def off_cooldown(c):
        age = days_since(c.get("last_used"), today)
        return age is None or age > cooldown_days

    def fresh_author(c):
        return c.get("author") not in stale_authors

    def fresh_category(c):
        return c.get("category") not in stale_categories

    def switches_register(c):
        # A row with no register set is a wildcard and always passes.
        return avoid_register is None or not c.get("register") or c["register"] != avoid_register

    # Order matters: the last constraint is the first one dropped when the
    # pool empties, so the strongest novelty guarantees sit at the top.
    return [
        ("no-verbatim-repeat", not_repeated),
        ("quote-cooldown", off_cooldown),
        ("author-cooldown", fresh_author),
        ("category-anti-streak", fresh_category),
        ("register-alternation", switches_register),
    ]


def pick_icon():
    """The day's page icon, drawn from ICONS with the same OS randomness."""
    return RNG.choice(ICONS)


def select(candidates, recent, today, cooldown_days):
    constraints = build_constraints(recent, today, cooldown_days)
    relaxed = []

    while True:
        pool = [c for c in candidates if all(pred(c) for _, pred in constraints)]
        if pool or not constraints:
            break
        relaxed.append(constraints.pop()[0])

    if not pool:
        raise SystemExit("pick_quote: no candidates supplied")

    # Deal without replacement: never repeat a quote until every quote in the
    # eligible pool has had a turn. This is what makes a year feel new.
    fewest = min(c.get("times_used") or 0 for c in pool)
    tier = [c for c in pool if (c.get("times_used") or 0) == fewest]

    return RNG.choice(tier), {
        "candidates_supplied": len(candidates),
        "eligible_after_constraints": len(pool),
        "tier_size": len(tier),
        "tier_times_used": fewest,
        "constraints_relaxed": relaxed,
        "cooldown_days": cooldown_days,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default=date.today().isoformat())
    ap.add_argument(
        "--cooldown-days",
        type=int,
        default=None,
        help="Quote cooldown. Defaults to 60%% of the corpus, min 90 days.",
    )
    ap.add_argument("--payload", default="-", help="JSON file, or - for stdin")
    args = ap.parse_args()

    raw = sys.stdin.read() if args.payload == "-" else open(args.payload).read()
    data = json.loads(raw)
    candidates = data.get("candidates") or []
    recent = data.get("recent") or []

    today = date.fromisoformat(args.today)
    cooldown = args.cooldown_days
    if cooldown is None:
        cooldown = max(90, int(len(candidates) * 0.6))

    pick, diagnostics = select(candidates, recent, today, cooldown)
    diagnostics["icon_pool"] = len(ICONS)
    json.dump(
        {"pick": pick, "icon": pick_icon(), "diagnostics": diagnostics},
        sys.stdout,
        ensure_ascii=False,
        indent=2,
    )
    print()


if __name__ == "__main__":
    main()
