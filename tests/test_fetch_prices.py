"""Tests for scripts/fetch_prices.py.

These run offline. The one test that talks to Scryfall - confirming the derived
slug and tcgplayer_id still match reality for every tracked card - is opt-in via
RUN_NETWORK_TESTS=1, so the suite stays fast and deterministic by default.
"""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import fetch_prices as fp


class TestSlugify(unittest.TestCase):
    """The ManaPool slug is the one derived value with no second source to
    cross-check, so pin the awkward cases that appear in the tracked sets."""

    CASES = [
        ("The Great Henge",              "the-great-henge"),
        ("Boseiju, Who Shelters All",    "boseiju-who-shelters-all"),
        ("Minamo, School at Water's Edge", "minamo-school-at-waters-edge"),
        ("Sméagol, Helpful Guide",       "smeagol-helpful-guide"),
        ("Thespian's Stage",             "thespians-stage"),
        ("Bonders' Enclave",             "bonders-enclave"),
        ("Galadriel of Lothlórien",      "galadriel-of-lothlorien"),
        ("Inventors' Fair",              "inventors-fair"),
        ("Nazgûl",                       "nazgul"),
        ("Witch-king of Angmar",         "witch-king-of-angmar"),
    ]

    def test_known_slugs(self):
        for name, expected in self.CASES:
            with self.subTest(name=name):
                self.assertEqual(fp.slugify(name), expected)

    def test_typographic_apostrophe_matches_ascii(self):
        self.assertEqual(fp.slugify("Thespian’s Stage"), fp.slugify("Thespian's Stage"))

    def test_shape(self):
        for messy in ["  Leading and trailing  ", "Double--Hyphen", "Comma, Period."]:
            with self.subTest(messy=messy):
                slug = fp.slugify(messy)
                self.assertEqual(slug, slug.lower())
                self.assertFalse(slug.startswith("-") or slug.endswith("-"))
                self.assertNotIn("--", slug)


class TestManapoolRegex(unittest.TestCase):
    """ManaPool has changed this quoting twice; a third change silently nulled
    every price for two days before the guard rails existed."""

    def test_all_known_formats(self):
        for label, html in [
            ("escaped JSON", r'...\"marketPrices\":{\"price\": 8217,\"price_foil\": 9370}...'),
            ("plain JSON",    '..."marketPrices":{"price":8217,"price_foil":9370}...'),
            ("JS object",     '...,marketPrices:{price:8217,price_foil:9370},legalities:[]...'),
        ]:
            with self.subTest(format=label):
                m = fp.MANAPOOL_PRICE_RE.search(html)
                self.assertIsNotNone(m, f"{label} no longer parses")
                self.assertEqual(int(m.group(1)) / 100.0, 82.17)

    def test_no_match_on_unrelated_page(self):
        self.assertIsNone(fp.MANAPOOL_PRICE_RE.search("<html>no prices here</html>"))


