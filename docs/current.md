# Tropical Adventure: Current State

This file is the handoff for what exists now. Use `docs/plans.md` for what to build next.

## How to start testing it yourself

Open a terminal at the project root:

```bash
cd C:/Users/xiaox/repos/tropical_adventure
uv run python -m tropical_adventure.server --save saves/island.json --host 127.0.0.1 --port 8765
```

Open another terminal for Alice:

```bash
cd C:/Users/xiaox/repos/tropical_adventure
uv run python -m tropical_adventure.client --host 127.0.0.1 --port 8765 --name Alice
```

Optional second player, for multiplayer UI testing:

```bash
cd C:/Users/xiaox/repos/tropical_adventure
uv run python -m tropical_adventure.client --host 127.0.0.1 --port 8765 --name Bob
```

Useful client commands:

```text
/forage
/gather unsafe water
/explore
/move rocks
/pick up coconut
/drop coconut
/craft sharp stone
/start fire
/save
/exit
```

Typing `/` opens the command list. Use `up` / `down` to move selection, `tab` to autocomplete the selected command, `escape` to close/clear it, and `enter` to submit exactly what is typed.

## Current product direction

The game is moving toward an **object-based scene interaction** model:

- Left panel: only the current player and their own state.
- Center/world panel: the current location as a scene, including other players, features, placed objects, ground items, and paths.
- Right panel: the current player's carried inventory, sorted by most recently used or acquired item.
- Slash commands should stay direct and discoverable: `/forage`, `/move rocks`, `/pick up coconut`, not `/action forage`.
- The server remains authoritative. The client can suggest commands, but `start_action()` validates whether they are possible.

Important current decision: `command_to_message()` accepts defined actions from `ACTION_DURATIONS`, even if they are not currently in `available_actions`. This is useful while experimenting; invalid actions are rejected by the server.

## Current UI shape

```text
+----------------+------------------------------+----------------+
| Player         | World / Scene                | Inventory      |
| current player | time/weather/location        | carried items  |
| stats only     | objects in current location  |                |
+----------------+------------------------------+----------------+
| recent event log, fixed 5 visible events                       |
+----------------------------------------------------------------+
| input                                                           |
+----------------------------------------------------------------+
```

Current behavior:

- Textual TUI client.
- English and Chinese object/action strings for supported content.
- Three top scrollable panels: player, world, inventory.
- Left/player panel already shows only the current player.
- World panel shows:
  - global time/weather/light/paused state
  - connected other players at the current location as scene objects, with public action/status only
  - current scene features with descriptions and resource state
  - placed objects with descriptions/state, e.g. fire fuel
  - ground items with descriptions/state, e.g. food freshness/spoilage
  - discovered paths to other locations
- World panel intentionally does **not** duplicate interaction hints like `/pick up`, `/move`, `/forage`; those belong in the slash command list.
- Inventory panel shows carried stacks newest-first. Acquiring, merging, or using a surviving vessel/tool/container moves that stack to the top of the displayed list.
- Inventory panel also shows effective carried load plus nested contents for carried containers.
- Event log shows the last 5 events and replaces the current player's “started action” event with a spinner line while the action is running.
- Slash command menu floats above the input and shows up to 20 visible rows with scroll indicators.

## What is already built

### Server and protocol

Files:

- `tropical_adventure/server.py`
- `tropical_adventure/protocol.py`
- `tropical_adventure/persistence.py`

Built:

- TCP server using newline-delimited JSON messages.
- Join by player name.
- Optional invite token with `--invite`.
- Duplicate connected names are rejected.
- Disconnected players can reconnect by name.
- Chat, events, snapshots, pause/resume, manual save, and exit handling.
- Tick loop; world time advances while at least one player is connected.
- Daily/manual/clean-shutdown JSON saves.

### World and gameplay model

Files:

- `tropical_adventure/models.py`
- `tropical_adventure/game.py`

Core data:

