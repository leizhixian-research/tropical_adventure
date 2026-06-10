# Tropical Adventure: Plans

This file is about what to work on next. Use `docs/current.md` for what is already built.

## Product direction to preserve

The next work should make the UI and gameplay feel like **interacting with objects in a location**:

- Player panel = only me.
- Scene/world panel = things at my current location.
- Other players = scene objects at the location, just like a fire, coconut, path, or ground item.
- Inventory panel = what I can use/carry, sorted by most recently used or acquired item.
- Slash commands stay direct: `/inspect Bob`, `/pick up coconut`, `/move rocks`, `/forage coconut`.

Keep changes small and testable. Avoid adding a big generic object-interaction framework until 2-3 concrete interactions prove what abstraction is needed.

## Recommended next work order

Recently completed:

- Other players now render as scene objects when they are connected and at the current player's location.
- Inventory now renders a single recent-used carried list. Hands/equipment/container sections are deferred until they have distinct mechanics.

### Completed: Show other players as objects in the scene

**Goal:** Alice should see Bob in the world panel when Bob is at Alice's location. Bob should not appear in Alice's left/player panel.

**Files:**

- Modify: `tropical_adventure/client.py`
  - `format_world_panel()`
  - possibly `OBJECT_NAMES_ZH` / translations for labels like `survivor` later
- Test: `tests/test_client.py`

**Implementation steps:**

1. Add a focused test in `tests/test_client.py`.
2. Build a snapshot with Alice at `beach`, Bob at `beach`, Cara at `rocks`.
3. Assert `format_players_panel(snapshot, "Alice")` contains Alice but not Bob/Cara.
4. Assert `format_world_panel(snapshot, "Alice")` contains Bob.
5. Assert the same world panel does not contain Cara.
6. Implement the smallest render-only change in `format_world_panel()`.
7. Run the focused test.
8. Run all tests.
9. Start two clients manually and check the feel.

Suggested first test:

```python
def test_world_panel_lists_other_players_in_current_scene_not_left_panel():
    snapshot = {
        "day": 1,
        "minute": 360,
        "weather": "clear",
        "light": "daylight",
        "paused": False,
        "players": {
            "Alice": {
                "name": "Alice",
                "connected": True,
                "location": "beach",
                "needs": {
                    "health": 100,
                    "hunger": 20,
                    "thirst": 20,
                    "fatigue": 10,
                    "morale": 50,
                    "stress": 10,
                },
            },
            "Bob": {"name": "Bob", "connected": True, "location": "beach", "needs": {}},
            "Cara": {"name": "Cara", "connected": True, "location": "rocks", "needs": {}},
        },
        "locations": {
            "beach": {"features": [], "resources": {}, "ground": [], "placed": []},
            "rocks": {"features": [], "resources": {}, "ground": [], "placed": []},
        },
    }

    player_panel = format_players_panel(snapshot, "Alice", "en")
    world_panel = format_world_panel(snapshot, "Alice", "en")

    assert "Alice" in player_panel
    assert "Bob" not in player_panel
    assert "Cara" not in player_panel
    assert "Bob" in world_panel
    assert "Cara" not in world_panel
```

Suggested first render line:

```text
Bob — survivor here
```

Do **not** add full social mechanics yet. The first version only needs to prove the layout model.

**Definition of done:**

- Left panel shows only current player.
- World panel shows connected other players at the same location.
- World panel does not show players elsewhere.
- Tests cover the behavior.
- Manual two-client smoke test feels right.

### 2. Add object-specific `/inspect <target>` as a client-side bridge

**Goal:** Make scene objects feel interactable without adding server complexity yet.

**Files:**

- Modify: `tropical_adventure/client.py`
  - `CLIENT_COMMANDS`
  - `command_choices()`
  - `command_to_message()` if needed
  - `SurvivalApp.handle_message()` or input handling if local-only feedback is added
- Test: `tests/test_client.py`

**First behavior:**

- `/inspect` keeps current behavior: request latest world snapshot.
- `/inspect Bob` can be local-only at first and add an event like `You inspect Bob: another survivor is here.`
- `/inspect fire` can describe visible fire state.
- `/inspect coconut palms` can describe visible resource state.

Keep server support for later, only when inspection needs hidden/private state.

**Definition of done:**

- Command menu includes useful inspect targets from visible scene data.
- `/inspect` still works as before.
- `/inspect <visible target>` gives understandable local feedback.
- Unknown/invisible targets produce a clear local error.

### 3. Improve command choices from scene objects

**Goal:** The slash menu should suggest commands based on objects currently visible in the scene.

Current `command_choices()` already suggests:

- `/move <location>` from discovered locations
- `/pick up <item>` from ground stacks
- `/drop <item>` from carried stacks
- `/pack <item>` and `/unpack <item>` from carried containers
- `/store <item>` and `/retrieve <item>` from placed storage
- `/forage <item>` and `/gather <item>` from location resources

Next additions:

- `/inspect Bob` for other players in the same location.
- `/inspect fire`, `/inspect shelter`, `/inspect raincatcher` for placed objects.
- `/inspect coconut palms`, `/inspect sea`, etc. for features.
- Later, maybe `/give Bob coconut` only after inventory/hand semantics exist.

Keep suggestions direct. Do not add `/action ...`.

### Completed: Simplify inventory panel to recent-used carried items

**Goal:** The right panel should show immediately relevant items first without implying hands/equipment mechanics that do not exist yet.

Current state:

- `Player` has `carried` stacks only.
- `format_inventory_panel()` renders all `carried` stacks in reversed order, so the newest model entry appears first.
- `add_items()` moves acquired/merged stacks to the end of `Player.carried`.
- Vessel/tool/container use moves surviving touched stacks to the end of `Player.carried`.
- Containers are now playable inside the flat carried model: storage stacks carry nested `contents`, slot limits, stored-weight capacity, and carried-load relief.
- There is still no distinction between hands and equipment.

Recommended incremental path:

1. Keep the flat list until a gameplay rule needs distinct hands or equipment.
2. When a new direct item interaction mutates but does not consume a carried stack, move that stack to most recent.
3. Add explicit model fields only if needed by mechanics:
   - `hands`: active held items with different action costs or blocking behavior
   - `equipped_bag`: worn storage with weight or access rules
   - `containers`: only if nested storage needs dedicated access, sorting, or ownership rules beyond stack `data`

**Do not** build a complete hands/equipment system before it changes real gameplay.

**Good first test:**

- Empty carried inventory renders clearly.
- Carried items render newest-first with item stats intact.
- Carried and placed storage render used/capacity and contents clearly.
- Existing Chinese item/stat labels still work.

### 5. Decide public information for other players

Before adding trade/help/combat, decide what another player exposes as a scene object.

Safe public information for now:

- name
- online/offline presence, but only if the player is visible in the same location
- current action, e.g. `Bob — survivor here, foraging`
- obvious visible condition later, e.g. wounded/wet/resting

Avoid showing full private needs/stats in the scene unless that becomes an explicit design choice.

### 6. Expand island content inspired by Card Survival, but keep it original

Current content is a small prototype: beach, jungle outskirts, rocks, tide pool. Later content expansion can follow the *mechanisms* of Card Survival without copying its exact data/writing.

Good next content categories:

- More locations: deeper jungle, wetlands/mangroves, cave, highlands, reef/shallows.
- More resource sources: palm fronds, long sticks, stones/flint, medicinal plants, shellfish, freshwater collection points.
- More craftables: cordage, leaf bed, coconut container, basic spear, hand drill/fire starter, improved shelter.
- More cooking/processing: roast fish, boil water in a container, dry meat/fish, crack/open coconut.
- More conditions: sunburn, infection risk, foot/hand damage, dirt/filth, fever, body temperature.

Add content only when it creates a playable loop. Prefer one complete loop over many disconnected items.

## Suggested workflow for each change

1. Write one focused test.
2. Run the focused test and see it fail:

```bash
uv run pytest tests/test_client.py::test_name_here -q
```

3. Make the smallest code change.
4. Run the focused test again.
5. Run the full test suite:

```bash
uv run pytest -q
```

6. If `ruff` is available in the environment, run:

```bash
uv run ruff check .
```

7. Manually test with one server and two clients if the change affects UI/interaction.

## Commands for manual test loop

Server:

```bash
cd C:/Users/xiaox/repos/tropical_adventure
uv run python -m tropical_adventure.server --save saves/island.json --host 127.0.0.1 --port 8765
```

Alice:

```bash
cd C:/Users/xiaox/repos/tropical_adventure
uv run python -m tropical_adventure.client --host 127.0.0.1 --port 8765 --name Alice
```

Bob:

```bash
cd C:/Users/xiaox/repos/tropical_adventure
uv run python -m tropical_adventure.client --host 127.0.0.1 --port 8765 --name Bob
```

## Do not do yet

- Do not create a large generic plugin/object-interaction framework.
- Do not put other players back into the left panel.
- Do not expose full private stats for other players by default.
- Do not implement trade/combat/help before the simpler scene-object display and inspect flow feel good.
- Do not replace the server-authoritative validation model with client-side rules.
