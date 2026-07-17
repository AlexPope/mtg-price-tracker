#!/usr/bin/env python3
import json
import os
import re
import subprocess
import datetime
import urllib.request
import urllib.error

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

# EOS #1-45 — Edge of Eternities: Stellar Sights, first art treatment
STELLAR_SIGHTS_I_CARDS = [
    {"mtg_name": "Ancient Tomb"           , "set": "eos", "num": "1"  , "slug": "ancient-tomb"           , "tcg_id": "643635"},
    {"mtg_name": "Blast Zone"             , "set": "eos", "num": "2"  , "slug": "blast-zone"             , "tcg_id": "644786"},
    {"mtg_name": "Blinkmoth Nexus"        , "set": "eos", "num": "3"  , "slug": "blinkmoth-nexus"        , "tcg_id": "641820"},
    {"mtg_name": "Bonders' Enclave"       , "set": "eos", "num": "4"  , "slug": "bonders-enclave"        , "tcg_id": "642774"},
    {"mtg_name": "Cascading Cataracts"    , "set": "eos", "num": "5"  , "slug": "cascading-cataracts"    , "tcg_id": "644787"},
    {"mtg_name": "Cathedral of War"       , "set": "eos", "num": "6"  , "slug": "cathedral-of-war"       , "tcg_id": "643905"},
    {"mtg_name": "Celestial Colonnade"    , "set": "eos", "num": "7"  , "slug": "celestial-colonnade"    , "tcg_id": "641797"},
    {"mtg_name": "Contested War Zone"     , "set": "eos", "num": "8"  , "slug": "contested-war-zone"     , "tcg_id": "644788"},
    {"mtg_name": "Creeping Tar Pit"       , "set": "eos", "num": "9"  , "slug": "creeping-tar-pit"       , "tcg_id": "643906"},
    {"mtg_name": "Crystal Quarry"         , "set": "eos", "num": "10" , "slug": "crystal-quarry"         , "tcg_id": "643639"},
    {"mtg_name": "Deserted Temple"        , "set": "eos", "num": "11" , "slug": "deserted-temple"        , "tcg_id": "643907"},
    {"mtg_name": "Dust Bowl"              , "set": "eos", "num": "12" , "slug": "dust-bowl"              , "tcg_id": "643643"},
    {"mtg_name": "Echoing Deeps"          , "set": "eos", "num": "13" , "slug": "echoing-deeps"          , "tcg_id": "643647"},
    {"mtg_name": "Eldrazi Temple"         , "set": "eos", "num": "14" , "slug": "eldrazi-temple"         , "tcg_id": "641822"},
    {"mtg_name": "Endless Sands"          , "set": "eos", "num": "15" , "slug": "endless-sands"          , "tcg_id": "644789"},
    {"mtg_name": "Gemstone Caverns"       , "set": "eos", "num": "16" , "slug": "gemstone-caverns"       , "tcg_id": "641799"},
    {"mtg_name": "Grove of the Burnwillows","set": "eos", "num": "17" , "slug": "grove-of-the-burnwillows","tcg_id": "643908"},
    {"mtg_name": "High Market"            , "set": "eos", "num": "18" , "slug": "high-market"            , "tcg_id": "641814"},
    {"mtg_name": "Hissing Quagmire"       , "set": "eos", "num": "19" , "slug": "hissing-quagmire"       , "tcg_id": "643909"},
    {"mtg_name": "Inkmoth Nexus"          , "set": "eos", "num": "20" , "slug": "inkmoth-nexus"          , "tcg_id": "643058"},
    {"mtg_name": "Inventors' Fair"        , "set": "eos", "num": "21" , "slug": "inventors-fair"         , "tcg_id": "644790"},
    {"mtg_name": "Lavaclaw Reaches"       , "set": "eos", "num": "22" , "slug": "lavaclaw-reaches"       , "tcg_id": "643910"},
    {"mtg_name": "Lotus Field"            , "set": "eos", "num": "23" , "slug": "lotus-field"            , "tcg_id": "643911"},
    {"mtg_name": "Lumbering Falls"        , "set": "eos", "num": "24" , "slug": "lumbering-falls"        , "tcg_id": "643912"},
    {"mtg_name": "Mana Confluence"        , "set": "eos", "num": "25" , "slug": "mana-confluence"        , "tcg_id": "641801"},
    {"mtg_name": "Meteor Crater"          , "set": "eos", "num": "26" , "slug": "meteor-crater"          , "tcg_id": "643651"},
    {"mtg_name": "Mirrorpool"             , "set": "eos", "num": "27" , "slug": "mirrorpool"             , "tcg_id": "643913"},
    {"mtg_name": "Mutavault"              , "set": "eos", "num": "28" , "slug": "mutavault"              , "tcg_id": "638925"},
    {"mtg_name": "Mystifying Maze"        , "set": "eos", "num": "29" , "slug": "mystifying-maze"        , "tcg_id": "643657"},
    {"mtg_name": "Needle Spires"          , "set": "eos", "num": "30" , "slug": "needle-spires"          , "tcg_id": "643914"},
    {"mtg_name": "Nesting Grounds"        , "set": "eos", "num": "31" , "slug": "nesting-grounds"        , "tcg_id": "641804"},
    {"mtg_name": "Petrified Field"        , "set": "eos", "num": "32" , "slug": "petrified-field"        , "tcg_id": "644791"},
    {"mtg_name": "Plaza of Heroes"        , "set": "eos", "num": "33" , "slug": "plaza-of-heroes"        , "tcg_id": "643661"},
    {"mtg_name": "Power Depot"            , "set": "eos", "num": "34" , "slug": "power-depot"            , "tcg_id": "644792"},
    {"mtg_name": "Raging Ravine"          , "set": "eos", "num": "35" , "slug": "raging-ravine"          , "tcg_id": "643915"},
    {"mtg_name": "Reflecting Pool"        , "set": "eos", "num": "36" , "slug": "reflecting-pool"        , "tcg_id": "642776"},
    {"mtg_name": "Scavenger Grounds"      , "set": "eos", "num": "37" , "slug": "scavenger-grounds"      , "tcg_id": "644793"},
    {"mtg_name": "Shambling Vent"         , "set": "eos", "num": "38" , "slug": "shambling-vent"         , "tcg_id": "643916"},
    {"mtg_name": "Stirring Wildwood"      , "set": "eos", "num": "39" , "slug": "stirring-wildwood"      , "tcg_id": "643917"},
    {"mtg_name": "Strip Mine"             , "set": "eos", "num": "40" , "slug": "strip-mine"             , "tcg_id": "643665"},
    {"mtg_name": "Sunken Citadel"         , "set": "eos", "num": "41" , "slug": "sunken-citadel"         , "tcg_id": "643508"},
    {"mtg_name": "Swarmyard"              , "set": "eos", "num": "42" , "slug": "swarmyard"              , "tcg_id": "643670"},
    {"mtg_name": "Terrain Generator"      , "set": "eos", "num": "43" , "slug": "terrain-generator"      , "tcg_id": "643675"},
    {"mtg_name": "Thespian's Stage"       , "set": "eos", "num": "44" , "slug": "thespians-stage"        , "tcg_id": "641824"},
    {"mtg_name": "Wandering Fumarole"     , "set": "eos", "num": "45" , "slug": "wandering-fumarole"     , "tcg_id": "643918"},
]

