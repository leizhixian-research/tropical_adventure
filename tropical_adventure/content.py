from __future__ import annotations

from copy import deepcopy
from typing import Any

from .models import Location


ACTION_DURATIONS = {
    "drink": 3,
    "eat": 3,
    "pick up": 3,
    "drop": 3,
    "tend fire": 6,
    "cook fish": 6,
    "boil water": 6,
    "gather": 12,
    "forage": 12,
    "move": 12,
    "wash": 12,
    "swim": 12,
    "leisure": 12,
    "explore": 18,
    "rest": 18,
    "treat wound": 18,
    "craft sharp stone": 24,
    "start fire": 36,
    "fish": 36,
    "build raincatcher": 60,
    "build shelter": 90,
}

RECIPES: dict[str, dict[str, int]] = {
    "craft sharp stone": {"stones": 1},
    "start fire": {"sticks": 2, "leaves": 1},
    "tend fire": {"sticks": 1},
    "build shelter": {"sticks": 4, "leaves": 6, "vine": 2},
    "build raincatcher": {"sticks": 2, "leaves": 4, "vine": 1},
    "fish": {"sharp stone": 1},
    "cook fish": {"raw fish": 1},
    "boil water": {"unsafe water": 1},
    "treat wound": {"bandage leaves": 1},
}

ACTION_BLUEPRINTS = {
    "craft sharp stone": "sharp stone",
    "start fire": "fire",
    "build shelter": "shelter",
    "build raincatcher": "raincatcher",
    "cook fish": "cook fish",
    "boil water": "boil water",
}

SKILL_BY_ACTION = {
    "forage": "herbology",
    "explore": "climbing",
    "wash": "swimming",
    "swim": "swimming",
    "craft sharp stone": "knapping",
    "start fire": "crafting",
    "tend fire": "crafting",
    "build shelter": "woodworking",
    "build raincatcher": "woodworking",
    "fish": "fishing",
    "cook fish": "cooking",
    "boil water": "cooking",
}

