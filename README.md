# Tropical Adventure

A self-hosted multiplayer terminal survival game inspired by detailed island survival sims.

## Run

```bash
uv run python -m tropical_adventure.server --save saves/island.json --host 127.0.0.1 --port 8765
uv run python -m tropical_adventure.client --host 127.0.0.1 --port 8765 --name Alice
uv run python -m tropical_adventure.client --host 127.0.0.1 --port 8765 --name Alice --lang zh
```

Use `--host 0.0.0.0` only for intentional LAN/trusted hosting. Prefer `--invite` when binding beyond localhost.

## Content

The island content is inspired by Card Survival: Tropical Island, adapted into direct scene actions instead of card drag/drop verbs. Examples:

Actions appear from concrete prerequisites such as carried materials, tools, fire, placed objects, and scene resources.
The campaign is won by raft rescue: sail the raft until a ship rescues you, or catch a passing ship's attention with signaling actions. It is lost when health reaches `$0$`.

```text
/harvest coconuts
/harvest aloe vera
/harvest lemongrass
/harvest ginger
/harvest spider lily
/harvest snakegrass
/dig wild yam
/collect bananas
/cut nipa fruit
/harvest coffee berries
/harvest chilies
/harvest jasmine
/harvest assorted mushrooms
/harvest puffballs
/harvest magic mushrooms
/dig up mud
/dig up dirt
/forage tide pool
/crack coconut
/weave cord
/weave rope
/weave palm fronds
/craft woven basket
/craft woven backpack
/add rope to basket
/detach rope from woven backpack
/place basket
/pack sticks
/unpack stones
/store sticks
/retrieve stones
/craft digging stick
/make aloe gel
/apply aloe leaf
/apply aloe gel
/brew ginger tea
/brew spider lily tea
/brew jasmine tea
/make bug repellent
/apply bug repellent
/prepare yam
/extract nipa seeds
/extract coffee beans
/roast coffee beans
/brew coffee
/craft stone axe
/cut sago palm
/cut palm fronds
/hew log
/split sago log
/scrape sago pith
/soak sago sawdust
/grind soaked sago
/dry sago pulp
/cook sago flatbread
/collect sand
/make quicklime
/mix mortar
/make clay
/make mud brick
/make mud
/crush dirt
/mix clay
/shape clay bowl
/shape clay jar
/shape cooking pot
/shape clay vase
/build kiln
/build advanced kiln
/build forge
/fuel kiln
/light kiln
/mine copper ore
/smelt copper
/shape knife mold
/shape axe mold
/shape shovel mold
/shape spear mold
/cast copper knife
/cast axe head
/cast shovel head
/cast spear head
/craft copper axe
/craft copper shovel
/craft copper spear
/hammer copper sheet
/make copper needles
/craft copper bottle
/craft copper jar
/fire clay bowl
/fire clay jar
/fire cooking pot
/fire clay vase
/build water reservoir
/build well
/build cistern
/collect salt water
/boil salt water
/fill vessel
/drink from vessel
/empty vessel
/build salt bed
/fill salt bed
/scrape salt
/salt fish
/salt meat
/cook coconut fish
/cook sago cake
/cook yam curry
/fry puffballs
/make wood shavings
/build campfire
/craft leaf bed
/build shed
/build mud hut
/build stone hut
/build cellar
/build storage chest
/build supply chest
/build drying rack
/dry fish
/build fish trap
/check fish trap
/build snare trap
/bait snare trap
/check snare trap
/cook meat
/build water filter
/filter water
/build solar still
/sail raft
/wave and shout
/signal with mirror
```

English and Chinese UI text are supported with `--lang en` and `--lang zh`.

Player stats are shown as normalized `0..100` survival scores where higher is better. The left panel sorts the lowest scores first and colors them red, yellow, or green so urgent hydration, stamina, morale, wounds, pain, wetness, heat/cold, chemical effects, and food saturation float to the top.

Inventory and scene item lines show item state where it matters, including food freshness, exposed-water evaporation, tool durability, kiln fuel/heat, vessel liquid/capacity, and container slots/storage capacity.

Containers use concrete storage rules. Baskets, woven backpacks, chests, and storage-capable shelters hold nested contents up to their slot and stored-weight limits; carried containers reduce effective load, and severe overburden blocks travel/work actions while still allowing inventory management.

Wiki-inspired stat and food/drink values are scaled into this game's `0..100` player model instead of copied raw from Card Survival's different stat ranges.

Timing is tuned around an 8-real-minute game day. Since a day is 1440 in-game minutes, every real second advances about 3 in-game minutes; passive trap, kiln, and curing waits use wiki-style ranges on that scale.
