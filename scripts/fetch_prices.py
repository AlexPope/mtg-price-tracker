#!/usr/bin/env python3
import json
import re
import subprocess
import datetime

try:
    import cloudscraper
    _have_cloudscraper = True
except ImportError:
    _have_cloudscraper = False

MOXFIELD_BINDER_ID = 'f6LqAFGUPEG7FWnGopkU1Q'

CONDITION_MAP = {
    'nearMint': 'NM',
    'lightlyPlayed': 'LP',
    'moderatelyPlayed': 'MP',
    'heavilyPlayed': 'HP',
    'damaged': 'DMG',
}

# LTC #348-377 — borderless non-foil (Realms & Relics)
REALMS_CARDS = [
    {"lotr_name": "The Party Tree",                    "mtg_name": "The Great Henge",                  "set": "ltc", "num": "348", "slug": "the-great-henge",                "tcg_id": "488284"},
    {"lotr_name": "Elessar, the Elfstone",             "mtg_name": "Cloudstone Curio",                 "set": "ltc", "num": "349", "slug": "cloudstone-curio",               "tcg_id": "498455"},
    {"lotr_name": "Bridge of Khazad-dûm",              "mtg_name": "Ensnaring Bridge",                 "set": "ltc", "num": "350", "slug": "ensnaring-bridge",               "tcg_id": "488283"},
    {"lotr_name": "Argonath, Pillars of the Kings",    "mtg_name": "The Ozolith",                      "set": "ltc", "num": "351", "slug": "the-ozolith",                    "tcg_id": "498457"},
    {"lotr_name": "Three Rings for the Elven-Kings",   "mtg_name": "Rings of Brighthearth",            "set": "ltc", "num": "352", "slug": "rings-of-brighthearth",          "tcg_id": "498466"},
    {"lotr_name": "Morgul-Knife",                      "mtg_name": "Shadowspear",                      "set": "ltc", "num": "353", "slug": "shadowspear",                    "tcg_id": "498464"},
    {"lotr_name": "Herugrim, Sword of Rohan",          "mtg_name": "Sword of Hearth and Home",         "set": "ltc", "num": "354", "slug": "sword-of-hearth-and-home",       "tcg_id": "499313"},
    {"lotr_name": "Ring of Barahir",                   "mtg_name": "Sword of the Animist",             "set": "ltc", "num": "355", "slug": "sword-of-the-animist",           "tcg_id": "499314"},
    {"lotr_name": "Shards of Narsil",                  "mtg_name": "Thorn of Amethyst",                "set": "ltc", "num": "356", "slug": "thorn-of-amethyst",              "tcg_id": "499315"},
    {"lotr_name": "Balin's Tomb",                      "mtg_name": "Ancient Tomb",                     "set": "ltc", "num": "357", "slug": "ancient-tomb",                   "tcg_id": "498456"},
    {"lotr_name": "Barrow-Downs",                      "mtg_name": "Bojuka Bog",                       "set": "ltc", "num": "358", "slug": "bojuka-bog",                     "tcg_id": "498461"},
    {"lotr_name": "Isengard, Saruman's Fortress",      "mtg_name": "Boseiju, Who Shelters All",        "set": "ltc", "num": "359", "slug": "boseiju-who-shelters-all",       "tcg_id": "498462"},
    {"lotr_name": "Minas Morgul",                      "mtg_name": "Cabal Coffers",                    "set": "ltc", "num": "360", "slug": "cabal-coffers",                  "tcg_id": "499316"},
    {"lotr_name": "Meduseld, Golden Hall of Edoras",   "mtg_name": "Castle Ardenvale",                 "set": "ltc", "num": "361", "slug": "castle-ardenvale",               "tcg_id": "499317"},
    {"lotr_name": "Paths of the Dead",                 "mtg_name": "Cavern of Souls",                  "set": "ltc", "num": "362", "slug": "cavern-of-souls",                "tcg_id": "498465"},
    {"lotr_name": "Weathertop",                        "mtg_name": "Deserted Temple",                  "set": "ltc", "num": "363", "slug": "deserted-temple",                "tcg_id": "498458"},
    {"lotr_name": "Glittering Caves of Aglarond",      "mtg_name": "Gemstone Caverns",                 "set": "ltc", "num": "364", "slug": "gemstone-caverns",               "tcg_id": "499318"},
    {"lotr_name": "Green Dragon Inn",                  "mtg_name": "Homeward Path",                    "set": "ltc", "num": "365", "slug": "homeward-path",                  "tcg_id": "498463"},
    {"lotr_name": "Bag End",                           "mtg_name": "Horizon Canopy",                   "set": "ltc", "num": "366", "slug": "horizon-canopy",                 "tcg_id": "499319"},
    {"lotr_name": "White Tower of Ecthelion",          "mtg_name": "Karakas",                          "set": "ltc", "num": "367", "slug": "karakas",                        "tcg_id": "499320"},
    {"lotr_name": "Osgiliath, Fallen Capital",         "mtg_name": "Kor Haven",                        "set": "ltc", "num": "368", "slug": "kor-haven",                      "tcg_id": "499321"},
    {"lotr_name": "Dol Amroth",                        "mtg_name": "Minamo, School at Water's Edge",   "set": "ltc", "num": "369", "slug": "minamo-school-at-waters-edge",   "tcg_id": "498460"},
    {"lotr_name": "Redhorn Pass",                      "mtg_name": "Mouth of Ronom",                   "set": "ltc", "num": "370", "slug": "mouth-of-ronom",                 "tcg_id": "499322"},
    {"lotr_name": "Bucklebury Ferry",                  "mtg_name": "Oboro, Palace in the Clouds",      "set": "ltc", "num": "371", "slug": "oboro-palace-in-the-clouds",     "tcg_id": "499323"},
    {"lotr_name": "Inn of the Prancing Pony",          "mtg_name": "Pillar of the Paruns",             "set": "ltc", "num": "372", "slug": "pillar-of-the-paruns",           "tcg_id": "499324"},
    {"lotr_name": "Henneth Annûn",                     "mtg_name": "Reflecting Pool",                  "set": "ltc", "num": "373", "slug": "reflecting-pool",                "tcg_id": "499327"},
    {"lotr_name": "Helm's Deep",                       "mtg_name": "Shinka, the Bloodsoaked Keep",     "set": "ltc", "num": "374", "slug": "shinka-the-bloodsoaked-keep",    "tcg_id": "499325"},
    {"lotr_name": "The Dead Marshes",                  "mtg_name": "Urborg, Tomb of Yawgmoth",         "set": "ltc", "num": "375", "slug": "urborg-tomb-of-yawgmoth",        "tcg_id": "499326"},
    {"lotr_name": "Valley of Gorgoroth",               "mtg_name": "Wasteland",                        "set": "ltc", "num": "376", "slug": "wasteland",                      "tcg_id": "488281"},
    {"lotr_name": "Fangorn Forest",                    "mtg_name": "Yavimaya, Cradle of Growth",       "set": "ltc", "num": "377", "slug": "yavimaya-cradle-of-growth",      "tcg_id": "498459"},
]

