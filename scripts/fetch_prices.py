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

CARDS = [
    {"lotr_name": "The Party Tree", "mtg_name": "The Great Henge", "scryfall_id": "ltc/348", "manapool_slug": "the-great-henge", "manapool_num": "348", "tcg_id": "488284"},
    {"lotr_name": "Argonath, Pillars of the Kings", "mtg_name": "The Ozolith", "scryfall_id": "ltc/351", "manapool_slug": "the-ozolith", "manapool_num": "351", "tcg_id": "498457"},
    {"lotr_name": "Elessar, the Elfstone", "mtg_name": "Cloudstone Curio", "scryfall_id": "ltc/349", "manapool_slug": "cloudstone-curio", "manapool_num": "349", "tcg_id": "498455"},
    {"lotr_name": "Bridge of Khazad-dûm", "mtg_name": "Ensnaring Bridge", "scryfall_id": "ltc/350", "manapool_slug": "ensnaring-bridge", "manapool_num": "350", "tcg_id": "488283"},
    {"lotr_name": "Three Rings for the Elven-Kings", "mtg_name": "Rings of Brighthearth", "scryfall_id": "ltc/352", "manapool_slug": "rings-of-brighthearth", "manapool_num": "352", "tcg_id": "498466"},
    {"lotr_name": "Morgul-Knife", "mtg_name": "Shadowspear", "scryfall_id": "ltc/353", "manapool_slug": "shadowspear", "manapool_num": "353", "tcg_id": "498464"},
    {"lotr_name": "Herugrim, Sword of Rohan", "mtg_name": "Sword of Hearth and Home", "scryfall_id": "ltc/354", "manapool_slug": "sword-of-hearth-and-home", "manapool_num": "354", "tcg_id": "499313"},
    {"lotr_name": "Ring of Barahir", "mtg_name": "Sword of the Animist", "scryfall_id": "ltc/355", "manapool_slug": "sword-of-the-animist", "manapool_num": "355", "tcg_id": "499314"},
    {"lotr_name": "Shards of Narsil", "mtg_name": "Thorn of Amethyst", "scryfall_id": "ltc/356", "manapool_slug": "thorn-of-amethyst", "manapool_num": "356", "tcg_id": "499315"},
    {"lotr_name": "Balin's Tomb", "mtg_name": "Ancient Tomb", "scryfall_id": "ltc/357", "manapool_slug": "ancient-tomb", "manapool_num": "357", "tcg_id": "498456"},
    {"lotr_name": "Barrow-Downs", "mtg_name": "Bojuka Bog", "scryfall_id": "ltc/358", "manapool_slug": "bojuka-bog", "manapool_num": "358", "tcg_id": "498461"},
    {"lotr_name": "Isengard, Saruman's Fortress", "mtg_name": "Boseiju, Who Shelters All", "scryfall_id": "ltc/359", "manapool_slug": "boseiju-who-shelters-all", "manapool_num": "359", "tcg_id": "498462"},
    {"lotr_name": "Minas Morgul", "mtg_name": "Cabal Coffers", "scryfall_id": "ltc/360", "manapool_slug": "cabal-coffers", "manapool_num": "360", "tcg_id": "499316"},
    {"lotr_name": "Meduseld, Golden Hall of Edoras", "mtg_name": "Castle Ardenvale", "scryfall_id": "ltc/361", "manapool_slug": "castle-ardenvale", "manapool_num": "361", "tcg_id": "499317"},
    {"lotr_name": "Paths of the Dead", "mtg_name": "Cavern of Souls", "scryfall_id": "ltc/362", "manapool_slug": "cavern-of-souls", "manapool_num": "362", "tcg_id": "498465"},
    {"lotr_name": "Weathertop", "mtg_name": "Deserted Temple", "scryfall_id": "ltc/363", "manapool_slug": "deserted-temple", "manapool_num": "363", "tcg_id": "498458"},
    {"lotr_name": "Glittering Caves of Aglarond", "mtg_name": "Gemstone Caverns", "scryfall_id": "ltc/364", "manapool_slug": "gemstone-caverns", "manapool_num": "364", "tcg_id": "499318"},
    {"lotr_name": "Green Dragon Inn", "mtg_name": "Homeward Path", "scryfall_id": "ltc/365", "manapool_slug": "homeward-path", "manapool_num": "365", "tcg_id": "498463"},
    {"lotr_name": "Bag End", "mtg_name": "Horizon Canopy", "scryfall_id": "ltc/366", "manapool_slug": "horizon-canopy", "manapool_num": "366", "tcg_id": "499319"},
    {"lotr_name": "White Tower of Ecthelion", "mtg_name": "Karakas", "scryfall_id": "ltc/367", "manapool_slug": "karakas", "manapool_num": "367", "tcg_id": "499320"},
    {"lotr_name": "Osgiliath, Fallen Capital", "mtg_name": "Kor Haven", "scryfall_id": "ltc/368", "manapool_slug": "kor-haven", "manapool_num": "368", "tcg_id": "499321"},
    {"lotr_name": "Dol Amroth", "mtg_name": "Minamo, School at Water's Edge", "scryfall_id": "ltc/369", "manapool_slug": "minamo-school-at-waters-edge", "manapool_num": "369", "tcg_id": "498460"},
    {"lotr_name": "Redhorn Pass", "mtg_name": "Mouth of Ronom", "scryfall_id": "ltc/370", "manapool_slug": "mouth-of-ronom", "manapool_num": "370", "tcg_id": "499322"},
    {"lotr_name": "Bucklebury Ferry", "mtg_name": "Oboro, Palace in the Clouds", "scryfall_id": "ltc/371", "manapool_slug": "oboro-palace-in-the-clouds", "manapool_num": "371", "tcg_id": "499323"},
    {"lotr_name": "Inn of the Prancing Pony", "mtg_name": "Pillar of the Paruns", "scryfall_id": "ltc/372", "manapool_slug": "pillar-of-the-paruns", "manapool_num": "372", "tcg_id": "499324"},
    {"lotr_name": "Henneth Annûn", "mtg_name": "Reflecting Pool", "scryfall_id": "ltc/373", "manapool_slug": "reflecting-pool", "manapool_num": "373", "tcg_id": "499327"},
    {"lotr_name": "Helm's Deep", "mtg_name": "Shinka, the Bloodsoaked Keep", "scryfall_id": "ltc/374", "manapool_slug": "shinka-the-bloodsoaked-keep", "manapool_num": "374", "tcg_id": "499325"},
    {"lotr_name": "The Dead Marshes", "mtg_name": "Urborg, Tomb of Yawgmoth", "scryfall_id": "ltc/375", "manapool_slug": "urborg-tomb-of-yawgmoth", "manapool_num": "375", "tcg_id": "499326"},
    {"lotr_name": "Valley of Gorgoroth", "mtg_name": "Wasteland", "scryfall_id": "ltc/376", "manapool_slug": "wasteland", "manapool_num": "376", "tcg_id": "488281"},
    {"lotr_name": "Fangorn Forest", "mtg_name": "Yavimaya, Cradle of Growth", "scryfall_id": "ltc/377", "manapool_slug": "yavimaya-cradle-of-growth", "manapool_num": "377", "tcg_id": "498459"},
]