AREA_DEFS: dict[str, dict[str, Any]] = {
    "beach": {
        "discovered": True,
        "features": ["sea", "sand", "coconut palms"],
        "ground": {"coconut": 2, "sticks": 2},
        "resources": {
            "unsafe water": {"source": "sea", "infinite": True, "action": "gather"},
            "coconut": {
                "source": "coconut palms",
                "qty": 2,
                "capacity": 2,
                "regen_minutes": 3 * 1440,
                "regen_progress": 0,
                "action": "forage",
            },
            "sticks": {"source": "sand", "infinite": True, "action": "forage"},
            "leaves": {"source": "coconut palms", "infinite": True, "action": "forage"},
        },
    },
    "jungle outskirts": {
        "features": ["trees", "vines", "leaf litter"],
        "resources": {
            "sticks": {"source": "trees", "infinite": True, "action": "gather"},
            "leaves": {"source": "leaf litter", "infinite": True, "action": "forage"},
            "vine": {"source": "vines", "infinite": True, "action": "forage"},
            "coconut": {
                "source": "trees",
                "qty": 2,
                "capacity": 2,
                "regen_minutes": 4 * 1440,
                "regen_progress": 0,
                "action": "forage",
            },
        },
    },
    "rocks": {
        "features": ["stone outcrops", "cliffs"],
        "resources": {
            "stones": {"source": "stone outcrops", "infinite": True, "action": "gather"},
        },
    },
    "jungle": {
        "features": ["dense trees", "vines", "leaf litter"],
        "resources": {
            "sticks": {"source": "dense trees", "infinite": True, "action": "gather"},
            "leaves": {"source": "leaf litter", "infinite": True, "action": "forage"},
            "vine": {"source": "vines", "infinite": True, "action": "forage"},
            "bandage leaves": {"source": "leaf litter", "infinite": True, "action": "forage"},
        },
    },
    "bay": {
        "features": ["sea", "sand", "coconut palms", "fish"],
        "resources": {
            "unsafe water": {"source": "sea", "infinite": True, "action": "gather"},
            "coconut": {
                "source": "coconut palms",
                "qty": 2,
                "capacity": 2,
                "regen_minutes": 3 * 1440,
                "regen_progress": 0,
                "action": "forage",
            },
            "stones": {"source": "sand", "infinite": True, "action": "forage"},
            "raw fish": {"source": "fish", "infinite": True, "action": "fish"},
        },
    },
    "mangrove forest": {
        "features": ["mangrove roots", "flooded mud", "palm fronds"],
        "resources": {
            "unsafe water": {"source": "flooded mud", "infinite": True, "action": "gather"},
            "leaves": {"source": "palm fronds", "infinite": True, "action": "forage"},
            "sticks": {"source": "mangrove roots", "infinite": True, "action": "forage"},
            "stones": {"source": "flooded mud", "infinite": True, "action": "forage"},
        },
    },
    "wetlands": {
        "features": ["rain puddles", "sago palms", "dense trees"],
        "resources": {
            "unsafe water": {"source": "rain puddles", "infinite": True, "action": "gather"},
            "leaves": {"source": "sago palms", "infinite": True, "action": "forage"},
            "vine": {"source": "dense trees", "infinite": True, "action": "forage"},
            "bandage leaves": {"source": "dense trees", "infinite": True, "action": "forage"},
        },
    },
    "deep jungle": {
        "features": ["dense trees", "vines", "deep shade"],
        "resources": {
            "sticks": {"source": "dense trees", "infinite": True, "action": "gather"},
            "leaves": {"source": "deep shade", "infinite": True, "action": "forage"},
            "vine": {"source": "vines", "infinite": True, "action": "forage"},
            "bandage leaves": {"source": "deep shade", "infinite": True, "action": "forage"},
        },
    },
    "secret cove": {
        "features": ["sea", "sand", "stone outcrops"],
        "resources": {
            "unsafe water": {"source": "sea", "infinite": True, "action": "gather"},
            "stones": {"source": "stone outcrops", "infinite": True, "action": "gather"},
        },
    },
    "acid lake": {
        "features": ["acid shore", "brimstone vent", "stone outcrops"],
        "resources": {
            "stones": {"source": "stone outcrops", "infinite": True, "action": "gather"},
        },
    },
    "atoll": {
        "features": ["sea", "sand", "coconut palms"],
        "resources": {
            "unsafe water": {"source": "sea", "infinite": True, "action": "gather"},
            "coconut": {
                "source": "coconut palms",
                "qty": 2,
                "capacity": 2,
                "regen_minutes": 3 * 1440,
                "regen_progress": 0,
                "action": "forage",
            },
            "leaves": {"source": "coconut palms", "infinite": True, "action": "forage"},
        },
    },
    "bird rock": {
        "features": ["sea", "stone outcrops", "seagull nests"],
        "resources": {
            "unsafe water": {"source": "sea", "infinite": True, "action": "gather"},
            "stones": {"source": "stone outcrops", "infinite": True, "action": "gather"},
        },
    },
    "desolate beach": {
        "features": ["sea", "sand", "debris"],
        "resources": {
            "unsafe water": {"source": "sea", "infinite": True, "action": "gather"},
            "sticks": {"source": "debris", "infinite": True, "action": "forage"},
            "stones": {"source": "sand", "infinite": True, "action": "forage"},
        },
    },
    "eastern grasslands": {
        "features": ["grass", "small trees", "open sun"],
        "resources": {
            "sticks": {"source": "small trees", "infinite": True, "action": "gather"},
            "leaves": {"source": "grass", "infinite": True, "action": "forage"},
        },
    },
    "western grasslands": {
        "features": ["grass", "small trees", "open sun"],
        "resources": {
            "sticks": {"source": "small trees", "infinite": True, "action": "gather"},
            "leaves": {"source": "grass", "infinite": True, "action": "forage"},
        },
    },
    "eastern highlands": {
        "features": ["high cliffs", "stone outcrops", "dry grass"],
        "resources": {
            "stones": {"source": "stone outcrops", "infinite": True, "action": "gather"},
            "sticks": {"source": "dry grass", "infinite": True, "action": "forage"},
        },
    },
    "western highlands": {
        "features": ["high cliffs", "stone outcrops", "dry grass"],
        "resources": {
            "stones": {"source": "stone outcrops", "infinite": True, "action": "gather"},
            "sticks": {"source": "dry grass", "infinite": True, "action": "forage"},
        },
    },
    "jungle highlands": {
        "features": ["high cliffs", "dense trees", "vines"],
        "resources": {
            "stones": {"source": "high cliffs", "infinite": True, "action": "gather"},
            "sticks": {"source": "dense trees", "infinite": True, "action": "gather"},
            "vine": {"source": "vines", "infinite": True, "action": "forage"},
        },
    },
    "secret valley": {
        "features": ["dense trees", "rain puddles", "wild yams"],
        "resources": {
            "unsafe water": {"source": "rain puddles", "infinite": True, "action": "gather"},
            "leaves": {"source": "dense trees", "infinite": True, "action": "forage"},
            "vine": {"source": "dense trees", "infinite": True, "action": "forage"},
        },
    },
    "volcano": {
        "features": ["brimstone vent", "stone outcrops", "hot ground"],
        "resources": {
            "stones": {"source": "stone outcrops", "infinite": True, "action": "gather"},
            "ash": {"source": "hot ground", "infinite": True, "action": "forage"},
        },
    },
    "highland hole": {
        "features": ["hole", "high cliffs", "stone outcrops"],
        "resources": {
            "stones": {"source": "stone outcrops", "infinite": True, "action": "gather"},
        },
    },
    "enclosure": {
        "features": ["fence", "trampled grass"],
        "resources": {
            "sticks": {"source": "fence", "infinite": True, "action": "forage"},
        },
    },
    "raft": {
        "features": ["sea", "floating debris"],
        "resources": {
            "unsafe water": {"source": "sea", "infinite": True, "action": "gather"},
            "sticks": {"source": "floating debris", "infinite": True, "action": "forage"},
        },
    },
    "bat cave": {
        "features": ["darkness", "bat colony", "stone outcrops"],
        "resources": {
            "stones": {"source": "stone outcrops", "infinite": True, "action": "gather"},
        },
    },
    "cellar": {
        "features": ["darkness", "storage shelves"],
        "resources": {
            "sticks": {"source": "storage shelves", "infinite": True, "action": "forage"},
        },
    },
    "dark cave": {
        "features": ["darkness", "stone outcrops", "cave puddle"],
        "resources": {
            "stones": {"source": "stone outcrops", "infinite": True, "action": "gather"},
            "unsafe water": {"source": "cave puddle", "infinite": True, "action": "gather"},
        },
    },
    "grasslands cave": {
        "features": ["darkness", "stone outcrops", "dry grass"],
        "resources": {
            "stones": {"source": "stone outcrops", "infinite": True, "action": "gather"},
            "sticks": {"source": "dry grass", "infinite": True, "action": "forage"},
        },
    },
    "macaque den": {
        "features": ["darkness", "dense trees", "debris"],
        "resources": {
            "sticks": {"source": "debris", "infinite": True, "action": "gather"},
            "leaves": {"source": "dense trees", "infinite": True, "action": "forage"},
        },
    },
    "mud hut": {
        "features": ["shelter walls", "storage shelves"],
        "resources": {
            "sticks": {"source": "storage shelves", "infinite": True, "action": "forage"},
        },
    },
    "plane crash": {
        "features": ["debris", "storage shelves"],
        "resources": {
            "sticks": {"source": "debris", "infinite": True, "action": "gather"},
        },
    },
    "sea cave": {
        "features": ["sea", "darkness", "stone outcrops"],
        "resources": {
            "unsafe water": {"source": "sea", "infinite": True, "action": "gather"},
            "stones": {"source": "stone outcrops", "infinite": True, "action": "gather"},
        },
    },
    "shed": {
        "features": ["shelter walls", "storage shelves"],
        "resources": {
            "sticks": {"source": "storage shelves", "infinite": True, "action": "forage"},
        },
    },
    "stone hut": {
        "features": ["shelter walls", "stone outcrops"],
        "resources": {
            "stones": {"source": "stone outcrops", "infinite": True, "action": "gather"},
        },
    },
    "tidal cave": {
        "features": ["sea", "darkness", "shallow pools"],
        "resources": {
            "unsafe water": {"source": "sea", "infinite": True, "action": "gather"},
            "raw fish": {"source": "shallow pools", "infinite": True, "action": "fish"},
        },
    },
    "crystal chamber": {
        "features": ["darkness", "crystals", "stone outcrops"],
        "resources": {
            "stones": {"source": "stone outcrops", "infinite": True, "action": "gather"},
        },
    },
    "damp chamber": {
        "features": ["darkness", "cave puddle", "stone outcrops"],
        "resources": {
            "unsafe water": {"source": "cave puddle", "infinite": True, "action": "gather"},
            "stones": {"source": "stone outcrops", "infinite": True, "action": "gather"},
        },
    },
    "darkness": {
        "features": ["darkness", "narrow passage"],
        "resources": {
            "stones": {"source": "narrow passage", "infinite": True, "action": "gather"},
        },
    },
    "flooded chamber": {
        "features": ["seawater", "darkness", "stone outcrops"],
        "resources": {
            "unsafe water": {"source": "seawater", "infinite": True, "action": "gather"},
            "stones": {"source": "stone outcrops", "infinite": True, "action": "gather"},
        },
    },
    "high chamber": {
        "features": ["darkness", "shaft", "stone outcrops"],
        "resources": {
            "stones": {"source": "stone outcrops", "infinite": True, "action": "gather"},
        },
    },
    "medium chamber": {
        "features": ["darkness", "shaft", "stone outcrops"],
        "resources": {
            "stones": {"source": "stone outcrops", "infinite": True, "action": "gather"},
        },
    },
    "low chamber": {
        "features": ["darkness", "shaft", "cave puddle"],
        "resources": {
            "unsafe water": {"source": "cave puddle", "infinite": True, "action": "gather"},
            "stones": {"source": "shaft", "infinite": True, "action": "gather"},
        },
    },
    "narrow tunnel": {
        "features": ["darkness", "narrow passage"],
        "resources": {
            "stones": {"source": "narrow passage", "infinite": True, "action": "gather"},
        },
    },
    "tunnel": {
        "features": ["darkness", "narrow passage"],
        "resources": {
            "stones": {"source": "narrow passage", "infinite": True, "action": "gather"},
        },
    },
}