- `World`: time, weather, season, locations, players, processes, event log.
- `Player`: location, raw needs, raw conditions, display-facing stats, skills, carried items, current action.
- `Location`: features, ground items, placed objects, resources.
- `PlacedObject`: shared objects such as fire, kiln, advanced kiln, forge, shelter, stone hut, raincatcher, leaf bed, drying rack, water filter, solar still, salt bed, water reservoir, well, cistern.
- `WorldProcess`: delayed shared processes such as cooking, boiling, drying, filtering, curing, firing, calcining, and smelting.
- `Action`: timed player action with reserved inputs.

Current locations:

- The island map in `tropical_adventure/content.py` covers the outdoor, indoor, and cave-system areas inspired by Card Survival: Tropical Island.
- The starting area is `beach`; exploration reveals routes/cards such as `jungle outskirts`, `rocks`, `bay`, `wetlands`, cave chambers, and highlands.

Current location content:

- content is object-oriented for this game rather than card-drag oriented
- resources include water sources, palm/coconut resources, mud deposits, dry puddle dirt, stone/flint/cave finds, tide-pool foods, vines, leaves, long sticks, medicinal leaves, edible plants, mushrooms, nipa palm, sago palms, and coffee/chili bushes
- placed objects include fire, campfire, kiln, advanced kiln, forge, shelter, shed, mud hut, stone hut, cellar, basket, storage chest, supply chest, raincatcher, leaf bed, drying rack, fish trap, snare trap, water filter, solar still, salt bed, water reservoir, well, cistern, sand castle/fire remnants in UI descriptions
- items include coconuts, coconut water/meat/shells, plant fiber cord, rope, palm fronds/weave, baskets/backpacks, logs, leather, digging sticks, fish/shellfish, raw/cooked trap meat, dried fish, salted fish/meat, coconut fish, sago cake, yam curry, fried puffballs, copper ore/copper, copper molds, copper knife/axe/shovel/spear tools, copper sheets/needles/bottle/jar, minerals, sand, quicklime, mortar, plastic bottles, ash, charcoal, mud piles, dirt piles, fine dirt, clay, mud bricks, unfired/fired clay vessels and vases, salt water, salt, wood shavings, sago pith/sawdust/pulp/flour/flatbread, and basic survival materials
- inventory and scene item lines render item state when available, including food freshness, exposed-water evaporation, vessel liquid/capacity, and tool durability stored on item stacks
- player stats are normalized `0..100` values where higher is better; raw hunger/thirst/fatigue/stress/pain/wetness/wounds are exposed as hydration, satiation, stamina, calm, comfort, dryness, and wound recovery
- the stat set covers core, mental, physical, damage, internal, chemical, protection, and saturation-style Card Survival-inspired categories with English and Chinese labels
- repeated foods lower their matching saturation/appetite score, while food variety and time let those scores recover

Storage and carrying:

- containers are concrete objects, not blueprint unlocks or card drag/drop targets
- carried containers and placed storage use `contents`, `storage_capacity`, optional `slots`, and optional `weight_reduction`
- a basket follows the wiki-inspired shape of 4 storage slots, 1000 stored-weight capacity, 1000 load relief, and 500 item weight
- a woven backpack keeps the basket capacity and adds equipped load relief; storage chests are heavy placed storage with a larger weight capacity and one stack slot
- `/pack <item>` moves a carried non-container item into a carried container, while `/unpack <item>` takes it back out
- `/store <item>` moves a carried non-container item into placed storage at the current location, while `/retrieve <item>` takes it back out
- filled open vessels and containers cannot be put inside another storage container
- carried load is shown as effective weight against base capacity; container relief lowers effective load, but severe overburden blocks travel, exploration, foraging, gathering, swimming, sailing, and heavy resource work while still allowing inventory management

Balance scaling:

- `PLAYER_STAT_RANGE` is `100`; every player-facing stat and effect must be normalized to `$0..100$` before it reaches snapshots or UI.
- `CARD_SURVIVAL_STAT_RANGES` records source ranges used when adapting wiki values, such as hydration `0..180`, stamina `0..32`, stress `0..240`, morale `-350..350`, appetite `0..250`, and satiation `0..151`.
- Use `scale_wiki_value()` for absolute source stat values and `scale_wiki_delta()` for source deltas such as food, drink, or condition changes. This keeps wiki-inspired balance proportional without copying raw Card Survival numbers into this game.