# LTR #302-331 — showcase borderless (Showcase)
SHOWCASE_CARDS = [
    {"mtg_name": "Boromir, Warden of the Tower",   "set": "ltr", "num": "302", "slug": "boromir-warden-of-the-tower",    "tcg_id": "498306"},
    {"mtg_name": "Faramir, Field Commander",        "set": "ltr", "num": "303", "slug": "faramir-field-commander",        "tcg_id": "499461"},
    {"mtg_name": "Frodo, Sauron's Bane",            "set": "ltr", "num": "304", "slug": "frodo-saurons-bane",             "tcg_id": "488264"},
    {"mtg_name": "Gandalf the White",               "set": "ltr", "num": "305", "slug": "gandalf-the-white",              "tcg_id": "498326"},
    {"mtg_name": "Samwise the Stouthearted",        "set": "ltr", "num": "306", "slug": "samwise-the-stouthearted",       "tcg_id": "488266"},
    {"mtg_name": "Elrond, Lord of Rivendell",       "set": "ltr", "num": "307", "slug": "elrond-lord-of-rivendell",       "tcg_id": "499198"},
    {"mtg_name": "Gandalf, Friend of the Shire",    "set": "ltr", "num": "308", "slug": "gandalf-friend-of-the-shire",    "tcg_id": "498446"},
    {"mtg_name": "Gollum, Patient Plotter",         "set": "ltr", "num": "309", "slug": "gollum-patient-plotter",         "tcg_id": "488263"},
    {"mtg_name": "Sauron, the Necromancer",         "set": "ltr", "num": "310", "slug": "sauron-the-necromancer",         "tcg_id": "498450"},
    {"mtg_name": "Witch-king of Angmar",            "set": "ltr", "num": "311", "slug": "witch-king-of-angmar",           "tcg_id": "498426"},
    {"mtg_name": "Gimli, Counter of Kills",         "set": "ltr", "num": "312", "slug": "gimli-counter-of-kills",         "tcg_id": "498738"},
    {"mtg_name": "Legolas, Master Archer",          "set": "ltr", "num": "313", "slug": "legolas-master-archer",          "tcg_id": "498343"},
    {"mtg_name": "Meriadoc Brandybuck",             "set": "ltr", "num": "314", "slug": "meriadoc-brandybuck",            "tcg_id": "498613"},
    {"mtg_name": "Peregrin Took",                   "set": "ltr", "num": "315", "slug": "peregrin-took",                  "tcg_id": "498615"},
    {"mtg_name": "Aragorn, Company Leader",         "set": "ltr", "num": "316", "slug": "aragorn-company-leader",         "tcg_id": "499954"},
    {"mtg_name": "Aragorn, the Uniter",             "set": "ltr", "num": "317", "slug": "aragorn-the-uniter",             "tcg_id": "498299"},
    {"mtg_name": "Elrond, Master of Healing",       "set": "ltr", "num": "318", "slug": "elrond-master-of-healing",       "tcg_id": "499864"},
    {"mtg_name": "Faramir, Prince of Ithilien",     "set": "ltr", "num": "319", "slug": "faramir-prince-of-ithilien",     "tcg_id": "498858"},
    {"mtg_name": "Frodo Baggins",                   "set": "ltr", "num": "320", "slug": "frodo-baggins",                  "tcg_id": "498429"},
    {"mtg_name": "Galadriel of Lothlórien",         "set": "ltr", "num": "321", "slug": "galadriel-of-lothlorien",        "tcg_id": "499863"},
    {"mtg_name": "Gandalf the Grey",                "set": "ltr", "num": "322", "slug": "gandalf-the-grey",               "tcg_id": "487804"},
    {"mtg_name": "Gimli, Mournful Avenger",         "set": "ltr", "num": "323", "slug": "gimli-mournful-avenger",         "tcg_id": "498330"},
    {"mtg_name": "Legolas, Counter of Kills",       "set": "ltr", "num": "324", "slug": "legolas-counter-of-kills",       "tcg_id": "498739"},
    {"mtg_name": "Merry, Esquire of Rohan",         "set": "ltr", "num": "325", "slug": "merry-esquire-of-rohan",         "tcg_id": "498349"},
    {"mtg_name": "Pippin, Guard of the Citadel",    "set": "ltr", "num": "326", "slug": "pippin-guard-of-the-citadel",    "tcg_id": "498371"},
    {"mtg_name": "Samwise Gamgee",                  "set": "ltr", "num": "327", "slug": "samwise-gamgee",                 "tcg_id": "498379"},
    {"mtg_name": "Saruman of Many Colors",          "set": "ltr", "num": "328", "slug": "saruman-of-many-colors",         "tcg_id": "498453"},
    {"mtg_name": "Sauron, the Dark Lord",           "set": "ltr", "num": "329", "slug": "sauron-the-dark-lord",           "tcg_id": "498382"},
    {"mtg_name": "Sméagol, Helpful Guide",          "set": "ltr", "num": "330", "slug": "smeagol-helpful-guide",          "tcg_id": "499398"},
    {"mtg_name": "Tom Bombadil",                    "set": "ltr", "num": "331", "slug": "tom-bombadil",                   "tcg_id": "488265"},
]