DISCOVERY_ORDER = [
    ("jungle outskirts", {"fire"}),
    ("rocks", {"shelter", "raincatcher"}),
    ("jungle", set()),
    ("bay", {"cook fish", "boil water"}),
    ("mangrove forest", set()),
    ("wetlands", set()),
    ("deep jungle", set()),
    ("secret cove", set()),
    ("desolate beach", set()),
    ("bird rock", set()),
    ("atoll", set()),
    ("eastern grasslands", set()),
    ("western grasslands", set()),
    ("eastern highlands", set()),
    ("western highlands", set()),
    ("jungle highlands", set()),
    ("secret valley", set()),
    ("volcano", set()),
    ("acid lake", set()),
    ("highland hole", set()),
    ("enclosure", set()),
    ("raft", set()),
    ("bat cave", set()),
    ("cellar", set()),
    ("dark cave", set()),
    ("grasslands cave", set()),
    ("macaque den", set()),
    ("mud hut", set()),
    ("plane crash", set()),
    ("sea cave", set()),
    ("shed", set()),
    ("stone hut", set()),
    ("tidal cave", set()),
    ("crystal chamber", set()),
    ("damp chamber", set()),
    ("darkness", set()),
    ("flooded chamber", set()),
    ("high chamber", set()),
    ("medium chamber", set()),
    ("low chamber", set()),
    ("narrow tunnel", set()),
    ("tunnel", set()),
]