Timing scale:

- one game day is 8 real minutes, so 1 real second is about 3 in-game minutes
- `FISH_TRAP_SOAK_RANGE` is 1500-4500 game minutes: 1d1h to 3d3h, or about 8m20s-25m real time
- `SNARE_TRAP_SOAK_RANGE` is 1125-3375 game minutes: 18h45m to 2d8h15m, or about 6m15s-18m45s real time
- salt beds use wiki-style 15-minute evaporation steps: each step converts salt water reservoir state into salt crystals until scraped
- kilns, advanced kilns, and forges use wiki-style 15-minute fuel/temperature steps; advanced kilns and forges have higher maximum temperatures for copper smelting; fired vessels use wiki-inspired 3h-4h firing processes; clay vessels carry liquid state directly on their item stacks; water reservoirs collect 50 clean water per rainy 15-minute step up to 12000; wells refill unsafe water by 4 per 15-minute step plus 50 while raining; cisterns collect 50 clean rainwater per rainy 15-minute step up to 24000

Outcome:

- losing means a player reaches `health == 0`; the player status becomes `dead`, the world outcome becomes `loss`, and actions stop
- winning is raft rescue inspired by Card Survival's raft event group: sailing the raft advances `raft_distance` toward 2016; passing ships can appear at distance milestones; signaling can fill progress to 100 for early rescue; reaching 2016 triggers guaranteed ship rescue
- snapshots include the world `outcome`, raft voyage state, and each player `status`, so the client can render victory, defeat, death, escape, and active passing-ship windows in English or Chinese

Current actions in `ACTION_DURATIONS`:

```text
drink, eat, pick up, drop, pack, unpack, store, retrieve,
tend fire, cook fish, cook meat, boil water, filter water,
gather, forage, forage tide pool, harvest coconuts, harvest aloe vera,
harvest lemongrass, harvest ginger, harvest spider lily, harvest snakegrass,
dig wild yam, dig up mud, dig up dirt, collect bananas, cut nipa fruit, cut sago palm, harvest coffee berries,
harvest chilies, harvest jasmine, harvest assorted mushrooms, harvest puffballs,
harvest magic mushrooms, move, wash, swim, leisure, explore, rest, sail raft,
wave and shout, signal with mirror, treat wound,
craft sharp stone, crack coconut, weave cord, weave rope, weave palm fronds,
craft woven basket, craft woven backpack, add rope to basket, detach rope from woven backpack,
place basket, craft stone axe, craft digging stick, make wood shavings, start fire, fish, dry fish,
make aloe gel, apply aloe leaf,
apply aloe gel, brew ginger tea, brew spider lily tea, brew jasmine tea,
make bug repellent, apply bug repellent, prepare yam, extract nipa seeds,
extract coffee beans, roast coffee beans, brew coffee,
split sago log, scrape sago pith, soak sago sawdust,
grind soaked sago, dry sago pulp, cook sago flatbread, collect sand,
make quicklime, mix mortar, make clay,
make mud brick, make mud, crush dirt, mix clay, shape clay bowl,
shape clay jar, shape cooking pot, shape clay vase, build kiln, build advanced kiln,
build forge, fuel kiln, light kiln, mine copper ore, smelt copper,
shape knife mold, shape axe mold, shape shovel mold, shape spear mold,
cast copper knife, cast axe head, cast shovel head, cast spear head,
craft copper axe, craft copper shovel, craft copper spear,
hammer copper sheet, make copper needles, craft copper bottle, craft copper jar,
fire clay bowl, fire clay jar, fire cooking pot, fire clay vase,
build water reservoir, build well, build cistern, fill vessel,
drink from vessel, empty vessel, collect salt water,
boil salt water, build salt bed, fill salt bed, scrape salt, salt fish,
salt meat, cook coconut fish, cook sago cake, cook yam curry, cut palm fronds, hew log,
fry puffballs, build raincatcher, build campfire,
craft leaf bed, build shelter, build shed, build mud hut, build stone hut, build cellar,
build storage chest, build supply chest, build drying rack, build fish trap,
check fish trap, build snare trap, bait snare trap, check snare trap,
build water filter, build solar still
```

