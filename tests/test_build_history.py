"""Tests for scripts/build_history.py - the card key and series extraction.

The card key has to stay stable across schema changes: rows are re-sorted by
price on every run and sections have been renamed, so position and section are
both useless as identity. Everything here runs offline.
"""
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_history as bh


class TestCardKey(unittest.TestCase):
    def test_extracts_set_and_number(self):
        entry = {"mp_url": "https://manapool.com/card/ltc/370/mouth-of-ronom?conditions=NM&finish=nonfoil"}
        self.assertEqual(bh.card_key(entry), "ltc/370")

    def test_ignores_the_slug(self):
        """A renamed card must not become a different card."""
        a = {"mp_url": "https://manapool.com/card/eos/1/ancient-tomb?conditions=NM"}
        b = {"mp_url": "https://manapool.com/card/eos/1/some-other-slug"}
        self.assertEqual(bh.card_key(a), bh.card_key(b))

    def test_without_query_string(self):
        self.assertEqual(bh.card_key({"mp_url": "https://manapool.com/card/ltr/302/boromir"}),
                         "ltr/302")

    def test_missing_or_junk_url(self):
        for entry in [{}, {"mp_url": ""}, {"mp_url": "https://example.com/nope"}]:
            with self.subTest(entry=entry):
                self.assertIsNone(bh.card_key(entry))


class TestExtractPrices(unittest.TestCase):
    def _doc(self, **extra):
        doc = {
            "updated_at": "2026-08-12T00:00:00Z",
            "realms_and_relics": [
                {"mp_url": "https://manapool.com/card/ltc/348/x", "tcg_price": 90.22, "mp_price": 82.17},
                {"mp_url": "https://manapool.com/card/ltc/349/y", "tcg_price": None, "mp_price": 1.5},
            ],
        }
        doc.update(extra)
        return doc

    def test_reads_every_section(self):
        doc = self._doc(showcase=[{"mp_url": "https://manapool.com/card/ltr/302/z",
                                   "tcg_price": 5.0, "mp_price": 4.0}])
        prices = bh.extract_prices(doc)
        self.assertEqual(prices["ltc/348"], (90.22, 82.17))
        self.assertEqual(prices["ltc/349"], (None, 1.5))
        self.assertEqual(prices["ltr/302"], (5.0, 4.0))

    def test_ignores_the_navigation_blocks(self):
        """prices.json carries "tabs" and "groups" arrays; both are lists of
        dicts like the card sections, and must not be mistaken for cards."""
        doc = self._doc(
            tabs=[{"key": "realms_and_relics", "group": "ltc", "label": "LTC"}],
            groups=[{"key": "ltc", "label": "Lord of the Rings — LTC"}])
        prices = bh.extract_prices(doc)
        self.assertEqual(set(prices), {"ltc/348", "ltc/349"})

    def test_ignores_scalars_and_malformed_entries(self):
        doc = self._doc(some_string="x", some_number=3)
        doc["realms_and_relics"].append("not a dict")
        self.assertEqual(set(bh.extract_prices(doc)), {"ltc/348", "ltc/349"})

    def test_handles_the_oldest_schema(self):
        """The earliest revisions used a single "cards" section with different
        field names; only mp_url and the prices were ever constant."""
        old = {"cards": [{"mp_url": "https://manapool.com/card/ltc/348/x",
                          "mtg_name": "The Great Henge", "lotr_name": "The Party Tree",
                          "tcg_price": 88.37, "mp_price": 88.56}]}
        self.assertEqual(bh.extract_prices(old), {"ltc/348": (88.37, 88.56)})


class TestRealArtifacts(unittest.TestCase):
    """Guards against the generated files drifting out of step with each other."""

    def setUp(self):
        self.prices = json.loads((REPO_ROOT / "prices.json").read_text(encoding="utf-8"))
        self.history = json.loads((REPO_ROOT / "history.json").read_text(encoding="utf-8"))

    def test_every_priced_card_has_history(self):
        """Priced, not merely tracked. A card neither vendor lists - hob #321
        is a bundle promo with no TCGplayer id and no ManaPool listing - is
        deliberately absent from history, because build() skips series that are
        null the whole way down. Anything carrying a price must have one."""
        priced = {key for key, (tcg, mp) in bh.extract_prices(self.prices).items()
                  if tcg is not None or mp is not None}
        missing = priced - set(self.history["cards"])
        self.assertEqual(missing, set(), "cards in prices.json with no history series")

    def test_history_holds_no_empty_series(self):
        """The other half of the rule above: a series that is null on every day
        is the thing build() skips, so one appearing here means it stopped."""
        empty = [key for key, s in self.history["cards"].items()
                 if not any(v is not None for v in s["tcg"] + s["mp"])]
        self.assertEqual(empty, [], "history series with no data points at all")

    def test_history_series_align_with_the_date_axis(self):
        n = len(self.history["dates"])
        self.assertGreater(n, 0)
        for key, series in self.history["cards"].items():
            with self.subTest(card=key):
                self.assertEqual(len(series["tcg"]), n)
                self.assertEqual(len(series["mp"]), n)

    def test_dates_are_sorted_and_unique(self):
        dates = self.history["dates"]
        self.assertEqual(dates, sorted(dates))
        self.assertEqual(len(dates), len(set(dates)))

    # The two blocks the front end builds its navigation from. "groups" are the
    # primary tabs, "tabs" the chips under them.
    NAV_BLOCKS = ("tabs", "groups")

    def test_tabs_block_matches_the_sections(self):
        tabs = self.prices.get("tabs")
        self.assertIsInstance(tabs, list)
        for tab in tabs:
            with self.subTest(tab=tab["key"]):
                self.assertIn(tab["key"], self.prices)
                self.assertIsInstance(self.prices[tab["key"]], list)
                self.assertTrue(tab["label"].strip())

    def test_tabs_cover_every_card_section(self):
        """A section with no tab would be invisible on the page."""
        tab_keys = {t["key"] for t in self.prices["tabs"]}
        sections = {k for k, v in self.prices.items()
                    if isinstance(v, list) and k not in self.NAV_BLOCKS}
        self.assertEqual(sections, tab_keys)

    def test_every_tab_belongs_to_a_declared_group(self):
        """A chip whose group is missing renders under no tab at all."""
        groups = self.prices.get("groups")
        self.assertIsInstance(groups, list)
        self.assertTrue(groups)
        keys = {g["key"] for g in groups}
        for g in groups:
            with self.subTest(group=g["key"]):
                self.assertTrue(g["label"].strip())
        for tab in self.prices["tabs"]:
            with self.subTest(tab=tab["key"]):
                self.assertIn(tab["group"], keys)

    def test_every_group_has_at_least_one_tab(self):
        """A group with no chips is a tab that opens onto nothing."""
        used = {t["group"] for t in self.prices["tabs"]}
        empty = [g["key"] for g in self.prices["groups"] if g["key"] not in used]
        self.assertEqual(empty, [])


if __name__ == "__main__":
    unittest.main()