AREA_NEIGHBORS = {
    "acid lake": ["volcano"],
    "atoll": ["raft"],
    "bay": ["beach", "jungle", "mangrove forest"],
    "beach": ["bay", "jungle outskirts", "rocks"],
    "bird rock": ["desolate beach", "rocks"],
    "crystal chamber": ["flooded chamber"],
    "damp chamber": ["dark cave", "wetlands"],
    "darkness": ["highland hole"],
    "deep jungle": ["jungle highlands", "secret valley", "wetlands"],
    "desolate beach": ["tidal cave", "bird rock", "eastern grasslands", "mangrove forest", "volcano"],
    "eastern grasslands": ["desolate beach", "western grasslands", "eastern highlands"],
    "eastern highlands": ["tunnel", "eastern grasslands", "western highlands", "volcano"],
    "flooded chamber": ["secret cove"],
    "high chamber": ["medium chamber"],
    "highland hole": ["darkness"],
    "jungle": ["bay", "western grasslands", "jungle outskirts", "wetlands"],
    "jungle highlands": ["bat cave", "macaque den", "deep jungle", "secret cove", "western highlands"],
    "jungle outskirts": ["beach", "jungle"],
    "low chamber": ["crystal chamber", "narrow tunnel"],
    "macaque den": ["jungle highlands"],
    "mangrove forest": ["bay", "desolate beach", "western grasslands"],
    "medium chamber": ["darkness", "low chamber"],
    "narrow tunnel": ["damp chamber"],
    "plane crash": ["wetlands"],
    "rocks": ["sea cave", "beach", "bird rock"],
    "secret cove": ["flooded chamber", "bird rock", "jungle highlands"],
    "secret valley": ["deep jungle"],
    "tunnel": ["high chamber"],
    "volcano": ["desolate beach", "acid lake", "eastern highlands"],
    "western grasslands": ["grasslands cave", "eastern grasslands", "western highlands", "jungle", "mangrove forest"],
    "western highlands": ["highland hole", "western grasslands", "eastern highlands", "jungle highlands"],
    "wetlands": ["dark cave", "deep jungle", "jungle", "jungle highlands"],
}