Important distinction:

- `ACTION_DEFS`: structured action metadata: duration, material inputs, tool requirements, skill, and English/Chinese descriptions.
- `PREREQUISITE_ACTIONS`: actions that appear automatically when their concrete materials, tools, placed objects, and scene prerequisites are satisfied.
- `ACTION_DURATIONS`: all defined action names and durations.
- `ACTION_BLOCKS_PLAYER`: whether starting the action occupies `current_action`. Unattended process actions such as boiling, drying, curing, firing, smelting, filtering, and pot-cooking reserve inputs and start a `WorldProcess` immediately, so the player can keep working while the wait completes.
- Every defined action is known from the beginning, while execution still requires the action's inputs and concrete world prerequisites.
- `available_actions(world, player_name)`: actions currently shown/available for that player.
  Availability is gated by concrete prerequisites such as materials, tools, fire, placed objects, and scene resources.
- `start_action(...)`: final server-side validation and resource reservation.
- `complete_action(...)`: action effects.
- `world_snapshot(...)`: state sent to the client, including full state for the current player and public scene state for connected nearby players.

### Tests

Files:

- `tests/test_game.py`
- `tests/test_client.py`
- `tests/test_integration.py`

Current coverage includes:

- tick/time progression and needs updates for connected players
- action completion, resource reservation, cancellation, and skill advancement
- concrete action prerequisite validation
- save/load round trips
- reconnect by name and duplicate name rejection
- multiplayer chat/actions/pause/resume/save/exit
- placed objects and world processes, including passive fish/snare trap readiness
- fire burn-down, raincatcher, evaporation, wounds
- normalized player stat snapshots and color-sorted player panel urgency
- resource depletion/regrowth
- client command parsing and slash menu behavior
- current player-only left panel
- world/inventory panel formatting
- English/Chinese UI text support

Latest verification run:

```text
.venv/bin/python -m pytest -q
125 passed in 1.81s

command -v ruff
not available in PATH
```

## Code map for continuing work

Start with these files:

- `tropical_adventure/client.py`
  - `format_players_panel()` — left panel; current player only.
  - `format_world_panel()` — center scene panel, including connected other players as location objects.
  - `format_inventory_panel()` — right panel; renders carried stacks from most recent to oldest.
  - `command_choices()` — slash autocomplete choices.
  - `CommandMenuState` — filtering, selection, tab behavior, menu rendering.
  - `command_to_message()` — slash command text to network message.
  - `SurvivalApp.CSS` — layout.
- `tropical_adventure/game.py`
  - `ACTION_DURATIONS`
  - `ACTION_BLOCKS_PLAYER`
  - `ACTION_INPUTS`
  - `available_actions()`
  - `start_action()`
  - `complete_action()`
  - `world_snapshot()`
- `tropical_adventure/models.py`
  - data classes for world/player/location/items/actions.
- `tropical_adventure/server.py`
  - client message handling and snapshot broadcasts.

## Manual testing checklist

Use this flow when trying UI changes yourself:

1. Start server.
2. Start Alice.
3. Start Bob.
4. In Alice, type `/` and verify the command menu appears above input.
5. Verify Alice's left panel shows only Alice.
6. Use `/forage` and wait for completion.
7. Use `/explore` until more locations appear.
8. Use `/move rocks` or another discovered location.
9. Check that the world panel is where scene objects belong.
10. Check that Bob appears in Alice's world panel only when Bob is at Alice's location.
11. Use `/save` before stopping.

## Current risks / cleanup notes

- The project directory is a git repository; check `git status --short` before larger changes because active work may already be present.
- `client.py` contains UI rendering, command parsing, and Textual app code. This is okay for now; split only when repeated patterns become painful.
- Other-player-as-scene-object is currently render-only. Do not build trade/combat/help systems until the scene object model feels right.
- Inventory intentionally uses one `Player.carried` list right now. Add explicit hands/equipment/container mechanics only when they have real gameplay behavior.
- Keep the server authoritative. Client-side scene rendering and autocomplete are convenience layers, not game-rule authority.