def fetch_tcg_price(card):
    url = f"https://api.scryfall.com/cards/{card['scryfall_id']}"
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
    url = f"https://manapool.com/card/ltc/{card['manapool_num']}/{card['manapool_slug']}"
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
    """Returns a dict of collector_number -> {condition, foil} for cards in the Moxfield binder."""
    if not _have_cloudscraper:
        print("cloudscraper not available, skipping binder fetch")
        return {}

    scraper = cloudscraper.create_scraper()
    headers = {
        'Accept': 'application/json',
        'Referer': 'https://moxfield.com/',
        'Origin': 'https://moxfield.com',
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
            if card.get("set", "").lower() != "ltc":
                continue
            cn = card.get("cn", "")
            if not (cn.isdigit() and 348 <= int(cn) <= 377):
                continue
            condition = CONDITION_MAP.get(entry.get("condition", ""), entry.get("condition", ""))
            is_foil = entry.get("finish", "nonFoil") == "foil"
            owned[cn] = {"condition": condition, "foil": is_foil}

        if data.get("pageNumber", 1) >= data.get("totalPages", 1):
            break
        page += 1

    print(f"  Moxfield: found {len(owned)} owned LTC cards")
    return owned

def main():
    print("Fetching Moxfield binder...")
    owned = fetch_owned()

    results = []
    for card in CARDS:
        print(f"Fetching {card['mtg_name']}...")
        tcg_price = fetch_tcg_price(card)
        mp_price = fetch_manapool_price(card)
        cn = card["manapool_num"]
        owned_entry = owned.get(cn)
        results.append({
            "lotr_name": card["lotr_name"],
            "mtg_name": card["mtg_name"],
            "tcg_price": tcg_price,
            "tcg_url": f"https://www.tcgplayer.com/product/{card['tcg_id']}?Condition=Near+Mint&Printing=Normal",
            "mp_price": mp_price,
            "mp_url": f"https://manapool.com/card/ltc/{cn}/{card['manapool_slug']}?conditions=NM&finish=nonfoil",
            "owned": owned_entry is not None,
            "condition": owned_entry["condition"] if owned_entry else None,
            "foil": owned_entry["foil"] if owned_entry else None,
        })

    results.sort(key=lambda x: x["tcg_price"] if x["tcg_price"] is not None else float("inf"))

    output = {
        "updated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "cards": results,
    }
    with open("prices.json", "w") as f:
        json.dump(output, f, indent=2)
    print(f"Done. Written to prices.json ({len(results)} cards, {sum(1 for r in results if r['owned'])} owned).")

if __name__ == "__main__":
    main()
