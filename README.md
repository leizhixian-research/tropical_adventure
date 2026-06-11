# Tropical Adventure

A self-hosted multiplayer terminal survival game inspired by detailed island survival sims.

## Run

```bash
uv run python -m tropical_adventure.server --save saves/island.json --host 127.0.0.1 --port 12222
uv run python -m tropical_adventure.client --host 127.0.0.1 --port 12222 --name Alice
uv run python -m tropical_adventure.client --host 127.0.0.1 --port 12222 --name Alice --lang zh
```

On Windows, a player can double-click `start.bat` from the repo folder and enter the server IP, port, player name, language, and optional invite code. The launcher defaults to Chinese and runs the client with `uv`.

Use `--host 0.0.0.0` only for intentional LAN/trusted hosting. Prefer `--invite` when binding beyond localhost.

## Content

The island content is inspired by Card Survival: Tropical Island, adapted into direct scene actions instead of card drag/drop verbs. Examples:

Actions appear from concrete prerequisites such as nearby materials, carried tools, fire, placed objects, and scene resources.
The campaign is won by raft rescue: build the raft, board it, sail until a ship rescues you, or catch a passing ship's attention with signaling actions. It is lost when health reaches `$0$`.

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
/go for a walk
/forage tide pool
/dive
/spear fish
/break conch
/cook conch meat
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
/flesh skin
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
/harvest cinchona bark
/dry cinchona bark
/grind cinchona powder
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
/dig up sand
/build sand castle
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
/craft hand drill
/craft bow drill
/make wood shavings
/craft torch
/light tinder with hand drill
/light tinder with bow drill
/light tinder from fire
/light tinder with mirror
/light torch
/extinguish torch
/gather dry leaves
/start fire
/collect bone splinters
/collect feathers
/craft bone hook
/craft fishing line
/craft fishing rod
/craft fish bait
/fish
/fish with bait
/build campfire
/craft leaf bed
/build raft
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

Untreated dirty wounds can develop bacterial infection, fever, and health loss. Bandaging wounds lowers infection pressure, and spider lily tea works as an antibiotic drink.

Unsafe water, raw foods, and heavy mosquito exposure can build parasite and malaria pressure. Cinchona bark can be dried and ground into quinine powder, which helps control parasites and malaria but has stomach side effects.

Tree coconuts are harvested by climbing fruiting coconut palms with `/harvest coconuts`; generic `/forage` is not supported. Tide pools keep the wiki-style concrete `/forage tide pool` action, but only at low tide; high tide floods them while still leaving seawater actions such as washing and swimming.

Beach and bay loose finds use the wiki-style `/go for a walk` action: a 15-minute light-required shore walk that can find shells, palm material, stones, sticks, wood, or coconuts while easing stress and wearing your feet.

Spear fishing uses the wiki-style shallow sea action: `/spear fish` takes 30 minutes, needs usable light and a copper spear, soaks you, wears the spear, and rolls a skill-improved fish catch.

Line fishing uses the wiki-style sea action as a concrete tool action: craft bone hooks into `/craft fishing line` or `/craft fishing rod`, then `/fish` for 1 hour at sea water. `/fish with bait` consumes fish bait made from shells, cord, and feathers, reducing the chance of catching nothing while still wearing the line or rod.

Diving uses the wiki-style sea action: `/dive` takes 30 minutes, needs usable light and enough stamina, soaks and cleans you, eases stress, trains swimming, and can find conch, urchins, crabs, seaweed, or stones depending on the coast. Conch can be opened with `/break conch`, then cooked with `/cook conch meat`.

Sand uses concrete wiki-style beach actions: `/collect sand` by hand, `/dig up sand` with a copper shovel for a larger haul, and `/build sand castle` as a small morale break.

The raft is built on the beach in five 90-minute stages, using the full component set of logs, rope, long sticks, leather, fiber cord, axe wear, and needle wear. Fresh skin from snares can be scraped into fleshed skin, then cured into leather over 4 in-game days. Heavy stage materials can be staged on the beach or in placed storage; an unfinished raft frame remains visible with its current stage and next required components.

The world panel focuses on current scene state, time, weather, sleep status, visible items, and exits. Use `/recipes` or `/crafts` when you want available crafts and missing recipe requirements.

When players rest, the world panel shows whether time is skipping for everyone or which connected living players are still active. Time only fast-forwards when every connected living player is resting; `/pause` and `/resume` remain global.

Weather now uses Card Survival-inspired clear, cloudy, rain, heavy rain, and storm states with rain counter, rain value, and sun strength shown in the world panel. The rain counter runs on the wiki-style `0..700` pressure scale: wet season raises it, dry season lowers it, rain and storms spend it down, and higher counter values bias future weather toward rain. Unsheltered storms build wetness, cold, stress, bruising, and fatigue faster, can damage exposed shelters, raincatchers, traps, solar stills, and drying racks, while exposed midday sun adds thirst and heat load; severe heat or cold can drain health.

Inventory uses a compact table: index, item, a condition bar when freshness/durability/fuel/liquid/storage matters, and a load number. Scene item lines keep richer descriptions for inspection. Command suggestions use indexes such as `/pick up 2(coconut) 1`, `/drop 1(stones) 1`, and `/retrieve 2.1(rope) 1`; typing only `/` shows action names first, then typing an action plus a space reveals targets.

Containers use concrete storage rules. A new survivor has 4 top-level hand/arm carry slots, adapted from the wiki's hand-row rule, plus one back slot for a backpack. Matching stackable loose items merge in one hand slot; baskets are hand-carried containers that can also be placed as storage, and one woven backpack can be worn on the back. Containers cannot be nested inside other containers, and extra backpacks cannot be held in hand in this direct-action model. Baskets, woven backpacks, chests, and storage-capable shelters hold contents up to their slot and stored-weight limits. Carried containers reduce effective load, and severe overburden blocks travel/work actions while still allowing inventory management.

Dark cave areas need usable light. Daylight does not reach locations marked with darkness; a carried lit torch or an active fire/campfire at the location lets you work there, while backtracking along discovered routes stays usable if your light goes out.

Wiki-inspired stat and food/drink values are scaled into this game's `0..100` player model instead of copied raw from Card Survival's different stat ranges.

Timing is tuned around an 8-real-minute game day. Since a day is 1440 in-game minutes, every real second advances about 3 in-game minutes; passive trap, kiln, leaf/cinchona-drying, lit-tinder, torch, and curing waits use wiki-style ranges on that scale. When every connected living player is resting, the server fast-forwards in-game time until someone wakes; if any connected player is active, time keeps its normal speed.
