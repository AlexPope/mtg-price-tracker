"""Tests for the generated prices.json - the file index.html actually reads.

These check the artifact rather than the code that writes it: the front end
builds its whole navigation out of the "groups" and "tabs" blocks and renders
the rarity column out of each row's "rarity", so a section with no chip, a chip
with no group or a rarity the page has no letter for are all wrong answers the
unit tests upstream cannot see. Everything here runs offline.
"""
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestPricesArtifact(unittest.TestCase):
    def setUp(self):
        self.prices = json.loads((REPO_ROOT / "prices.json").read_text(encoding="utf-8"))

    # The two blocks the front end builds its navigation from. "groups" are the
    # primary tabs, "tabs" the chips under them. Both are lists of dicts, like
    # the card sections beside them, so anything walking the sections has to
    # skip these by name.
    NAV_BLOCKS = ("tabs", "groups")

    # The rarities index.html has a letter and a colour for; see RARITY there.
    # A card outside this set still renders, as its own initial, but the letter
    # is a guess and the colour is the default - worth being told about.
    KNOWN_RARITIES = {"common", "uncommon", "rare", "special", "mythic", "bonus"}

    def test_every_card_has_a_rarity_the_page_can_render(self):
        unknown = {}
        for key, value in self.prices.items():
            if not isinstance(value, list) or key in self.NAV_BLOCKS:
                continue
            for row in value:
                if row.get("rarity") not in self.KNOWN_RARITIES:
                    unknown[row.get("mtg_name")] = row.get("rarity")
        self.assertEqual(unknown, {}, "rarities index.html has no letter for")

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