AREA_EXPLORE_AREAS = {
    "bay": ["jungle", "beach"],
    "beach": ["jungle outskirts", "rocks"],
    "bird rock": ["rocks", "desolate beach"],
    "deep jungle": ["wetlands", "jungle highlands", "secret valley"],
    "desolate beach": ["eastern grasslands", "volcano", "tidal cave", "mangrove forest", "bird rock"],
    "eastern grasslands": ["western grasslands", "eastern highlands", "desolate beach"],
    "eastern highlands": ["eastern grasslands", "volcano"],
    "jungle": ["wetlands", "bay", "western grasslands", "jungle outskirts"],
    "jungle highlands": ["deep jungle", "macaque den", "western highlands", "bat cave", "secret cove"],
    "jungle outskirts": ["beach"],
    "low chamber": ["narrow tunnel"],
    "narrow tunnel": ["damp chamber"],
    "rocks": ["beach"],
    "secret cove": ["jungle highlands", "bird rock"],
    "secret valley": ["deep jungle"],
    "volcano": ["eastern highlands", "desolate beach", "acid lake"],
    "western grasslands": ["mangrove forest", "western highlands", "eastern grasslands"],
    "western highlands": ["jungle highlands", "eastern highlands", "western grasslands"],
    "wetlands": ["jungle highlands", "jungle", "deep jungle"],
}

AREA_EXPLORE_CARDS = {
    "acid lake": ["brimstone vent"],
    "bird rock": ["tide pool", "flooded tide pool", "shipwreck"],
    "crystal chamber": ["copper vein", "narrow passage"],
    "damp chamber": ["dry cave pond", "narrow passage"],
    "dark cave": ["dry puddle"],
    "desolate beach": ["tide pool", "flooded tide pool"],
    "eastern highlands": ["collapsed tunnel entrance"],
    "high chamber": ["copper vein", "shaft"],
    "low chamber": ["copper vein", "narrow passage"],
    "medium chamber": ["copper vein", "shaft", "narrow passage"],
    "narrow tunnel": ["copper vein"],
    "rocks": ["tide pool", "flooded tide pool"],
    "western highlands": ["hole"],
    "wetlands": ["dry puddle"],
}