# EOS #46-90 — Edge of Eternities: Stellar Sights, second art treatment
STELLAR_SIGHTS_II_CARDS = [
    {"mtg_name": "Ancient Tomb"           , "set": "eos", "num": "46" , "slug": "ancient-tomb"           , "tcg_id": "643637"},
    {"mtg_name": "Blast Zone"             , "set": "eos", "num": "47" , "slug": "blast-zone"             , "tcg_id": "644801"},
    {"mtg_name": "Blinkmoth Nexus"        , "set": "eos", "num": "48" , "slug": "blinkmoth-nexus"        , "tcg_id": "641821"},
    {"mtg_name": "Bonders' Enclave"       , "set": "eos", "num": "49" , "slug": "bonders-enclave"        , "tcg_id": "642778"},
    {"mtg_name": "Cascading Cataracts"    , "set": "eos", "num": "50" , "slug": "cascading-cataracts"    , "tcg_id": "644806"},
    {"mtg_name": "Cathedral of War"       , "set": "eos", "num": "51" , "slug": "cathedral-of-war"       , "tcg_id": "643919"},
    {"mtg_name": "Celestial Colonnade"    , "set": "eos", "num": "52" , "slug": "celestial-colonnade"    , "tcg_id": "641810"},
    {"mtg_name": "Contested War Zone"     , "set": "eos", "num": "53" , "slug": "contested-war-zone"     , "tcg_id": "644809"},
    {"mtg_name": "Creeping Tar Pit"       , "set": "eos", "num": "54" , "slug": "creeping-tar-pit"       , "tcg_id": "643920"},
    {"mtg_name": "Crystal Quarry"         , "set": "eos", "num": "55" , "slug": "crystal-quarry"         , "tcg_id": "643641"},
    {"mtg_name": "Deserted Temple"        , "set": "eos", "num": "56" , "slug": "deserted-temple"        , "tcg_id": "643921"},
    {"mtg_name": "Dust Bowl"              , "set": "eos", "num": "57" , "slug": "dust-bowl"              , "tcg_id": "643645"},
    {"mtg_name": "Echoing Deeps"          , "set": "eos", "num": "58" , "slug": "echoing-deeps"          , "tcg_id": "643649"},
    {"mtg_name": "Eldrazi Temple"         , "set": "eos", "num": "59" , "slug": "eldrazi-temple"         , "tcg_id": "641823"},
    {"mtg_name": "Endless Sands"          , "set": "eos", "num": "60" , "slug": "endless-sands"          , "tcg_id": "644812"},
    {"mtg_name": "Gemstone Caverns"       , "set": "eos", "num": "61" , "slug": "gemstone-caverns"       , "tcg_id": "641811"},
    {"mtg_name": "Grove of the Burnwillows","set": "eos", "num": "62" , "slug": "grove-of-the-burnwillows","tcg_id": "643923"},
    {"mtg_name": "High Market"            , "set": "eos", "num": "63" , "slug": "high-market"            , "tcg_id": "641815"},
    {"mtg_name": "Hissing Quagmire"       , "set": "eos", "num": "64" , "slug": "hissing-quagmire"       , "tcg_id": "643924"},
    {"mtg_name": "Inkmoth Nexus"          , "set": "eos", "num": "65" , "slug": "inkmoth-nexus"          , "tcg_id": "643060"},
    {"mtg_name": "Inventors' Fair"        , "set": "eos", "num": "66" , "slug": "inventors-fair"         , "tcg_id": "644815"},
    {"mtg_name": "Lavaclaw Reaches"       , "set": "eos", "num": "67" , "slug": "lavaclaw-reaches"       , "tcg_id": "643925"},
    {"mtg_name": "Lotus Field"            , "set": "eos", "num": "68" , "slug": "lotus-field"            , "tcg_id": "643926"},
    {"mtg_name": "Lumbering Falls"        , "set": "eos", "num": "69" , "slug": "lumbering-falls"        , "tcg_id": "643922"},
    {"mtg_name": "Mana Confluence"        , "set": "eos", "num": "70" , "slug": "mana-confluence"        , "tcg_id": "641816"},
    {"mtg_name": "Meteor Crater"          , "set": "eos", "num": "71" , "slug": "meteor-crater"          , "tcg_id": "643654"},
    {"mtg_name": "Mirrorpool"             , "set": "eos", "num": "72" , "slug": "mirrorpool"             , "tcg_id": "643927"},
    {"mtg_name": "Mutavault"              , "set": "eos", "num": "73" , "slug": "mutavault"              , "tcg_id": "638926"},
    {"mtg_name": "Mystifying Maze"        , "set": "eos", "num": "74" , "slug": "mystifying-maze"        , "tcg_id": "643659"},
    {"mtg_name": "Needle Spires"          , "set": "eos", "num": "75" , "slug": "needle-spires"          , "tcg_id": "643928"},
    {"mtg_name": "Nesting Grounds"        , "set": "eos", "num": "76" , "slug": "nesting-grounds"        , "tcg_id": "641819"},
    {"mtg_name": "Petrified Field"        , "set": "eos", "num": "77" , "slug": "petrified-field"        , "tcg_id": "644818"},
    {"mtg_name": "Plaza of Heroes"        , "set": "eos", "num": "78" , "slug": "plaza-of-heroes"        , "tcg_id": "643663"},
    {"mtg_name": "Power Depot"            , "set": "eos", "num": "79" , "slug": "power-depot"            , "tcg_id": "644821"},
    {"mtg_name": "Raging Ravine"          , "set": "eos", "num": "80" , "slug": "raging-ravine"          , "tcg_id": "643929"},
    {"mtg_name": "Reflecting Pool"        , "set": "eos", "num": "81" , "slug": "reflecting-pool"        , "tcg_id": "642780"},
    {"mtg_name": "Scavenger Grounds"      , "set": "eos", "num": "82" , "slug": "scavenger-grounds"      , "tcg_id": "644824"},
    {"mtg_name": "Shambling Vent"         , "set": "eos", "num": "83" , "slug": "shambling-vent"         , "tcg_id": "643930"},
    {"mtg_name": "Stirring Wildwood"      , "set": "eos", "num": "84" , "slug": "stirring-wildwood"      , "tcg_id": "643931"},
    {"mtg_name": "Strip Mine"             , "set": "eos", "num": "85" , "slug": "strip-mine"             , "tcg_id": "643667"},
    {"mtg_name": "Sunken Citadel"         , "set": "eos", "num": "86" , "slug": "sunken-citadel"         , "tcg_id": "643510"},
    {"mtg_name": "Swarmyard"              , "set": "eos", "num": "87" , "slug": "swarmyard"              , "tcg_id": "643672"},
    {"mtg_name": "Terrain Generator"      , "set": "eos", "num": "88" , "slug": "terrain-generator"      , "tcg_id": "643678"},
    {"mtg_name": "Thespian's Stage"       , "set": "eos", "num": "89" , "slug": "thespians-stage"        , "tcg_id": "641825"},
    {"mtg_name": "Wandering Fumarole"     , "set": "eos", "num": "90" , "slug": "wandering-fumarole"     , "tcg_id": "643932"},
]


