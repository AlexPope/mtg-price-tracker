#!/usr/bin/env python3
"""Fetch prices for the tracked sets and write prices.json.

Sets are declared as data in data/sets.json - a set code plus a collector
number range - and everything else is derived from Scryfall: card names, LOTR
flavor names, TCGplayer product ids, and the ManaPool slug. Adding a set is a
few lines of JSON, not a hand-transcribed table of ids.

Scryfall is queried through its batch endpoint, so the whole run costs a
handful of requests rather than one per card. ManaPool has no such endpoint and
is still scraped a page at a time.
"""
import csv
import datetime
import json
import re
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path

SETS_FILE = Path("data/sets.json")
PRICES_FILE = Path("prices.json")

USER_AGENT = 'Mozilla/5.0'

# Scryfall asks for 50-100ms between requests; ManaPool has no published limit.
SCRYFALL_DELAY = 0.1
MANAPOOL_DELAY = 0.1

# Transient statuses worth retrying. Anything else (404, 403) won't change on retry.
RETRY_STATUSES = {408, 429, 500, 502, 503, 504}
HTTP_ATTEMPTS = 3
HTTP_TIMEOUT = 20

# Scryfall's /cards/collection accepts at most 75 identifiers per request.
SCRYFALL_BATCH_SIZE = 75

# Guard rails: refuse to write prices.json if the run degraded badly. A healthy
# run has 0 nulls across all cards, so these are generous.
MAX_FETCH_FAILURE_RATE = 0.10   # network/HTTP errors, per source
MAX_MANAPOOL_MISS_RATE = 0.50   # pages that loaded but had no parseable price

# ManaPool embeds prices in a script tag whose quoting has changed over time:
#   escaped JSON   \"marketPrices\":{\"price\": 8217,
#   plain JSON      "marketPrices":{"price":8217,
#   JS object       marketPrices:{price:8217,price_foil:9370}
# Tolerate all three so a quoting change doesn't silently null out every price.
MANAPOOL_PRICE_RE = re.compile(r'marketPrices\\?"?:\s*\{\s*\\?"?price\\?"?:\s*(\d+)')


class FetchError(Exception):
    """A network or HTTP failure.

    Deliberately distinct from a card that simply has no price listed - the
    former means our data is unreliable, the latter is a legitimate null.
    """


def http_request(url, accept, json_body=None, timeout=HTTP_TIMEOUT,
                 attempts=HTTP_ATTEMPTS):
    """GET, or POST when json_body is given, retrying transient failures.

    The body goes through a temp file rather than argv so a large batch payload
    can't run into command-line length or quoting limits.
    """
    cmd = [
        "curl", "-s", "--compressed",
        "--max-time", str(timeout),
        "-A", USER_AGENT,
        "-H", f"Accept: {accept}",
        # Append the status code on its own line so we can tell a real response
        # from an error page.
        "-w", "\n%{http_code}",
    ]

    body_file = None
    try:
        if json_body is not None:
            body_file = tempfile.NamedTemporaryFile(
                "w", suffix=".json", delete=False, encoding="utf-8")
            json.dump(json_body, body_file)
            body_file.close()
            cmd += ["-X", "POST",
                    "-H", "Content-Type: application/json",
                    "--data-binary", f"@{body_file.name}"]
        cmd.append(url)

        last_error = "no attempt made"
        for attempt in range(1, attempts + 1):
            result = subprocess.run(cmd, capture_output=True, text=False)

            if result.returncode != 0:
                # 28 = timeout, 6/7 = DNS/connection failure, etc.
                last_error = f"curl exited {result.returncode}"
            else:
                payload = result.stdout.decode("utf-8", errors="replace")
                text, _, status = payload.rpartition("\n")
                status = status.strip()
                if status == "200":
                    return text
                last_error = f"HTTP {status}"
                if not (status.isdigit() and int(status) in RETRY_STATUSES):
                    break

            if attempt < attempts:
                time.sleep(attempt)  # 1s, then 2s

        raise FetchError(f"{last_error} for {url}")
    finally:
        if body_file:
            Path(body_file.name).unlink(missing_ok=True)


def slugify(name):
    """Card name -> ManaPool URL slug.

    Verified to reproduce every previously hardcoded slug, including the
    awkward ones: Sméagol -> smeagol, Thespian's -> thespians,
    Galadriel of Lothlórien -> galadriel-of-lothlorien.
    """
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.replace("'", "").replace("’", "")
    return re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()