AREA_EXPLORE_ITEMS = {
    "acid lake": [("geode_3_limit", 75, "geode", 1, 1, 3), (75, "heavy stone", 1, 1), (800, "stones", 1, 1), (200, "sulphurous stone", 1, 1)],
    "atoll": [("stone_4_limit", 300, "stones", 1, 1, 4), (200, "pretty seashells", 1, 1)],
    "bay": [("coconut_5_limit", 300, "coconut", 1, 1, 5), ("coconut_1_limit", 3000, "coconut", 1, 1, 1), ("stone_1_limit", 3000, "stones", 1, 1, 1), ("stone_6_limit", 900, "stones", 1, 1, 6), ("stone_heavy_1_limit", 10000, "heavy stone", 1, 1, 1), ("stone_heavy_3_limit", 150, "heavy stone", 1, 1, 3), ("sticks_2_limit", 1000, "sticks", 1, 1, 2), (350, "leaves", 4, 8), (75, "palm bush", 1, 1), (200, "pretty seashells", 1, 1), (100, "sticks", 1, 1)],
    "beach": [("coconut_5_limit", 300, "coconut", 1, 1, 5), ("stone_1_limit", 1000, "stones", 1, 1, 1), ("stone_5_limit", 300, "stones", 1, 1, 5), ("heavy_stone_1_limit", 10000, "heavy stone", 1, 1, 1), ("heavy_stone_3_limit", 100, "heavy stone", 1, 1, 3), (250, "leaves", 4, 8), (75, "palm bush", 1, 1), (200, "pretty seashells", 1, 1), (100, "sticks", 1, 2), (50, "wood", 1, 1)],
    "bird rock": [(1500, "guano", 1, 2), (1000, "heavy stone", 1, 1), (300, "pretty seashells", 1, 1), (2000, "stones", 1, 1)],
    "crystal chamber": [("calcite_4_limit", 1, "calcite crystal", 1, 1, 4), ("geode_3_limit", 5, "geode", 1, 1, 3), (10, "stones", 1, 1)],
    "damp chamber": [("stone_4_limit", 10, "stones", 1, 1, 4), ("geode_3_limit", 5, "geode", 1, 1, 3), (4, "bugs", 3, 3)],
    "dark cave": [("stone_4_limit", 10, "stones", 1, 1, 4), (4, "bugs", 3, 3)],
    "deep jungle": [("wood_1_limit", 1000000, "wood", 1, 1, 1), ("stone_3_limit", 800, "stones", 1, 1, 3), ("heavy_stone_2_limit", 300, "heavy stone", 1, 1, 2), (1200, "leaves", 1, 4), (600, "long stick", 1, 1), (400, "palm bush", 1, 1), (800, "sticks", 1, 2), (800, "wood", 1, 1)],
    "desolate beach": [("cocon_1_limit", 500, "coconut", 1, 1, 1), ("brimstone_stone_12_limit", 75, "sulphurous stone", 1, 1, 12), ("sticks_1_limit", 1000, "sticks", 1, 1, 1), ("wood_1_limit", 750, "wood", 1, 1, 1), (100, "coconut", 1, 1), (100, "flint", 1, 1), (50, "flint slab", 1, 1), (750, "heavy stone", 1, 1), (50, "obsidian", 1, 1), (400, "pretty seashells", 1, 1), (300, "sticks", 1, 1), (1500, "stones", 1, 1), (200, "wood", 1, 1)],
    "eastern grasslands": [("stones_8_limit", 400, "stones", 1, 1, 8), ("heavy_stone_4_limit", 300, "heavy stone", 1, 1, 4), (400, "leaves", 1, 2), (400, "sticks", 1, 2), (500, "wood", 1, 1)],
    "eastern highlands": [("copper_1_limit", 125, "copper ore", 1, 1, 1), ("geode_9_limit", 100, "geode", 1, 1, 9), (200, "flint", 1, 1), (50, "flint slab", 1, 1), (300, "heavy stone", 1, 1), (800, "stones", 1, 1), (500, "wood", 1, 1)],
    "flooded chamber": [("geode_2_limit", 2, "geode", 1, 1, 2), ("flint_3_limit", 1, "flint", 1, 1, 3), ("flint_slab_1_limit", 1, "flint slab", 1, 1, 1), (1, "crab", 1, 1), (1, "prawns", 1, 1), (10, "stones", 1, 1)],
    "high chamber": [("geode_3_limit", 3, "geode", 1, 1, 3), ("flint_4_limit", 1, "flint", 1, 1, 4), ("flint_slab_1_limit", 1, "flint slab", 1, 1, 1), (10, "stones", 1, 1)],
    "jungle": [("wood_2_limit", 1000000, "wood", 1, 1, 2), ("stone_3_limit", 800, "stones", 1, 1, 3), ("heavy_stone_2_limit", 300, "heavy stone", 1, 1, 2), (1200, "leaves", 1, 4), (600, "long stick", 1, 1), (300, "palm bush", 1, 1), (800, "sticks", 1, 2), (800, "wood", 1, 1)],
    "jungle highlands": [("wood_1_limit", 1000000, "wood", 1, 1, 1), ("stone_6_limit", 800, "stones", 1, 1, 6), ("flint_3_limit", 400, "flint", 1, 1, 3), ("flint_slab_1_limit", 200, "flint slab", 1, 1, 1), (300, "heavy stone", 1, 1), (1000, "leaves", 1, 4), (600, "long stick", 1, 1), (200, "palm bush", 1, 1), (800, "sticks", 1, 2), (800, "wood", 1, 1)],
    "jungle outskirts": [("wood_1_limit", 9999, "wood", 1, 1, 1), ("wood_8_limit", 400, "wood", 1, 1, 8), ("coconut_6_limit", 100, "coconut", 1, 1, 6), ("aloe_vera_1_limit", 1000, "aloe vera", 1, 1, 1), ("heavy_stone_2_limit", 200, "heavy stone", 1, 1, 2), (600, "leaves", 1, 8), (200, "palm bush", 1, 1), (400, "sticks", 1, 2), (200, "wood", 1, 1)],
    "low chamber": [("geode_4_limit", 3, "geode", 1, 1, 4), ("flint_4_limit", 1, "flint", 1, 1, 4), ("flint_slab_1_limit", 1, "flint slab", 1, 1, 1), (10, "stones", 1, 1)],
    "mangrove forest": [("stone_5_limit", 100, "stones", 1, 1, 5), ("heavy_stone_2_limit", 50, "heavy stone", 1, 1, 2), (300, "leaves", 3, 6)],
    "medium chamber": [("geode_3_limit", 3, "geode", 1, 1, 3), ("flint_4_limit", 1, "flint", 1, 1, 4), ("flint_slab_1_limit", 1, "flint slab", 1, 1, 1), (10, "stones", 1, 1)],
    "narrow tunnel": [("stone_4_limit", 10, "stones", 1, 1, 4), ("geode_2_limit", 3, "geode", 1, 1, 2)],
    "rocks": [("flint_1_limit", 3000, "flint", 1, 1, 1), ("plastic_bottle_1_limit", 100, "plastic bottle", 1, 1, 1), (400, "flint", 1, 1), (200, "flint slab", 1, 1), (250, "guano", 1, 1), (1000, "heavy stone", 1, 1), (300, "pretty seashells", 1, 1), (2000, "stones", 1, 1)],
    "secret cove": [("stone_5_limit", 300, "stones", 1, 1, 5), ("heavy_stone_3_limit", 100, "heavy stone", 1, 1, 3), (200, "pretty seashells", 1, 1)],
    "secret valley": [("stone_1_limit", 2000, "stones", 1, 1, 1), ("stones_8_limit", 400, "stones", 1, 1, 8), ("heavy_stone_4_limit", 300, "heavy stone", 1, 1, 4), (400, "leaves", 1, 2), (400, "sticks", 1, 2), (300, "wood", 1, 1)],
    "volcano": [("copper_1_limit", 75, "copper ore", 1, 1, 1), ("geode_9_limit", 25, "geode", 1, 1, 9), (150, "heavy stone", 1, 1), (50, "obsidian", 1, 1), (800, "stones", 1, 1), (150, "sulphurous stone", 1, 1)],
    "western grasslands": [("stones_8_limit", 400, "stones", 1, 1, 8), ("heavy_stone_4_limit", 300, "heavy stone", 1, 1, 4), (400, "leaves", 1, 2), (400, "sticks", 1, 2), (500, "wood", 1, 1)],
    "western highlands": [("geode_3_limit", 100, "geode", 1, 1, 3), (200, "flint", 1, 1), (50, "flint slab", 1, 1), (300, "heavy stone", 1, 1), (900, "leaves", 1, 8), (700, "sticks", 1, 2), (800, "stones", 1, 1), (500, "wood", 1, 1)],
    "wetlands": [("sticks_1_limit", 5000, "sticks", 1, 2, 1), ("stone_5_limit", 1000, "stones", 1, 1, 5), ("heavy_stone_3_limit", 400, "heavy stone", 1, 1, 3), (300, "assorted mushrooms", 1, 2), (600, "leaves", 3, 6), (600, "long stick", 1, 1), (550, "palm bush", 1, 1), (1000, "sticks", 1, 2), (800, "wood", 1, 1)],
}