def fetch_scryfall(card):
    """Returns dict with tcg price and image_url for the card."""
    url = f"https://api.scryfall.com/cards/{card['set']}/{card['num']}"
    result = subprocess.run(
        ["curl", "-s", "-A", "Mozilla/5.0", url],
        capture_output=True,
        text=False,
    )
    try:
        stdout = result.stdout.decode("utf-8", errors="replace")
        data = json.loads(stdout)
        price = data.get("prices", {}).get("usd")
        images = data.get("image_uris") or {}
        # Fallback for double-faced cards
        if not images and data.get("card_faces"):
            images = data["card_faces"][0].get("image_uris") or {}
        image_url = images.get("normal") or images.get("large") or images.get("small")
        return {
            "tcg_price": float(price) if price else None,
            "image_url": image_url,
        }
    except Exception:
        return {"tcg_price": None, "image_url": None}


def fetch_manapool_price(card):
    url = f"https://manapool.com/card/{card['set']}/{card['num']}/{card['slug']}"
    result = subprocess.run(
        ["curl", "-s", "-A", "Mozilla/5.0",
         "-H", "Accept: text/html,application/xhtml+xml",
         url],
        capture_output=True,
        text=False,
    )
    html = result.stdout.decode("utf-8", errors="replace")
    m = re.search(r'\\"marketPrices\\":\{\\"price\\": (\d+),', html)
    if m:
        return int(m.group(1)) / 100.0
    return None