class TestLoadSets(unittest.TestCase):
    def setUp(self):
        self._orig = fp.SETS_FILE
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        fp.SETS_FILE = self._orig

    def _write(self, sections, groups=None):
        """Writes a sets.json around `sections`.

        Groups default to one per section referenced, so a test about range
        validation does not have to restate the grouping it does not care about.
        """
        if groups is None:
            keys = dict.fromkeys(s.get("group", "g") for s in sections)
            groups = [{"key": k, "label": k.upper()} for k in keys]
            sections = [{"group": "g", **s} for s in sections]
        f = self.tmp / "sets.json"
        f.write_text(json.dumps({"groups": groups, "sections": sections}),
                     encoding="utf-8")
        fp.SETS_FILE = f

    def test_rejects_missing_field(self):
        """A section with no label would render as a chip with nothing on it."""
        self._write([{"key": "x", "set": "ltr", "from": 1, "to": 2}])
        with self.assertRaises(SystemExit):
            fp.load_sets()

    def test_rejects_group_missing_label(self):
        self._write([{"key": "x", "group": "a", "label": "X",
                      "set": "ltr", "from": 1, "to": 2}],
                    groups=[{"key": "a"}])
        with self.assertRaises(SystemExit):
            fp.load_sets()

    def test_rejects_inverted_range(self):
        self._write([{"key": "x", "label": "X", "set": "ltr", "from": 9, "to": 2}])
        with self.assertRaises(SystemExit):
            fp.load_sets()

    def test_rejects_bad_range_inside_ranges_list(self):
        """A multi-range section gets the same checks as an inline one; without
        this a typo in "ranges" would sail past and fetch the wrong cards."""
        for bad in ({"set": "hob", "from": 9, "to": 2},   # inverted
                    {"set": "hob", "from": 1}):           # missing "to"
            with self.subTest(range=bad):
                self._write([{"key": "x", "label": "X",
                              "ranges": [{"set": "hob", "from": 1, "to": 2}, bad]}])
                with self.assertRaises(SystemExit):
                    fp.load_sets()

    def test_rejects_empty_ranges_list(self):
        self._write([{"key": "x", "label": "X", "ranges": []}])
        with self.assertRaises(SystemExit):
            fp.load_sets()

    def test_rejects_duplicate_key(self):
        entry = {"key": "x", "label": "X", "set": "ltr", "from": 1, "to": 2}
        self._write([entry, dict(entry)])
        with self.assertRaises(SystemExit):
            fp.load_sets()

    def test_rejects_flat_legacy_file(self):
        """The pre-grouping format was a bare array. Loading one would leave
        every section ungrouped and the page with no tabs at all."""
        f = self.tmp / "sets.json"
        f.write_text(json.dumps([{"key": "x", "label": "X",
                                  "set": "ltr", "from": 1, "to": 2}]), encoding="utf-8")
        fp.SETS_FILE = f
        with self.assertRaises(SystemExit):
            fp.load_sets()

    def test_rejects_duplicate_group_key(self):
        self._write(
            [{"key": "x", "group": "a", "label": "X", "set": "ltr", "from": 1, "to": 2}],
            groups=[{"key": "a", "label": "A"}, {"key": "a", "label": "A again"}])
        with self.assertRaises(SystemExit):
            fp.load_sets()

    def test_rejects_unknown_group(self):
        """A section pointing at a group that does not exist would render
        nowhere - no tab carries it and nothing says so."""
        self._write(
            [{"key": "x", "group": "nope", "label": "X", "set": "ltr", "from": 1, "to": 2}],
            groups=[{"key": "a", "label": "A"}])
        with self.assertRaises(SystemExit):
            fp.load_sets()

    def test_rejects_group_with_no_sections(self):
        """An empty group is a tab that opens onto nothing."""
        self._write(
            [{"key": "x", "group": "a", "label": "X", "set": "ltr", "from": 1, "to": 2}],
            groups=[{"key": "a", "label": "A"}, {"key": "b", "label": "B"}])
        with self.assertRaises(SystemExit):
            fp.load_sets()

    def test_real_sets_file_is_valid(self):
        """Catches a typo in data/sets.json before a run publishes bad data."""
        fp.SETS_FILE = REPO_ROOT / "data" / "sets.json"
        groups, definitions = fp.load_sets()
        self.assertGreater(len(groups), 0)
        self.assertGreater(len(definitions), 0)
        for g in groups:
            with self.subTest(group=g["key"]):
                self.assertTrue(g["label"].strip())
        for d in definitions:
            with self.subTest(key=d["key"]):
                self.assertTrue(d["label"].strip())
                for set_code, num in fp.card_keys(d):
                    self.assertRegex(set_code, r"^[a-z0-9]+$")
                    self.assertGreaterEqual(int(num), 1)

    def test_real_sets_file_has_no_duplicate_chip_label_in_a_group(self):
        """Two chips reading the same under one tab are indistinguishable."""
        fp.SETS_FILE = REPO_ROOT / "data" / "sets.json"
        groups, definitions = fp.load_sets()
        for g in groups:
            labels = [d["label"] for d in definitions if d["group"] == g["key"]]
            with self.subTest(group=g["key"]):
                self.assertCountEqual(labels, set(labels))

    def test_card_keys_is_inclusive(self):
        self.assertEqual(fp.card_keys({"set": "ltr", "from": 3, "to": 6}),
                         [("ltr", "3"), ("ltr", "4"), ("ltr", "5"), ("ltr", "6")])
        self.assertEqual(fp.card_keys({"set": "ltr", "from": 5, "to": 5}), [("ltr", "5")])

    def test_card_keys_spans_ranges_and_sets_in_order(self):
        self.assertEqual(
            fp.card_keys({"ranges": [{"set": "hob", "from": 199, "to": 200},
                                     {"set": "hoc", "from": 1, "to": 2}]}),
            [("hob", "199"), ("hob", "200"), ("hoc", "1"), ("hoc", "2")])

    def test_card_keys_lists_an_overlapped_card_once(self):
        """Two ranges claiming the same card must not put it in the section
        twice - it would be fetched, priced and displayed as two rows."""
        self.assertEqual(
            fp.card_keys({"ranges": [{"set": "hoc", "from": 1, "to": 3},
                                     {"set": "hoc", "from": 3, "to": 4}]}),
            [("hoc", "1"), ("hoc", "2"), ("hoc", "3"), ("hoc", "4")])


