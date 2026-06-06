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
- Center/world panel: the current location as a scene, including features, placed objects, ground items, paths, and next: other players as scene objects.
- Right panel: the current player's inventory, next: hands first, then equipped bags/containers.
- Slash commands should stay direct and discoverable: `/forage`, `/move rocks`, `/pick up coconut`, not `/action forage`.
- The server remains authoritative. The client can suggest commands, but `start_action()` validates whether they are possible.

Important current decision: `command_to_message()` accepts globally known actions from `ACTION_DURATIONS`, even if they are not currently in `available_actions`. This is useful while experimenting; invalid actions are rejected by the server.

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
  - current scene features with descriptions and resource state
  - placed objects with descriptions/state, e.g. fire fuel
  - ground items with descriptions/state, e.g. food freshness/spoilage
  - discovered paths to other locations
- World panel intentionally does **not** duplicate interaction hints like `/pick up`, `/move`, `/forage`; those belong in the slash command list.
- Inventory panel currently shows carried items only, newest/reversed stack order.
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
- `Player`: location, needs, conditions, skills, carried items, known blueprints, current action.
- `Location`: features, ground items, placed objects, resources.
- `PlacedObject`: shared objects such as fire, shelter, raincatcher.
- `WorldProcess`: delayed shared processes such as cooking and boiling.
- `Action`: timed player action with reserved inputs.

Current locations:

- `beach`
- `jungle outskirts`
- `rocks`
- `tide pool`

Current location content:

- beach: sea, sand, coconut palms, unsafe water, coconuts, sticks
- jungle outskirts: trees, vines, leaf litter
- rocks: stone outcrops, cliffs
- tide pool: shallow pools, fish, unsafe water
- placed objects: fire, shelter, raincatcher, sand castle/fire remnants in UI descriptions
- items: coconut, sticks, leaves, vine, stones, sharp stone, unsafe water, clean water, raw fish, cooked fish, bandage leaves, ash, charcoal

Current actions in `ACTION_DURATIONS`:

```text
drink, eat, pick up, drop, tend fire, cook fish, boil water,
gather, forage, move, wash, swim, leisure, explore, rest,
treat wound, craft sharp stone, start fire, fish,
build raincatcher, build shelter
```

Important distinction:

- `ACTION_DURATIONS`: all known action names and durations.
- `available_actions(world, player_name)`: actions currently shown/available for that player.
- `start_action(...)`: final server-side validation and resource reservation.
- `complete_action(...)`: action effects.
- `world_snapshot(...)`: state sent to the client.

### Tests

Files:

- `tests/test_game.py`
- `tests/test_client.py`
- `tests/test_integration.py`

Current coverage includes:

- tick/time progression and needs updates for connected players
- action completion, resource reservation, cancellation, and skill advancement
- per-player blueprint unlocks
- save/load round trips
- reconnect by name and duplicate name rejection
- multiplayer chat/actions/pause/resume/save/exit
- placed objects and world processes
- fire burn-down, raincatcher, evaporation, wounds
- resource depletion/regrowth
- client command parsing and slash menu behavior
- current player-only left panel
- world/inventory panel formatting
- English/Chinese UI text support

Latest verification run:

```text
uv run pytest -q
52 passed in 0.94s

uv run ruff check .
failed: `ruff` executable was not available in the current uv environment
```

## Code map for continuing work

Start with these files:

- `tropical_adventure/client.py`
  - `format_players_panel()` — left panel; current player only.
  - `format_world_panel()` — center scene panel; best place to render other players as location objects.
  - `format_inventory_panel()` — right panel; currently carried stacks only, next should become hands + bags.
  - `command_choices()` — slash autocomplete choices.
  - `CommandMenuState` — filtering, selection, tab behavior, menu rendering.
  - `command_to_message()` — slash command text to network message.
  - `SurvivalApp.CSS` — layout.
- `tropical_adventure/game.py`
  - `ACTION_DURATIONS`
  - `RECIPES`
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
10. For the next feature, check that Bob appears in Alice's world panel only when Bob is at Alice's location.
11. Use `/save` before stopping.

## Current risks / cleanup notes

- The project directory is currently not a git repository. Initialize git before larger changes if you want rollback/history.
- `client.py` contains UI rendering, command parsing, and Textual app code. This is okay for now; split only when repeated patterns become painful.
- Other-player-as-scene-object should start as rendering only. Do not build trade/combat/help systems until the scene object model feels right.
- Inventory should become hands + bags, but current model has only `Player.carried`; avoid overbuilding container systems before the UI shape is tested.
- Keep the server authoritative. Client-side scene rendering and autocomplete are convenience layers, not game-rule authority.