def fetch_owned():
    """Returns {(set, cn): {condition, foil}} for all cards in the Moxfield binder."""
    headers = {
        'Accept': 'application/json',
        'Referer': 'https://moxfield.com/',
        'Origin': 'https://moxfield.com',
        'User-Agent': 'Mozilla/5.0',
    }

    session_cookie = os.environ.get("MOXFIELD_SESSION_COOKIE", "").strip()
    if session_cookie:
        headers['Cookie'] = session_cookie
        print("  Using authenticated Moxfield session cookie")
    else:
        print("  No Moxfield session cookie configured; binder ownership data will be skipped")

    # Collector number ranges we care about, by set
    ranges = {
        'ltc': (348, 377),
        'ltr': (302, 331),
        'eos': (1, 90),
    }

    owned = {}
    page = 1
    while True:
        url = f"https://api2.moxfield.com/v1/trade-binders/{MOXFIELD_BINDER_ID}?pageNumber={page}&pageSize=100"
        request = urllib.request.Request(url, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                data = json.load(response)
        except urllib.error.HTTPError as e:
            if e.code == 403:
                print("  Moxfield API returned HTTP 403; binder ownership data will be skipped")
            else:
                print(f"  Moxfield fetch error (page {page}): {e}")
            return {}
        except Exception as e:
            print(f"  Moxfield fetch error (page {page}): {e}")
            return {}

        for entry in data.get("data", []):
            card = entry.get("card", {})
            card_set = card.get("set", "").lower()
            if card_set not in ranges:
                continue
            cn = card.get("cn", "")
            lo, hi = ranges[card_set]
            if not (cn.isdigit() and lo <= int(cn) <= hi):
                continue
            key = (card_set, cn)
            if key not in owned:
                owned[key] = {"nonfoil": False, "foil": False}
            if entry.get("finish", "nonFoil") == "foil":
                owned[key]["foil"] = True
            else:
                owned[key]["nonfoil"] = True

        if data.get("pageNumber", 1) >= data.get("totalPages", 1):
            break
        page += 1

    print(f"  Moxfield: found {len(owned)} owned cards across both sets")
    return owned


def build_card_row(card, owned):
    print(f"  {card['mtg_name']}...")
    scryfall = fetch_scryfall(card)
    mp_price = fetch_manapool_price(card)
    key = (card["set"], card["num"])
    owned_entry = owned.get(key)
    display_name = card["mtg_name"]
    if card.get("lotr_name"):
        display_name = f"{card['lotr_name']} ({card['mtg_name']})"
    return {
        "display_name": display_name,
        "mtg_name": card["mtg_name"],
        "tcg_price": scryfall["tcg_price"],
        "tcg_url": f"https://www.tcgplayer.com/product/{card['tcg_id']}?Condition=Near+Mint&Printing=Normal",
        "mp_price": mp_price,
        "mp_url": f"https://manapool.com/card/{card['set']}/{card['num']}/{card['slug']}?conditions=NM&finish=nonfoil",
        "image_url": scryfall["image_url"],
        "collected_nonfoil": owned_entry["nonfoil"] if owned_entry else False,
        "collected_foil": owned_entry["foil"] if owned_entry else False,
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

    print("Fetching Stellar Sights I prices (EOS #1-45)...")
    stellar_i = [build_card_row(c, owned) for c in STELLAR_SIGHTS_I_CARDS]
    stellar_i.sort(key=lambda x: x["tcg_price"] if x["tcg_price"] is not None else float("inf"))

    print("Fetching Stellar Sights II prices (EOS #46-90)...")
    stellar_ii = [build_card_row(c, owned) for c in STELLAR_SIGHTS_II_CARDS]
    stellar_ii.sort(key=lambda x: x["tcg_price"] if x["tcg_price"] is not None else float("inf"))

    output = {
        "updated_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "realms_and_relics": realms,
        "showcase": showcase,
        "stellar_sights_i": stellar_i,
        "stellar_sights_ii": stellar_ii,
    }
    with open("prices.json", "w") as f:
        json.dump(output, f, indent=2)

    all_cards = realms + showcase + stellar_i + stellar_ii
    owned_count = sum(1 for r in all_cards if r["collected_nonfoil"] or r["collected_foil"])
    print(f"Done. {len(realms)} R&R + {len(showcase)} Showcase + {len(stellar_i)} SS-I + {len(stellar_ii)} SS-II cards, {owned_count} owned.")


if __name__ == "__main__":
    main()