def fetch_tcg_price(card):
    url = f"https://api.scryfall.com/cards/{card['set']}/{card['num']}"
    result = subprocess.run(
        ["curl", "-s", "-A", "Mozilla/5.0", url],
        capture_output=True, text=True
    )
    try:
        data = json.loads(result.stdout)
        price = data.get("prices", {}).get("usd")
        return float(price) if price else None
    except Exception:
        return None


def fetch_manapool_price(card):
    url = f"https://manapool.com/card/{card['set']}/{card['num']}/{card['slug']}"
    result = subprocess.run(
        ["curl", "-s", "-A", "Mozilla/5.0",
         "-H", "Accept: text/html,application/xhtml+xml",
         url],
        capture_output=True, text=True
    )
    html = result.stdout
    m = re.search(r'\\"marketPrices\\":\{\\"price\\": (\d+),', html)
    if m:
        return int(m.group(1)) / 100.0
    return None


def fetch_owned():
    """Returns {(set, cn): {condition, foil}} for all cards in the Moxfield binder."""
    if not _have_cloudscraper:
        print("  cloudscraper not available, skipping binder fetch")
        return {}

    scraper = cloudscraper.create_scraper()
    headers = {
        'Accept': 'application/json',
        'Referer': 'https://moxfield.com/',
        'Origin': 'https://moxfield.com',
    }

    # Collector number ranges we care about, by set
    ranges = {
        'ltc': (348, 377),
        'ltr': (302, 331),
    }

    owned = {}
    page = 1
    while True:
        url = f"https://api2.moxfield.com/v1/trade-binders/{MOXFIELD_BINDER_ID}?pageNumber={page}&pageSize=100"
        try:
            r = scraper.get(url, headers=headers, timeout=15)
            data = r.json()
        except Exception as e:
            print(f"  Moxfield fetch error (page {page}): {e}")
            break

        for entry in data.get("data", []):
            card = entry.get("card", {})
            card_set = card.get("set", "").lower()
            if card_set not in ranges:
                continue
            cn = card.get("cn", "")
            lo, hi = ranges[card_set]
            if not (cn.isdigit() and lo <= int(cn) <= hi):
                continue
            condition = CONDITION_MAP.get(entry.get("condition", ""), entry.get("condition", ""))
            is_foil = entry.get("finish", "nonFoil") == "foil"
            owned[(card_set, cn)] = {"condition": condition, "foil": is_foil}

        if data.get("pageNumber", 1) >= data.get("totalPages", 1):
            break
        page += 1

    print(f"  Moxfield: found {len(owned)} owned cards across both sets")
    return owned