def load_sets():
    definitions = json.loads(SETS_FILE.read_text(encoding="utf-8"))
    required = {"key", "label", "subtitle", "set", "from", "to"}
    seen = set()
    for d in definitions:
        missing = required - set(d)
        if missing:
            raise SystemExit(f"{SETS_FILE}: entry {d.get('key', '?')} is missing {sorted(missing)}")
        if d["from"] > d["to"]:
            raise SystemExit(f"{SETS_FILE}: {d['key']} has from > to")
        if d["key"] in seen:
            raise SystemExit(f"{SETS_FILE}: duplicate key {d['key']}")
        seen.add(d["key"])
    return definitions


def card_numbers(definition):
    return [str(n) for n in range(definition["from"], definition["to"] + 1)]


def fetch_scryfall_cards(definitions, stats):
    """Fetch every tracked card from Scryfall in batches.

    Returns {(set, collector_number): card}. Cards that could not be fetched
    are simply absent; the caller records them as errors.
    """
    wanted = []
    for d in definitions:
        wanted += [(d["set"], num) for num in card_numbers(d)]
    # The same card can appear in two sections; only ask for it once.
    unique = sorted(set(wanted))

    found = {}
    for i in range(0, len(unique), SCRYFALL_BATCH_SIZE):
        chunk = unique[i:i + SCRYFALL_BATCH_SIZE]
        payload = {"identifiers": [{"set": s, "collector_number": n} for s, n in chunk]}
        batch_no = i // SCRYFALL_BATCH_SIZE + 1
        print(f"  Scryfall batch {batch_no}: {len(chunk)} cards")
        try:
            body = http_request("https://api.scryfall.com/cards/collection",
                                accept="application/json", json_body=payload)
            data = json.loads(body)
        except (FetchError, json.JSONDecodeError) as e:
            # One failed batch is up to 75 cards; record each so the failure
            # rate reflects the real damage.
            for s, n in chunk:
                stats.scryfall_errors.append((f"{s}/{n}", str(e)))
            continue

        for card in data.get("data", []):
            found[(card["set"], card["collector_number"])] = card
        for miss in data.get("not_found", []):
            key = f"{miss.get('set')}/{miss.get('collector_number')}"
            stats.scryfall_errors.append((key, "not found on Scryfall"))

        time.sleep(SCRYFALL_DELAY)

    return found


def scryfall_image(card):
    images = card.get("image_uris") or {}
    # Fallback for double-faced cards
    if not images and card.get("card_faces"):
        images = card["card_faces"][0].get("image_uris") or {}
    return images.get("normal") or images.get("large") or images.get("small")


def fetch_manapool_price(set_code, num, slug):
    """Returns the NM non-foil price, or None if the page lists no price.

    Raises FetchError if the page itself could not be fetched.
    """
    url = f"https://manapool.com/card/{set_code}/{num}/{slug}"
    html = http_request(url, accept="text/html,application/xhtml+xml")
    m = MANAPOOL_PRICE_RE.search(html)
    return int(m.group(1)) / 100.0 if m else None


def fetch_owned(definitions):
    """Returns {(set, cn): {nonfoil, foil}} from the latest Moxfield CSV."""
    data_dir = Path("data")
    # Sort by filename, not mtime: the export timestamp is already in the name,
    # and a fresh `git checkout` in CI stamps every file with the same mtime.
    csv_files = sorted(data_dir.glob("*.csv"))
    if not csv_files:
        print("  No Moxfield CSV snapshot found in data/; ownership will be skipped")
        return {}

    latest_file = csv_files[-1]
    print(f"  Using latest Moxfield CSV snapshot: {latest_file.name}")

    tracked = set()
    for d in definitions:
        tracked |= {(d["set"], num) for num in card_numbers(d)}

    owned = {}
    with latest_file.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            key = ((row.get("Edition") or "").strip().lower(),
                   (row.get("Collector Number") or "").strip())
            if key not in tracked:
                continue
            entry = owned.setdefault(key, {"nonfoil": False, "foil": False})
            if (row.get("Foil") or "").strip().lower() == "foil":
                entry["foil"] = True
            else:
                entry["nonfoil"] = True

    print(f"  Moxfield CSV snapshot: found {len(owned)} owned cards across the tracked sets")
    return owned


