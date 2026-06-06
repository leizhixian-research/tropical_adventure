# Tropical Adventure: Plans

This file is about what to work on next. Use `docs/current.md` for what is already built.

## Product direction to preserve

The next work should make the UI and gameplay feel like **interacting with objects in a location**:

- Player panel = only me.
- Scene/world panel = things at my current location.
- Other players = scene objects at the location, just like a fire, coconut, path, or ground item.
- Inventory panel = what I can use/carry, starting with hands, then equipped bags/containers.
- Slash commands stay direct: `/inspect Bob`, `/pick up coconut`, `/move rocks`, `/forage coconut`.

Keep changes small and testable. Avoid adding a big generic object-interaction framework until 2-3 concrete interactions prove what abstraction is needed.

## Recommended next work order

### 1. Show other players as objects in the scene

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
- `/forage <item>` and `/gather <item>` from location resources

Next additions:

- `/inspect Bob` for other players in the same location.
- `/inspect fire`, `/inspect shelter`, `/inspect raincatcher` for placed objects.
- `/inspect coconut palms`, `/inspect sea`, etc. for features.
- Later, maybe `/give Bob coconut` only after inventory/hand semantics exist.

Keep suggestions direct. Do not add `/action ...`.

### 4. Redesign inventory panel as hands + bags

**Goal:** The right panel should show game content the way the player thinks about it: what is in hands first, then bags/containers if equipped.

Current state:

- `Player` has `carried` stacks only.
- `format_inventory_panel()` renders all `carried` stacks in reversed order.

Recommended incremental path:

1. Start with a UI-only grouping before changing the data model.
2. Add labels:

```text
Inventory
Hands
  1 sharp stone
Bags
  none equipped
Carried
  2 coconut
  3 sticks
```

3. If no hands/bag model exists, infer a simple temporary display:
   - first/top carried stack can appear under `Hands`, or hands can show `empty` until the model is added.
   - keep all real data under `Carried` so nothing disappears.
4. After the UI feels right, add explicit model fields only if needed:
   - `hands`: maybe 0-2 item stacks
   - `equipped_bag`: optional placed/equipped item
   - `containers`: later, for water/food/storage rules

**Do not** build a complete equipment/container system before testing the display.

**Good first test:**

- Empty carried inventory renders `Hands` and `Bags` sections clearly.
- Carried items are still visible.
- Existing Chinese inventory labels still work or are updated intentionally.

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