def build_card_row(card, owned):
    print(f"  {card['mtg_name']}...")
    tcg_price = fetch_tcg_price(card)
    mp_price = fetch_manapool_price(card)
    key = (card["set"], card["num"])
    owned_entry = owned.get(key)
    display_name = card["mtg_name"]
    if card.get("lotr_name"):
        display_name = f"{card['lotr_name']} ({card['mtg_name']})"
    return {
        "display_name": display_name,
        "mtg_name": card["mtg_name"],
        "tcg_price": tcg_price,
        "tcg_url": f"https://www.tcgplayer.com/product/{card['tcg_id']}?Condition=Near+Mint&Printing=Normal",
        "mp_price": mp_price,
        "mp_url": f"https://manapool.com/card/{card['set']}/{card['num']}/{card['slug']}?conditions=NM&finish=nonfoil",
        "owned": owned_entry is not None,
        "condition": owned_entry["condition"] if owned_entry else None,
        "foil": owned_entry["foil"] if owned_entry else None,
    }


def main():
    print("Fetching Moxfield binder...")
    owned = fetch_owned()

    print("Fetching Realms & Relics prices (LTC #348-377)...")
    realms = [build_card_row(c, owned) for c in REALMS_CARDS]
    realms.sort(key=lambda x: x["tcg_price"] if x["tcg_price"] is not None else float("inf"))

    print("Fetching Showcase prices (LTR #302-331)...")
    showcase = [build_card_row(c, owned) for c in SHOWCASE_CARDS]
    showcase.sort(key=lambda x: x["tcg_price"] if x["tcg_price"] is not None else float("inf"))

    output = {
        "updated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "realms_and_relics": realms,
        "showcase": showcase,
    }
    with open("prices.json", "w") as f:
        json.dump(output, f, indent=2)

    owned_count = sum(1 for r in realms + showcase if r["owned"])
    print(f"Done. {len(realms)} Realms & Relics + {len(showcase)} Showcase cards, {owned_count} owned.")


if __name__ == "__main__":
    main()