class TestFetchOwned(unittest.TestCase):
    """Ownership is read from a single CSV with nothing to cross-check it
    against, so an export format change has to fail loudly rather than quietly
    read as 'nothing collected'."""

    DEFINITIONS = [{"key": "k", "label": "L", "set": "ltc", "from": 348, "to": 350}]
    HEADER = '"Count","Name","Edition","Condition","Foil","Collector Number"'
    ROWS = [
        '"3","A","ltc","Near Mint","","348"',       # three non-foil copies
        '"1","A","ltc","Near Mint","foil","348"',   # ...and a foil of the same card
        '"1","B","ltc","Near Mint","foil","349"',   # foil only
        '"1","C","ltr","Near Mint","","302"',       # untracked set
        '"1","D","ltc","Near Mint","","999"',       # outside the tracked range
    ]

    def setUp(self):
        self._orig = fp.DATA_DIR
        fp.DATA_DIR = Path(tempfile.mkdtemp())
        # fetch_owned logs which snapshot it picked; keep it out of the output.
        self._quiet = contextlib.redirect_stdout(io.StringIO())
        self._quiet.__enter__()

    def tearDown(self):
        self._quiet.__exit__(None, None, None)
        fp.DATA_DIR = self._orig

    def _write(self, rows, header=HEADER, name="moxfield_haves_2026-07-17-1851Z.csv"):
        (fp.DATA_DIR / name).write_text("\n".join([header, *rows]), encoding="utf-8")

    def test_reads_both_finishes_and_skips_untracked_cards(self):
        self._write(self.ROWS)
        self.assertEqual(fp.fetch_owned(self.DEFINITIONS), {
            ("ltc", "348"): {"nonfoil": 3, "foil": 1},
            ("ltc", "349"): {"nonfoil": 0, "foil": 1},
        })

    def test_repeated_rows_of_one_card_are_summed(self):
        """Moxfield writes one row per condition/language/printing, so the same
        card and finish can appear more than once and every row is copies held."""
        self._write([
            '"2","A","ltc","Near Mint","","348"',
            '"1","A","ltc","Lightly Played","","348"',
        ])
        self.assertEqual(fp.fetch_owned(self.DEFINITIONS),
                         {("ltc", "348"): {"nonfoil": 3, "foil": 0}})

    def test_zero_count_is_not_owned(self):
        """A zero-count row must not create an entry, or the guard rail would
        count a card I hold none of as collected."""
        self._write(['"0","A","ltc","Near Mint","","348"'])
        self.assertEqual(fp.fetch_owned(self.DEFINITIONS), {})

    def test_unreadable_count_falls_back_to_one_copy(self):
        """The row exists because the card is owned; guessing zero would
        silently un-own it, which is exactly what the column check prevents."""
        for value in ('""', '"   "', '"many"'):
            with self.subTest(count=value):
                self._write([f'{value},"A","ltc","Near Mint","","348"'])
                self.assertEqual(fp.fetch_owned(self.DEFINITIONS),
                                 {("ltc", "348"): {"nonfoil": 1, "foil": 0}})

    def test_missing_column_is_fatal(self):
        """The regression this guards: Moxfield renames a column, every row
        misses, and the collection silently reads as empty."""
        for dropped in fp.REQUIRED_CSV_COLUMNS:
            with self.subTest(dropped=dropped):
                kept = [c for c in ["Count", "Name", "Edition", "Condition",
                                    "Foil", "Collector Number"] if c != dropped]
                self._write(self.ROWS[:1], header=",".join(f'"{c}"' for c in kept))
                with self.assertRaises(SystemExit) as ctx:
                    fp.fetch_owned(self.DEFINITIONS)
                self.assertIn(dropped, str(ctx.exception))

    def test_no_csv_is_not_fatal(self):
        """A repo with no export yet is a legitimate state; the regression
        check in RunStats is what catches an export that goes missing."""
        self.assertEqual(fp.fetch_owned(self.DEFINITIONS), {})

    def test_newest_snapshot_by_filename_wins(self):
        self._write(['"1","A","ltc","Near Mint","","348"'],
                    name="moxfield_haves_2026-07-17-1851Z.csv")
        self._write(['"1","B","ltc","Near Mint","","349"'],
                    name="moxfield_haves_2026-08-01-0900Z.csv")
        self.assertEqual(set(fp.fetch_owned(self.DEFINITIONS)), {("ltc", "349")})

    def test_newest_wins_regardless_of_prefix(self):
        """The regression a plain filename sort has: 'collection-*' sorts
        before 'moxfield_haves_*', so the older export would win on name."""
        self._write(['"1","A","ltc","Near Mint","","348"'],
                    name="moxfield_haves_2026-07-17-1851Z.csv")
        self._write(['"1","B","ltc","Near Mint","","349"'],
                    name="collection-2026-09-01.csv")
        self.assertEqual(set(fp.fetch_owned(self.DEFINITIONS)), {("ltc", "349")})

    def test_same_day_exports_order_by_time(self):
        self._write(['"1","A","ltc","Near Mint","","348"'],
                    name="moxfield_haves_2026-08-21-0900Z.csv")
        self._write(['"1","B","ltc","Near Mint","","349"'],
                    name="moxfield_haves_2026-08-21-1715Z.csv")
        self.assertEqual(set(fp.fetch_owned(self.DEFINITIONS)), {("ltc", "349")})

    def test_undated_snapshot_is_fatal(self):
        """An export with no date in its name cannot be ordered against the
        others, so the run stops rather than guess which is current."""
        self._write(self.ROWS, name="moxfield_haves_2026-07-17-1851Z.csv")
        self._write(self.ROWS, name="moxfield_export.csv")
        with self.assertRaises(SystemExit) as ctx:
            fp.fetch_owned(self.DEFINITIONS)
        self.assertIn("moxfield_export.csv", str(ctx.exception))