class RunStats:
    """Tracks how much of a run actually succeeded, so main() can refuse to
    publish a prices.json built from failed requests."""

    def __init__(self):
        self.cards = 0
        self.scryfall_errors = []
        self.manapool_errors = []
        self.manapool_misses = []

    def report(self):
        for label, errors in (("Scryfall", self.scryfall_errors),
                              ("ManaPool", self.manapool_errors)):
            if errors:
                print(f"\n{len(errors)} {label} request(s) failed:")
                for name, err in errors[:10]:
                    print(f"  - {name}: {err}")
                if len(errors) > 10:
                    print(f"  ... and {len(errors) - 10} more")
        if self.manapool_misses:
            print(f"\n{len(self.manapool_misses)} ManaPool page(s) had no parseable price: "
                  f"{', '.join(self.manapool_misses[:10])}"
                  f"{' ...' if len(self.manapool_misses) > 10 else ''}")

    def failures(self):
        """Returns a list of human-readable reasons the run is untrustworthy."""
        if not self.cards:
            return ["no cards were processed"]

        reasons = []
        for label, errors, limit in (
            ("Scryfall", self.scryfall_errors, MAX_FETCH_FAILURE_RATE),
            ("ManaPool", self.manapool_errors, MAX_FETCH_FAILURE_RATE),
        ):
            rate = len(errors) / self.cards
            if rate > limit:
                reasons.append(
                    f"{label} failed for {len(errors)}/{self.cards} cards "
                    f"({rate:.0%} > {limit:.0%} allowed)"
                )

        miss_rate = len(self.manapool_misses) / self.cards
        if miss_rate > MAX_MANAPOOL_MISS_RATE:
            reasons.append(
                f"ManaPool price could not be parsed for {len(self.manapool_misses)}/{self.cards} "
                f"cards ({miss_rate:.0%} > {MAX_MANAPOOL_MISS_RATE:.0%} allowed) - "
                f"their page format may have changed"
            )
        return reasons


def build_card_row(definition, num, card, owned, stats):
    """Assemble one output row. `card` is the Scryfall record, or None."""
    set_code = definition["set"]
    stats.cards += 1

    if card is None:
        # Already recorded as a Scryfall error by the batch fetch.
        return None

    name = card["name"]
    flavor = card.get("flavor_name")
    display_name = f"{flavor} ({name})" if flavor else name
    slug = slugify(name)

    price = card.get("prices", {}).get("usd")
    tcg_price = float(price) if price else None

    print(f"  {name}...")
    try:
        mp_price = fetch_manapool_price(set_code, num, slug)
        if mp_price is None:
            stats.manapool_misses.append(name)
        time.sleep(MANAPOOL_DELAY)
    except FetchError as e:
        stats.manapool_errors.append((name, str(e)))
        mp_price = None

    tcg_id = card.get("tcgplayer_id")
    tcg_url = (f"https://www.tcgplayer.com/product/{tcg_id}"
               f"?Condition=Near+Mint&Printing=Normal") if tcg_id else \
              (card.get("purchase_uris") or {}).get("tcgplayer", "")

    owned_entry = owned.get((set_code, num))
    return {
        "display_name": display_name,
        "mtg_name": name,
        "tcg_price": tcg_price,
        "tcg_url": tcg_url,
        "mp_price": mp_price,
        "mp_url": f"https://manapool.com/card/{set_code}/{num}/{slug}?conditions=NM&finish=nonfoil",
        "image_url": scryfall_image(card),
        "collected_nonfoil": owned_entry["nonfoil"] if owned_entry else False,
        "collected_foil": owned_entry["foil"] if owned_entry else False,
    }


def main():
    definitions = load_sets()
    print(f"Tracking {len(definitions)} sets from {SETS_FILE}")

    print("Reading Moxfield CSV snapshot...")
    owned = fetch_owned(definitions)

    stats = RunStats()
    print("Fetching cards from Scryfall...")
    cards = fetch_scryfall_cards(definitions, stats)

    sections = {}
    for d in definitions:
        print(f"Fetching ManaPool prices for {d['label']}...")
        rows = []
        for num in card_numbers(d):
            row = build_card_row(d, num, cards.get((d["set"], num)), owned, stats)
            if row:
                rows.append(row)
        rows.sort(key=lambda x: x["tcg_price"] if x["tcg_price"] is not None else float("inf"))
        sections[d["key"]] = rows

    stats.report()

    reasons = stats.failures()
    if reasons:
        print("\nRefusing to write prices.json - this run is not trustworthy:")
        for reason in reasons:
            print(f"  * {reason}")
        print("\nThe existing prices.json has been left untouched.")
        sys.exit(1)

    output = {
        "updated_at": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        # The front end builds its tabs from this, so adding a set needs no
        # HTML change.
        "tabs": [{"key": d["key"], "label": d["label"], "subtitle": d["subtitle"]}
                 for d in definitions],
        **sections,
    }
    PRICES_FILE.write_text(json.dumps(output, indent=2), encoding="utf-8")

    all_rows = [r for rows in sections.values() for r in rows]
    owned_count = sum(1 for r in all_rows if r["collected_nonfoil"] or r["collected_foil"])
    counts = " + ".join(f"{len(sections[d['key']])} {d['key']}" for d in definitions)
    print(f"\nDone. {counts} = {len(all_rows)} cards, {owned_count} owned.")


if __name__ == "__main__":
    main()
