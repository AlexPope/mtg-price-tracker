# MTG Collection Price Tracker

A price tracker for special Magic: the Gathering sets, comparing TCGplayer and
ManaPool prices against what I actually own.

**Live site: https://alexpope.github.io/mtg-price-tracker/**

For each tracked set it shows the complete card list, both vendors' prices with
the cheaper one highlighted, a 30-day price trend, and how many copies of the
card are already in my collection. The list can be filtered by card name and
narrowed to just the missing or just the collected cards, each tab keeping its
own filter. The page follows the system light/dark setting, with a toggle that
overrides it. Prices refresh automatically once a day, and the header says
when the next run is due, in the reader's own timezone.

Navigation is two levels. A **tab** is a set as the collection thinks of it —
`Hobbit — HOB`, `Lord of the Rings — LTR` — and the **chips** under it are that
set's treatments — for HOB: Main Set, Full Art Lands, Seasonal Lands,
Borderless Scene, Dragon Hoard Frame, Book Cover. The first chip is
**All**, which unions them, so "everything in HOB I am still missing, cheapest
first" is one view rather than four tabs read side by side. The summary cards
follow the chip, which makes the set-wide cost-to-complete a number the page
can actually show; the search box and the collected control do not, so
filtering to one card never claims the set is worth $4.

The current view lives in the URL as `#hob/hob_scene`, so a reload comes back
to where you were and a single treatment can be linked to directly.

The two collected columns are copy counts taken from the export's `Count`
column, summed across the rows Moxfield splits a card into (one per condition,
language and printing). A card I own none of shows a **blank** cell rather than
a `0` — the page is mostly missing cards, and a column of zeroes reads as
noise.

All prices are **Near Mint, non-foil**. Foil ownership is counted in a separate
column because the Moxfield export distinguishes it, but foil *prices* are not
tracked — the non-foil price is the number of interest.

## How it works

```
data/sets.json  ──┐
                  ├─→ scripts/fetch_prices.py ──→ prices.json  ──┐
Scryfall (batch) ─┤                                             ├─→ index.html
ManaPool (scrape)─┘                                             │
                                                                │
git history of prices.json → scripts/build_history.py → history.json
```

Nothing is built or bundled — `index.html` is a single static page that fetches
the two JSON files at runtime. GitHub Pages serves the repository as-is.

| File | Role |
|---|---|
| `data/sets.json` | The only file you edit to track a new set or treatment |
| `data/*.csv` | Moxfield collection exports; the newest by filename wins |
| `scripts/fetch_prices.py` | Fetches prices, writes `prices.json` |
| `scripts/build_history.py` | Replays git history, writes `history.json` |
| `index.html` | The whole front end |
| `prices.json` / `history.json` | Generated — do not edit by hand |

Three workflows drive it: `update-prices.yml` runs daily at 11:07 UTC — and on
any push that adds a `data/*.csv` export — then commits the regenerated data,
`pages.yml` redeploys the site afterwards, and `ci.yml` runs the test suite on
every push and pull request.

The daily job takes roughly 13 minutes, and almost all of it is one ManaPool
page fetch per card at about 0.6s each. That scales linearly with the number of
tracked cards, so it is the cost to watch when adding a set: Scryfall is
batched 75 at a time and costs seconds, and `build_history.py` replays the
whole git history in about three. The 6-hour job limit is a long way off, but
at ~0.6s per card it would arrive somewhere north of 30,000 cards.

That cannot loop: `update-prices.yml` commits only `prices.json` and
`history.json`, neither of which matches its `data/*.csv` path filter, and a
push made with `GITHUB_TOKEN` does not start another workflow run regardless.
`pages.yml` ignores `data/*.csv` on push for the opposite reason — the served
page never reads the CSV, so deploying on the export alone would only publish
the old numbers a few minutes before the real update replaced them.

## Adding a set or a treatment

[`data/sets.json`](data/sets.json) is the only file to edit — no Python and no
HTML to touch. It has two lists, mirroring the two levels of the navigation:

```json
{
  "groups": [
    { "key": "eos", "label": "Edge of Eternities — EOS" }
  ],
  "sections": [
    { "key": "stellar_sights_i", "group": "eos", "label": "Stellar Sights I",
      "set": "eos", "from": 1, "to": 45 }
  ]
}
```

A **group** is a primary tab:

| Field | Meaning |
|---|---|
| `key` | Panel DOM id suffix and the URL fragment. Must be unique |
| `label` | Text on the tab button |

A **section** is one chip under it:

| Field | Meaning |
|---|---|
| `key` | Section name in `prices.json`. Must be unique and should not change once data exists |
| `group` | The `key` of the group it belongs to. Must resolve |
| `label` | Text on the chip |
| `set` | Scryfall set code, lowercase |
| `from` / `to` | Collector number range, inclusive |

Everything else — card names, LOTR flavor names, TCGplayer product ids, images
and the ManaPool URL slug — is derived from Scryfall at fetch time.

Adding a **treatment** to a set already tracked is one entry in `sections`.
Adding a **set** is one entry in each list. A section larger than 75 cards is
fine — LTR's Main Set is 279 — and requests are batched automatically.

Grouping is declared rather than inferred from the label, because it is not
derivable in general: a treatment can span two set codes, and two set codes can
be separate tabs, so which cards belong where is a decision only the file can
record. `load_sets` rejects a section whose `group` does not resolve and a
group with no sections — the first would render nowhere, the second is a tab
that opens onto nothing.

A section need not cover a whole set, and the numbers it skips are simply not
tracked: HOC declares five treatments across #1–52 and #93–106, and #53–92 is
absent from the page entirely.

Ranges are integer runs, so a collector number carrying a letter suffix is not
covered by one. That keeps doing useful work by accident, because the suffixed
printings so far are exactly the ones there is no point pricing:

- LTR #1–271 holds 273 cards by Scryfall's reckoning. The two extras are
  `A-103` and `A-246`, the Alchemy digital-only rebalances of Orcish Bowmasters
  and The One Ring — no physical printing to price or own.
- LTR #731–750 holds 40. Half are `731z`–`750z`, the serialized double-rainbow
  posters, which have no USD price on Scryfall at all.

So a Scryfall search by collector number can legitimately return more cards
than the matching section tracks. Check the suffixed ones before assuming a
range is wrong.

A section that is *not* one contiguous run — a treatment split across two
stretches of numbers, or across two set codes — replaces the inline
`set`/`from`/`to` with a `ranges` list of exactly those three fields. The
inline form is the one-range case of the same thing, so nothing else changes.
Main Set is the live example, being #1–193 plus the #321 bundle promo:

```json
{
  "key": "hob_main", "group": "hob", "label": "Main Set",
  "ranges": [
    { "set": "hob", "from": 1, "to": 193 },
    { "set": "hob", "from": 321, "to": 321 }
  ]
}
```

Ranges are listed in the order given and a card claimed by two of them appears
once, so overlapping ranges cannot produce a duplicate row. The unioned "All"
view applies the same rule one level up: where two treatments in a group claim
the same collector number, the first chip's row is the one shown.

The one derived value with no second source to cross-check is the ManaPool
slug, so that is the thing to eyeball for an unusual set: it is the card name
lowercased, with diacritics stripped and apostrophes removed
(`Sméagol, Helpful Guide` → `smeagol-helpful-guide`).

## Updating what I own

Export the collection from Moxfield as CSV, drop it in `data/`, and push. The
`Update Prices` workflow triggers on any push touching `data/*.csv`, so the
site republishes within a few minutes instead of waiting for the next daily
run. Nothing else to do — no local Python, no manual workflow dispatch.

The newest export wins, and *newest* means the date parsed out of the filename,
not the order the names happen to sort in. **Keep the timestamped export name**
(`moxfield_haves_2026-08-21-1715Z.csv`): a file whose name carries no date
stops the run rather than being ignored or trusted, because either would risk
quietly publishing a stale collection. Old exports can stay in `data/`
indefinitely; only the newest is read.

There is no automated Moxfield sync: `api2.moxfield.com` is not a public API and
blocks unauthenticated automation, so the export is a manual step.

## Running locally

Only the standard library and `curl` are needed — no dependencies to install.

```sh
python scripts/fetch_prices.py     # ~12 min at 1,157 cards: refreshes prices.json
python scripts/build_history.py    # replays git history into history.json
python -m http.server 8765         # then open http://localhost:8765
```

The local server matters: opening `index.html` directly gives a `file://` page,
and the browser blocks its `fetch()` of `prices.json`, so every price shows as
unavailable.

## Tests

```sh
python -m unittest discover -s tests          # offline, well under a second
RUN_NETWORK_TESTS=1 python -m unittest discover -s tests   # also checks Scryfall
```

The offline suite covers the derivation rules that replaced the old hardcoded
card tables (the slug cases, `flavor_name` handling, TCGplayer URL assembly),
the guard-rail thresholds, `data/sets.json` and Moxfield CSV validation, and
the invariants between `prices.json` and `history.json` — every priced card has
a series, the series align with the date axis, every section has a chip, every
chip resolves to a group, and no group is left empty.

The network test is opt-in so the suite stays fast and deterministic. It
confirms every tracked card still resolves on Scryfall with a `tcgplayer_id`
and a well-formed slug, which is the check that made deleting the hardcoded
tables safe. Worth running after adding a set.

`ci.yml` runs the offline suite on every push and pull request, against Python
3.11 (what the daily job pins) and 3.14 (what the scripts are developed
against). The daily workflow *also* runs it after regenerating the data and
before committing it — CI checks the code, the daily run checks the freshly
built data, and both are needed.

## When something breaks

`fetch_prices.py` **refuses to write `prices.json` if a run goes badly** — more
than 10% of cards failing at either vendor, or more than 50% of ManaPool pages
returning no parseable price. It prints what broke, exits non-zero, and leaves
the previous data in place.

This exists because it already happened: ManaPool changed the markup their
prices are embedded in, the scrape silently returned `None` for every card, and
the job committed 150 nulls a day while reporting success. A red workflow run is
the intended outcome — it means the guard caught something.

The likeliest future failure is that same scrape breaking again. The parser
tolerates the three quoting styles seen so far; a fourth would trip the 50%
threshold and stop the run rather than publish nulls.

Ownership is guarded the same way, because it can fail the same way: it comes
from one CSV with no second source to cross-check it against, and every way of
misreading it — a renamed column, a set code that no longer matches, an empty
export — zeroes the whole collection at once rather than shaving a few cards
off it. So there are two checks and no threshold between them:

- the export must still have its `Count`, `Edition`, `Collector Number` and
  `Foil` columns, or the run stops immediately, before any network work;
- if a run matches **no** owned cards when the previous `prices.json` matched
  some, it refuses to publish. A collection that was already empty is fine —
  the check only fires on a drop to zero from something.

The consequence worth knowing: genuinely selling the entire collection trips
the guard once. Delete `data/*.csv` if that is really what happened.

The quantity itself is deliberately not guarded the same way, because it cannot
fail the same way: a row exists because the card is owned, so a `Count` that
will not parse is read as one copy rather than zero. That errs toward showing a
card as collected — the one direction that never quietly loses a card.

`build_history.py` needs real git history and the workflow checks out with
`fetch-depth: 0`. It rebuilds the series from scratch every run rather than
appending, so a bad run cannot corrupt it.