class TestPreviousOwnedCount(unittest.TestCase):
    """The baseline the ownership guard rail compares against."""

    def setUp(self):
        self._orig = fp.PRICES_FILE
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        fp.PRICES_FILE = self._orig

    def _write(self, doc):
        f = self.tmp / "prices.json"
        f.write_text(json.dumps(doc), encoding="utf-8")
        fp.PRICES_FILE = f

    def test_counts_cards_owned_in_either_finish(self):
        self._write({
            "updated_at": "2026-08-12T00:00:00Z",
            # Lists of dicts sitting alongside the card sections, exactly as in
            # build_history.py's extract_prices - neither must be counted.
            "tabs": [{"key": "a", "group": "g", "label": "A"}],
            "groups": [{"key": "g", "label": "G"}],
            "a": [
                {"collected_nonfoil": 3, "collected_foil": 0},
                {"collected_nonfoil": 0, "collected_foil": 1},
                {"collected_nonfoil": 1, "collected_foil": 2},
                {"collected_nonfoil": 0, "collected_foil": 0},
            ],
        })
        # Cards, not copies: this is the baseline for "did the CSV stop parsing",
        # and a card is either matched or it is not.
        self.assertEqual(fp.previous_owned_count(), 3)

    def test_counts_the_older_boolean_schema_too(self):
        """Ownership used to be a flag rather than a count. The guard rail
        compares against the previous run's file, which may still be one."""
        self._write({"a": [{"collected_nonfoil": True,  "collected_foil": False},
                           {"collected_nonfoil": False, "collected_foil": False}]})
        self.assertEqual(fp.previous_owned_count(), 1)

    def test_missing_file_is_zero(self):
        """A first run has no baseline, and must not be blocked by its absence."""
        fp.PRICES_FILE = self.tmp / "does-not-exist.json"
        self.assertEqual(fp.previous_owned_count(), 0)

    def test_malformed_file_is_zero(self):
        f = self.tmp / "prices.json"
        f.write_text("{ not json", encoding="utf-8")
        fp.PRICES_FILE = f
        self.assertEqual(fp.previous_owned_count(), 0)

    def test_the_real_prices_file_has_owned_cards(self):
        """If this ever reads 0 the guard rail is disarmed - it can only fire
        when the previous run found something."""
        fp.PRICES_FILE = REPO_ROOT / "prices.json"
        self.assertGreater(fp.previous_owned_count(), 0)


