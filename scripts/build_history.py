#!/usr/bin/env python3
"""Build history.json — a per-card price time series mined from git history.

Every scheduled run commits a fresh prices.json, so the repository already
contains a daily snapshot going back to the first commit. This script replays
those revisions into a compact series the front end can draw sparklines from.

It rebuilds from scratch each time rather than appending to an existing file,
which makes it idempotent and self-healing: a bad run can't corrupt the series,
because the series is never read back in. That does mean CI needs full history
(actions/checkout with fetch-depth: 0), not the default shallow clone.
"""
import datetime
import json
import re
import subprocess
import sys
from pathlib import Path

PRICES_FILE = "prices.json"
HISTORY_FILE = "history.json"

# Cap the series so the file can't grow without bound. At 150 cards this is
# roughly 2KB per day retained.
HISTORY_DAYS = 180

# Card identity has to survive schema changes: sections have been renamed
# (cards -> realms_and_relics + showcase) and rows are re-sorted by price on
# every run, so neither position nor section is stable. mp_url is present in
# every revision ever committed and encodes set + collector number, which is
# the one genuinely stable key.
#   https://manapool.com/card/ltc/370/mouth-of-ronom?conditions=NM -> ltc/370
CARD_KEY_RE = re.compile(r"/card/([^/]+)/([^/?]+)")


def card_key(entry):
    m = CARD_KEY_RE.search(entry.get("mp_url") or "")
    return f"{m.group(1)}/{m.group(2)}" if m else None


def extract_prices(doc):
    """Returns {card_key: (tcg_price, mp_price)} from one prices.json document."""
    out = {}
    for value in doc.values():
        if not isinstance(value, list):
            continue
        for entry in value:
            if not isinstance(entry, dict):
                continue
            key = card_key(entry)
            if key:
                out[key] = (entry.get("tcg_price"), entry.get("mp_price"))
    return out


def git(*args):
    result = subprocess.run(["git", *args], capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout


def iter_revisions():
    """Yields (date, prices_dict) for each committed prices.json, oldest first.

    Where a day has several commits the last one wins, which is what the caller
    gets by iterating in chronological order and overwriting.
    """
    log = git("log", "--format=%H %cI", "--", PRICES_FILE).strip().splitlines()
    for line in reversed(log):  # oldest first
        sha, iso = line.split()
        day = datetime.datetime.fromisoformat(iso).astimezone(
            datetime.timezone.utc).date().isoformat()
        try:
            doc = json.loads(git("show", f"{sha}:{PRICES_FILE}"))
        except (RuntimeError, json.JSONDecodeError):
            # A revision that predates the file or was committed malformed is
            # simply a day we have no data for.
            continue
        yield day, doc


def build():
    current_doc = json.loads(Path(PRICES_FILE).read_text(encoding="utf-8"))
    # Only track cards that still exist, so retired sets don't accumulate.
    tracked = set(extract_prices(current_doc))
    if not tracked:
        raise SystemExit(f"No cards with a usable key found in {PRICES_FILE}")

    by_day = {}
    for day, doc in iter_revisions():
        by_day[day] = extract_prices(doc)

    # The working-tree prices.json is newer than anything committed - in CI it
    # was written moments ago and has not been committed yet.
    today = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
    by_day[today] = extract_prices(current_doc)

    dates = sorted(by_day)[-HISTORY_DAYS:]
    cards = {}
    for key in sorted(tracked):
        tcg, mp = [], []
        for day in dates:
            t, m = by_day[day].get(key, (None, None))
            tcg.append(round(t, 2) if isinstance(t, (int, float)) else None)
            mp.append(round(m, 2) if isinstance(m, (int, float)) else None)
        # Skip cards with no recorded price at all - nothing to plot.
        if any(v is not None for v in tcg) or any(v is not None for v in mp):
            cards[key] = {"tcg": tcg, "mp": mp}

    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc)
                                 .strftime("%Y-%m-%dT%H:%M:%SZ"),
        "dates": dates,
        "cards": cards,
    }


def main():
    history = build()
    Path(HISTORY_FILE).write_text(json.dumps(history, separators=(",", ":")),
                                  encoding="utf-8")

    days = len(history["dates"])
    cards = len(history["cards"])
    size_kb = Path(HISTORY_FILE).stat().st_size / 1024
    covered = sum(
        1 for c in history["cards"].values()
        if sum(v is not None for v in c["tcg"]) > 1
    )
    print(f"Wrote {HISTORY_FILE}: {cards} cards x {days} days "
          f"({history['dates'][0]} to {history['dates'][-1]}), {size_kb:.0f}KB")
    print(f"  {covered}/{cards} cards have more than one data point")

    if days < 2:
        print("  Only one day of history - sparklines will not render yet.",
              file=sys.stderr)


if __name__ == "__main__":
    main()