DEFAULT_FORAGE_OUTPUTS = ["coconut", "sticks", "leaves", "stones", "vine", "bandage leaves"]
WATER_LOCATIONS = {
    "atoll",
    "beach",
    "bay",
    "bird rock",
    "dark cave",
    "damp chamber",
    "desolate beach",
    "flooded chamber",
    "low chamber",
    "mangrove forest",
    "raft",
    "sea cave",
    "secret cove",
    "secret valley",
    "tidal cave",
    "wetlands",
}
FISH_LOCATIONS = {"bay", "tidal cave"}

LOCATION_CARD_DEFS = {
    "bat colony": {"description": "restless bats overhead"},
    "bird rock": {"description": "an exposed offshore rock"},
    "brimstone vent": {"description": "a sulfurous volcanic vent"},
    "collapsed tunnel entrance": {"description": "a blocked cave passage"},
    "copper vein": {"description": "green-streaked ore in stone"},
    "damp chamber": {"description": "a wet cave chamber"},
    "debris": {"description": "scattered useful debris"},
    "desolate beach": {"description": "a harsh stretch of empty shore"},
    "dry acid lake": {"description": "a caustic dry lakebed"},
    "dry cave pond": {"description": "a dry basin inside the cave"},
    "dry puddle": {"description": "a cracked dry puddle bed"},
    "flooded tide pool": {"description": "a tide pool filled by seawater"},
    "hole": {"description": "a dark opening downward"},
    "macaque den": {"description": "a den used by macaques"},
    "narrow passage": {"description": "a tight rocky passage"},
    "narrow tunnel": {"description": "a cramped tunnel"},
    "rocks": {"description": "rocky passage back to the shore"},
    "sand": {"description": "a useful patch of sand"},
    "sea": {"description": "open salt water"},
    "seawater": {"description": "salt water filling the passage"},
    "shaft": {"description": "a vertical cave passage"},
    "shipwreck": {"description": "wreckage washed by the sea"},
    "skeleton": {"description": "old bones and scraps"},
    "tide pool": {"description": "shallow pools with small fish"},
    "wall scratchings": {"description": "marks cut into the wall"},
    "basket": {"description": "a simple container"},
    "luggage": {"description": "weathered luggage"},
    "storage chest": {"description": "a sturdy storage chest"},
    "supply chest": {"description": "a supply chest"},
    "tent": {"description": "portable cloth shelter"},
    "trunk": {"description": "a large storage trunk"},
    "empty crop plot": {"description": "prepared soil for planting"},
    "exit": {"description": "a way back out"},
    "banana tree": {"description": "a banana tree"},
    "large tree": {"description": "a large tree"},
    "small tree": {"description": "a small tree"},
    "palm bush": {"description": "a low palm bush"},
    "palm tree": {"description": "a tall palm tree"},
    "wild yam": {"description": "wild yam vines"},
    "fish trap": {"description": "a trap for small fish"},
    "snare trap": {"description": "a small animal snare"},
    "campfire": {"description": "a built campfire"},
    "drying rack": {"description": "a rack for drying food"},
    "leaf bed": {"description": "a simple bed of leaves"},
    "mud deposit": {"description": "a patch of workable mud"},
    "rain catcher": {"description": "a collector for rainwater"},
    "salt bed": {"description": "a place for evaporating seawater"},
    "seagull nest": {"description": "a nest on exposed rock"},
    "shelter": {"description": "rough protection from weather"},
    "solar still": {"description": "a slow water purifier"},
    "water filter": {"description": "a filter for unsafe water"},
    "well": {"description": "a dug water source"},
}