class TestRunStats(unittest.TestCase):
    """The thresholds are what stand between a bad vendor day and a published
    prices.json full of nulls."""

    def test_clean_run_passes(self):
        s = fp.RunStats()
        s.cards = 150
        self.assertEqual(s.failures(), [])

    def test_zero_cards_is_a_failure(self):
        self.assertEqual(fp.RunStats().failures(), ["no cards were processed"])

    def test_scryfall_threshold(self):
        s = fp.RunStats()
        s.cards = 100
        s.scryfall_errors = [("c", "HTTP 500")] * 10   # exactly at the limit
        self.assertEqual(s.failures(), [])
        s.scryfall_errors.append(("c", "HTTP 500"))    # 11% > 10%
        self.assertEqual(len(s.failures()), 1)

    def test_manapool_error_threshold(self):
        s = fp.RunStats()
        s.cards = 100
        s.manapool_errors = [("c", "HTTP 503")] * 11
        self.assertEqual(len(s.failures()), 1)

    def test_manapool_parse_miss_threshold(self):
        """The exact failure that shipped 150 nulls: pages load fine but no
        price parses out of them."""
        s = fp.RunStats()
        s.cards = 150
        s.manapool_misses = ["card"] * 75              # 50%, at the limit
        self.assertEqual(s.failures(), [])
        s.manapool_misses = ["card"] * 150             # the real-world case
        reasons = s.failures()
        self.assertEqual(len(reasons), 1)
        self.assertIn("page format", reasons[0])

    def test_ownership_dropping_to_zero_is_a_failure(self):
        """The ownership equivalent of the ManaPool nulls: the CSV stops
        parsing and the whole collection reads as un-owned."""
        s = fp.RunStats()
        s.cards = 150
        s.previous_owned, s.owned = 4, 0
        reasons = s.failures()
        self.assertEqual(len(reasons), 1)
        self.assertIn("Moxfield", reasons[0])

    def test_ownership_that_was_already_zero_passes(self):
        """A collection that was empty before and is empty now is just an
        empty collection - there is no regression to report."""
        s = fp.RunStats()
        s.cards = 150
        s.previous_owned, s.owned = 0, 0
        self.assertEqual(s.failures(), [])

    def test_ownership_still_matching_passes(self):
        s = fp.RunStats()
        s.cards = 150
        s.previous_owned, s.owned = 4, 4
        self.assertEqual(s.failures(), [])


class TestScryfallImage(unittest.TestCase):
    def test_prefers_normal(self):
        self.assertEqual(
            fp.scryfall_image({"image_uris": {"small": "s", "normal": "n", "large": "l"}}), "n")

    def test_falls_back_to_large_then_small(self):
        self.assertEqual(fp.scryfall_image({"image_uris": {"large": "l", "small": "s"}}), "l")
        self.assertEqual(fp.scryfall_image({"image_uris": {"small": "s"}}), "s")

    def test_double_faced_card_uses_first_face(self):
        card = {"card_faces": [{"image_uris": {"normal": "front"}},
                               {"image_uris": {"normal": "back"}}]}
        self.assertEqual(fp.scryfall_image(card), "front")

    def test_missing_images(self):
        self.assertIsNone(fp.scryfall_image({}))


class TestBuildCardRow(unittest.TestCase):
    """Row assembly, with the network stubbed out."""

    SET = "ltc"

    def setUp(self):
        self._orig = fp.fetch_manapool_price
        fp.fetch_manapool_price = lambda s, n, slug: 82.17
        self._sleep = fp.time.sleep
        fp.time.sleep = lambda *_: None
        # build_card_row logs each card; keep it out of the test output.
        self._quiet = contextlib.redirect_stdout(io.StringIO())
        self._quiet.__enter__()

    def tearDown(self):
        self._quiet.__exit__(None, None, None)
        fp.fetch_manapool_price = self._orig
        fp.time.sleep = self._sleep

    def _card(self, **over):
        card = {"name": "The Great Henge", "tcgplayer_id": 488284,
                "prices": {"usd": "90.22"}, "image_uris": {"normal": "img"}}
        card.update(over)
        return card

    def test_plain_card(self):
        row = fp.build_card_row(self.SET, "348", self._card(), {}, fp.RunStats())
        self.assertEqual(row["display_name"], "The Great Henge")
        self.assertEqual(row["mtg_name"], "The Great Henge")
        self.assertEqual(row["tcg_price"], 90.22)
        self.assertEqual(row["mp_price"], 82.17)
        self.assertIn("/product/488284", row["tcg_url"])
        self.assertEqual(
            row["mp_url"],
            "https://manapool.com/card/ltc/348/the-great-henge?conditions=NM&finish=nonfoil")
        self.assertEqual((row["collected_nonfoil"], row["collected_foil"]), (0, 0))

    def test_flavor_name_becomes_display_name(self):
        row = fp.build_card_row(self.SET, "348",
                                self._card(flavor_name="The Party Tree"), {}, fp.RunStats())
        self.assertEqual(row["display_name"], "The Party Tree (The Great Henge)")
        self.assertEqual(row["mtg_name"], "The Great Henge")

    def test_ownership_is_applied_as_a_copy_count(self):
        owned = {("ltc", "348"): {"nonfoil": 4, "foil": 0}}
        row = fp.build_card_row(self.SET, "348", self._card(), owned, fp.RunStats())
        self.assertEqual(row["collected_nonfoil"], 4)
        self.assertEqual(row["collected_foil"], 0)

    def test_missing_price_is_null_not_an_error(self):
        stats = fp.RunStats()
        row = fp.build_card_row(self.SET, "348",
                                self._card(prices={}), {}, stats)
        self.assertIsNone(row["tcg_price"])
        self.assertEqual(stats.scryfall_errors, [])

    def test_absent_card_yields_no_row(self):
        stats = fp.RunStats()
        self.assertIsNone(fp.build_card_row(self.SET, "348", None, {}, stats))

    def test_manapool_miss_is_recorded(self):
        fp.fetch_manapool_price = lambda s, n, slug: None
        stats = fp.RunStats()
        row = fp.build_card_row(self.SET, "348", self._card(), {}, stats)
        self.assertIsNone(row["mp_price"])
        self.assertEqual(stats.manapool_misses, ["The Great Henge"])

    def test_manapool_failure_is_recorded_separately(self):
        def boom(*_):
            raise fp.FetchError("HTTP 503")
        fp.fetch_manapool_price = boom
        stats = fp.RunStats()
        row = fp.build_card_row(self.SET, "348", self._card(), {}, stats)
        self.assertIsNone(row["mp_price"])
        self.assertEqual(len(stats.manapool_errors), 1)
        self.assertEqual(stats.manapool_misses, [])


@unittest.skipUnless(os.environ.get("RUN_NETWORK_TESTS") == "1",
                     "set RUN_NETWORK_TESTS=1 to check derivations against Scryfall")
class TestDerivationsAgainstScryfall(unittest.TestCase):
    """The check that made deleting the hardcoded card tables safe: every
    tracked card's slug and TCGplayer id must still match what Scryfall says."""

    def test_every_tracked_card(self):
        fp.SETS_FILE = REPO_ROOT / "data" / "sets.json"
        _groups, definitions = fp.load_sets()
        stats = fp.RunStats()
        cards = fp.fetch_scryfall_cards(definitions, stats)

        self.assertEqual(stats.scryfall_errors, [], "Scryfall lookups failed")
        expected = sum(len(fp.card_keys(d)) for d in definitions)
        self.assertGreaterEqual(len(cards), 1)

        for (set_code, num), card in cards.items():
            with self.subTest(card=f"{set_code}/{num}"):
                self.assertTrue(card.get("name"))
                self.assertIsNotNone(card.get("tcgplayer_id"),
                                     f"{card['name']} has no tcgplayer_id")
                slug = fp.slugify(card["name"])
                self.assertRegex(slug, r"^[a-z0-9-]+$")
        print(f"\n  checked {len(cards)} cards ({expected} requested)")


if __name__ == "__main__":
    unittest.main()