AREA_LOCATION_CARDS = {
    "beach": ["sea", "sand", "palm tree", "palm bush"],
    "bay": ["sea", "sand", "palm tree", "tide pool"],
    "rocks": ["sea", "tide pool", "flooded tide pool", "copper vein"],
    "secret cove": ["sea", "sand", "shipwreck"],
    "desolate beach": ["sea", "sand", "debris", "skeleton"],
    "bird rock": ["sea", "seagull nest", "rocks"],
    "mangrove forest": ["sea", "mud deposit", "small tree"],
    "wetlands": ["dry puddle", "mud deposit", "palm tree", "wild yam"],
    "jungle outskirts": ["palm tree", "small tree", "snare trap"],
    "jungle": ["large tree", "palm tree", "banana tree", "empty crop plot"],
    "deep jungle": ["large tree", "palm tree", "wild yam"],
    "secret valley": ["dry puddle", "large tree", "wild yam"],
    "western grasslands": ["small tree", "dry puddle"],
    "eastern grasslands": ["small tree", "dry puddle"],
    "western highlands": ["hole", "copper vein"],
    "eastern highlands": ["hole", "copper vein"],
    "jungle highlands": ["hole", "narrow passage"],
    "highland hole": ["copper vein", "skeleton"],
    "volcano": ["brimstone vent", "dry acid lake"],
    "acid lake": ["dry acid lake", "brimstone vent"],
    "atoll": ["sea", "sand", "palm tree"],
    "raft": ["sea", "debris"],
    "bat cave": ["bat colony", "narrow passage"],
    "dark cave": ["dry cave pond", "narrow passage", "wall scratchings"],
    "darkness": ["exit"],
    "grasslands cave": ["narrow passage", "copper vein"],
    "macaque den": ["exit"],
    "sea cave": ["seawater", "narrow passage", "wall scratchings"],
    "tidal cave": ["seawater", "tide pool", "flooded tide pool"],
    "crystal chamber": ["narrow passage", "shaft"],
    "damp chamber": ["dry cave pond", "narrow tunnel"],
    "flooded chamber": ["seawater", "shaft"],
    "high chamber": ["shaft", "narrow passage"],
    "medium chamber": ["shaft", "narrow tunnel"],
    "low chamber": ["shaft", "dry cave pond"],
    "narrow tunnel": ["narrow passage"],
    "tunnel": ["copper vein", "narrow passage"],
    "mud hut": ["storage chest", "leaf bed"],
    "shed": ["storage chest", "drying rack"],
    "stone hut": ["storage chest", "well"],
    "plane crash": ["exit", "debris", "luggage", "supply chest"],
    "cellar": ["storage chest", "supply chest"],
}


def build_locations() -> dict[str, Location]:
    locations = {}
    for name, data in AREA_DEFS.items():
        hidden_cards = set(AREA_EXPLORE_CARDS.get(name, []))
        locations[name] = Location(
            name=name,
            discovered=bool(data.get("discovered", False)),
            features=list(data.get("features", [])),
            location_cards=[card for card in AREA_LOCATION_CARDS.get(name, []) if card not in hidden_cards],
            resources=deepcopy(data.get("resources", {})),
        )
    return locations
